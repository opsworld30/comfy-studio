import { Card, CardContent } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Progress } from '@/components/ui/progress'
import { formatDateTime } from '@/lib/utils'
import {
  Eye,
  Pause,
  Play,
  Trash2,
  RotateCcw,
  Loader2,
  CheckCircle,
  XCircle,
  Clock,
  StopCircle,
  RefreshCw
} from 'lucide-react'
import type { SmartCreateTask } from '@/lib/api'

interface TaskListProps {
  tasks: SmartCreateTask[]
  onView: (task: SmartCreateTask) => void
  onPause: (taskId: number) => void
  onResume: (taskId: number) => void
  onStop: (taskId: number) => void
  onDelete: (taskId: number) => void
  onRerun: (task: SmartCreateTask) => void
  onRetry?: (taskId: number) => void
}

const TEMPLATE_ICONS: Record<string, string> = {
  novel_storyboard: '📖',
  character_multiview: '🧍',
  video_storyboard: '🎬',
  scene_multiview: '🏠',
  fashion_design: '👗',
  comic_series: '📚',
}

const STATUS_CONFIG: Record<string, { label: string; color: string; icon: React.ReactNode }> = {
  pending: { label: '等待中', color: 'bg-gray-500', icon: <Clock className="h-4 w-4" /> },
  analyzing: { label: 'AI分析中', color: 'bg-blue-500', icon: <Loader2 className="h-4 w-4 animate-spin" /> },
  generating: { label: '生成中', color: 'bg-yellow-500', icon: <Loader2 className="h-4 w-4 animate-spin" /> },
  paused: { label: '已暂停', color: 'bg-orange-500', icon: <Pause className="h-4 w-4" /> },
  completed: { label: '已完成', color: 'bg-green-500', icon: <CheckCircle className="h-4 w-4" /> },
  failed: { label: '失败', color: 'bg-red-500', icon: <XCircle className="h-4 w-4" /> },
}

export function TaskList({ tasks, onView, onPause, onResume, onStop, onDelete, onRerun, onRetry }: TaskListProps) {
  if (tasks.length === 0) {
    return (
      <div className="text-center py-12 text-muted-foreground">
        <p>暂无创作任务</p>
        <p className="text-sm mt-1">点击上方模板开始创作</p>
      </div>
    )
  }

  return (
    <div className="space-y-3">
      {tasks.map((task) => {
        const status = STATUS_CONFIG[task.status] || STATUS_CONFIG.pending
        const progress = task.total_count > 0 
          ? Math.round((task.completed_count / task.total_count) * 100) 
          : 0
        const icon = TEMPLATE_ICONS[task.template_type] || '📄'

        return (
          <Card key={task.id} className="bg-card/50 border-border/50">
            <CardContent className="p-4">
              <div className="flex items-start justify-between gap-4">
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-2">
                    <span className="text-xl">{icon}</span>
                    <h3 className="font-medium truncate">{task.name}</h3>
                    <Badge className={`${status.color} text-white`}>
                      <span className="mr-1">{status.icon}</span>
                      {status.label}
                    </Badge>
                  </div>
                  
                  {task.status === 'generating' && (
                    <div className="mb-2">
                      <div className="flex justify-between text-xs text-muted-foreground mb-1">
                        <span>进度: {task.completed_count}/{task.total_count}</span>
                        <span>{progress}%</span>
                      </div>
                      <Progress value={progress} className="h-2" />
                    </div>
                  )}
                  
                  {task.status === 'completed' && (
                    <p className="text-sm text-muted-foreground">
                      已生成 {task.completed_count} 张图片
                      {task.failed_count > 0 && (
                        <span className="text-red-400 ml-1">
                          ({task.failed_count} 张失败)
                        </span>
                      )}
                    </p>
                  )}

                  {task.status === 'failed' && (
                    <p className="text-sm text-muted-foreground">
                      完成 {task.completed_count}/{task.total_count}
                      {task.failed_count > 0 && (
                        <span className="text-red-400 ml-1">
                          ({task.failed_count} 张失败)
                        </span>
                      )}
                    </p>
                  )}

                  {task.status === 'failed' && task.error_message && (
                    <p className="text-sm text-red-400 truncate">
                      错误: {task.error_message}
                    </p>
                  )}
                  
                  <p className="text-xs text-muted-foreground mt-1">
                    创建于 {formatDateTime(task.created_at)}
                  </p>
                </div>
                
                <div className="flex items-center gap-1">
                  <Button 
                    variant="ghost" 
                    size="icon"
                    onClick={() => onView(task)}
                    title="查看详情"
                  >
                    <Eye className="h-4 w-4" />
                  </Button>
                  
                  {task.status === 'generating' && (
                    <>
                      <Button 
                        variant="ghost" 
                        size="icon"
                        onClick={() => onPause(task.id)}
                        title="暂停"
                      >
                        <Pause className="h-4 w-4" />
                      </Button>
                      <Button 
                        variant="ghost" 
                        size="icon"
                        onClick={() => onStop(task.id)}
                        title="停止"
                        className="text-red-400 hover:text-red-500"
                      >
                        <StopCircle className="h-4 w-4" />
                      </Button>
                    </>
                  )}
                  
                  {task.status === 'paused' && (
                    <Button 
                      variant="ghost" 
                      size="icon"
                      onClick={() => onResume(task.id)}
                      title="继续"
                    >
                      <Play className="h-4 w-4" />
                    </Button>
                  )}
                  
                  {(task.status === 'completed' || task.status === 'failed') && (
                    <>
                      {/* 重试失败的分镜 */}
                      {task.failed_count > 0 && onRetry && (
                        <Button
                          variant="ghost"
                          size="icon"
                          onClick={() => onRetry(task.id)}
                          title="重试失败的分镜"
                          className="text-orange-400 hover:text-orange-500"
                        >
                          <RefreshCw className="h-4 w-4" />
                        </Button>
                      )}
                      {/* 重新执行全部 */}
                      <Button
                        variant="ghost"
                        size="icon"
                        onClick={() => onRerun(task)}
                        title="重新执行全部"
                      >
                        <RotateCcw className="h-4 w-4" />
                      </Button>
                    </>
                  )}
                  
                  {task.status !== 'generating' && (
                    <Button 
                      variant="ghost" 
                      size="icon"
                      onClick={() => onDelete(task.id)}
                      title="删除"
                      className="text-red-400 hover:text-red-500"
                    >
                      <Trash2 className="h-4 w-4" />
                    </Button>
                  )}
                </div>
              </div>
            </CardContent>
          </Card>
        )
      })}
    </div>
  )
}
