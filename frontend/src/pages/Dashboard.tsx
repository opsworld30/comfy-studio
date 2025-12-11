import { useState, useRef } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useCircuitBreaker } from '@/hooks/useCircuitBreaker'
import { Card, CardContent } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Badge } from '@/components/ui/badge'
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from '@/components/ui/dialog'
import { Label } from '@/components/ui/label'
import {
  Search,
  Plus,
  Upload,
  Star,
  Play,
  Edit,
  Copy,
  MoreHorizontal,
  Flame,
  Clock,
  CheckCircle,
  XCircle,
  TrendingUp,
  FolderOpen,
  Tag,
  Loader2,
  Trash2,
  Check,
} from 'lucide-react'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
  DropdownMenuSeparator,
} from '@/components/ui/dropdown-menu'
import { workflowsApi, batchApi, comfyuiApi, performanceApi, marketplaceApi, type Workflow, type MarketplaceWorkflow } from '@/lib/api'
import WorkflowTemplates from '@/components/WorkflowTemplates'

export default function Dashboard() {
  const queryClient = useQueryClient()
  const navigate = useNavigate()
  const [searchQuery, setSearchQuery] = useState('')
  const [activeTab, setActiveTab] = useState('all')
  const [showCreateDialog, setShowCreateDialog] = useState(false)
  const [newWorkflowName, setNewWorkflowName] = useState('')
  const [showTemplates, setShowTemplates] = useState(false)
  const fileInputRef = useRef<HTMLInputElement>(null)
  
  // 熔断器：控制轮询，防止后端离线时无限重试
  const { createRefetchInterval, shouldEnableQuery, wrapQueryFn } = useCircuitBreaker()

  // 获取工作流列表
  const { data: workflows = [], isLoading: workflowsLoading } = useQuery({
    queryKey: ['workflows', { search: searchQuery, favorite_only: activeTab === 'favorites' }],
    queryFn: async () => {
      const { data } = await workflowsApi.list({
        search: searchQuery || undefined,
        favorite_only: activeTab === 'favorites',
      })
      return data
    },
  })

  // 获取批处理统计（带熔断器保护）
  const { data: batchStats } = useQuery({
    queryKey: ['batch', 'stats'],
    queryFn: wrapQueryFn(async () => {
      const { data } = await batchApi.getStats()
      return data
    }),
    refetchInterval: createRefetchInterval(5000),
    enabled: shouldEnableQuery(),
    retry: 1,
  })

  // 获取 ComfyUI 队列状态（带熔断器保护）
  const { data: queueData } = useQuery({
    queryKey: ['comfyui', 'queue'],
    queryFn: wrapQueryFn(async () => {
      const { data } = await comfyuiApi.getDetailedQueue()
      return data
    }),
    refetchInterval: createRefetchInterval(3000),
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

  // 获取市场推荐工作流
  const { data: featuredWorkflows = [] } = useQuery({
    queryKey: ['marketplace', 'featured'],
    queryFn: async () => {
      const { data } = await marketplaceApi.getFeatured(4)
      return data
    },
  })

  // 切换收藏
  const toggleFavorite = useMutation({
    mutationFn: (id: number) => workflowsApi.toggleFavorite(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['workflows'] })
    },
  })

  // 删除工作流
  const deleteWorkflow = useMutation({
    mutationFn: (id: number) => workflowsApi.delete(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['workflows'] })
    },
  })

  // 执行工作流
  const executeWorkflow = useMutation({
    mutationFn: (id: number) => comfyuiApi.executeWorkflow(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['comfyui', 'queue'] })
    },
  })

  // 设为默认工作流
  const setDefaultWorkflow = useMutation({
    mutationFn: (id: number) => workflowsApi.setDefault(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['workflows'] })
    },
  })

  // 导入工作流
  const importWorkflow = useMutation({
    mutationFn: (file: File) => workflowsApi.import(file),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['workflows'] })
    },
  })

  // 创建工作流
  const createWorkflow = useMutation({
    mutationFn: (name: string) => workflowsApi.create({ 
      name, 
      workflow_data: { nodes: [], links: [] },
      description: '',
    }),
    onSuccess: (response: { data: Workflow }) => {
      queryClient.invalidateQueries({ queryKey: ['workflows'] })
      setShowCreateDialog(false)
      setNewWorkflowName('')
      // 跳转到编辑页面
      navigate(`/workflow/${response.data.id}`)
    },
  })

  const handleCreateWorkflow = () => {
    if (newWorkflowName.trim()) {
      createWorkflow.mutate(newWorkflowName.trim())
    }
  }

  const handleCreateFromTemplate = (template: any, name: string) => {
    // 跳转到编辑页面
    const workflowId = name // 这里应该从API返回获取实际的ID
    console.log('Created from template:', template, name)
  }

  const handleImport = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (file) {
      importWorkflow.mutate(file)
    }
  }

  // 计算统计数据
  const runningCount = (queueData as { running?: unknown[] })?.running?.length || 0
  const pendingCount = (queueData as { pending?: unknown[] })?.pending?.length || 0
  // 今日完成 = 执行统计中的成功数（近7天的，暂时用这个）
  const completedToday = execStats?.successful || 0
  const totalImages = execStats?.total_images || 0
  const failedCount = execStats?.failed || 0
  const successRate = execStats?.total_executions ? 
    ((execStats.successful / execStats.total_executions) * 100).toFixed(0) : '0'

  // 过滤工作流
  const filteredWorkflows = workflows.filter((w: Workflow) => {
    if (activeTab === 'favorites') return w.is_favorite
    if (activeTab === 'popular') return w.execution_count > 10
    return true
  })

  // 排序
  const sortedWorkflows = [...filteredWorkflows].sort((a: Workflow, b: Workflow) => {
    if (activeTab === 'popular') {
      return b.execution_count - a.execution_count
    }
    return new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime()
  })

  return (
    <div className="space-y-6">
      {/* Stats Overview */}
      <Card className="bg-card/50 border-border/50">
        <CardContent className="py-4">
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-2">
              <TrendingUp className="h-5 w-5 text-muted-foreground" />
              <span className="font-medium">快速概览</span>
            </div>
            <span className="text-sm text-muted-foreground">
              近7天生成: <span className="text-foreground font-medium">{totalImages}张</span>{' '}
              <span className="text-green-500">成功率 {successRate}%</span>
            </span>
          </div>
          <div className="grid grid-cols-4 gap-6">
            <div className="flex items-center gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-full bg-orange-500/10">
                <Flame className="h-5 w-5 text-orange-500" />
              </div>
              <div>
                <p className="text-2xl font-bold">{runningCount}</p>
                <p className="text-sm text-muted-foreground">执行中</p>
              </div>
            </div>
            <div className="flex items-center gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-full bg-blue-500/10">
                <Clock className="h-5 w-5 text-blue-500" />
              </div>
              <div>
                <p className="text-2xl font-bold">{pendingCount}</p>
                <p className="text-sm text-muted-foreground">队列中</p>
              </div>
            </div>
            <div className="flex items-center gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-full bg-green-500/10">
                <CheckCircle className="h-5 w-5 text-green-500" />
              </div>
              <div>
                <p className="text-2xl font-bold">{completedToday}</p>
                <p className="text-sm text-muted-foreground">今日完成</p>
              </div>
            </div>
            <div className="flex items-center gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-full bg-red-500/10">
                <XCircle className="h-5 w-5 text-red-500" />
              </div>
              <div>
                <p className="text-2xl font-bold">{failedCount}</p>
                <p className="text-sm text-muted-foreground">失败</p>
              </div>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Toolbar */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <h2 className="text-lg font-medium">工作流管理</h2>
          <div className="relative">
            <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
            <Input
              placeholder="搜索工作流..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-64 pl-9 bg-muted/50 border-border/50"
            />
          </div>
          <Button variant="outline" size="sm" className="border-border/50">
            <FolderOpen className="mr-2 h-4 w-4" />
            分类
          </Button>
          <Button variant="outline" size="sm" className="border-border/50">
            <Tag className="mr-2 h-4 w-4" />
            标签
          </Button>
        </div>
        <div className="flex items-center gap-2">
          <input
            ref={fileInputRef}
            type="file"
            accept=".json"
            onChange={handleImport}
            className="hidden"
          />
          <Button 
            variant="outline" 
            size="sm"
            onClick={() => setShowTemplates(true)}
          >
            <FolderOpen className="mr-2 h-4 w-4" />
            模板
          </Button>
          <Button 
            variant="outline" 
            size="sm"
            onClick={() => fileInputRef.current?.click()}
            disabled={importWorkflow.isPending}
          >
            {importWorkflow.isPending ? (
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
            ) : (
              <Upload className="mr-2 h-4 w-4" />
            )}
            导入
          </Button>
          <Button 
            size="sm" 
            className="bg-primary hover:bg-primary/90"
            onClick={() => setShowCreateDialog(true)}
          >
            <Plus className="mr-2 h-4 w-4" />
            新建
          </Button>
        </div>
      </div>

      {/* Create Workflow Dialog */}
      <Dialog open={showCreateDialog} onOpenChange={setShowCreateDialog}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>新建工作流</DialogTitle>
          </DialogHeader>
          <div className="space-y-4 py-4">
            <div className="space-y-2">
              <Label htmlFor="name">工作流名称</Label>
              <Input
                id="name"
                placeholder="输入工作流名称..."
                value={newWorkflowName}
                onChange={(e) => setNewWorkflowName(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && handleCreateWorkflow()}
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowCreateDialog(false)}>
              取消
            </Button>
            <Button 
              onClick={handleCreateWorkflow}
              disabled={!newWorkflowName.trim() || createWorkflow.isPending}
            >
              {createWorkflow.isPending ? (
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              ) : (
                <Plus className="mr-2 h-4 w-4" />
              )}
              创建
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Templates Dialog */}
      <Dialog open={showTemplates} onOpenChange={setShowTemplates}>
        <DialogContent className="max-w-6xl max-h-[80vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>工作流模板</DialogTitle>
          </DialogHeader>
          <WorkflowTemplates onCreateFromTemplate={handleCreateFromTemplate} />
        </DialogContent>
      </Dialog>

      {/* Tabs */}
      <Tabs value={activeTab} onValueChange={setActiveTab}>
        <TabsList className="bg-muted/50">
          <TabsTrigger value="all" className="data-[state=active]:bg-background">
            <Star className="mr-2 h-4 w-4" />
            全部
          </TabsTrigger>
          <TabsTrigger value="favorites" className="data-[state=active]:bg-background">
            <Star className="mr-2 h-4 w-4 fill-current" />
            收藏
          </TabsTrigger>
          <TabsTrigger value="recent" className="data-[state=active]:bg-background">
            <Clock className="mr-2 h-4 w-4" />
            最近
          </TabsTrigger>
          <TabsTrigger value="popular" className="data-[state=active]:bg-background">
            <TrendingUp className="mr-2 h-4 w-4" />
            热门
          </TabsTrigger>
        </TabsList>
      </Tabs>

      {/* Workflow Grid */}
      {workflowsLoading ? (
        <div className="flex items-center justify-center py-12">
          <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
        </div>
      ) : sortedWorkflows.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-12 text-muted-foreground">
          <FolderOpen className="h-12 w-12 mb-4" />
          <p>暂无工作流</p>
          <Button variant="outline" size="sm" className="mt-4">
            <Plus className="mr-2 h-4 w-4" />
            创建第一个工作流
          </Button>
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
          {sortedWorkflows.map((workflow: Workflow) => (
            <Card
              key={workflow.id}
              className="group overflow-hidden transition-all hover:shadow-lg hover:border-primary/50 bg-card/50 border-border/50"
            >
              {/* Thumbnail */}
              <div className="relative aspect-video bg-muted/50">
                <div className="absolute inset-0 flex items-center justify-center text-muted-foreground">
                  <FolderOpen className="h-12 w-12 opacity-50" />
                </div>
                {/* Hover Actions */}
                <div className="absolute inset-0 flex items-center justify-center gap-2 bg-black/70 opacity-0 transition-opacity group-hover:opacity-100">
                  <Button size="sm" variant="secondary" asChild>
                    <Link to={`/workflow/${workflow.id}`}>
                      <Edit className="mr-1 h-4 w-4" />
                      编辑
                    </Link>
                  </Button>
                  <Button 
                    size="sm"
                    onClick={() => executeWorkflow.mutate(workflow.id)}
                    disabled={executeWorkflow.isPending}
                  >
                    {executeWorkflow.isPending ? (
                      <Loader2 className="mr-1 h-4 w-4 animate-spin" />
                    ) : (
                      <Play className="mr-1 h-4 w-4" />
                    )}
                    执行
                  </Button>
                </div>
                {/* Badges */}
                <div className="absolute left-2 top-2 flex gap-1">
                  {workflow.is_default && (
                    <Badge className="bg-green-500/90 text-white text-xs">
                      默认
                    </Badge>
                  )}
                  {workflow.is_favorite && (
                    <Star className="h-5 w-5 fill-yellow-400 text-yellow-400" />
                  )}
                </div>
              </div>

              {/* Content */}
              <CardContent className="p-4">
                <div className="flex items-start justify-between">
                  <div className="flex-1 min-w-0">
                    <h3 className="font-medium truncate">{workflow.name}</h3>
                    <p className="text-sm text-muted-foreground">
                      v1.0 · {workflow.execution_count || 0}次
                    </p>
                  </div>
                  <DropdownMenu>
                    <DropdownMenuTrigger asChild>
                      <Button variant="ghost" size="icon" className="h-8 w-8 shrink-0">
                        <MoreHorizontal className="h-4 w-4" />
                      </Button>
                    </DropdownMenuTrigger>
                    <DropdownMenuContent align="end">
                      <DropdownMenuItem asChild>
                        <Link to={`/workflow/${workflow.id}`}>
                          <Edit className="mr-2 h-4 w-4" />
                          编辑
                        </Link>
                      </DropdownMenuItem>
                      <DropdownMenuItem>
                        <Copy className="mr-2 h-4 w-4" />
                        复制
                      </DropdownMenuItem>
                      <DropdownMenuItem onClick={() => toggleFavorite.mutate(workflow.id)}>
                        <Star className="mr-2 h-4 w-4" />
                        {workflow.is_favorite ? '取消收藏' : '收藏'}
                      </DropdownMenuItem>
                      {!workflow.is_default && (
                        <DropdownMenuItem onClick={() => setDefaultWorkflow.mutate(workflow.id)}>
                          <Check className="mr-2 h-4 w-4" />
                          设为默认
                        </DropdownMenuItem>
                      )}
                      <DropdownMenuSeparator />
                      <DropdownMenuItem 
                        className="text-destructive"
                        onClick={() => deleteWorkflow.mutate(workflow.id)}
                        disabled={workflow.is_default}
                      >
                        <Trash2 className="mr-2 h-4 w-4" />
                        删除
                      </DropdownMenuItem>
                    </DropdownMenuContent>
                  </DropdownMenu>
                </div>
                <div className="mt-2 flex flex-wrap gap-1">
                  {(workflow.tags || []).slice(0, 3).map((tag: string) => (
                    <Badge key={tag} variant="secondary" className="text-xs bg-muted/50">
                      {tag}
                    </Badge>
                  ))}
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      {/* Community Recommendations */}
      <Card className="bg-gradient-to-r from-orange-500/10 via-pink-500/10 to-purple-500/10 border-border/50">
        <CardContent className="py-3">
          <div className="flex items-center gap-4">
            <div className="flex items-center gap-2 shrink-0">
              <Flame className="h-5 w-5 text-orange-500" />
              <span className="font-medium text-sm">社区推荐</span>
            </div>
            <div className="flex items-center gap-2 overflow-x-auto scrollbar-hide">
              {featuredWorkflows.length > 0 ? (
                featuredWorkflows.map((workflow: MarketplaceWorkflow) => (
                  <Link key={workflow.id} to="/market">
                    <Badge 
                      variant="secondary" 
                      className="shrink-0 cursor-pointer hover:bg-accent transition-colors"
                    >
                      {workflow.name}
                    </Badge>
                  </Link>
                ))
              ) : (
                ['动漫大师 v2', '写实摄影 Pro', '概念艺术', 'SDXL 高清'].map((name) => (
                  <Badge 
                    key={name} 
                    variant="secondary" 
                    className="shrink-0 cursor-pointer hover:bg-accent transition-colors"
                  >
                    {name}
                  </Badge>
                ))
              )}
            </div>
            <Link to="/market">
              <Button variant="ghost" size="sm" className="shrink-0 text-muted-foreground">
                查看更多 →
              </Button>
            </Link>
          </div>
        </CardContent>
      </Card>

      {/* Footer */}
      <div className="flex items-center justify-between text-sm text-muted-foreground">
        <span>显示 {sortedWorkflows.length}/{workflows.length} 个工作流</span>
        <span>按{activeTab === 'popular' ? '使用次数' : '修改时间'}排序</span>
      </div>
    </div>
  )
}
