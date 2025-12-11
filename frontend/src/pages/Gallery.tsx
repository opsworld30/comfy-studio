import { useState, useCallback } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useCircuitBreaker } from '@/hooks/useCircuitBreaker'
import { Card, CardContent } from '@/components/ui/card'
import { GallerySkeleton } from '@/components/ui/skeleton'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Badge } from '@/components/ui/badge'
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs'
import {
  Search,
  Grid,
  List,
  Download,
  Star,
  Heart,
  Share2,
  Filter,
  Calendar,
  Image as ImageIcon,
  Loader2,
  X,
  ChevronLeft,
  ChevronRight,
  ZoomIn,
  Copy,
  ExternalLink,
  Sparkles,
} from 'lucide-react'
import { Dialog, DialogContent, DialogTitle } from '@/components/ui/dialog'
import { comfyuiApi, type StoredImage } from '@/lib/api'

const PAGE_SIZE = 48 // 每页显示数量

export default function Gallery() {
  const [searchQuery, setSearchQuery] = useState('')
  const [activeTab, setActiveTab] = useState('all')
  const [viewMode, setViewMode] = useState<'grid' | 'list'>('grid')
  const [selectedImage, setSelectedImage] = useState<StoredImage | null>(null)
  const [lightboxIndex, setLightboxIndex] = useState(0)
  const [favorites, setFavorites] = useState<Set<number>>(() => {
    // 从 localStorage 加载收藏
    const saved = localStorage.getItem('gallery_favorites')
    return saved ? new Set(JSON.parse(saved)) : new Set()
  })
  const [selectedCategory, setSelectedCategory] = useState<string | null>(null)
  const [currentPage, setCurrentPage] = useState(1)

  // 熔断器：控制轮询，防止后端离线时无限重试
  const { createRefetchInterval, shouldEnableQuery, wrapQueryFn } = useCircuitBreaker()

  // 获取本地存储的图片列表（带熔断器保护）
  const { data: images = [], isLoading, refetch } = useQuery({
    queryKey: ['gallery', 'stored-images'],
    queryFn: wrapQueryFn(async () => {
      const { data } = await comfyuiApi.getStoredImages({ limit: 1000 })
      return data
    }),
    refetchInterval: createRefetchInterval(15000), // 15秒刷新一次
    staleTime: 5000, // 5秒后数据过期
    enabled: shouldEnableQuery(),
    retry: 1,
  })

  // 过滤图片
  const filteredImages = images.filter((img: StoredImage) => {
    // 收藏过滤
    if (activeTab === 'favorites' && !favorites.has(img.id)) {
      return false
    }
    // 今日过滤
    if (activeTab === 'today' && img.created_at) {
      const today = new Date().toDateString()
      const imgDate = new Date(img.created_at).toDateString()
      if (today !== imgDate) return false
    }
    // 分类过滤
    if (selectedCategory && categorizeImage(img) !== selectedCategory) {
      return false
    }
    // 搜索过滤
    if (searchQuery) {
      const query = searchQuery.toLowerCase()
      return (
        img.filename.toLowerCase().includes(query) ||
        img.positive?.toLowerCase().includes(query) ||
        img.model?.toLowerCase().includes(query)
      )
    }
    return true
  })

  // 分页计算
  const totalPages = Math.ceil(filteredImages.length / PAGE_SIZE)
  const paginatedImages = filteredImages.slice(
    (currentPage - 1) * PAGE_SIZE,
    currentPage * PAGE_SIZE
  )

  // 当过滤条件变化时重置页码
  const resetPage = () => setCurrentPage(1)

  // 打开灯箱
  const openLightbox = (image: StoredImage, index: number) => {
    setSelectedImage(image)
    setLightboxIndex(index)
  }

  // 关闭灯箱
  const closeLightbox = () => {
    setSelectedImage(null)
  }

  // 上一张/下一张
  const navigateLightbox = (direction: 'prev' | 'next') => {
    const newIndex = direction === 'prev' 
      ? (lightboxIndex - 1 + filteredImages.length) % filteredImages.length
      : (lightboxIndex + 1) % filteredImages.length
    setLightboxIndex(newIndex)
    setSelectedImage(filteredImages[newIndex])
  }

  // 下载图片
  const downloadImage = async (image: StoredImage) => {
    const url = comfyuiApi.getStoredImageUrl(image.id)
    const link = document.createElement('a')
    link.href = url
    link.download = image.filename
    link.click()
  }

  // 复制提示词
  const copyPrompt = (text: string) => {
    navigator.clipboard.writeText(text)
  }

  // 切换收藏
  const toggleFavorite = (imageId: number, e?: React.MouseEvent) => {
    e?.stopPropagation()
    setFavorites(prev => {
      const newFavorites = new Set(prev)
      if (newFavorites.has(imageId)) {
        newFavorites.delete(imageId)
      } else {
        newFavorites.add(imageId)
      }
      // 保存到 localStorage
      localStorage.setItem('gallery_favorites', JSON.stringify([...newFavorites]))
      return newFavorites
    })
  }

  // 根据提示词分类图片
  const categorizeImage = (image: StoredImage): string => {
    const prompt = (image.positive || '').toLowerCase()
    if (prompt.includes('girl') || prompt.includes('boy') || prompt.includes('woman') || prompt.includes('man') || prompt.includes('person')) {
      return '人物'
    }
    if (prompt.includes('landscape') || prompt.includes('mountain') || prompt.includes('forest') || prompt.includes('sky')) {
      return '风景'
    }
    if (prompt.includes('animal') || prompt.includes('cat') || prompt.includes('dog') || prompt.includes('bird')) {
      return '动物'
    }
    if (prompt.includes('building') || prompt.includes('city') || prompt.includes('architecture')) {
      return '建筑'
    }
    if (prompt.includes('abstract') || prompt.includes('pattern')) {
      return '抽象'
    }
    return '其他'
  }

  // 统计各分类数量
  const categoryStats = images.reduce((acc: Record<string, number>, img: StoredImage) => {
    const cat = categorizeImage(img)
    acc[cat] = (acc[cat] || 0) + 1
    return acc
  }, {})

  // 图片加载状态管理
  const [loadedImages, setLoadedImages] = useState<Set<number>>(new Set())
  
  const handleImageLoad = useCallback((imageId: number) => {
    setLoadedImages(prev => new Set([...prev, imageId]))
  }, [])

  if (isLoading) {
    return (
      <div className="space-y-6">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-4">
            <h2 className="text-lg font-medium">图片画廊</h2>
          </div>
        </div>
        <GallerySkeleton count={24} />
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* Toolbar */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <h2 className="text-lg font-medium">图片画廊</h2>
          <div className="relative">
            <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
            <Input
              placeholder="搜索图片..."
              value={searchQuery}
              onChange={(e) => { setSearchQuery(e.target.value); resetPage() }}
              className="w-64 pl-9 bg-muted/50 border-border/50"
            />
          </div>
          <Button 
            variant="outline" 
            size="sm" 
            className="border-border/50"
            onClick={() => refetch()}
            disabled={isLoading}
          >
            <Loader2 className={`mr-2 h-4 w-4 ${isLoading ? 'animate-spin' : ''}`} />
            刷新
          </Button>
          <Button variant="outline" size="sm" className="border-border/50">
            <Filter className="mr-2 h-4 w-4" />
            筛选
          </Button>
          <Button variant="outline" size="sm" className="border-cyan-500/50 text-cyan-400 hover:bg-cyan-500/10">
            <Search className="mr-2 h-4 w-4" />
            相似图搜索
          </Button>
        </div>
        <div className="flex items-center gap-2">
          <div className="flex items-center border rounded-md bg-muted/50">
            <Button
              variant={viewMode === 'grid' ? 'secondary' : 'ghost'}
              size="icon"
              className="h-8 w-8"
              onClick={() => setViewMode('grid')}
            >
              <Grid className="h-4 w-4" />
            </Button>
            <Button
              variant={viewMode === 'list' ? 'secondary' : 'ghost'}
              size="icon"
              className="h-8 w-8"
              onClick={() => setViewMode('list')}
            >
              <List className="h-4 w-4" />
            </Button>
          </div>
        </div>
      </div>

      {/* Tabs */}
      <Tabs value={activeTab} onValueChange={(v) => { setActiveTab(v); resetPage() }}>
        <TabsList className="bg-muted/50">
          <TabsTrigger value="all" className="data-[state=active]:bg-background">
            <ImageIcon className="mr-2 h-4 w-4" />
            全部
          </TabsTrigger>
          <TabsTrigger value="favorites" className="data-[state=active]:bg-background">
            <Star className="mr-2 h-4 w-4" />
            收藏
          </TabsTrigger>
          <TabsTrigger value="today" className="data-[state=active]:bg-background">
            <Calendar className="mr-2 h-4 w-4" />
            今日
          </TabsTrigger>
        </TabsList>
      </Tabs>

      {/* AI Smart Categories */}
      <Card className="bg-card/50 border-border/50">
        <CardContent className="py-3">
          <div className="flex items-center gap-4">
            <div className="flex items-center gap-2 shrink-0">
              <Sparkles className="h-4 w-4 text-cyan-400" />
              <span className="text-sm font-medium">智能分类</span>
            </div>
            <div className="flex items-center gap-2 flex-wrap">
              <button
                onClick={() => setSelectedCategory(null)}
                className={`px-3 py-1 rounded-full text-xs font-medium transition-colors ${!selectedCategory ? 'bg-primary text-primary-foreground' : 'bg-muted hover:bg-muted/80'}`}
              >
                全部
              </button>
              {[
                { name: '人物', color: 'bg-pink-500/10 text-pink-500 hover:bg-pink-500/20' },
                { name: '风景', color: 'bg-green-500/10 text-green-500 hover:bg-green-500/20' },
                { name: '动物', color: 'bg-yellow-500/10 text-yellow-500 hover:bg-yellow-500/20' },
                { name: '抽象', color: 'bg-purple-500/10 text-purple-500 hover:bg-purple-500/20' },
                { name: '建筑', color: 'bg-blue-500/10 text-blue-500 hover:bg-blue-500/20' },
                { name: '其他', color: 'bg-gray-500/10 text-gray-400 hover:bg-gray-500/20' },
              ].map((cat) => (
                <button
                  key={cat.name}
                  onClick={() => setSelectedCategory(selectedCategory === cat.name ? null : cat.name)}
                  className={`px-3 py-1 rounded-full text-xs font-medium transition-colors ${selectedCategory === cat.name ? 'ring-2 ring-offset-1 ring-offset-background' : ''} ${cat.color}`}
                >
                  {cat.name} <span className="opacity-70">({categoryStats[cat.name] || 0})</span>
                </button>
              ))}
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Image Grid */}
      {filteredImages.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-12 text-muted-foreground">
          <ImageIcon className="h-12 w-12 mb-4" />
          <p>暂无图片</p>
        </div>
      ) : (
        <div className={viewMode === 'grid' 
          ? "grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6 gap-4"
          : "space-y-2"
        }>
          {paginatedImages.map((image: StoredImage, index: number) => (
            <Card 
              key={`${image.filename}-${index}`}
              className="group overflow-hidden cursor-pointer transition-all hover:shadow-lg hover:border-primary/50 bg-card/50 border-border/50"
              onClick={() => openLightbox(image, (currentPage - 1) * PAGE_SIZE + index)}
            >
              <div className="relative aspect-square bg-muted/50 overflow-hidden">
                {/* 骨架占位 - 使用 aspect-ratio 防止布局抖动 */}
                {!loadedImages.has(image.id) && (
                  <div className="absolute inset-0 bg-muted animate-pulse" />
                )}
                <img
                  src={comfyuiApi.getStoredThumbnailUrl(image.id, 150)}
                  alt={image.filename}
                  className={`w-full h-full object-cover transition-opacity duration-300 ${
                    loadedImages.has(image.id) ? 'opacity-100' : 'opacity-0'
                  }`}
                  loading="lazy"
                  onLoad={() => handleImageLoad(image.id)}
                />
                {/* Hover Overlay */}
                <div className="absolute inset-0 bg-black/60 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center gap-2">
                  <Button size="icon" variant="secondary" className="h-8 w-8">
                    <ZoomIn className="h-4 w-4" />
                  </Button>
                  <Button 
                    size="icon" 
                    variant="secondary" 
                    className="h-8 w-8"
                    onClick={(e) => toggleFavorite(image.id, e)}
                  >
                    <Heart className={`h-4 w-4 ${favorites.has(image.id) ? 'fill-red-500 text-red-500' : ''}`} />
                  </Button>
                  <Button 
                    size="icon" 
                    variant="secondary" 
                    className="h-8 w-8"
                    onClick={(e) => {
                      e.stopPropagation()
                      downloadImage(image)
                    }}
                  >
                    <Download className="h-4 w-4" />
                  </Button>
                </div>
              </div>
              {viewMode === 'list' && (
                <CardContent className="p-3">
                  <p className="text-sm font-medium truncate">{image.filename}</p>
                  {image.positive && (
                    <p className="text-xs text-muted-foreground truncate mt-1">
                      {image.positive}
                    </p>
                  )}
                </CardContent>
              )}
            </Card>
          ))}
        </div>
      )}

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-center gap-2 py-4">
          <Button
            variant="outline"
            size="sm"
            onClick={() => setCurrentPage(1)}
            disabled={currentPage === 1}
          >
            首页
          </Button>
          <Button
            variant="outline"
            size="sm"
            onClick={() => setCurrentPage(p => Math.max(1, p - 1))}
            disabled={currentPage === 1}
          >
            <ChevronLeft className="h-4 w-4" />
          </Button>
          <div className="flex items-center gap-1">
            {Array.from({ length: Math.min(5, totalPages) }, (_, i) => {
              let page: number
              if (totalPages <= 5) {
                page = i + 1
              } else if (currentPage <= 3) {
                page = i + 1
              } else if (currentPage >= totalPages - 2) {
                page = totalPages - 4 + i
              } else {
                page = currentPage - 2 + i
              }
              return (
                <Button
                  key={page}
                  variant={currentPage === page ? "default" : "outline"}
                  size="sm"
                  className="w-8"
                  onClick={() => setCurrentPage(page)}
                >
                  {page}
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
            <ChevronRight className="h-4 w-4" />
          </Button>
          <Button
            variant="outline"
            size="sm"
            onClick={() => setCurrentPage(totalPages)}
            disabled={currentPage === totalPages}
          >
            末页
          </Button>
        </div>
      )}

      {/* Footer */}
      <div className="flex items-center justify-between text-sm text-muted-foreground">
        <span>共 {filteredImages.length} 张图片，当前第 {currentPage}/{totalPages || 1} 页</span>
        <span>按生成时间排序</span>
      </div>

      {/* Lightbox Dialog */}
      <Dialog open={!!selectedImage} onOpenChange={() => closeLightbox()}>
        <DialogContent className="max-w-6xl h-[90vh] p-0 bg-black/95 border-none">
          <DialogTitle className="sr-only">图片详情</DialogTitle>
          {selectedImage && (
            <div className="flex h-full">
              {/* Image Area */}
              <div className="flex-1 relative flex items-center justify-center">
                {/* Navigation */}
                <Button
                  variant="ghost"
                  size="icon"
                  className="absolute left-4 text-white hover:bg-white/20"
                  onClick={() => navigateLightbox('prev')}
                >
                  <ChevronLeft className="h-8 w-8" />
                </Button>
                <Button
                  variant="ghost"
                  size="icon"
                  className="absolute right-4 text-white hover:bg-white/20"
                  onClick={() => navigateLightbox('next')}
                >
                  <ChevronRight className="h-8 w-8" />
                </Button>

                {/* Image */}
                <img
                  src={comfyuiApi.getStoredImageUrl(selectedImage.id)}
                  alt={selectedImage.filename}
                  className="max-h-full max-w-full object-contain"
                />

                {/* Close Button */}
                <Button
                  variant="ghost"
                  size="icon"
                  className="absolute top-4 right-4 text-white hover:bg-white/20"
                  onClick={closeLightbox}
                >
                  <X className="h-6 w-6" />
                </Button>
              </div>

              {/* Info Panel */}
              <div className="w-80 bg-card border-l border-border p-4 overflow-y-auto">
                <h3 className="font-medium mb-4">图片信息</h3>
                
                <div className="space-y-4">
                  <div>
                    <p className="text-sm text-muted-foreground mb-1">文件名</p>
                    <p className="text-sm font-medium">{selectedImage.filename}</p>
                  </div>

                  {selectedImage.model && (
                    <div>
                      <p className="text-sm text-muted-foreground mb-1">模型</p>
                      <Badge variant="secondary">{selectedImage.model}</Badge>
                    </div>
                  )}

                  {selectedImage.positive && (
                    <div>
                      <div className="flex items-center justify-between mb-1">
                        <p className="text-sm text-muted-foreground">正向提示词</p>
                        <Button 
                          variant="ghost" 
                          size="icon" 
                          className="h-6 w-6"
                          onClick={() => copyPrompt(selectedImage.positive!)}
                        >
                          <Copy className="h-3 w-3" />
                        </Button>
                      </div>
                      <p className="text-sm bg-muted/50 p-2 rounded max-h-32 overflow-y-auto">
                        {selectedImage.positive}
                      </p>
                    </div>
                  )}

                  {selectedImage.negative && (
                    <div>
                      <div className="flex items-center justify-between mb-1">
                        <p className="text-sm text-muted-foreground">负向提示词</p>
                        <Button 
                          variant="ghost" 
                          size="icon" 
                          className="h-6 w-6"
                          onClick={() => copyPrompt(selectedImage.negative!)}
                        >
                          <Copy className="h-3 w-3" />
                        </Button>
                      </div>
                      <p className="text-sm bg-muted/50 p-2 rounded max-h-32 overflow-y-auto">
                        {selectedImage.negative}
                      </p>
                    </div>
                  )}

                  {/* 生成参数 */}
                  <div className="grid grid-cols-2 gap-2 text-sm">
                    {selectedImage.seed && (
                      <div>
                        <p className="text-muted-foreground">Seed</p>
                        <p className="font-medium">{selectedImage.seed}</p>
                      </div>
                    )}
                    {selectedImage.steps && (
                      <div>
                        <p className="text-muted-foreground">Steps</p>
                        <p className="font-medium">{selectedImage.steps}</p>
                      </div>
                    )}
                    {selectedImage.cfg && (
                      <div>
                        <p className="text-muted-foreground">CFG</p>
                        <p className="font-medium">{selectedImage.cfg}</p>
                      </div>
                    )}
                    {selectedImage.sampler && (
                      <div>
                        <p className="text-muted-foreground">Sampler</p>
                        <p className="font-medium">{selectedImage.sampler}</p>
                      </div>
                    )}
                  </div>
                </div>

                {/* Actions */}
                <div className="mt-6 space-y-2">
                  <Button className="w-full" onClick={() => downloadImage(selectedImage)}>
                    <Download className="mr-2 h-4 w-4" />
                    下载原图
                  </Button>
                  <div className="grid grid-cols-3 gap-2">
                    <Button variant="outline" size="sm">
                      <Heart className="h-4 w-4" />
                    </Button>
                    <Button variant="outline" size="sm">
                      <Share2 className="h-4 w-4" />
                    </Button>
                    <Button variant="outline" size="sm">
                      <ExternalLink className="h-4 w-4" />
                    </Button>
                  </div>
                </div>
              </div>
            </div>
          )}
        </DialogContent>
      </Dialog>
    </div>
  )
}
