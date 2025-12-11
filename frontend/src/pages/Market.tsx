import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Badge } from '@/components/ui/badge'
import { toast } from 'sonner'
import {
  Download,
  Star,
  Globe,
  FolderOpen,
  Loader2,
  Upload,
  ExternalLink,
  Sparkles,
  Zap,
  Box,
  FileJson,
  Wand2,
  Copy,
  Check,
  Save,
} from 'lucide-react'

// 根据基础模型获取颜色
const getModelColor = (baseModel: string): string => {
  const colorMap: Record<string, string> = {
    'Flux': 'from-yellow-500/10 to-yellow-600/10 border-yellow-500/30 hover:border-yellow-500/50',
    'SD3': 'from-blue-500/10 to-blue-600/10 border-blue-500/30 hover:border-blue-500/50',
    'SDXL': 'from-purple-500/10 to-purple-600/10 border-purple-500/30 hover:border-purple-500/50',
    'SD1.5': 'from-green-500/10 to-green-600/10 border-green-500/30 hover:border-green-500/50',
    '通用': 'from-gray-500/10 to-gray-600/10 border-gray-500/30 hover:border-gray-500/50',
  }
  return colorMap[baseModel] || colorMap['通用']
}

const getModelIconColor = (baseModel: string): string => {
  const colorMap: Record<string, string> = {
    'Flux': 'text-yellow-500 bg-yellow-500/20',
    'SD3': 'text-blue-500 bg-blue-500/20',
    'SDXL': 'text-purple-500 bg-purple-500/20',
    'SD1.5': 'text-green-500 bg-green-500/20',
    '通用': 'text-gray-500 bg-gray-500/20',
  }
  return colorMap[baseModel] || colorMap['通用']
}
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from '@/components/ui/dialog'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { marketplaceApi, workflowsApi, builtinWorkflowsApi, serversApi, type MarketplaceWorkflow, type Workflow, type BuiltinWorkflow, type ComfyUIServer } from '@/lib/api'

interface ServerModels {
  checkpoints: string[]
  loras: string[]
  vaes: string[]
}

export default function Market() {
  const queryClient = useQueryClient()
  const [searchQuery] = useState('')
  const [sortBy, setSortBy] = useState('download_count')
  const [selectedCategory, setSelectedCategory] = useState<string | null>(null)
  const [selectedBaseModel, setSelectedBaseModel] = useState<string | null>(null)
  const [showPublishDialog, setShowPublishDialog] = useState(false)
  const [showPreviewDialog, setShowPreviewDialog] = useState(false)
  const [selectedWorkflow, setSelectedWorkflow] = useState<MarketplaceWorkflow | null>(null)
  const [publishData, setPublishData] = useState({
    workflow_id: 0,
    name: '',
    description: '',
  })
  const [showAIDialog, setShowAIDialog] = useState(false)
  const [aiPrompt, setAiPrompt] = useState('')
  const [aiGenerating, setAiGenerating] = useState(false)
  const [aiResult, setAiResult] = useState<string | null>(null)
  const [aiSelectedServer, setAiSelectedServer] = useState<string>('')
  const [serverModels, setServerModels] = useState<ServerModels | null>(null)
  const [loadingModels, setLoadingModels] = useState(false)
  const [selectedCheckpoint, setSelectedCheckpoint] = useState<string>('')
  const [selectedLora, setSelectedLora] = useState<string>('')
  const [copied, setCopied] = useState(false)

  // 获取市场工作流列表
  const { data: workflows = [], isLoading } = useQuery({
    queryKey: ['marketplace', { search: searchQuery, sort_by: sortBy, category: selectedCategory, base_model: selectedBaseModel }],
    queryFn: async () => {
      const { data } = await marketplaceApi.list({
        search: searchQuery || undefined,
        sort_by: sortBy,
        category: selectedCategory || undefined,
        base_model: selectedBaseModel || undefined,
        limit: 20,
      })
      return data
    },
  })

  // 获取精选工作流
  const { data: featuredWorkflows = [] } = useQuery({
    queryKey: ['marketplace', 'featured'],
    queryFn: async () => {
      const { data } = await marketplaceApi.getFeatured(4)
      return data
    },
  })

  // 获取分类列表
  const { data: categories = [] } = useQuery({
    queryKey: ['marketplace', 'categories'],
    queryFn: async () => {
      const { data } = await marketplaceApi.getCategories()
      return data
    },
  })

  // 获取本地工作流列表（用于发布）
  const { data: localWorkflows = [] } = useQuery({
    queryKey: ['workflows'],
    queryFn: async () => {
      const { data } = await workflowsApi.list()
      return data
    },
  })

  // 获取内置工作流模板
  const { data: builtinWorkflows = [], isLoading: isLoadingBuiltin } = useQuery({
    queryKey: ['builtin-workflows'],
    queryFn: async () => {
      const { data } = await builtinWorkflowsApi.list()
      return data
    },
  })

  // 获取服务器列表
  const { data: servers = [] } = useQuery({
    queryKey: ['comfyui-servers'],
    queryFn: async () => {
      const { data } = await serversApi.list()
      return data
    },
  })

  // API 基础 URL
  const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8001/api'

  // 当选择服务器时获取模型列表
  const handleServerSelect = async (serverId: string) => {
    setAiSelectedServer(serverId)
    setServerModels(null)
    setSelectedCheckpoint('')
    setSelectedLora('')
    
    if (!serverId) return
    
    setLoadingModels(true)
    try {
      // 通过后端代理获取，传入服务器 ID
      const response = await fetch(`${API_BASE}/comfyui-servers/${serverId}/models`)
      if (!response.ok) throw new Error('获取模型失败')
      
      const data = await response.json()
      const models = {
        checkpoints: data.checkpoints || [],
        loras: data.loras || [],
        vaes: data.vaes || [],
      }
      setServerModels(models)
      // 自动选择第一个模型
      if (models.checkpoints.length > 0) {
        setSelectedCheckpoint(models.checkpoints[0])
      }
    } catch (error) {
      console.error('获取模型列表失败:', error)
      toast.error('获取模型列表失败，请确保服务器已连接')
    } finally {
      setLoadingModels(false)
    }
  }

  // 下载工作流
  const downloadWorkflow = useMutation({
    mutationFn: (id: number) => marketplaceApi.download(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['workflows'] })
      queryClient.invalidateQueries({ queryKey: ['marketplace'] })
    },
  })

  // 发布工作流
  const publishWorkflow = useMutation({
    mutationFn: (data: { name: string; description: string; workflow_data: object }) => 
      marketplaceApi.publish(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['marketplace'] })
      setShowPublishDialog(false)
      setPublishData({ workflow_id: 0, name: '', description: '' })
    },
  })

  // 评分
  const rateWorkflow = useMutation({
    mutationFn: ({ id, rating }: { id: number; rating: number }) => 
      marketplaceApi.rate(id, rating),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['marketplace'] })
    },
  })

  const handlePreview = (workflow: MarketplaceWorkflow) => {
    setSelectedWorkflow(workflow)
    setShowPreviewDialog(true)
  }

  const handlePublish = async () => {
    const workflow = localWorkflows.find((w: Workflow) => w.id === publishData.workflow_id)
    if (workflow && publishData.name) {
      publishWorkflow.mutate({
        name: publishData.name,
        description: publishData.description,
        workflow_data: workflow.workflow_data || {},
      })
    }
  }

  const handleDownload = (id: number) => {
    downloadWorkflow.mutate(id)
  }

  // 下载内置工作流
  const handleDownloadBuiltin = async (id: string, name: string) => {
    try {
      const { data } = await builtinWorkflowsApi.download(id)
      const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' })
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `${name}.json`
      document.body.appendChild(a)
      a.click()
      document.body.removeChild(a)
      URL.revokeObjectURL(url)
      toast.success(`已下载工作流: ${name}`)
    } catch (error) {
      toast.error('下载失败')
    }
  }

  const handleRate = (id: number, rating: number) => {
    rateWorkflow.mutate({ id, rating })
  }

  const formatCount = (count: number) => {
    if (count >= 1000) return `${(count / 1000).toFixed(1)}K`
    return count.toString()
  }

  const handleSortChange = (value: string) => {
    setSortBy(value)
  }

  const handleBaseModelFilter = (model: string) => {
    setSelectedBaseModel(selectedBaseModel === model ? null : model)
  }

  // AI 生成工作流
  const handleAIGenerate = async () => {
    if (!aiPrompt.trim()) {
      toast.error('请输入工作流描述')
      return
    }
    
    setAiGenerating(true)
    setAiResult(null)
    
    try {
      // 构建请求数据，包含选中的模型
      const requestData: {
        prompt: string
        server_id?: number
        selected_checkpoint?: string
        selected_lora?: string
        models?: ServerModels
      } = { prompt: aiPrompt }
      
      if (aiSelectedServer && serverModels) {
        requestData.server_id = parseInt(aiSelectedServer)
        requestData.models = serverModels
        if (selectedCheckpoint) {
          requestData.selected_checkpoint = selectedCheckpoint
        }
        if (selectedLora) {
          requestData.selected_lora = selectedLora
        }
      }
      
      // 调用 AI 生成 API
      const response = await fetch(`${API_BASE}/ai/generate-workflow`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(requestData),
      })
      
      if (!response.ok) {
        throw new Error('生成失败')
      }
      
      const data = await response.json()
      setAiResult(JSON.stringify(data.workflow, null, 2))
      toast.success('工作流生成成功！')
    } catch (error) {
      toast.error('AI 生成失败，请稍后重试')
    } finally {
      setAiGenerating(false)
    }
  }

  const handleDownloadAIResult = () => {
    if (!aiResult) return
    const blob = new Blob([aiResult], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = 'ai-generated-workflow.json'
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    URL.revokeObjectURL(url)
    toast.success('已下载工作流')
  }

  const handleCopyAIResult = async () => {
    if (!aiResult) return
    try {
      await navigator.clipboard.writeText(aiResult)
      setCopied(true)
      toast.success('已复制到剪贴板')
      setTimeout(() => setCopied(false), 2000)
    } catch {
      toast.error('复制失败')
    }
  }

  const handleSaveToLocal = async () => {
    if (!aiResult) return
    try {
      // 保存到本地工作流
      const workflowData = JSON.parse(aiResult)
      await workflowsApi.create({
        name: `AI生成-${new Date().toLocaleString()}`,
        description: 'AI 自动生成的工作流',
        workflow_data: workflowData,
      })
      // 刷新工作流列表
      queryClient.invalidateQueries({ queryKey: ['workflows'] })
      queryClient.invalidateQueries({ queryKey: ['marketplace'] })
      toast.success('已保存到本地工作流')
      setShowAIDialog(false)
    } catch {
      toast.error('保存失败')
    }
  }

  if (isLoading) {
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
        <div>
          <h1 className="text-2xl font-bold">工作流市场</h1>
          <p className="text-muted-foreground">发现和下载社区分享的优质工作流</p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" onClick={() => setShowAIDialog(true)}>
            <Wand2 className="mr-2 h-4 w-4" />
            AI 生成
          </Button>
          <Button onClick={() => setShowPublishDialog(true)}>
            <Upload className="mr-2 h-4 w-4" />
            分享我的工作流
          </Button>
        </div>
      </div>

      {/* External Workflow Sites */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <a 
          href="https://openart.ai/workflows" 
          target="_blank" 
          rel="noopener noreferrer"
          className="block"
        >
          <Card className="bg-gradient-to-br from-purple-500/10 to-pink-500/10 border-border/50 hover:border-purple-500/50 transition-all cursor-pointer h-full">
            <CardContent className="pt-6">
              <div className="flex items-center gap-3">
                <div className="flex h-10 w-10 items-center justify-center rounded-full bg-purple-500/20">
                  <Sparkles className="h-5 w-5 text-purple-500" />
                </div>
                <div className="flex-1">
                  <h3 className="font-semibold">OpenArt</h3>
                  <p className="text-xs text-muted-foreground">海量 AI 工作流</p>
                </div>
                <ExternalLink className="h-4 w-4 text-muted-foreground" />
              </div>
            </CardContent>
          </Card>
        </a>
        <a 
          href="https://civitai.com/models?types=Workflows" 
          target="_blank" 
          rel="noopener noreferrer"
          className="block"
        >
          <Card className="bg-gradient-to-br from-blue-500/10 to-cyan-500/10 border-border/50 hover:border-blue-500/50 transition-all cursor-pointer h-full">
            <CardContent className="pt-6">
              <div className="flex items-center gap-3">
                <div className="flex h-10 w-10 items-center justify-center rounded-full bg-blue-500/20">
                  <Globe className="h-5 w-5 text-blue-500" />
                </div>
                <div className="flex-1">
                  <h3 className="font-semibold">Civitai</h3>
                  <p className="text-xs text-muted-foreground">模型和工作流社区</p>
                </div>
                <ExternalLink className="h-4 w-4 text-muted-foreground" />
              </div>
            </CardContent>
          </Card>
        </a>
        <a 
          href="https://comfyworkflows.com" 
          target="_blank" 
          rel="noopener noreferrer"
          className="block"
        >
          <Card className="bg-gradient-to-br from-green-500/10 to-emerald-500/10 border-border/50 hover:border-green-500/50 transition-all cursor-pointer h-full">
            <CardContent className="pt-6">
              <div className="flex items-center gap-3">
                <div className="flex h-10 w-10 items-center justify-center rounded-full bg-green-500/20">
                  <Zap className="h-5 w-5 text-green-500" />
                </div>
                <div className="flex-1">
                  <h3 className="font-semibold">ComfyWorkflows</h3>
                  <p className="text-xs text-muted-foreground">工作流分享平台</p>
                </div>
                <ExternalLink className="h-4 w-4 text-muted-foreground" />
              </div>
            </CardContent>
          </Card>
        </a>
        <a 
          href="https://www.comfy.org/workflows" 
          target="_blank" 
          rel="noopener noreferrer"
          className="block"
        >
          <Card className="bg-gradient-to-br from-orange-500/10 to-yellow-500/10 border-border/50 hover:border-orange-500/50 transition-all cursor-pointer h-full">
            <CardContent className="pt-6">
              <div className="flex items-center gap-3">
                <div className="flex h-10 w-10 items-center justify-center rounded-full bg-orange-500/20">
                  <Box className="h-5 w-5 text-orange-500" />
                </div>
                <div className="flex-1">
                  <h3 className="font-semibold">Comfy.org</h3>
                  <p className="text-xs text-muted-foreground">官方工作流库</p>
                </div>
                <ExternalLink className="h-4 w-4 text-muted-foreground" />
              </div>
            </CardContent>
          </Card>
        </a>
      </div>

      {/* Built-in Workflow Templates */}
      <Card className="bg-card/50 border-border/50">
        <CardHeader className="py-3">
          <CardTitle className="text-sm flex items-center gap-2">
            <Box className="h-4 w-4" />
            常用工作流模板
            <span className="text-xs text-muted-foreground font-normal">
              点击下载
            </span>
            {isLoadingBuiltin && <Loader2 className="h-3 w-3 animate-spin" />}
          </CardTitle>
        </CardHeader>
        <CardContent className="pt-0 pb-3">
          <div className="grid grid-cols-4 md:grid-cols-8 gap-2">
            {builtinWorkflows.map((workflow: BuiltinWorkflow) => (
              <div
                key={workflow.id}
                className={`p-2 rounded-lg bg-gradient-to-br ${getModelColor(workflow.baseModel)} cursor-pointer transition-all hover:scale-[1.02] text-center`}
                onClick={() => handleDownloadBuiltin(workflow.id, workflow.name)}
                title={workflow.description}
              >
                <div className={`flex h-6 w-6 mx-auto items-center justify-center rounded ${getModelIconColor(workflow.baseModel)}`}>
                  <FileJson className="h-3 w-3" />
                </div>
                <p className="text-xs font-medium mt-1 truncate">{workflow.name}</p>
                <Badge variant="secondary" className="text-[9px] px-1 py-0 mt-0.5">{workflow.baseModel}</Badge>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>

      {/* Local Workflows - Compact with Pagination */}
      <Card className="bg-card/50 border-border/50">
        <CardHeader className="py-3">
          <div className="flex items-center justify-between">
            <CardTitle className="text-sm flex items-center gap-2">
              <FolderOpen className="h-4 w-4" />
              我的工作流
              <span className="text-xs text-muted-foreground font-normal">
                共 {localWorkflows.length} 个
              </span>
            </CardTitle>
          </div>
        </CardHeader>
        <CardContent className="pt-0 pb-3">
          {localWorkflows.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-6 text-muted-foreground">
              <FolderOpen className="h-6 w-6 mb-2" />
              <p className="text-xs">暂无本地工作流</p>
            </div>
          ) : (
            <div className="grid grid-cols-3 md:grid-cols-6 gap-2">
              {localWorkflows.slice(0, 6).map((workflow: Workflow) => (
                <div 
                  key={workflow.id} 
                  className="p-2 rounded-lg border border-border/50 hover:border-primary/50 transition-colors bg-card/30 text-center"
                  title={workflow.description || workflow.name}
                >
                  <div className="w-8 h-8 mx-auto bg-muted rounded flex items-center justify-center mb-1">
                    <FileJson className="h-4 w-4 text-muted-foreground" />
                  </div>
                  <p className="text-[10px] font-medium truncate">{workflow.name}</p>
                  <p className="text-[9px] text-muted-foreground">{workflow.category}</p>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Featured Section */}
      {featuredWorkflows.length > 0 && (
        <Card className="bg-card/50 border-border/50">
          <CardHeader>
            <CardTitle className="text-base flex items-center gap-2">
              <Star className="h-5 w-5 text-yellow-500" />
              编辑推荐
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-4 gap-4">
              {featuredWorkflows.map((workflow: MarketplaceWorkflow) => (
                <div 
                  key={workflow.id} 
                  className="text-center cursor-pointer hover:opacity-80 transition-opacity"
                  onClick={() => handlePreview(workflow)}
                >
                  <div className="aspect-square rounded-lg bg-muted flex items-center justify-center mb-2 overflow-hidden">
                    {workflow.thumbnail ? (
                      <img src={workflow.thumbnail} alt={workflow.name} className="w-full h-full object-cover" />
                    ) : (
                      <FolderOpen className="h-8 w-8 text-muted-foreground" />
                    )}
                  </div>
                  <p className="text-sm font-medium truncate">{workflow.name}</p>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Categories */}
      {categories.length > 0 && (
        <Card className="bg-card/50 border-border/50">
          <CardHeader>
            <CardTitle className="text-base">分类浏览</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex flex-wrap gap-2">
              <Button
                variant={selectedCategory === null ? 'default' : 'outline'}
                size="sm"
                onClick={() => setSelectedCategory(null)}
              >
                全部
              </Button>
              {categories.map((cat: { category: string; count: number }) => (
                <Button
                  key={cat.category}
                  variant={selectedCategory === cat.category ? 'default' : 'outline'}
                  size="sm"
                  onClick={() => setSelectedCategory(cat.category)}
                >
                  {cat.category} ({cat.count})
                </Button>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Footer */}
      <div className="flex items-center justify-between text-sm text-muted-foreground">
        <span>显示 {workflows.length} 个工作流</span>
      </div>

      {/* Preview Dialog */}
      <Dialog open={showPreviewDialog} onOpenChange={setShowPreviewDialog}>
        <DialogContent className="max-w-3xl">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              {selectedWorkflow?.name}
              {selectedWorkflow?.is_featured && <Badge>精选</Badge>}
            </DialogTitle>
          </DialogHeader>
          {selectedWorkflow && (
            <div className="space-y-4">
              <div className="flex gap-4">
                <div className="w-64 h-64 bg-muted rounded-lg flex items-center justify-center shrink-0">
                  {selectedWorkflow.thumbnail ? (
                    <img src={selectedWorkflow.thumbnail} alt={selectedWorkflow.name} className="w-full h-full object-cover rounded-lg" />
                  ) : (
                    <FolderOpen className="h-16 w-16 text-muted-foreground" />
                  )}
                </div>
                <div className="flex-1 space-y-3">
                  <p className="text-muted-foreground">{selectedWorkflow.description || '暂无描述'}</p>
                  <div className="grid grid-cols-2 gap-2 text-sm">
                    <div><span className="text-muted-foreground">作者:</span> {selectedWorkflow.author || '匿名'}</div>
                    <div><span className="text-muted-foreground">基础模型:</span> {selectedWorkflow.base_model || '未知'}</div>
                    <div><span className="text-muted-foreground">下载量:</span> {formatCount(selectedWorkflow.download_count)}</div>
                    <div><span className="text-muted-foreground">评分:</span> {selectedWorkflow.rating.toFixed(1)} ({selectedWorkflow.rating_count})</div>
                  </div>
                  {selectedWorkflow.tags && selectedWorkflow.tags.length > 0 && (
                    <div className="flex flex-wrap gap-1">
                      {selectedWorkflow.tags.map((tag: string) => (
                        <Badge key={tag} variant="outline">{tag}</Badge>
                      ))}
                    </div>
                  )}
                </div>
              </div>
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <span className="text-sm text-muted-foreground">评分:</span>
                  {[1, 2, 3, 4, 5].map((star) => (
                    <button
                      key={star}
                      onClick={() => handleRate(selectedWorkflow.id, star)}
                      className="hover:scale-110 transition-transform"
                    >
                      <Star 
                        className={`h-5 w-5 ${star <= selectedWorkflow.rating ? 'fill-yellow-400 text-yellow-400' : 'text-muted-foreground'}`} 
                      />
                    </button>
                  ))}
                </div>
                <Button onClick={() => handleDownload(selectedWorkflow.id)} disabled={downloadWorkflow.isPending}>
                  {downloadWorkflow.isPending ? (
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  ) : (
                    <Download className="mr-2 h-4 w-4" />
                  )}
                  下载到本地
                </Button>
              </div>
            </div>
          )}
        </DialogContent>
      </Dialog>

      {/* Publish Dialog */}
      <Dialog open={showPublishDialog} onOpenChange={setShowPublishDialog}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <Globe className="h-5 w-5" />
              分享工作流到市场
            </DialogTitle>
          </DialogHeader>
          <div className="space-y-4 py-4">
            <div className="space-y-2">
              <Label>选择工作流</Label>
              <Select
                value={publishData.workflow_id.toString()}
                onValueChange={(value) => setPublishData({ ...publishData, workflow_id: parseInt(value) })}
              >
                <SelectTrigger>
                  <SelectValue placeholder="选择要分享的工作流" />
                </SelectTrigger>
                <SelectContent>
                  {localWorkflows.map((w: Workflow) => (
                    <SelectItem key={w.id} value={w.id.toString()}>
                      {w.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <Label>显示名称</Label>
              <Input
                placeholder="在市场中显示的名称"
                value={publishData.name}
                onChange={(e) => setPublishData({ ...publishData, name: e.target.value })}
              />
            </div>
            <div className="space-y-2">
              <Label>描述</Label>
              <Textarea
                placeholder="介绍一下这个工作流的特点和用途..."
                value={publishData.description}
                onChange={(e) => setPublishData({ ...publishData, description: e.target.value })}
                rows={4}
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowPublishDialog(false)}>
              取消
            </Button>
            <Button
              onClick={handlePublish}
              disabled={!publishData.workflow_id || !publishData.name || publishWorkflow.isPending}
            >
              {publishWorkflow.isPending && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              发布
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* AI Generate Dialog */}
      <Dialog open={showAIDialog} onOpenChange={setShowAIDialog}>
        <DialogContent className="max-w-2xl">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <Wand2 className="h-5 w-5 text-purple-500" />
              AI 生成工作流
            </DialogTitle>
          </DialogHeader>
          <div className="space-y-4 py-4">
            {/* 服务器选择 */}
            <div className="space-y-2">
              <Label>选择 ComfyUI 服务器（可选）</Label>
              <Select value={aiSelectedServer || "none"} onValueChange={(v) => handleServerSelect(v === "none" ? "" : v)}>
                <SelectTrigger>
                  <SelectValue placeholder={servers.length > 0 ? "选择服务器以使用本地模型" : "无可用服务器"} />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="none">不使用服务器（通用模板）</SelectItem>
                  {servers.map((server: ComfyUIServer) => (
                    <SelectItem key={server.id} value={server.id.toString()}>
                      {server.name} {server.is_default && '(默认)'}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              {servers.length === 0 && (
                <p className="text-xs text-muted-foreground">没有配置服务器，将生成通用工作流模板</p>
              )}
            </div>

            {/* 显示已获取的模型 */}
            {loadingModels && (
              <div className="flex items-center gap-2 text-sm text-muted-foreground">
                <Loader2 className="h-4 w-4 animate-spin" />
                正在获取模型列表...
              </div>
            )}
            {serverModels && serverModels.checkpoints.length > 0 && (
              <div className="grid grid-cols-2 gap-3">
                <div className="space-y-2">
                  <Label className="text-xs">选择模型 (Checkpoint)</Label>
                  <Select value={selectedCheckpoint} onValueChange={setSelectedCheckpoint}>
                    <SelectTrigger className="h-8 text-xs">
                      <SelectValue placeholder="选择模型" />
                    </SelectTrigger>
                    <SelectContent>
                      {serverModels.checkpoints.map((m) => (
                        <SelectItem key={m} value={m} className="text-xs">
                          {m.split('/').pop()}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
                {serverModels.loras.length > 0 && (
                  <div className="space-y-2">
                    <Label className="text-xs">选择 LoRA（可选）</Label>
                    <Select value={selectedLora || "none"} onValueChange={(v) => setSelectedLora(v === "none" ? "" : v)}>
                      <SelectTrigger className="h-8 text-xs">
                        <SelectValue placeholder="不使用 LoRA" />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="none" className="text-xs">不使用 LoRA</SelectItem>
                        {serverModels.loras.map((m) => (
                          <SelectItem key={m} value={m} className="text-xs">
                            {m.split('/').pop()}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                )}
              </div>
            )}

            <div className="space-y-2">
              <Label>描述你想要的工作流</Label>
              <Textarea
                placeholder="例如：一个使用 SDXL 模型的文生图工作流，带有 LoRA 加载和高清放大功能..."
                value={aiPrompt}
                onChange={(e) => setAiPrompt(e.target.value)}
                rows={3}
              />
            </div>
            <div className="flex gap-2 flex-wrap">
              <Badge 
                variant="outline" 
                className="cursor-pointer hover:bg-muted"
                onClick={() => setAiPrompt('一个简单的 SDXL 文生图工作流')}
              >
                SDXL 文生图
              </Badge>
              <Badge 
                variant="outline" 
                className="cursor-pointer hover:bg-muted"
                onClick={() => setAiPrompt('Flux 模型的高质量文生图工作流')}
              >
                Flux 文生图
              </Badge>
              <Badge 
                variant="outline" 
                className="cursor-pointer hover:bg-muted"
                onClick={() => setAiPrompt('带有 ControlNet 深度图控制的图生图工作流')}
              >
                ControlNet 深度
              </Badge>
              <Badge 
                variant="outline" 
                className="cursor-pointer hover:bg-muted"
                onClick={() => setAiPrompt('图片放大工作流，使用 RealESRGAN 模型')}
              >
                图片放大
              </Badge>
            </div>
            {aiResult && (
              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <Label>生成结果</Label>
                  <div className="flex gap-1">
                    <Button
                      variant="ghost"
                      size="sm"
                      className="h-6 px-2 text-xs"
                      onClick={handleCopyAIResult}
                    >
                      {copied ? <Check className="h-3 w-3 mr-1" /> : <Copy className="h-3 w-3 mr-1" />}
                      {copied ? '已复制' : '复制'}
                    </Button>
                    <Button
                      variant="ghost"
                      size="sm"
                      className="h-6 px-2 text-xs"
                      onClick={handleSaveToLocal}
                    >
                      <Save className="h-3 w-3 mr-1" />
                      保存到本地
                    </Button>
                  </div>
                </div>
                <div className="bg-muted rounded-lg p-3 max-h-32 overflow-auto">
                  <pre className="text-xs text-muted-foreground whitespace-pre-wrap">
                    {aiResult.slice(0, 300)}...
                  </pre>
                </div>
              </div>
            )}
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowAIDialog(false)}>
              取消
            </Button>
            {aiResult ? (
              <Button onClick={handleDownloadAIResult}>
                <Download className="mr-2 h-4 w-4" />
                下载工作流
              </Button>
            ) : (
              <Button onClick={handleAIGenerate} disabled={aiGenerating || !aiPrompt.trim()}>
                {aiGenerating ? (
                  <>
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    生成中...
                  </>
                ) : (
                  <>
                    <Sparkles className="mr-2 h-4 w-4" />
                    生成工作流
                  </>
                )}
              </Button>
            )}
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}
