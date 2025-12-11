import { NavLink } from 'react-router-dom'
import { cn } from '@/lib/utils'
import {
  LayoutDashboard,
  Zap,
  Image,
  Package,
  Sparkles,
  Activity,
  Globe,
  Server,
  Settings,
} from 'lucide-react'
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip'
import { ScrollArea } from '@/components/ui/scroll-area'
import { usePageModulesStore } from '@/stores/pageModules'

const navItems = [
  { path: '/', icon: LayoutDashboard, label: '工作流', color: 'text-blue-400', pageKey: 'Dashboard' },
  { path: '/batch', icon: Zap, label: '任务队列', color: 'text-yellow-400', pageKey: 'Batch' },
  { path: '/gallery', icon: Image, label: '画廊', color: 'text-pink-400', pageKey: 'Gallery' },
  { path: '/models', icon: Package, label: '模型库', color: 'text-purple-400', pageKey: 'Models' },
  { path: '/prompts', icon: Sparkles, label: '提示词', color: 'text-cyan-400', pageKey: 'Prompts' },
  { path: '/monitor', icon: Activity, label: '监控', color: 'text-green-400', pageKey: 'Monitor' },
  { path: '/market', icon: Globe, label: '市场', color: 'text-orange-400', pageKey: 'Market' },
  { path: '/servers', icon: Server, label: '服务器', color: 'text-indigo-400', pageKey: null },
  { path: '/settings', icon: Settings, label: '设置', color: 'text-gray-400', pageKey: 'Settings' },
]

export default function Sidebar() {
  const { isPageVisible } = usePageModulesStore()
  
  // 过滤可见的页面
  const visibleNavItems = navItems.filter(item => 
    item.pageKey === null || isPageVisible(item.pageKey.toLowerCase())
  )
  return (
    <aside className="relative flex flex-col w-20 border-r border-border/40 bg-gradient-to-b from-card to-card/80">
      {/* Logo */}
      <div className="flex h-14 items-center justify-center border-b border-border/40">
        <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-br from-blue-500 to-blue-600 text-white shadow-lg shadow-blue-500/20">
          <Zap className="h-5 w-5" />
        </div>
      </div>

      {/* Navigation */}
      <ScrollArea className="flex-1 py-4">
        <nav className="flex flex-col items-center space-y-1.5 px-3">
          {visibleNavItems.map((item) => (
            <Tooltip key={item.path} delayDuration={0}>
              <TooltipTrigger asChild>
                <NavLink
                  to={item.path}
                  className={({ isActive }) =>
                    cn(
                      'group flex flex-col items-center justify-center gap-1 rounded-xl px-3 py-2.5 text-xs font-medium transition-all duration-200 w-full',
                      'hover:bg-accent/80 hover:shadow-sm',
                      isActive
                        ? 'bg-accent shadow-sm text-foreground'
                        : 'text-muted-foreground hover:text-foreground',
                    )
                  }
                >
                  <item.icon className={cn('h-5 w-5 shrink-0 transition-colors', item.color)} />
                  <span className="truncate">{item.label}</span>
                </NavLink>
              </TooltipTrigger>
              <TooltipContent side="right" className="font-medium">
                {item.label}
              </TooltipContent>
            </Tooltip>
          ))}
        </nav>
      </ScrollArea>

    </aside>
  )
}
