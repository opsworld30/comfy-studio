import { useState, useEffect, useRef } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useCircuitBreaker } from '@/hooks/useCircuitBreaker'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Progress } from '@/components/ui/progress'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import {
  RefreshCw,
  Cpu,
  Clock,
  CheckCircle,
  Loader2,
  StopCircle,
  Trash2,
  Play,
  Sparkles,
  History,
} from 'lucide-react'
import { comfyuiApi, performanceApi, smartCreateApi } from '@/lib/api'
import { SmartCreatePanel } from '@/components/smart-create'

// WebSocket 进度信息类型
interface ExecutionProgress {
  promptId: string
  currentNode: string
  currentStep: number
  totalSteps: number
  progress: number // 0-100
}

export default function TaskQueue() {
  const queryClient = useQueryClient()
  const [activeTab, setActiveTab] = useState('smart-create')
  
  // 执行进度状态
  const [executionProgress, setExecutionProgress] = useState<ExecutionProgress | null>(null)
  const wsRef = useRef<WebSocket | null>(null)
  
  // 熔断器：控制轮询，防止后端离线时无限重试
  const { createRefetchInterval, shouldEnableQuery, wrapQueryFn } = useCircuitBreaker()
  
  // 获取智能创作任务数量（用于显示红点，带熔断器保护）
  const { data: smartCreateTasks } = useQuery({
    queryKey: ['smart-create', 'tasks', 'running'],
    queryFn: wrapQueryFn(async () => {
      const { data } = await smartCreateApi.list({ status: 'generating', limit: 10 })
      return data
    }),
    refetchInterval: createRefetchInterval(5000),
    enabled: shouldEnableQuery(),
    retry: 1,
  })
  const runningSmartTasks = smartCreateTasks?.length || 0

  // 获取 ComfyUI 历史记录（带熔断器保护）
  const { data: historyData } = useQuery({
    queryKey: ['comfyui', 'history'],
    queryFn: wrapQueryFn(async () => {
      const { data } = await comfyuiApi.getHistory()
      // 转换为数组格式
      if (data && typeof data === 'object') {
        return Object.entries(data).map(([promptId, info]: [string, any]) => ({
          prompt_id: promptId,
          status: info.status?.completed ? 'completed' : 'running',
          outputs: info.outputs,
          created_at: info.status?.status_str,
        })).slice(0, 50)
      }
      return []
    }),
    enabled: activeTab === 'history' && shouldEnableQuery(),
    retry: 1,
  })
  
  // WebSocket 连接获取实时进度
  useEffect(() => {
    const connectWs = () => {
      // 通过后端代理连接 ComfyUI WebSocket
      const wsUrl = comfyuiApi.getBaseUrl().replace('http://', 'ws://').replace('https://', 'wss://') + '/ws'
      const ws = new WebSocket(wsUrl)
      wsRef.current = ws
      
      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data)
          
          // 处理进度消息
          if (data.type === 'progress') {
            const { value, max } = data.data
            setExecutionProgress(prev => ({
              ...prev,
              promptId: prev?.promptId || '',
              currentNode: prev?.currentNode || '',
              currentStep: value,
              totalSteps: max,
              progress: Math.round((value / max) * 100)
            }))
          }
          
          // 处理执行开始
          if (data.type === 'execution_start') {
            setExecutionProgress({
              promptId: data.data.prompt_id,
              currentNode: '',
              currentStep: 0,
              totalSteps: 0,
              progress: 0
            })
          }
          
          // 处理节点执行
          if (data.type === 'executing') {
            if (data.data.node) {
              setExecutionProgress(prev => ({
                ...prev,
                promptId: prev?.promptId || '',
                currentNode: data.data.node,
                currentStep: prev?.currentStep || 0,
                totalSteps: prev?.totalSteps || 0,
                progress: prev?.progress || 0
              }))
            } else {
              // 执行完成
              setExecutionProgress(null)
              queryClient.invalidateQueries({ queryKey: ['comfyui', 'queue'] })
            }
          }
        } catch {
          // 忽略解析错误
        }
      }
      
      ws.onerror = () => {
        // WebSocket 连接失败，静默处理
      }
      
      ws.onclose = () => {
        // 5秒后重连
        setTimeout(connectWs, 5000)
      }
    }
    
    connectWs()
    
    return () => {
      if (wsRef.current) {
        wsRef.current.close()
      }
    }
  }, [queryClient])

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

  // 获取 ComfyUI 队列详情（带熔断器保护）
  const { data: comfyQueue } = useQuery({
    queryKey: ['comfyui', 'queue', 'detailed'],
    queryFn: wrapQueryFn(async () => {
      const { data } = await comfyuiApi.getDetailedQueue()
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
    refetchInterval: createRefetchInterval(30000),
    enabled: shouldEnableQuery(),
    retry: 1,
  })

  // 中断当前任务
  const interruptMutation = useMutation({
    mutationFn: () => comfyuiApi.interrupt(),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['comfyui', 'queue'] })
    },
  })

  // 清空队列
  const clearQueueMutation = useMutation({
    mutationFn: () => comfyuiApi.clearQueue(),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['comfyui', 'queue'] })
    },
  })

  const runningCount = comfyQueue?.running?.length || 0
  const pendingCount = comfyQueue?.pending?.length || 0
  const totalInQueue = runningCount + pendingCount

  // GPU 信息
  const devices = comfyStatus?.system_stats?.devices ?? []
  const gpu = devices[0]
  const vramTotal = gpu ? gpu.vram_total / (1024 * 1024 * 1024) : 16
  const vramUsed = gpu ? (gpu.vram_total - gpu.vram_free) / (1024 * 1024 * 1024) : 0
  const vramPercent = (vramUsed / vramTotal) * 100

  return (
    <div className="space-y-6">
      {/* Tab 切换 */}
      <Tabs value={activeTab} onValueChange={setActiveTab} className="w-full">
        <TabsList className="grid w-full grid-cols-3 max-w-md">
          <TabsTrigger value="smart-create" className="flex items-center gap-2 relative">
            <Sparkles className="h-4 w-4" />
            智能创作
            {runningSmartTasks > 0 && (
              <span className="absolute -top-1 -right-1 w-2 h-2 bg-red-500 rounded-full" />
            )}
          </TabsTrigger>
          <TabsTrigger value="comfyui" className="flex items-center gap-2">
            <Cpu className="h-4 w-4" />
            队列
          </TabsTrigger>
          <TabsTrigger value="history" className="flex items-center gap-2">
            <History className="h-4 w-4" />
            历史
          </TabsTrigger>
        </TabsList>

        {/* ComfyUI 队列 Tab */}
        <TabsContent value="comfyui" className="mt-6 space-y-6">
          {/* ComfyUI Queue Status */}
          <Card className="bg-card/50 border-border/50">
        <CardHeader className="pb-2">
          <div className="flex items-center justify-between">
            <CardTitle className="text-base flex items-center gap-2">
              <Cpu className="h-4 w-4" />
              ComfyUI 队列状态
              {comfyStatus?.connected ? (
                <Badge className="bg-green-500 ml-2">已连接</Badge>
              ) : (
                <Badge variant="destructive" className="ml-2">未连接</Badge>
              )}
            </CardTitle>
          </div>
        </CardHeader>
        <CardContent className="py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-8">
              <div className="flex items-center gap-3">
                <div className="flex h-10 w-10 items-center justify-center rounded-full bg-blue-500/10">
                  <Play className="h-5 w-5 text-blue-500" />
                </div>
                <div>
                  <p className="text-2xl font-bold">{runningCount}</p>
                  <p className="text-sm text-muted-foreground">正在生成</p>
                </div>
              </div>
              <div className="flex items-center gap-3">
                <div className="flex h-10 w-10 items-center justify-center rounded-full bg-yellow-500/10">
                  <Clock className="h-5 w-5 text-yellow-500" />
                </div>
                <div>
                  <p className="text-2xl font-bold">{pendingCount}</p>
                  <p className="text-sm text-muted-foreground">队列等待</p>
                </div>
              </div>
              <div className="flex items-center gap-3">
                <div className="flex h-10 w-10 items-center justify-center rounded-full bg-green-500/10">
                  <CheckCircle className="h-5 w-5 text-green-500" />
                </div>
                <div>
                  <p className="text-2xl font-bold">{execStats?.successful || 0}</p>
                  <p className="text-sm text-muted-foreground">近7天完成</p>
                </div>
              </div>
            </div>
            
            {/* GPU 负载 */}
            {comfyStatus?.connected && (
              <div className="flex items-center gap-4">
                <div className="text-right">
                  <div className="flex items-center gap-2 text-sm text-muted-foreground mb-1">
                    <Cpu className="h-4 w-4" />
                    GPU 负载
                  </div>
                  <div className="w-48">
                    <div className="flex justify-between text-xs mb-1">
                      <span>{vramUsed.toFixed(1)} / {vramTotal.toFixed(0)} GB VRAM</span>
                      <span>{vramPercent.toFixed(0)}%</span>
                    </div>
                    <Progress value={vramPercent} className="h-2" />
                  </div>
                </div>
              </div>
            )}
          </div>
        </CardContent>
      </Card>

      {/* Queue Details */}
      {comfyStatus?.connected && (
        <Card className="bg-card/50 border-border/50">
          <CardHeader className="pb-2">
            <div className="flex items-center justify-between">
              <CardTitle className="text-base flex items-center gap-2">
                队列详情
                <Badge variant="outline" className="ml-2">{totalInQueue} 个任务</Badge>
              </CardTitle>
              <div className="flex items-center gap-2">
                <Button 
                  variant="outline" 
                  size="sm"
                  onClick={() => interruptMutation.mutate()}
                  disabled={runningCount === 0 || interruptMutation.isPending}
                >
                  <StopCircle className="mr-2 h-4 w-4" />
                  中断当前
                </Button>
                <Button 
                  variant="outline" 
                  size="sm"
                  onClick={() => clearQueueMutation.mutate()}
                  disabled={pendingCount === 0 || clearQueueMutation.isPending}
                >
                  <Trash2 className="mr-2 h-4 w-4" />
                  清空队列
                </Button>
                <Button 
                  variant="outline" 
                  size="sm"
                  onClick={() => queryClient.invalidateQueries({ queryKey: ['comfyui', 'queue'] })}
                >
                  <RefreshCw className="mr-2 h-4 w-4" />
                  刷新
                </Button>
              </div>
            </div>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-2 gap-6">
              {/* Running */}
              <div>
                <h3 className="text-sm font-medium mb-3 flex items-center gap-2">
                  <span className="w-2 h-2 rounded-full bg-blue-500 animate-pulse"></span>
                  正在执行
                </h3>
                <ScrollArea className="h-[400px]">
                  <div className="space-y-2 pr-4">
                    {comfyQueue?.running?.length ? (
                      comfyQueue.running.map((item: { prompt_id: string; number: number }) => {
                        const isCurrentTask = executionProgress?.promptId === item.prompt_id
                        const progress = isCurrentTask ? executionProgress?.progress || 0 : 0
                        const currentStep = isCurrentTask ? executionProgress?.currentStep || 0 : 0
                        const totalSteps = isCurrentTask ? executionProgress?.totalSteps || 0 : 0
                        
                        return (
                          <div key={item.prompt_id} className="p-3 rounded-lg bg-blue-500/10 border border-blue-500/20">
                            <div className="flex items-center justify-between mb-2">
                              <div className="flex items-center gap-2">
                                <Loader2 className="h-4 w-4 animate-spin text-blue-500" />
                                <span className="text-sm font-medium">
                                  {progress > 0 ? `生成中 ${progress}%` : '生成中...'}
                                </span>
                              </div>
                              <Badge className="bg-blue-500">#{item.number}</Badge>
                            </div>
                            <p className="text-xs font-mono text-muted-foreground break-all">
                              {item.prompt_id}
                            </p>
                            {totalSteps > 0 && (
                              <p className="text-xs text-muted-foreground mt-1">
                                步骤: {currentStep} / {totalSteps}
                              </p>
                            )}
                            <Progress value={progress} className="h-1.5 mt-2" />
                          </div>
                        )
                      })
                    ) : (
                      <div className="p-3 text-center text-sm text-muted-foreground">
                        暂无执行中的任务
                      </div>
                    )}
                  </div>
                </ScrollArea>
              </div>
              
              {/* Pending */}
              <div>
                <h3 className="text-sm font-medium mb-3 flex items-center gap-2">
                  <Clock className="h-4 w-4 text-yellow-500" />
                  等待队列
                  <span className="text-muted-foreground">{pendingCount}</span>
                </h3>
                <ScrollArea className="h-[400px]">
                  <div className="space-y-1 pr-4">
                    {comfyQueue?.pending?.length ? (
                      comfyQueue.pending.map((item: { prompt_id: string; number: number }, index: number) => (
                        <div 
                          key={item.prompt_id} 
                          className="p-2 rounded-lg bg-muted/50 flex items-center justify-between"
                        >
                          <div className="flex items-center gap-2 min-w-0">
                            <span className="text-xs text-muted-foreground">#{index + 1}</span>
                            <span className="text-xs font-mono text-muted-foreground truncate">
                              {item.prompt_id}
                            </span>
                          </div>
                          <span className="text-xs text-muted-foreground">#{item.number}</span>
                        </div>
                      ))
                    ) : (
                      <div className="p-3 text-center text-sm text-muted-foreground">
                        队列为空
                      </div>
                    )}
                  </div>
                </ScrollArea>
              </div>
            </div>
          </CardContent>
        </Card>
      )}
        </TabsContent>

        {/* 智能创作 Tab */}
        <TabsContent value="smart-create" className="mt-6">
          <SmartCreatePanel />
        </TabsContent>

        {/* 任务历史 Tab */}
        <TabsContent value="history" className="mt-6">
          <Card className="bg-card/50 border-border/50">
            <CardHeader>
              <CardTitle className="text-base flex items-center gap-2">
                <History className="h-4 w-4" />
                ComfyUI 任务历史
              </CardTitle>
            </CardHeader>
            <CardContent>
              {historyData && historyData.length > 0 ? (
                <div className="space-y-2 max-h-[500px] overflow-y-auto">
                  {historyData.slice(0, 50).map((item) => (
                    <div key={item.prompt_id} className="p-3 bg-muted/50 rounded flex items-center justify-between">
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2">
                          <span className={`w-2 h-2 rounded-full ${item.status === 'completed' ? 'bg-green-500' : item.status === 'running' ? 'bg-yellow-500' : 'bg-red-500'}`} />
                          <span className="text-sm font-mono truncate">{item.prompt_id}</span>
                        </div>
                        <p className="text-xs text-muted-foreground mt-1">
                          {item.outputs?.images?.length || 0} 张图片
                          {item.created_at && ` · ${new Date(item.created_at).toLocaleString()}`}
                        </p>
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="text-center py-12 text-muted-foreground">
                  <History className="h-12 w-12 mx-auto mb-4 opacity-50" />
                  <p>暂无任务历史</p>
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  )
}
