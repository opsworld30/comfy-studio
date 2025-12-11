import { useState, useEffect } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Input } from '@/components/ui/input'
import { Textarea } from '@/components/ui/textarea'
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs'
import {
  Search,
  Plus,
  Star,
  Copy,
  Trash2,
  Edit,
  Sparkles,
  Tag,
  Loader2,
  Wand2,
  ThumbsUp,
  Send,
  Shuffle,
  Save,
  Check,
} from 'lucide-react'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from '@/components/ui/dialog'
import { Label } from '@/components/ui/label'
import { promptsApi, workflowsApi, type Prompt, type Workflow, type GeneratedPrompt } from '@/lib/api'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { toast } from 'sonner'

// 每页显示数量
const PAGE_SIZE = 12

export default function Prompts() {
  const queryClient = useQueryClient()
  const [searchQuery, setSearchQuery] = useState('')
  const [activeTab, setActiveTab] = useState('all')
  const [currentPage, setCurrentPage] = useState(1)
  const [showAddDialog, setShowAddDialog] = useState(false)
  const [showGenerateDialog, setShowGenerateDialog] = useState(false)
  const [generateDescription, setGenerateDescription] = useState('')
  const [newPrompt, setNewPrompt] = useState({
    name: '',
    positive: '',
    negative: '',
    category: '',
    tags: [] as string[],
  })
  const [editingPrompt, setEditingPrompt] = useState<Prompt | null>(null)
  const [showEditDialog, setShowEditDialog] = useState(false)
  const [showRunDialog, setShowRunDialog] = useState(false)
  const [promptToRun, setPromptToRun] = useState<Prompt | null>(null)
  const [selectedWorkflowId, setSelectedWorkflowId] = useState<number | null>(null)
  const [runCount, setRunCount] = useState(1)
  const [showRandomDialog, setShowRandomDialog] = useState(false)
  const [randomCount, setRandomCount] = useState(5)
  const [randomTheme, setRandomTheme] = useState('')
  const [randomStyle, setRandomStyle] = useState('')
  const [generatedPrompts, setGeneratedPrompts] = useState<GeneratedPrompt[]>([])
  const [savedPromptIds, setSavedPromptIds] = useState<Set<number>>(new Set())

  // 获取提示词列表
  const { data: prompts = [], isLoading } = useQuery({
    queryKey: ['prompts', { search: searchQuery, favorite_only: activeTab === 'favorites' }],
    queryFn: async () => {
      const { data } = await promptsApi.list({
        search: searchQuery || undefined,
        favorite_only: activeTab === 'favorites',
      })
      return data
    },
  })

  // 获取分类
  const { data: categories = [] } = useQuery({
    queryKey: ['prompts', 'categories'],
    queryFn: async () => {
      const { data } = await promptsApi.getCategories()
      return data
    },
  })

  // 获取工作流列表
  const { data: workflows = [] } = useQuery({
    queryKey: ['workflows'],
    queryFn: async () => {
      const { data } = await workflowsApi.list()
      return data
    },
  })

  // 自动选择默认工作流
  useEffect(() => {
    if (workflows.length > 0 && selectedWorkflowId === null) {
      // 优先选择默认工作流
      const defaultWorkflow = workflows.find((w: Workflow) => w.is_default)
      if (defaultWorkflow) {
        setSelectedWorkflowId(defaultWorkflow.id)
      } else {
        // 没有默认工作流，选择第一个
        setSelectedWorkflowId(workflows[0].id)
      }
    }
  }, [workflows, selectedWorkflowId])

  // 创建提示词
  const createPrompt = useMutation({
    mutationFn: (data: Partial<Prompt>) => promptsApi.create(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['prompts'] })
      setShowAddDialog(false)
      setNewPrompt({ name: '', positive: '', negative: '', category: '', tags: [] })
    },
  })

  // 删除提示词
  const deletePrompt = useMutation({
    mutationFn: (id: number) => promptsApi.delete(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['prompts'] }),
  })

  // 切换收藏
  const toggleFavorite = useMutation({
    mutationFn: (id: number) => promptsApi.toggleFavorite(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['prompts'] }),
  })

  // AI 生成提示词
  const generatePrompt = useMutation({
    mutationFn: (description: string) => promptsApi.generate(description),
    onSuccess: (response) => {
      setNewPrompt({
        ...newPrompt,
        name: response.data.name || '',
        category: response.data.category || '',
        positive: response.data.positive,
        negative: response.data.negative,
      })
      setShowGenerateDialog(false)
      setGenerateDescription('')
      setShowAddDialog(true)
    },
    onError: (error: Error & { response?: { data?: { detail?: string } } }) => {
      const message = error.response?.data?.detail || error.message || 'AI 生成失败'
      toast.error('AI 生成失败', { description: message })
    },
  })

  // 更新提示词
  const updatePrompt = useMutation({
    mutationFn: ({ id, data }: { id: number; data: Partial<Prompt> }) => promptsApi.update(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['prompts'] })
      setShowEditDialog(false)
      setEditingPrompt(null)
    },
  })

  // 随机生成提示词
  const generateRandomMutation = useMutation({
    mutationFn: () => promptsApi.generateRandom({ 
      count: randomCount, 
      style: randomStyle || undefined,
      theme: randomTheme || undefined,
    }),
    onSuccess: (response) => {
      setGeneratedPrompts(response.data)
      setSavedPromptIds(new Set())
    },
    onError: (error: Error & { response?: { data?: { detail?: string } } }) => {
      const message = error.response?.data?.detail || error.message || '生成失败'
      toast.error('随机生成失败', { description: message })
    },
  })

  // 保存单个生成的提示词
  const saveGeneratedPrompt = async (prompt: GeneratedPrompt, index: number) => {
    try {
      await promptsApi.create({
        name: prompt.name,
        positive: prompt.positive,
        negative: prompt.negative,
        category: prompt.category || 'AI生成',
      })
      setSavedPromptIds(prev => new Set([...prev, index]))
      queryClient.invalidateQueries({ queryKey: ['prompts'] })
      toast.success('已保存')
    } catch {
      toast.error('保存失败')
    }
  }

  // 保存全部生成的提示词
  const saveAllGeneratedPrompts = async () => {
    let savedCount = 0
    for (let i = 0; i < generatedPrompts.length; i++) {
      if (!savedPromptIds.has(i)) {
        try {
          await promptsApi.create({
            name: generatedPrompts[i].name,
            positive: generatedPrompts[i].positive,
            negative: generatedPrompts[i].negative,
            category: generatedPrompts[i].category || 'AI生成',
          })
          savedCount++
        } catch {
          // 继续保存其他的
        }
      }
    }
    if (savedCount > 0) {
      queryClient.invalidateQueries({ queryKey: ['prompts'] })
      toast.success(`已保存 ${savedCount} 个提示词`)
      setShowRandomDialog(false)
      setGeneratedPrompts([])
      setSavedPromptIds(new Set())
    }
  }

  // 复制到剪贴板
  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text)
  }

  // 复制全部提示词
  const copyAll = (prompt: Prompt) => {
    const text = `正向提示词:\n${prompt.positive}\n\n负向提示词:\n${prompt.negative || '无'}`
    navigator.clipboard.writeText(text)
  }

  // 运行提示词
  const runPromptMutation = useMutation({
    mutationFn: async ({ prompt, workflowId, count }: { prompt: Prompt; workflowId: number; count: number }) => {
      const workflow = workflows.find((w: Workflow) => w.id === workflowId)
      if (!workflow) throw new Error('未找到工作流')
      
      const results = []
      for (let i = 0; i < count; i++) {
        const res = await promptsApi.runWithWorkflow({
          prompt_id: prompt.id,
          workflow_data: workflow.workflow_data,
        })
        results.push(res.data)
      }
      return results
    },
    onSuccess: (results) => {
      setShowRunDialog(false)
      setPromptToRun(null)
      setRunCount(1)
      
      // 只显示 toast 通知
      toast.success('已发送到 ComfyUI', {
        description: `替换节点: ${results[0]?.replaced_nodes?.join(', ') || '无'}`,
      })
    },
    onError: (error: Error) => {
      toast.error('执行失败', {
        description: error.message,
      })
    },
  })

  // 打开运行对话框
  const openRunDialog = (prompt: Prompt) => {
    setPromptToRun(prompt)
    setShowRunDialog(true)
  }

  // 确认运行
  const handleRunPrompt = () => {
    if (promptToRun && selectedWorkflowId) {
      runPromptMutation.mutate({
        prompt: promptToRun,
        workflowId: selectedWorkflowId,
        count: runCount,
      })
    }
  }

  // 发送到工作流执行
  const sendToWorkflow = async (prompt: Prompt) => {
    // 如果有工作流，打开选择对话框
    if (workflows.length > 0) {
      openRunDialog(prompt)
      return
    }
    
    // 没有工作流，提示用户先导入
    toast.warning('暂无工作流', {
      description: '请先在 Dashboard 页面导入或创建工作流',
    })
  }

  // 开始编辑
  const startEdit = (prompt: Prompt) => {
    setEditingPrompt({ ...prompt })
    setShowEditDialog(true)
  }

  // 保存编辑
  const handleSaveEdit = () => {
    if (editingPrompt) {
      updatePrompt.mutate({
        id: editingPrompt.id,
        data: {
          name: editingPrompt.name,
          positive: editingPrompt.positive,
          negative: editingPrompt.negative,
          category: editingPrompt.category,
        },
      })
    }
  }

  const handleCreate = () => {
    if (newPrompt.name && newPrompt.positive) {
      createPrompt.mutate(newPrompt)
    }
  }

  const handleGenerate = () => {
    if (generateDescription) {
      generatePrompt.mutate(generateDescription)
    }
  }

  // 过滤提示词
  const filteredPrompts = prompts.filter((p: Prompt) => {
    if (activeTab === 'favorites') return p.is_favorite
    if (activeTab !== 'all' && activeTab !== 'favorites') {
      return p.category === activeTab
    }
    return true
  })

  // 分页计算
  const totalPages = Math.ceil(filteredPrompts.length / PAGE_SIZE)
  const paginatedPrompts = filteredPrompts.slice(
    (currentPage - 1) * PAGE_SIZE,
    currentPage * PAGE_SIZE
  )

  // 切换标签时重置页码
  const handleTabChange = (tab: string) => {
    setActiveTab(tab)
    setCurrentPage(1)
  }

  // 搜索时重置页码
  const handleSearch = (query: string) => {
    setSearchQuery(query)
    setCurrentPage(1)
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
        <div className="flex items-center gap-4">
          <h2 className="text-lg font-medium">Prompt 智能库</h2>
          <div className="relative">
            <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
            <Input
              placeholder="搜索提示词..."
              value={searchQuery}
              onChange={(e) => handleSearch(e.target.value)}
              className="w-64 pl-9 bg-muted/50 border-border/50"
            />
          </div>
        </div>
        <div className="flex items-center gap-2">
          <Button 
            variant="outline" 
            size="sm"
            onClick={() => {
              setGeneratedPrompts([])
              setSavedPromptIds(new Set())
              setShowRandomDialog(true)
            }}
          >
            <Shuffle className="mr-2 h-4 w-4" />
            随机生成
          </Button>
          <Button 
            variant="outline" 
            size="sm"
            onClick={() => setShowGenerateDialog(true)}
          >
            <Wand2 className="mr-2 h-4 w-4" />
            AI 生成
          </Button>
          <Button size="sm" onClick={() => setShowAddDialog(true)}>
            <Plus className="mr-2 h-4 w-4" />
            新建
          </Button>
        </div>
      </div>

      {/* Tabs */}
      <Tabs value={activeTab} onValueChange={handleTabChange}>
        <TabsList className="bg-muted/50">
          <TabsTrigger value="all" className="data-[state=active]:bg-background">
            <Tag className="mr-2 h-4 w-4" />
            全部
          </TabsTrigger>
          <TabsTrigger value="favorites" className="data-[state=active]:bg-background">
            <Star className="mr-2 h-4 w-4" />
            收藏
          </TabsTrigger>
          {categories.slice(0, 4).map((cat: { category: string; count: number }) => (
            <TabsTrigger key={cat.category} value={cat.category} className="data-[state=active]:bg-background">
              {cat.category} ({cat.count})
            </TabsTrigger>
          ))}
        </TabsList>
      </Tabs>

      {/* Prompt Grid */}
      {filteredPrompts.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-12 text-muted-foreground">
          <Sparkles className="h-12 w-12 mb-4" />
          <p>暂无提示词</p>
          <Button 
            variant="outline" 
            size="sm" 
            className="mt-4"
            onClick={() => setShowAddDialog(true)}
          >
            <Plus className="mr-2 h-4 w-4" />
            创建第一个提示词
          </Button>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {paginatedPrompts.map((prompt: Prompt) => (
            <Card 
              key={prompt.id} 
              className="bg-card/50 border-border/50 hover:border-primary/50 transition-colors"
            >
              <CardHeader className="pb-2">
                <div className="flex items-start justify-between">
                  <div className="flex-1 min-w-0">
                    <CardTitle className="text-base truncate">{prompt.name}</CardTitle>
                    <div className="flex items-center gap-2 mt-1">
                      {prompt.category && (
                        <Badge variant="secondary" className="text-xs">
                          {prompt.category}
                        </Badge>
                      )}
                      <div className="flex items-center gap-1 text-xs text-muted-foreground">
                        <ThumbsUp className="h-3 w-3" />
                        {prompt.quality_score || 0}
                      </div>
                    </div>
                  </div>
                  <Button
                    variant="ghost"
                    size="icon"
                    className="h-8 w-8 shrink-0"
                    onClick={() => toggleFavorite.mutate(prompt.id)}
                  >
                    <Star className={`h-4 w-4 ${prompt.is_favorite ? 'fill-yellow-500 text-yellow-500' : ''}`} />
                  </Button>
                </div>
              </CardHeader>
              <CardContent className="space-y-3">
                {/* Positive Prompt */}
                <div>
                  <div className="flex items-center justify-between mb-1">
                    <span className="text-xs text-green-500 font-medium">正向提示词</span>
                    <Button
                      variant="ghost"
                      size="icon"
                      className="h-6 w-6"
                      onClick={() => copyToClipboard(prompt.positive)}
                    >
                      <Copy className="h-3 w-3" />
                    </Button>
                  </div>
                  <p className="text-sm bg-muted/50 p-2 rounded h-20 overflow-y-auto">
                    {prompt.positive}
                  </p>
                </div>

                {/* Negative Prompt */}
                <div>
                  <div className="flex items-center justify-between mb-1">
                    <span className="text-xs text-red-500 font-medium">负向提示词</span>
                    {prompt.negative && (
                      <Button
                        variant="ghost"
                        size="icon"
                        className="h-6 w-6"
                        onClick={() => copyToClipboard(prompt.negative)}
                      >
                        <Copy className="h-3 w-3" />
                      </Button>
                    )}
                  </div>
                  <p className="text-sm bg-muted/50 p-2 rounded h-16 overflow-y-auto text-muted-foreground">
                    {prompt.negative || <span className="text-muted-foreground/50 italic">无</span>}
                  </p>
                </div>

                {/* Tags */}
                {prompt.tags && prompt.tags.length > 0 && (
                  <div className="flex flex-wrap gap-1">
                    {prompt.tags.slice(0, 5).map((tag: string) => (
                      <Badge key={tag} variant="outline" className="text-xs">
                        {tag}
                      </Badge>
                    ))}
                  </div>
                )}

                {/* Actions */}
                <div className="flex items-center gap-1 pt-2 border-t border-border/50">
                  <Button 
                    variant="default" 
                    size="sm" 
                    className="flex-1"
                    onClick={() => sendToWorkflow(prompt)}
                  >
                    <Send className="mr-1 h-3 w-3" />
                    发送执行
                  </Button>
                  <Button 
                    variant="ghost" 
                    size="sm" 
                    className="flex-1"
                    onClick={() => copyAll(prompt)}
                  >
                    <Copy className="mr-1 h-3 w-3" />
                    复制
                  </Button>
                  <Button 
                    variant="ghost" 
                    size="icon" 
                    className="h-8 w-8"
                    onClick={() => startEdit(prompt)}
                  >
                    <Edit className="h-4 w-4" />
                  </Button>
                  <Button 
                    variant="ghost" 
                    size="icon" 
                    className="h-8 w-8"
                    onClick={() => deletePrompt.mutate(prompt.id)}
                  >
                    <Trash2 className="h-4 w-4" />
                  </Button>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-center gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={() => setCurrentPage(p => Math.max(1, p - 1))}
            disabled={currentPage === 1}
          >
            上一页
          </Button>
          <div className="flex items-center gap-1">
            {Array.from({ length: Math.min(totalPages, 7) }, (_, i) => {
              let pageNum: number
              if (totalPages <= 7) {
                pageNum = i + 1
              } else if (currentPage <= 4) {
                pageNum = i + 1
              } else if (currentPage >= totalPages - 3) {
                pageNum = totalPages - 6 + i
              } else {
                pageNum = currentPage - 3 + i
              }
              return (
                <Button
                  key={pageNum}
                  variant={currentPage === pageNum ? "default" : "outline"}
                  size="sm"
                  className="w-8 h-8 p-0"
                  onClick={() => setCurrentPage(pageNum)}
                >
                  {pageNum}
                </Button>
              )
            })}
          </div>
          <Button
            variant="outline"
            size="sm"
            onClick={() => setCurrentPage(p => Math.min(totalPages, p + 1))}
            disabled={currentPage === totalPages}
          >
            下一页
          </Button>
        </div>
      )}

      {/* Footer */}
      <div className="flex items-center justify-between text-sm text-muted-foreground">
        <span>显示 {paginatedPrompts.length}/{filteredPrompts.length} 个提示词（第 {currentPage}/{totalPages} 页）</span>
        <span>共 {prompts.length} 个提示词</span>
      </div>

      {/* Add Prompt Dialog */}
      <Dialog open={showAddDialog} onOpenChange={setShowAddDialog}>
        <DialogContent className="max-w-2xl">
          <DialogHeader>
            <DialogTitle>新建提示词</DialogTitle>
          </DialogHeader>
          <div className="space-y-4 py-4">
            <div className="space-y-2">
              <Label htmlFor="name">名称</Label>
              <Input
                id="name"
                placeholder="提示词名称"
                value={newPrompt.name}
                onChange={(e) => setNewPrompt({ ...newPrompt, name: e.target.value })}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="positive">正向提示词</Label>
              <Textarea
                id="positive"
                placeholder="描述你想要的内容..."
                value={newPrompt.positive}
                onChange={(e) => setNewPrompt({ ...newPrompt, positive: e.target.value })}
                rows={4}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="negative">负向提示词</Label>
              <Textarea
                id="negative"
                placeholder="描述你不想要的内容..."
                value={newPrompt.negative}
                onChange={(e) => setNewPrompt({ ...newPrompt, negative: e.target.value })}
                rows={3}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="category">分类</Label>
              <Input
                id="category"
                placeholder="例如: 人物、风景、动漫"
                value={newPrompt.category}
                onChange={(e) => setNewPrompt({ ...newPrompt, category: e.target.value })}
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowAddDialog(false)}>
              取消
            </Button>
            <Button 
              onClick={handleCreate}
              disabled={!newPrompt.name || !newPrompt.positive || createPrompt.isPending}
            >
              {createPrompt.isPending && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              创建
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Edit Prompt Dialog */}
      <Dialog open={showEditDialog} onOpenChange={setShowEditDialog}>
        <DialogContent className="max-w-2xl">
          <DialogHeader>
            <DialogTitle>编辑提示词</DialogTitle>
          </DialogHeader>
          {editingPrompt && (
            <div className="space-y-4 py-4">
              <div className="space-y-2">
                <Label>名称</Label>
                <Input
                  value={editingPrompt.name}
                  onChange={(e) => setEditingPrompt({ ...editingPrompt, name: e.target.value })}
                />
              </div>
              <div className="space-y-2">
                <Label>正向提示词</Label>
                <Textarea
                  value={editingPrompt.positive}
                  onChange={(e) => setEditingPrompt({ ...editingPrompt, positive: e.target.value })}
                  rows={4}
                />
              </div>
              <div className="space-y-2">
                <Label>负向提示词</Label>
                <Textarea
                  value={editingPrompt.negative}
                  onChange={(e) => setEditingPrompt({ ...editingPrompt, negative: e.target.value })}
                  rows={3}
                />
              </div>
              <div className="space-y-2">
                <Label>分类</Label>
                <Input
                  value={editingPrompt.category}
                  onChange={(e) => setEditingPrompt({ ...editingPrompt, category: e.target.value })}
                />
              </div>
            </div>
          )}
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowEditDialog(false)}>
              取消
            </Button>
            <Button 
              onClick={handleSaveEdit}
              disabled={!editingPrompt?.name || !editingPrompt?.positive || updatePrompt.isPending}
            >
              {updatePrompt.isPending && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              保存
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* AI Generate Dialog */}
      <Dialog open={showGenerateDialog} onOpenChange={setShowGenerateDialog}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <Wand2 className="h-5 w-5" />
              AI 生成提示词
            </DialogTitle>
          </DialogHeader>
          <div className="space-y-4 py-4">
            <div className="space-y-2">
              <Label htmlFor="description">描述你想要的图片</Label>
              <Textarea
                id="description"
                placeholder="例如: 一个穿着红色连衣裙的女孩站在樱花树下，阳光透过花瓣洒落..."
                value={generateDescription}
                onChange={(e) => setGenerateDescription(e.target.value)}
                rows={4}
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowGenerateDialog(false)}>
              取消
            </Button>
            <Button 
              onClick={handleGenerate}
              disabled={!generateDescription || generatePrompt.isPending}
            >
              {generatePrompt.isPending ? (
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              ) : (
                <Sparkles className="mr-2 h-4 w-4" />
              )}
              生成
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Run Prompt Dialog */}
      <Dialog open={showRunDialog} onOpenChange={setShowRunDialog}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle>发送到工作流执行</DialogTitle>
          </DialogHeader>
          <div className="space-y-4 py-4">
            <div className="space-y-2">
              <Label>提示词</Label>
              <p className="text-sm text-muted-foreground truncate">
                {promptToRun?.name}
              </p>
            </div>
            <div className="space-y-2">
              <Label>选择工作流</Label>
              <Select 
                value={selectedWorkflowId?.toString() || ''} 
                onValueChange={(v) => setSelectedWorkflowId(Number(v))}
              >
                <SelectTrigger>
                  <SelectValue placeholder="选择一个工作流" />
                </SelectTrigger>
                <SelectContent>
                  {workflows.map((w: Workflow) => (
                    <SelectItem key={w.id} value={w.id.toString()}>
                      <span className="flex items-center gap-2">
                        {w.name}
                        {w.is_default && (
                          <Badge variant="secondary" className="text-xs">默认</Badge>
                        )}
                      </span>
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              {workflows.length === 0 && (
                <p className="text-sm text-muted-foreground">
                  暂无工作流，请先创建工作流
                </p>
              )}
            </div>
            <div className="space-y-2">
              <Label>执行次数</Label>
              <Input
                type="number"
                min={1}
                value={runCount}
                onChange={(e) => {
                  const val = parseInt(e.target.value, 10)
                  if (!isNaN(val) && val >= 1) {
                    setRunCount(val)
                  }
                }}
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowRunDialog(false)}>
              取消
            </Button>
            <Button 
              onClick={handleRunPrompt}
              disabled={!selectedWorkflowId || runPromptMutation.isPending}
            >
              {runPromptMutation.isPending ? (
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              ) : (
                <Send className="mr-2 h-4 w-4" />
              )}
              发送执行
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Random Generate Dialog */}
      <Dialog open={showRandomDialog} onOpenChange={setShowRandomDialog}>
        <DialogContent className="max-w-3xl max-h-[80vh] overflow-hidden flex flex-col">
          <DialogHeader>
            <DialogTitle>随机生成提示词</DialogTitle>
          </DialogHeader>
          <div className="space-y-4 py-4">
            <div className="grid grid-cols-3 gap-4">
              <div className="space-y-2">
                <Label>生成数量</Label>
                <Select 
                  value={randomCount.toString()} 
                  onValueChange={(v) => setRandomCount(Number(v))}
                >
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {[3, 5, 8, 10].map(n => (
                      <SelectItem key={n} value={n.toString()}>{n} 个</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-2">
                <Label>主题（可选）</Label>
                <Input
                  placeholder="留空随机"
                  value={randomTheme}
                  onChange={(e) => setRandomTheme(e.target.value)}
                />
              </div>
              <div className="space-y-2">
                <Label>风格（可选）</Label>
                <Input
                  placeholder="留空随机"
                  value={randomStyle}
                  onChange={(e) => setRandomStyle(e.target.value)}
                />
              </div>
            </div>
            <Button 
              onClick={() => generateRandomMutation.mutate()}
              disabled={generateRandomMutation.isPending}
              className="w-full"
            >
              {generateRandomMutation.isPending ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  生成中...
                </>
              ) : (
                <>
                  <Shuffle className="mr-2 h-4 w-4" />
                  开始生成
                </>
              )}
            </Button>
          </div>
          
          {/* Generated Results */}
          {generatedPrompts.length > 0 && (
            <div className="flex-1 overflow-auto space-y-3 border-t pt-4">
              <div className="flex items-center justify-between">
                <span className="text-sm text-muted-foreground">
                  已生成 {generatedPrompts.length} 个提示词
                </span>
                <Button 
                  size="sm" 
                  onClick={saveAllGeneratedPrompts}
                  disabled={savedPromptIds.size === generatedPrompts.length}
                >
                  <Save className="mr-2 h-4 w-4" />
                  保存全部 ({generatedPrompts.length - savedPromptIds.size})
                </Button>
              </div>
              {generatedPrompts.map((prompt, index) => (
                <Card key={index} className={`p-3 ${savedPromptIds.has(index) ? 'opacity-50' : ''}`}>
                  <div className="flex items-start justify-between gap-2">
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 mb-1">
                        <span className="font-medium text-sm">{prompt.name}</span>
                        <Badge variant="secondary" className="text-xs">{prompt.category}</Badge>
                        {savedPromptIds.has(index) && (
                          <Badge className="bg-green-500/20 text-green-500 text-xs">
                            <Check className="h-3 w-3 mr-1" />
                            已保存
                          </Badge>
                        )}
                      </div>
                      <p className="text-xs text-muted-foreground line-clamp-2">{prompt.positive}</p>
                    </div>
                    <div className="flex gap-1 shrink-0">
                      <Button 
                        variant="ghost" 
                        size="icon"
                        className="h-7 w-7"
                        onClick={() => copyToClipboard(prompt.positive)}
                      >
                        <Copy className="h-3 w-3" />
                      </Button>
                      <Button 
                        variant="ghost" 
                        size="icon"
                        className="h-7 w-7"
                        onClick={() => saveGeneratedPrompt(prompt, index)}
                        disabled={savedPromptIds.has(index)}
                      >
                        <Save className="h-3 w-3" />
                      </Button>
                    </div>
                  </div>
                </Card>
              ))}
            </div>
          )}
          
          <DialogFooter className="border-t pt-4">
            <Button variant="outline" onClick={() => setShowRandomDialog(false)}>
              关闭
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}
