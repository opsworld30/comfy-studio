import { useQuery } from '@tanstack/react-query'
import { useThemeStore } from '@/stores/theme'
import { useCircuitBreaker } from '@/hooks/useCircuitBreaker'
import { Button } from '@/components/ui/button'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import {
  Bell,
  Moon,
  Sun,
  Monitor,
  User,
  Cpu,
  WifiOff,
} from 'lucide-react'
import { comfyuiApi, batchApi } from '@/lib/api'

export default function Header() {
  const { theme, setTheme } = useThemeStore()
  
  // 熔断器：控制轮询，防止后端离线时无限重试
  const { createRefetchInterval, shouldEnableQuery, wrapQueryFn } = useCircuitBreaker()

  // 获取 ComfyUI 状态（带熔断器保护）
  const { data: status } = useQuery({
    queryKey: ['comfyui', 'status'],
    queryFn: wrapQueryFn(async () => {
      const { data } = await comfyuiApi.getStatus()
      return data
    }),
    refetchInterval: createRefetchInterval(3000),
    enabled: shouldEnableQuery(),
    retry: 1,
  })

  // 获取今日完成数量（带熔断器保护）
  const { data: stats } = useQuery({
    queryKey: ['batch', 'stats'],
    queryFn: wrapQueryFn(async () => {
      const { data } = await batchApi.getStats()
      return data
    }),
    refetchInterval: createRefetchInterval(10000),
    enabled: shouldEnableQuery(),
    retry: 1,
  })

  const connected = status?.connected ?? false
  const devices = status?.system_stats?.devices ?? []
  const gpu = devices[0]
  const vramTotal = gpu ? gpu.vram_total / (1024 * 1024 * 1024) : 24
  const vramUsed = gpu ? (gpu.vram_total - gpu.vram_free) / (1024 * 1024 * 1024) : 0
  
  // 显示服务器信息（从系统信息中获取）
  const osInfo = status?.system_stats?.system?.os ?? ''
  const serverUrl = connected 
    ? (osInfo === 'linux' ? '云端服务器' : '本地服务器')
    : '未连接'
  
  // 通知数量 = 今日完成数量
  const todayCompleted = stats?.completed_today ?? 0
  const notifications = todayCompleted

  const themeIcon = {
    light: Sun,
    dark: Moon,
    system: Monitor,
  }
  const ThemeIcon = themeIcon[theme]

  return (
    <header className="flex h-14 items-center justify-between border-b border-border/40 bg-card/50 backdrop-blur-sm px-6">
      {/* Left: Server Status */}
      <div className="flex items-center gap-6">
        <div className="flex items-center gap-3 px-3 py-1.5 rounded-full bg-muted/50">
          {connected ? (
            <div className="flex items-center gap-2">
              <span className="relative flex h-2.5 w-2.5">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-green-400 opacity-75"></span>
                <span className="relative inline-flex rounded-full h-2.5 w-2.5 bg-green-500"></span>
              </span>
              <span className="text-sm font-medium text-green-500">已连接</span>
            </div>
          ) : (
            <div className="flex items-center gap-2">
              <WifiOff className="h-4 w-4 text-destructive" />
              <span className="text-sm font-medium text-destructive">未连接</span>
            </div>
          )}
          <span className="text-sm text-muted-foreground font-mono">
            {serverUrl}
          </span>
        </div>

        {/* GPU Status */}
        {connected && (
          <div className="flex items-center gap-3 px-3 py-1.5 rounded-full bg-muted/50">
            <Cpu className="h-4 w-4 text-purple-400" />
            <span className="text-sm font-medium">
              {vramUsed.toFixed(1)}<span className="text-muted-foreground">/{vramTotal.toFixed(0)}GB</span>
            </span>
            <div className="h-2 w-24 rounded-full bg-secondary overflow-hidden">
              <div
                className="h-full rounded-full bg-gradient-to-r from-purple-500 to-blue-500 transition-all"
                style={{
                  width: `${(vramUsed / vramTotal) * 100}%`,
                }}
              />
            </div>
          </div>
        )}
      </div>

      {/* Right: Actions */}
      <div className="flex items-center gap-1">
        {/* Notifications */}
        <Button variant="ghost" size="icon" className="relative rounded-full hover:bg-accent/80">
          <Bell className="h-5 w-5" />
          {notifications > 0 && (
            <span className="absolute -right-0.5 -top-0.5 h-5 w-5 rounded-full bg-red-500 text-white text-xs flex items-center justify-center font-medium">
              {notifications}
            </span>
          )}
        </Button>

        {/* Theme Toggle */}
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button variant="ghost" size="icon" className="rounded-full hover:bg-accent/80">
              <ThemeIcon className="h-5 w-5" />
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end" className="w-36">
            <DropdownMenuLabel>主题</DropdownMenuLabel>
            <DropdownMenuSeparator />
            <DropdownMenuItem onClick={() => setTheme('light')} className="cursor-pointer">
              <Sun className="mr-2 h-4 w-4 text-yellow-500" />
              浅色
            </DropdownMenuItem>
            <DropdownMenuItem onClick={() => setTheme('dark')} className="cursor-pointer">
              <Moon className="mr-2 h-4 w-4 text-blue-400" />
              深色
            </DropdownMenuItem>
            <DropdownMenuItem onClick={() => setTheme('system')} className="cursor-pointer">
              <Monitor className="mr-2 h-4 w-4 text-gray-400" />
              跟随系统
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>

        {/* User Menu */}
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button variant="ghost" size="icon" className="rounded-full hover:bg-accent/80">
              <div className="h-8 w-8 rounded-full bg-gradient-to-br from-blue-500 to-purple-500 flex items-center justify-center">
                <User className="h-4 w-4 text-white" />
              </div>
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end" className="w-48">
            <DropdownMenuLabel>我的账户</DropdownMenuLabel>
            <DropdownMenuSeparator />
            <DropdownMenuItem className="cursor-pointer">个人设置</DropdownMenuItem>
            <DropdownMenuItem className="cursor-pointer">帮助文档</DropdownMenuItem>
            <DropdownMenuItem className="cursor-pointer">关于</DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </div>
    </header>
  )
}
