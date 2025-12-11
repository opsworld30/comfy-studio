import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Input } from '@/components/ui/input'
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import {
  Search,
  Download,
  Trash2,
  RefreshCw,
  Box,
  Layers,
  Palette,
  Loader2,
  HardDrive,
  FolderOpen,
  ExternalLink,
  AlertTriangle,
  AlertCircle,
  Star,
  Globe,
  Heart,
  ChevronLeft,
  ChevronRight,
} from 'lucide-react'
import { modelsApi, comfyuiApi, civitaiApi, type ModelInfo, type CivitaiModel, type StorageAnalysis, type ModelDetail } from '@/lib/api'
import { usePageModulesStore } from '@/stores/pageModules'

export default function Models() {
  const { isModuleVisible } = usePageModulesStore()
  const queryClient = useQueryClient()
  const [searchQuery, setSearchQuery] = useState('')
  const [activeTab, setActiveTab] = useState('all')
  const [viewMode, setViewMode] = useState<'local' | 'civitai'>('local')
  const [civitaiSearch, setCivitaiSearch] = useState('')
  const [civitaiType, setCivitaiType] = useState('Checkpoint')
  const [civitaiSort, setCivitaiSort] = useState('Most Downloaded')
  const [civitaiPage, setCivitaiPage] = useState(1)
  const [selectedCivitaiModel, setSelectedCivitaiModel] = useState<CivitaiModel | null>(null)

  // 获取模型列表
  const { data: models = [], isLoading } = useQuery({
    queryKey: ['models', activeTab],
    queryFn: async () => {
      const type = activeTab === 'all' ? undefined : activeTab
      const { data } = await modelsApi.list(type)
      return data
    },
  })

  // 获取模型统计
  const { data: stats } = useQuery({
    queryKey: ['models', 'stats'],
    queryFn: async () => {
      const { data } = await modelsApi.getStats()
      return data
    },
  })

  // 获取 ComfyUI 模型列表
  const { data: comfyModels = [] } = useQuery({
    queryKey: ['comfyui', 'models'],
    queryFn: async () => {
      const { data } = await comfyuiApi.getModels()
      return data
    },
  })

  // 获取 LoRA 列表
  const { data: loras = [] } = useQuery({
    queryKey: ['comfyui', 'loras'],
    queryFn: async () => {
      const { data } = await comfyuiApi.getLoras()
      return data
    },
  })

  // 获取存储分析 - 真实文件系统数据
  const { data: storageAnalysis, isLoading: storageLoading } = useQuery({
    queryKey: ['models', 'storage', 'analysis'],
    queryFn: async () => {
      const response = await modelsApi.getStorageAnalysis()
      return response.data
    },
    staleTime: 60000, // 1分钟缓存
  })

  // 获取模型详情（真实文件大小）
  const { data: modelDetails = [] } = useQuery({
    queryKey: ['models', 'storage', 'details'],
    queryFn: async () => {
      const { data } = await modelsApi.getStorageDetails()
      return data
    },
  })

  // Civitai 模型列表（默认加载热门模型，搜索时加载搜索结果）
  const { data: civitaiModels, isLoading: civitaiLoading } = useQuery({
    queryKey: ['civitai', 'models', civitaiSearch, civitaiType, civitaiSort, civitaiPage],
    queryFn: async () => {
      const { data } = await civitaiApi.search({
        query: civitaiSearch,
        types: civitaiType,
        sort: civitaiSort,
        limit: 24,
        page: civitaiPage,
      })
      return data
    },
    enabled: viewMode === 'civitai',
  })

  // 重置页码当筛选条件变化时
  const handleCivitaiFilterChange = (setter: (v: string) => void, value: string) => {
    setter(value)
    setCivitaiPage(1)
  }

  // 扫描模型
  const scanModels = useMutation({
    mutationFn: () => modelsApi.scan(),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['models'] })
    },
  })

  // 删除模型
  const deleteModel = useMutation({
    mutationFn: (id: number) => modelsApi.delete(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['models'] })
    },
  })

  // 切换收藏
  const toggleFavorite = useMutation({
    mutationFn: (id: number) => modelsApi.toggleFavorite(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['models'] })
    },
  })

  // 格式化文件大小
  const formatSize = (bytes: number) => {
    if (bytes >= 1024 * 1024 * 1024) {
      return `${(bytes / (1024 * 1024 * 1024)).toFixed(2)} GB`
    }
    if (bytes >= 1024 * 1024) {
      return `${(bytes / (1024 * 1024)).toFixed(0)} MB`
    }
    return `${(bytes / 1024).toFixed(0)} KB`
  }

  // 使用真实文件数据或数据库数据
  const displayModels: (ModelInfo | ModelDetail)[] = modelDetails.length > 0 ? modelDetails : models

  // 过滤模型
  const filteredModels = displayModels.filter((m) => {
    // 按类型过滤
    if (activeTab !== 'all') {
      const typeMap: Record<string, string[]> = {
        checkpoints: ['checkpoints', 'checkpoint'],
        loras: ['loras', 'lora'],
        vae: ['vae'],
      }
      const allowedTypes = typeMap[activeTab] || [activeTab]
      if (!allowedTypes.includes(m.type)) return false
    }
    // 按搜索词过滤
    if (searchQuery) {
      return m.name.toLowerCase().includes(searchQuery.toLowerCase())
    }
    return true
  })

  // 统计数据 - 优先使用存储分析的真实数据
  const totalSize = storageAnalysis?.total_size || stats?.total_size || 0
  const totalCount = storageAnalysis?.total_files || stats?.total_count || 0
  const checkpointCount = storageAnalysis?.models_by_type?.checkpoints?.count || comfyModels.length
  const loraCount = storageAnalysis?.models_by_type?.loras?.count || loras.length

  const getTypeIcon = (type: string) => {
    switch (type) {
      case 'checkpoints':
        return <Box className="h-4 w-4" />
      case 'loras':
        return <Layers className="h-4 w-4" />
      case 'vae':
        return <Palette className="h-4 w-4" />
      default:
        return <FolderOpen className="h-4 w-4" />
    }
  }

  const getTypeBadge = (type: string) => {
    switch (type) {
      case 'checkpoints':
        return <Badge className="bg-blue-500">Checkpoint</Badge>
      case 'loras':
        return <Badge className="bg-purple-500">LoRA</Badge>
      case 'vae':
        return <Badge className="bg-green-500">VAE</Badge>
      case 'embeddings':
        return <Badge className="bg-orange-500">Embedding</Badge>
      case 'controlnet':
        return <Badge className="bg-cyan-500">ControlNet</Badge>
      default:
        return <Badge variant="secondary">{type}</Badge>
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
        <div className="flex items-center gap-4">
          <h2 className="text-lg font-medium">模型库</h2>
          <div className="relative">
            <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
            <Input
              placeholder="搜索模型..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-64 pl-9 bg-muted/50 border-border/50"
            />
          </div>
        </div>
        <div className="flex items-center gap-2">
          <Button 
            variant="outline" 
            size="sm"
            onClick={() => scanModels.mutate()}
            disabled={scanModels.isPending}
          >
            {scanModels.isPending ? (
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
            ) : (
              <RefreshCw className="mr-2 h-4 w-4" />
            )}
            扫描模型
          </Button>
        </div>
      </div>

      {/* Storage Analysis */}
      <Card className="bg-gradient-to-r from-blue-500/10 via-purple-500/10 to-pink-500/10 border-border/50">
        <CardContent className="py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-6">
              <div className="flex items-center gap-2">
                <HardDrive className="h-5 w-5 text-blue-400" />
                <span className="font-medium">存储概览</span>
              </div>
              <div className="text-sm">
                已用: <span className="font-bold text-blue-400">{storageAnalysis?.total_size_display || formatSize(totalSize)}</span> / 500GB
              </div>
              <div className="h-2 w-48 rounded-full bg-muted overflow-hidden">
                <div 
                  className="h-full bg-gradient-to-r from-blue-500 to-purple-500 transition-all"
                  style={{ width: `${Math.min(((storageAnalysis?.total_size || totalSize) / (500 * 1024 * 1024 * 1024)) * 100, 100)}%` }}
                />
              </div>
            </div>
            <div className="flex items-center gap-4 text-sm">
              {(storageAnalysis?.duplicate_count || 0) > 0 && (
                <div className="flex items-center gap-2 text-yellow-400">
                  <AlertTriangle className="h-4 w-4" />
                  <span>重复文件: {storageAnalysis?.duplicate_count}个 ({storageAnalysis?.duplicate_size_display})</span>
                  <Button variant="ghost" size="sm" className="h-6 text-xs">清理</Button>
                </div>
              )}
              {(storageAnalysis?.missing_count || 0) > 0 && (
                <div className="flex items-center gap-2 text-red-400">
                  <AlertCircle className="h-4 w-4" />
                  <span>缺失依赖: {storageAnalysis?.missing_count}个</span>
                  <Button variant="ghost" size="sm" className="h-6 text-xs">下载</Button>
                </div>
              )}
              {(storageAnalysis?.duplicate_count || 0) === 0 && (storageAnalysis?.missing_count || 0) === 0 && (
                <div className="flex items-center gap-2 text-green-400">
                  <Box className="h-4 w-4" />
                  <span>存储状态良好</span>
                </div>
              )}
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Stats */}
      <div className="grid grid-cols-4 gap-4">
        <Card className="bg-card/50 border-border/50">
          <CardContent className="pt-6">
            <div className="flex items-center gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-full bg-blue-500/10">
                <Box className="h-5 w-5 text-blue-500" />
              </div>
              <div>
                <p className="text-2xl font-bold">{checkpointCount}</p>
                <p className="text-sm text-muted-foreground">Checkpoints</p>
              </div>
            </div>
          </CardContent>
        </Card>
        <Card className="bg-card/50 border-border/50">
          <CardContent className="pt-6">
            <div className="flex items-center gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-full bg-purple-500/10">
                <Layers className="h-5 w-5 text-purple-500" />
              </div>
              <div>
                <p className="text-2xl font-bold">{loraCount}</p>
                <p className="text-sm text-muted-foreground">LoRAs</p>
              </div>
            </div>
          </CardContent>
        </Card>
        <Card className="bg-card/50 border-border/50">
          <CardContent className="pt-6">
            <div className="flex items-center gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-full bg-green-500/10">
                <FolderOpen className="h-5 w-5 text-green-500" />
              </div>
              <div>
                <p className="text-2xl font-bold">{totalCount}</p>
                <p className="text-sm text-muted-foreground">总模型数</p>
              </div>
            </div>
          </CardContent>
        </Card>
        <Card className="bg-card/50 border-border/50">
          <CardContent className="pt-6">
            <div className="flex items-center gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-full bg-orange-500/10">
                <HardDrive className="h-5 w-5 text-orange-500" />
              </div>
              <div>
                <p className="text-2xl font-bold">{formatSize(totalSize)}</p>
                <p className="text-sm text-muted-foreground">总大小</p>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Main Tabs - Local vs Civitai */}
      <Tabs value={viewMode} onValueChange={(v) => setViewMode(v as 'local' | 'civitai')}>
        <div className="flex items-center justify-between">
          <TabsList className="bg-muted/50">
            <TabsTrigger value="local" className="data-[state=active]:bg-background">
              <FolderOpen className="mr-2 h-4 w-4" />
              本地模型
            </TabsTrigger>
            <TabsTrigger value="civitai" className="data-[state=active]:bg-background">
              <Globe className="mr-2 h-4 w-4" />
              Civitai 浏览
            </TabsTrigger>
          </TabsList>
          
          {viewMode === 'local' && isModuleVisible('models', 'showLocalModels') && (
            <Tabs value={activeTab} onValueChange={setActiveTab}>
              <TabsList className="bg-muted/50">
                <TabsTrigger value="all">全部</TabsTrigger>
                <TabsTrigger value="checkpoints">Checkpoints</TabsTrigger>
                <TabsTrigger value="loras">LoRAs</TabsTrigger>
                <TabsTrigger value="vae">VAE</TabsTrigger>
              </TabsList>
            </Tabs>
          )}
          
          {viewMode === 'civitai' && isModuleVisible('models', 'showCivitai') && (
            <div className="flex items-center gap-2">
              <div className="relative">
                <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                <Input
                  placeholder="搜索 Civitai 模型..."
                  value={civitaiSearch}
                  onChange={(e) => handleCivitaiFilterChange(setCivitaiSearch, e.target.value)}
                  className="pl-9 w-64"
                />
              </div>
              <Tabs value={civitaiType} onValueChange={(v) => handleCivitaiFilterChange(setCivitaiType, v)}>
                <TabsList>
                  <TabsTrigger value="Checkpoint">Checkpoint</TabsTrigger>
                  <TabsTrigger value="LORA">LoRA</TabsTrigger>
                  <TabsTrigger value="TextualInversion">Embedding</TabsTrigger>
                </TabsList>
              </Tabs>
              <select 
                value={civitaiSort} 
                onChange={(e) => handleCivitaiFilterChange(setCivitaiSort, e.target.value)}
                className="h-9 rounded-md border border-input bg-background px-3 text-sm"
              >
                <option value="Most Downloaded">最多下载</option>
                <option value="Highest Rated">最高评分</option>
                <option value="Newest">最新发布</option>
              </select>
            </div>
          )}
        </div>
      </Tabs>

      {/* Local Model List */}
      {viewMode === 'local' && isModuleVisible('models', 'showLocalModels') && (
        <>
          {filteredModels.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-12 text-muted-foreground">
              <Box className="h-12 w-12 mb-4" />
              <p>暂无模型</p>
              <Button 
                variant="outline" 
                size="sm" 
                className="mt-4"
                onClick={() => scanModels.mutate()}
              >
                <RefreshCw className="mr-2 h-4 w-4" />
                扫描模型目录
              </Button>
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {filteredModels.map((model) => (
                <Card 
                  key={model.name} 
                  className="bg-card/50 border-border/50 hover:border-primary/50 transition-colors"
                >
                  <CardHeader className="pb-2">
                    <div className="flex items-start justify-between">
                      <div className="flex items-center gap-2">
                        {getTypeIcon(model.type)}
                        <CardTitle className="text-base truncate">{model.name}</CardTitle>
                      </div>
                      {getTypeBadge(model.type)}
                    </div>
                  </CardHeader>
                  <CardContent className="space-y-3">
                    <div className="flex items-center justify-between text-sm">
                      <span className="text-muted-foreground">大小</span>
                      <span className="font-medium">
                        {'size_display' in model ? model.size_display : formatSize(model.size)}
                      </span>
                    </div>
                    
                    {model.base_model && (
                      <div className="flex items-center justify-between text-sm">
                        <span className="text-muted-foreground">基础模型</span>
                        <Badge variant="outline">{model.base_model}</Badge>
                      </div>
                    )}

                    {'description' in model && model.description && (
                      <p className="text-sm text-muted-foreground line-clamp-2">
                        {model.description}
                      </p>
                    )}

                    {'tags' in model && model.tags && model.tags.length > 0 && (
                      <div className="flex flex-wrap gap-1">
                        {model.tags.slice(0, 3).map((tag: string) => (
                          <Badge key={tag} variant="secondary" className="text-xs">
                            {tag}
                          </Badge>
                        ))}
                      </div>
                    )}

                    {/* Actions */}
                    <div className="flex items-center gap-1 pt-2 border-t border-border/50">
                      {'id' in model && (
                        <Button 
                          variant="ghost" 
                          size="icon" 
                          className="h-8 w-8"
                          onClick={() => toggleFavorite.mutate(model.id)}
                        >
                          <Heart className={`h-4 w-4 ${'is_favorite' in model && model.is_favorite ? 'fill-red-500 text-red-500' : ''}`} />
                        </Button>
                      )}
                      {'civitai_id' in model && model.civitai_id && (
                        <Button variant="ghost" size="sm" className="flex-1" asChild>
                          <a href={`https://civitai.com/models/${model.civitai_id}`} target="_blank" rel="noopener noreferrer">
                            <ExternalLink className="mr-1 h-3 w-3" />
                            Civitai
                          </a>
                        </Button>
                      )}
                      {'id' in model && (
                        <Button 
                          variant="ghost" 
                          size="icon" 
                          className="h-8 w-8"
                          onClick={() => deleteModel.mutate(model.id)}
                        >
                          <Trash2 className="h-4 w-4" />
                        </Button>
                      )}
                    </div>
                  </CardContent>
                </Card>
              ))}
            </div>
          )}

          {/* Footer */}
          <div className="flex items-center justify-between text-sm text-muted-foreground">
            <span>显示 {filteredModels.length}/{models.length} 个模型</span>
            <span>按名称排序</span>
          </div>
        </>
      )}

      {/* Civitai Model List */}
      {viewMode === 'civitai' && isModuleVisible('models', 'showCivitai') && (
        <>
          {civitaiLoading ? (
            <div className="flex items-center justify-center py-12">
              <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
            </div>
          ) : civitaiModels?.items?.length ? (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
              {civitaiModels.items.map((model: CivitaiModel) => (
                <Card 
                  key={model.id} 
                  className="overflow-hidden cursor-pointer hover:border-primary/50 transition-colors bg-card/50 border-border/50"
                  onClick={() => setSelectedCivitaiModel(model)}
                >
                  {model.previewUrl ? (
                    <div className="aspect-square bg-muted overflow-hidden">
                      <img 
                        src={model.previewUrl} 
                        alt={model.name}
                        className="w-full h-full object-cover"
                        loading="lazy"
                      />
                    </div>
                  ) : (
                    <div className="aspect-square bg-muted flex items-center justify-center">
                      <Box className="h-12 w-12 text-muted-foreground" />
                    </div>
                  )}
                  <CardContent className="p-3 space-y-2">
                    <h4 className="font-medium text-sm truncate">{model.name}</h4>
                    <div className="flex items-center justify-between text-xs text-muted-foreground">
                      <span className="truncate">{model.creator}</span>
                      <Badge variant="outline" className="text-xs shrink-0 ml-1">{model.version?.baseModel || 'Unknown'}</Badge>
                    </div>
                    <div className="flex items-center gap-3 text-xs text-muted-foreground">
                      <span className="flex items-center gap-1">
                        <Download className="h-3 w-3" />
                        {(model.stats?.downloadCount || 0).toLocaleString()}
                      </span>
                      <span className="flex items-center gap-1">
                        <Star className="h-3 w-3" />
                        {(model.stats?.rating || 0).toFixed(1)}
                      </span>
                      <span className="flex items-center gap-1">
                        <Heart className="h-3 w-3" />
                        {(model.stats?.favoriteCount || 0).toLocaleString()}
                      </span>
                    </div>
                  </CardContent>
                </Card>
              ))}
            </div>
          ) : (
            <div className="flex flex-col items-center justify-center py-12 text-muted-foreground">
              <Globe className="h-12 w-12 mb-4" />
              <p>切换到 Civitai 浏览标签页查看热门模型</p>
              <p className="text-sm mt-2">使用搜索框搜索更多模型</p>
            </div>
          )}

          {/* Pagination */}
          <div className="flex items-center justify-between text-sm">
            <span className="text-muted-foreground">
              第 {civitaiPage} 页，共 {civitaiModels?.metadata?.totalPages || 1} 页
              {civitaiModels?.metadata?.totalItems && ` (共 ${civitaiModels.metadata.totalItems.toLocaleString()} 个模型)`}
            </span>
            <div className="flex items-center gap-2">
              <Button
                variant="outline"
                size="sm"
                onClick={() => setCivitaiPage(p => Math.max(1, p - 1))}
                disabled={civitaiPage <= 1 || civitaiLoading}
              >
                <ChevronLeft className="h-4 w-4 mr-1" />
                上一页
              </Button>
              <span className="px-3 py-1 bg-muted rounded text-sm font-medium">
                {civitaiPage}
              </span>
              <Button
                variant="outline"
                size="sm"
                onClick={() => setCivitaiPage(p => p + 1)}
                disabled={(civitaiModels?.items?.length || 0) < 24 || civitaiLoading}
              >
                下一页
                <ChevronRight className="h-4 w-4 ml-1" />
              </Button>
            </div>
            <span className="text-muted-foreground">数据来源: Civitai.com</span>
          </div>
        </>
      )}

      {/* Model Detail Dialog */}
      <Dialog open={!!selectedCivitaiModel} onOpenChange={() => setSelectedCivitaiModel(null)}>
        <DialogContent className="max-w-2xl">
          <DialogHeader>
            <DialogTitle>{selectedCivitaiModel?.name}</DialogTitle>
          </DialogHeader>
          {selectedCivitaiModel && (
            <div className="space-y-4">
              {selectedCivitaiModel.previewUrl && (
                <div className="aspect-video bg-muted rounded-lg overflow-hidden">
                  <img 
                    src={selectedCivitaiModel.previewUrl} 
                    alt={selectedCivitaiModel.name}
                    className="w-full h-full object-cover"
                  />
                </div>
              )}
              
              <div className="grid grid-cols-2 gap-4 text-sm">
                <div>
                  <span className="text-muted-foreground">作者:</span>
                  <span className="ml-2 font-medium">{selectedCivitaiModel.creator}</span>
                </div>
                <div>
                  <span className="text-muted-foreground">类型:</span>
                  <span className="ml-2 font-medium">{selectedCivitaiModel.type}</span>
                </div>
                <div>
                  <span className="text-muted-foreground">基础模型:</span>
                  <Badge variant="outline" className="ml-2">{selectedCivitaiModel.version?.baseModel}</Badge>
                </div>
                <div>
                  <span className="text-muted-foreground">版本:</span>
                  <span className="ml-2 font-medium">{selectedCivitaiModel.version?.name}</span>
                </div>
              </div>

              <div className="flex items-center gap-4 text-sm">
                <span className="flex items-center gap-1">
                  <Download className="h-4 w-4" />
                  {(selectedCivitaiModel.stats?.downloadCount || 0).toLocaleString()} 下载
                </span>
                <span className="flex items-center gap-1">
                  <Star className="h-4 w-4" />
                  {(selectedCivitaiModel.stats?.rating || 0).toFixed(1)} 评分
                </span>
                <span className="flex items-center gap-1">
                  <Heart className="h-4 w-4" />
                  {(selectedCivitaiModel.stats?.favoriteCount || 0).toLocaleString()} 收藏
                </span>
              </div>

              {selectedCivitaiModel.tags?.length > 0 && (
                <div className="flex flex-wrap gap-1">
                  {selectedCivitaiModel.tags.map((tag: string) => (
                    <Badge key={tag} variant="secondary" className="text-xs">{tag}</Badge>
                  ))}
                </div>
              )}

              {selectedCivitaiModel.description && (
                <p className="text-sm text-muted-foreground line-clamp-3">
                  {selectedCivitaiModel.description.replace(/<[^>]*>/g, '')}
                </p>
              )}

              <div className="flex items-center gap-2 pt-4 border-t">
                <Button className="flex-1" asChild>
                  <a 
                    href={selectedCivitaiModel.version?.downloadUrl || `https://civitai.com/models/${selectedCivitaiModel.id}`} 
                    target="_blank" 
                    rel="noopener noreferrer"
                  >
                    <Download className="mr-2 h-4 w-4" />
                    下载模型
                  </a>
                </Button>
                <Button variant="outline" asChild>
                  <a 
                    href={`https://civitai.com/models/${selectedCivitaiModel.id}`} 
                    target="_blank" 
                    rel="noopener noreferrer"
                  >
                    <ExternalLink className="mr-2 h-4 w-4" />
                    Civitai 页面
                  </a>
                </Button>
              </div>
            </div>
          )}
        </DialogContent>
      </Dialog>
    </div>
  )
}
