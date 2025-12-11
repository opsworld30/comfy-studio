import { useState, useRef, useEffect } from 'react'
import { useQuery } from '@tanstack/react-query'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Card, CardContent } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Skeleton } from '@/components/ui/skeleton'
import { 
  CheckCircle, 
  XCircle, 
  Clock, 
  Loader2,
  Pause,
  Image as ImageIcon,
  ImageOff
} from 'lucide-react'
import type { SmartCreateTask } from '@/lib/api'
import { comfyuiApi, smartCreateApi } from '@/lib/api'

interface TaskDetailDialogProps {
  open: boolean
  onClose: () => void
  task: SmartCreateTask | null
}

const TEMPLATE_NAMES: Record<string, string> = {
  novel_storyboard: '小说分镜画面',
  character_multiview: '人物多视角设定',
  video_storyboard: '视频分镜脚本',
  scene_multiview: '场景多角度生成',
  fashion_design: '服装设计展示',
  comic_series: '连续漫画生成',
}

const STYLE_NAMES: Record<string, string> = {
  realistic: '科幻写实',
  anime: '动漫风格',
  cyberpunk: '赛博朋克',
  fantasy: '奇幻史诗',
  watercolor: '水墨风格',
}

const STATUS_CONFIG: Record<string, { label: string; color: string; icon: React.ReactNode }> = {
  pending: { label: '等待中', color: 'bg-gray-500', icon: <Clock className="h-4 w-4" /> },
  analyzing: { label: 'AI分析中', color: 'bg-blue-500', icon: <Loader2 className="h-4 w-4 animate-spin" /> },
  generating: { label: '生成中', color: 'bg-yellow-500', icon: <Loader2 className="h-4 w-4 animate-spin" /> },
  paused: { label: '已暂停', color: 'bg-orange-500', icon: <Pause className="h-4 w-4" /> },
  completed: { label: '已完成', color: 'bg-green-500', icon: <CheckCircle className="h-4 w-4" /> },
  failed: { label: '失败', color: 'bg-red-500', icon: <XCircle className="h-4 w-4" /> },
}

// 图片组件，带懒加载、缩略图和错误处理
function LazyImage({ 
  thumbnailSrc, 
  alt, 
  onClick 
}: { 
  thumbnailSrc: string; 
  alt: string;
  onClick?: () => void;
}) {
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(false)
  const [isVisible, setIsVisible] = useState(false)
  const imgRef = useRef<HTMLDivElement>(null)

  // 使用 Intersection Observer 实现懒加载
  useEffect(() => {
    if (!imgRef.current) return

    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            setIsVisible(true)
            observer.disconnect()
          }
        })
      },
      { rootMargin: '50px' } // 提前 50px 开始加载
    )

    observer.observe(imgRef.current)

    return () => observer.disconnect()
  }, [])

  return (
    <div 
      ref={imgRef}
      className="aspect-square bg-muted rounded overflow-hidden relative cursor-pointer hover:ring-2 hover:ring-primary transition-all"
      onClick={onClick}
    >
      {!isVisible ? (
        <Skeleton className="absolute inset-0" />
      ) : (
        <>
          {loading && !error && (
            <Skeleton className="absolute inset-0" />
          )}
          {error ? (
            <div className="w-full h-full flex flex-col items-center justify-center text-muted-foreground">
              <ImageOff className="h-8 w-8 mb-2" />
              <span className="text-xs">加载失败</span>
            </div>
          ) : (
            <img
              src={thumbnailSrc}
              alt={alt}
              className={`w-full h-full object-cover transition-opacity duration-200 ${loading ? 'opacity-0' : 'opacity-100'}`}
              loading="lazy"
              onLoad={() => setLoading(false)}
              onError={() => {
                setLoading(false)
                setError(true)
              }}
            />
          )}
        </>
      )}
    </div>
  )
}

// 图片预览对话框
function ImagePreviewDialog({ 
  open, 
  onClose, 
  src, 
  alt 
}: { 
  open: boolean; 
  onClose: () => void; 
  src: string; 
  alt: string;
}) {
  return (
    <Dialog open={open} onOpenChange={onClose}>
      <DialogContent className="max-w-6xl max-h-[90vh] p-2">
        <div className="relative w-full h-full flex items-center justify-center">
          <img
            src={src}
            alt={alt}
            className="max-w-full max-h-[85vh] object-contain"
          />
        </div>
      </DialogContent>
    </Dialog>
  )
}

export function TaskDetailDialog({ open, onClose, task }: TaskDetailDialogProps) {
  const [previewImage, setPreviewImage] = useState<{ src: string; alt: string } | null>(null)
  
  // 实时查询任务详情，当任务正在执行时每 1.5 秒刷新
  const { data: liveTask } = useQuery({
    queryKey: ['smart-create', 'task', task?.id],
    queryFn: async () => {
      if (!task?.id) return null
      const { data } = await smartCreateApi.get(task.id)
      return data
    },
    enabled: open && !!task?.id,
    refetchInterval: (query) => {
      const currentTask = query.state.data
      // 只有在任务正在执行时才快速轮询
      if (currentTask?.status === 'generating' || currentTask?.status === 'analyzing') {
        return 1500 // 1.5 秒刷新
      }
      return false // 完成或失败后停止轮询
    },
    staleTime: 1000,
  })
  
  // 使用实时数据或传入的任务数据
  const currentTask = liveTask || task
  
  if (!currentTask) return null

  const status = STATUS_CONFIG[currentTask.status] || STATUS_CONFIG.pending
  const templateName = TEMPLATE_NAMES[task.template_type] || task.template_type
  const styleName = STYLE_NAMES[task.style] || task.style

  return (
    <Dialog open={open} onOpenChange={onClose}>
      <DialogContent className="max-w-4xl max-h-[85vh] flex flex-col">
        <DialogHeader className="flex-shrink-0">
          <DialogTitle className="flex items-center gap-2">
            <span>任务详情</span>
            <Badge className={`${status.color} text-white`}>
              <span className="mr-1">{status.icon}</span>
              {status.label}
            </Badge>
          </DialogTitle>
        </DialogHeader>

        <div className="flex-1 overflow-y-auto min-h-0">
          <div className="space-y-4 py-2">
            {/* 基本信息 */}
            <Card className="bg-card/50">
              <CardContent className="p-4">
                <h4 className="font-medium mb-3">基本信息</h4>
                <div className="grid grid-cols-2 gap-2 text-sm">
                  <div className="text-muted-foreground">任务名称:</div>
                  <div>{task.name}</div>
                  <div className="text-muted-foreground">创作模板:</div>
                  <div>{templateName}</div>
                  <div className="text-muted-foreground">画面风格:</div>
                  <div>{styleName}</div>
                  <div className="text-muted-foreground">图片尺寸:</div>
                  <div>{task.image_size}</div>
                  <div className="text-muted-foreground">创建时间:</div>
                  <div>{new Date(task.created_at).toLocaleString()}</div>
                  {task.started_at && (
                    <>
                      <div className="text-muted-foreground">开始时间:</div>
                      <div>{new Date(task.started_at).toLocaleString()}</div>
                    </>
                  )}
                  {task.completed_at && (
                    <>
                      <div className="text-muted-foreground">完成时间:</div>
                      <div>{new Date(task.completed_at).toLocaleString()}</div>
                    </>
                  )}
                </div>
              </CardContent>
            </Card>

            {/* 执行进度 */}
            <Card className="bg-card/50">
              <CardContent className="p-4">
                <h4 className="font-medium mb-3">执行进度</h4>
                <div className="grid grid-cols-3 gap-4 text-center">
                  <div>
                    <div className="text-2xl font-bold text-primary">{task.total_count}</div>
                    <div className="text-xs text-muted-foreground">总任务数</div>
                  </div>
                  <div>
                    <div className="text-2xl font-bold text-green-500">{task.completed_count}</div>
                    <div className="text-xs text-muted-foreground">已完成</div>
                  </div>
                  <div>
                    <div className="text-2xl font-bold text-red-500">{task.failed_count}</div>
                    <div className="text-xs text-muted-foreground">失败</div>
                  </div>
                </div>
                {task.error_message && (
                  <div className="mt-3 p-2 bg-red-500/10 rounded text-sm text-red-400">
                    错误: {task.error_message}
                  </div>
                )}
              </CardContent>
            </Card>

            {/* 分镜列表 */}
            {task.analyzed_prompts && task.analyzed_prompts.length > 0 && (
              <Card className="bg-card/50">
                <CardContent className="p-4">
                  <h4 className="font-medium mb-3">分镜列表 ({task.analyzed_prompts.length})</h4>
                  <div className="space-y-2 max-h-[300px] overflow-y-auto pr-2">
                    {task.analyzed_prompts.map((prompt, index) => (
                      <details key={index} className="group">
                        <summary className="p-2 bg-muted/50 rounded text-sm cursor-pointer hover:bg-muted/70 list-none">
                          <div className="flex items-center justify-between">
                            <span className="font-medium">#{index + 1} {prompt.title}</span>
                            <span className="text-xs text-muted-foreground">点击展开</span>
                          </div>
                          <div className="text-muted-foreground text-xs mt-1">
                            {prompt.description}
                          </div>
                        </summary>
                        <div className="mt-1 p-2 bg-muted/30 rounded text-xs space-y-2">
                          <div>
                            <span className="text-green-500 font-medium">正向提示词:</span>
                            <p className="font-mono text-muted-foreground mt-1 whitespace-pre-wrap break-all">
                              {prompt.positive}
                            </p>
                          </div>
                          {prompt.negative && (
                            <div>
                              <span className="text-red-400 font-medium">负向提示词:</span>
                              <p className="font-mono text-muted-foreground mt-1 whitespace-pre-wrap break-all">
                                {prompt.negative}
                              </p>
                            </div>
                          )}
                        </div>
                      </details>
                    ))}
                  </div>
                </CardContent>
              </Card>
            )}

            {/* 生成结果 */}
            {task.result_images && task.result_images.length > 0 && (
              <Card className="bg-card/50">
                <CardContent className="p-4">
                  <h4 className="font-medium mb-3 flex items-center gap-2">
                    <ImageIcon className="h-4 w-4" />
                    生成结果 ({task.result_images.length} 张)
                  </h4>
                  <div className="text-xs text-muted-foreground mb-2">点击图片查看原图</div>
                  <div className="grid grid-cols-4 gap-2 max-h-[400px] overflow-y-auto pr-2">
                    {task.result_images.map((img, index) => {
                      // img 可能是字符串或对象
                      const imagePath = typeof img === 'string' ? img : (img as { path?: string }).path || ''
                      const fullImageUrl = comfyuiApi.getImageUrl(imagePath)
                      const thumbnailUrl = comfyuiApi.getThumbnailUrl(imagePath, '', 'output', 256)
                      
                      return (
                        <LazyImage
                          key={index}
                          thumbnailSrc={thumbnailUrl}
                          alt={`结果 ${index + 1}`}
                          onClick={() => setPreviewImage({ src: fullImageUrl, alt: `结果 ${index + 1}` })}
                        />
                      )
                    })}
                  </div>
                </CardContent>
              </Card>
            )}

            {/* 原始内容 */}
            <Card className="bg-card/50">
              <CardContent className="p-4">
                <h4 className="font-medium mb-3">原始输入内容</h4>
                <div className="bg-muted/50 p-3 rounded text-sm max-h-[150px] overflow-y-auto whitespace-pre-wrap">
                  {task.input_content}
                </div>
              </CardContent>
            </Card>
          </div>
        </div>
      </DialogContent>
      
      {/* 图片预览 */}
      {previewImage && (
        <ImagePreviewDialog
          open={!!previewImage}
          onClose={() => setPreviewImage(null)}
          src={previewImage.src}
          alt={previewImage.alt}
        />
      )}
    </Dialog>
  )
}
