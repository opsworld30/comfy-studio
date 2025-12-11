import { useState, useEffect } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useCircuitBreaker } from '@/hooks/useCircuitBreaker'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Progress } from '@/components/ui/progress'
import {
  Cpu,
  HardDrive,
  Activity,
  Thermometer,
  Clock,
  CheckCircle,
  XCircle,
  Image,
  Loader2,
  RefreshCw,
  TrendingUp,
} from 'lucide-react'
import { Button } from '@/components/ui/button'
import { performanceApi, comfyuiApi } from '@/lib/api'
import { usePageModulesStore } from '@/stores/pageModules'
import {
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  AreaChart,
  Area,
} from 'recharts'

// 性能历史数据类型
interface PerformanceHistoryPoint {
  time: string
  gpu: number
  cpu: number
  vram: number
  memory: number
}

export default function Monitor() {
  const { isModuleVisible } = usePageModulesStore()
  // 性能历史数据
  const [perfHistory, setPerfHistory] = useState<PerformanceHistoryPoint[]>([])
  
  // 熔断器：控制轮询，防止后端离线时无限重试
  const { createRefetchInterval, shouldEnableQuery, wrapQueryFn } = useCircuitBreaker()

  // 获取性能统计（带熔断器保护）
  const { data: perfStats, isLoading: perfLoading, refetch: refetchPerf } = useQuery({
    queryKey: ['performance', 'stats'],
    queryFn: wrapQueryFn(async () => {
      const { data } = await performanceApi.getStats()
      return data
    }),
    refetchInterval: createRefetchInterval(2000),
    enabled: shouldEnableQuery(),
    retry: 1,
  })

  // 获取执行统计（带熔断器保护）
  const { data: execStats } = useQuery({
    queryKey: ['performance', 'execution-stats'],
    queryFn: wrapQueryFn(async () => {
      const { data } = await performanceApi.getExecutionStats(7)
      return data
    }),
    refetchInterval: createRefetchInterval(10000),
    enabled: shouldEnableQuery(),
    retry: 1,
  })

  // 获取 ComfyUI 状态（带熔断器保护）
  const { data: comfyStatus } = useQuery({
    queryKey: ['comfyui', 'status'],
    queryFn: wrapQueryFn(async () => {
      const { data } = await comfyuiApi.getStatus()
      return data
    }),
    refetchInterval: createRefetchInterval(3000),
    enabled: shouldEnableQuery(),
    retry: 1,
  })

  // GPU 信息
  const gpu = comfyStatus?.system_stats?.devices?.[0]
  const gpuName = gpu?.name || 'Unknown GPU'
  const vramTotal = gpu ? gpu.vram_total / (1024 * 1024 * 1024) : 24
  const vramUsed = gpu ? (gpu.vram_total - gpu.vram_free) / (1024 * 1024 * 1024) : 0
  const vramPercent = vramTotal > 0 ? (vramUsed / vramTotal) * 100 : 0

  // 更新性能历史
  useEffect(() => {
    if (perfStats) {
      const now = new Date()
      const timeStr = `${now.getHours().toString().padStart(2, '0')}:${now.getMinutes().toString().padStart(2, '0')}:${now.getSeconds().toString().padStart(2, '0')}`
      
      setPerfHistory(prev => {
        const newPoint: PerformanceHistoryPoint = {
          time: timeStr,
          gpu: perfStats.gpu_usage ?? 0,
          cpu: perfStats.cpu_usage ?? 0,
          vram: perfStats.gpu_memory_used ? (perfStats.gpu_memory_used / (1024 * 1024 * 1024)) : 0,
          memory: perfStats.memory_used ?? 0,
        }
        const updated = [...prev, newPoint]
        // 保留最近30个数据点
        return updated.slice(-30)
      })
    }
  }, [perfStats])

  // 性能数据
  const gpuUsage = perfStats?.gpu_usage ?? 0
  const gpuTemp = perfStats?.gpu_temperature ?? 0
  const cpuUsage = perfStats?.cpu_usage ?? 0
  const memUsed = perfStats?.memory_used ?? 0
  const memTotal = perfStats?.memory_total ?? 32
  const memPercent = memTotal > 0 ? (memUsed / memTotal) * 100 : 0
  const diskUsed = perfStats?.disk_used ?? 0
  const diskTotal = perfStats?.disk_total ?? 500
  const diskPercent = diskTotal > 0 ? (diskUsed / diskTotal) * 100 : 0

  // 执行统计
  const totalExec = execStats?.total_executions ?? 0
  const successExec = execStats?.successful ?? 0
  const failedExec = execStats?.failed ?? 0
  const totalImages = execStats?.total_images ?? 0
  const avgTime = execStats?.avg_time ?? 0

  const getUsageColor = (percent: number) => {
    if (percent >= 90) return 'text-red-500'
    if (percent >= 70) return 'text-yellow-500'
    return 'text-green-500'
  }

  if (perfLoading) {
    return (
      <div className="flex items-center justify-center h-96">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-medium">性能监控</h2>
        <Button variant="outline" size="sm" onClick={() => refetchPerf()}>
          <RefreshCw className="mr-2 h-4 w-4" />
          刷新
        </Button>
      </div>

      {/* GPU Stats */}
      {isModuleVisible('monitor', 'showSystemStatus') && (
      <div className="grid grid-cols-4 gap-4">
        <Card className="bg-card/50 border-border/50">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium flex items-center gap-2">
              <Cpu className="h-4 w-4 text-blue-500" />
              GPU 使用率
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex items-end justify-between">
              <span className={`text-3xl font-bold ${getUsageColor(gpuUsage)}`}>
                {gpuUsage.toFixed(0)}%
              </span>
              <span className="text-sm text-muted-foreground">{gpuName}</span>
            </div>
            <Progress value={gpuUsage} className="mt-2 h-2" />
          </CardContent>
        </Card>

        <Card className="bg-card/50 border-border/50">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium flex items-center gap-2">
              <HardDrive className="h-4 w-4 text-purple-500" />
              显存使用
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex items-end justify-between">
              <span className={`text-3xl font-bold ${getUsageColor(vramPercent)}`}>
                {vramUsed.toFixed(1)}GB
              </span>
              <span className="text-sm text-muted-foreground">/ {vramTotal.toFixed(0)}GB</span>
            </div>
            <Progress value={vramPercent} className="mt-2 h-2" />
          </CardContent>
        </Card>

        <Card className="bg-card/50 border-border/50">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium flex items-center gap-2">
              <Thermometer className="h-4 w-4 text-orange-500" />
              GPU 温度
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex items-end justify-between">
              <span className={`text-3xl font-bold ${gpuTemp >= 80 ? 'text-red-500' : gpuTemp >= 70 ? 'text-yellow-500' : 'text-green-500'}`}>
                {gpuTemp}°C
              </span>
              <span className="text-sm text-muted-foreground">
                {gpuTemp >= 80 ? '过热' : gpuTemp >= 70 ? '偏高' : '正常'}
              </span>
            </div>
            <Progress value={(gpuTemp / 100) * 100} className="mt-2 h-2" />
          </CardContent>
        </Card>

        <Card className="bg-card/50 border-border/50">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium flex items-center gap-2">
              <Activity className="h-4 w-4 text-green-500" />
              CPU 使用率
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex items-end justify-between">
              <span className={`text-3xl font-bold ${getUsageColor(cpuUsage)}`}>
                {cpuUsage.toFixed(0)}%
              </span>
              <span className="text-sm text-muted-foreground">系统</span>
            </div>
            <Progress value={cpuUsage} className="mt-2 h-2" />
          </CardContent>
        </Card>
      </div>
      )}

      {/* Memory & Disk */}
      {isModuleVisible('monitor', 'showSystemStatus') && (
      <div className="grid grid-cols-2 gap-4">
        <Card className="bg-card/50 border-border/50">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium flex items-center gap-2">
              <HardDrive className="h-4 w-4 text-cyan-500" />
              系统内存
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex items-center justify-between mb-2">
              <span className={`text-2xl font-bold ${getUsageColor(memPercent)}`}>
                {memUsed.toFixed(1)}GB
              </span>
              <span className="text-sm text-muted-foreground">/ {memTotal.toFixed(0)}GB ({memPercent.toFixed(0)}%)</span>
            </div>
            <Progress value={memPercent} className="h-3" />
          </CardContent>
        </Card>

        <Card className="bg-card/50 border-border/50">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium flex items-center gap-2">
              <HardDrive className="h-4 w-4 text-amber-500" />
              磁盘空间
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex items-center justify-between mb-2">
              <span className={`text-2xl font-bold ${getUsageColor(diskPercent)}`}>
                {diskUsed.toFixed(0)}GB
              </span>
              <span className="text-sm text-muted-foreground">/ {diskTotal.toFixed(0)}GB ({diskPercent.toFixed(0)}%)</span>
            </div>
            <Progress value={diskPercent} className="h-3" />
          </CardContent>
        </Card>
      </div>
      )}

      {/* Execution Stats */}
      {isModuleVisible('monitor', 'showExecutionHistory') && (
      <Card className="bg-card/50 border-border/50">
        <CardHeader>
          <CardTitle className="text-base flex items-center gap-2">
            <TrendingUp className="h-4 w-4" />
            执行统计 (近7天)
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-5 gap-6">
            <div className="text-center">
              <div className="flex items-center justify-center h-12 w-12 mx-auto rounded-full bg-blue-500/10 mb-2">
                <Activity className="h-6 w-6 text-blue-500" />
              </div>
              <p className="text-2xl font-bold">{totalExec}</p>
              <p className="text-sm text-muted-foreground">总执行次数</p>
            </div>
            <div className="text-center">
              <div className="flex items-center justify-center h-12 w-12 mx-auto rounded-full bg-green-500/10 mb-2">
                <CheckCircle className="h-6 w-6 text-green-500" />
              </div>
              <p className="text-2xl font-bold text-green-500">{successExec}</p>
              <p className="text-sm text-muted-foreground">成功</p>
            </div>
            <div className="text-center">
              <div className="flex items-center justify-center h-12 w-12 mx-auto rounded-full bg-red-500/10 mb-2">
                <XCircle className="h-6 w-6 text-red-500" />
              </div>
              <p className="text-2xl font-bold text-red-500">{failedExec}</p>
              <p className="text-sm text-muted-foreground">失败</p>
            </div>
            <div className="text-center">
              <div className="flex items-center justify-center h-12 w-12 mx-auto rounded-full bg-purple-500/10 mb-2">
                <Image className="h-6 w-6 text-purple-500" />
              </div>
              <p className="text-2xl font-bold">{totalImages}</p>
              <p className="text-sm text-muted-foreground">生成图片</p>
            </div>
            <div className="text-center">
              <div className="flex items-center justify-center h-12 w-12 mx-auto rounded-full bg-orange-500/10 mb-2">
                <Clock className="h-6 w-6 text-orange-500" />
              </div>
              <p className="text-2xl font-bold">{avgTime.toFixed(1)}s</p>
              <p className="text-sm text-muted-foreground">平均耗时</p>
            </div>
          </div>
        </CardContent>
      </Card>
      )}

      {/* Performance Trend Chart */}
      {isModuleVisible('monitor', 'showPerformanceChart') && (
      <Card className="bg-card/50 border-border/50">
        <CardHeader>
          <CardTitle className="text-base flex items-center gap-2">
            <TrendingUp className="h-4 w-4" />
            性能趋势 (实时)
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={perfHistory}>
                <CartesianGrid strokeDasharray="3 3" stroke="#333" />
                <XAxis 
                  dataKey="time" 
                  stroke="#666" 
                  fontSize={12}
                  tickLine={false}
                />
                <YAxis 
                  stroke="#666" 
                  fontSize={12}
                  tickLine={false}
                  domain={[0, 100]}
                />
                <Tooltip 
                  contentStyle={{ 
                    backgroundColor: '#1a1a2e', 
                    border: '1px solid #333',
                    borderRadius: '8px'
                  }}
                  labelStyle={{ color: '#999' }}
                />
                <Area 
                  type="monotone" 
                  dataKey="gpu" 
                  name="GPU %" 
                  stroke="#3b82f6" 
                  fill="#3b82f6" 
                  fillOpacity={0.2}
                />
                <Area 
                  type="monotone" 
                  dataKey="cpu" 
                  name="CPU %" 
                  stroke="#22c55e" 
                  fill="#22c55e" 
                  fillOpacity={0.2}
                />
              </AreaChart>
            </ResponsiveContainer>
          </div>
          <div className="flex items-center justify-center gap-6 mt-4">
            <div className="flex items-center gap-2">
              <div className="h-3 w-3 rounded-full bg-blue-500" />
              <span className="text-sm text-muted-foreground">GPU 使用率</span>
            </div>
            <div className="flex items-center gap-2">
              <div className="h-3 w-3 rounded-full bg-green-500" />
              <span className="text-sm text-muted-foreground">CPU 使用率</span>
            </div>
          </div>
        </CardContent>
      </Card>
      )}

      {/* Success Rate */}
      {isModuleVisible('monitor', 'showExecutionHistory') && (
      <Card className="bg-card/50 border-border/50">
        <CardHeader>
          <CardTitle className="text-base">成功率</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex items-center gap-4">
            <div className="flex-1">
              <div className="flex items-center justify-between mb-2">
                <span className="text-sm text-muted-foreground">执行成功率</span>
                <span className="text-sm font-medium">
                  {totalExec > 0 ? ((successExec / totalExec) * 100).toFixed(1) : 0}%
                </span>
              </div>
              <div className="h-4 bg-muted rounded-full overflow-hidden flex">
                <div 
                  className="h-full bg-green-500 transition-all"
                  style={{ width: `${totalExec > 0 ? (successExec / totalExec) * 100 : 0}%` }}
                />
                <div 
                  className="h-full bg-red-500 transition-all"
                  style={{ width: `${totalExec > 0 ? (failedExec / totalExec) * 100 : 0}%` }}
                />
              </div>
            </div>
            <div className="flex items-center gap-4 text-sm">
              <div className="flex items-center gap-1">
                <div className="h-3 w-3 rounded-full bg-green-500" />
                <span>成功 {successExec}</span>
              </div>
              <div className="flex items-center gap-1">
                <div className="h-3 w-3 rounded-full bg-red-500" />
                <span>失败 {failedExec}</span>
              </div>
            </div>
          </div>
        </CardContent>
      </Card>
      )}
    </div>
  )
}
