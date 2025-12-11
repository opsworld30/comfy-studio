import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useCircuitBreaker } from '@/hooks/useCircuitBreaker'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Sparkles, Plus, ChevronDown, ChevronUp } from 'lucide-react'
import { smartCreateApi, type SmartCreateTemplate, type SmartCreateTask } from '@/lib/api'
import { TemplateSelector } from './TemplateSelector'
import { TaskList } from './TaskList'
import { TaskDetailDialog } from './TaskDetailDialog'
import { GenericWizard } from './GenericWizard'
import { toast } from 'sonner'

export function SmartCreatePanel() {
  const queryClient = useQueryClient()
  const [showTemplates, setShowTemplates] = useState(true)
  const [selectedTemplate, setSelectedTemplate] = useState<SmartCreateTemplate | null>(null)
  const [wizardOpen, setWizardOpen] = useState(false)
  const [selectedTask, setSelectedTask] = useState<SmartCreateTask | null>(null)
  const [taskDetailOpen, setTaskDetailOpen] = useState(false)
  
  // 熔断器：控制轮询，防止后端离线时无限重试
  const { createRefetchInterval, shouldEnableQuery, wrapQueryFn } = useCircuitBreaker()

  // 获取模板列表（带熔断器保护）
  const { data: templatesData, isLoading: templatesLoading } = useQuery({
    queryKey: ['smart-create', 'templates'],
    queryFn: wrapQueryFn(async () => {
      const { data } = await smartCreateApi.getTemplates()
      return data.templates
    }),
    staleTime: 5 * 60 * 1000, // 5分钟内不重新请求
    retry: 1,
    enabled: shouldEnableQuery(),
  })

  // 获取任务列表（带熔断器保护）
  const { data: tasks = [], refetch: refetchTasks } = useQuery({
    queryKey: ['smart-create', 'tasks'],
    queryFn: wrapQueryFn(async () => {
      const { data } = await smartCreateApi.list({ limit: 20 })
      return data
    }),
    refetchInterval: createRefetchInterval(2000), // 缩短到 2 秒，加快任务状态更新
    staleTime: 1000, // 1秒内数据视为新鲜
    enabled: shouldEnableQuery(),
    retry: 1,
  })

  // 暂停任务
  const pauseMutation = useMutation({
    mutationFn: (taskId: number) => smartCreateApi.pause(taskId),
    onSuccess: () => {
      toast.success('任务已暂停')
      refetchTasks()
    },
    onError: (error: Error) => {
      toast.error('暂停失败: ' + error.message)
    },
  })

  // 恢复任务
  const resumeMutation = useMutation({
    mutationFn: (taskId: number) => smartCreateApi.resume(taskId),
    onSuccess: () => {
      toast.success('任务已恢复')
      refetchTasks()
    },
    onError: (error: Error) => {
      toast.error('恢复失败: ' + error.message)
    },
  })

  // 停止任务
  const stopMutation = useMutation({
    mutationFn: (taskId: number) => smartCreateApi.stop(taskId),
    onSuccess: () => {
      toast.success('任务已停止')
      refetchTasks()
    },
    onError: (error: Error) => {
      toast.error('停止失败: ' + error.message)
    },
  })

  // 删除任务
  const deleteMutation = useMutation({
    mutationFn: (taskId: number) => smartCreateApi.delete(taskId),
    onSuccess: () => {
      toast.success('任务已删除')
      refetchTasks()
    },
    onError: (error: Error) => {
      toast.error('删除失败: ' + error.message)
    },
  })

  const handleSelectTemplate = (template: SmartCreateTemplate) => {
    setSelectedTemplate(template)
    setWizardOpen(true)
  }

  const handleWizardClose = () => {
    setWizardOpen(false)
    setSelectedTemplate(null)
  }

  const handleWizardSuccess = () => {
    queryClient.invalidateQueries({ queryKey: ['smart-create', 'tasks'] })
  }

  const handleViewTask = (task: SmartCreateTask) => {
    setSelectedTask(task)
    setTaskDetailOpen(true)
  }

  // 重新执行任务
  const rerunMutation = useMutation({
    mutationFn: async (task: SmartCreateTask) => {
      // 直接使用已有的提示词重新执行
      await smartCreateApi.execute(task.id, {
        workflow_id: task.workflow_id || undefined,
        images_per_prompt: 1,
        save_to_gallery: true,
      })
      return task
    },
    onSuccess: () => {
      toast.success('任务已重新开始执行')
      refetchTasks()
    },
    onError: (error: Error) => {
      toast.error('重新执行失败: ' + error.message)
    },
  })

  // 重试失败的分镜
  const retryMutation = useMutation({
    mutationFn: (taskId: number) => smartCreateApi.retry(taskId),
    onSuccess: () => {
      toast.success('开始重试失败的分镜')
      refetchTasks()
    },
    onError: (error: Error) => {
      toast.error('重试失败: ' + error.message)
    },
  })

  const handleRerunTask = (task: SmartCreateTask) => {
    rerunMutation.mutate(task)
  }

  const handleRetryTask = (taskId: number) => {
    retryMutation.mutate(taskId)
  }

  // 渲染通用向导
  const renderWizard = () => {
    if (!selectedTemplate || !wizardOpen) return null

    return (
      <GenericWizard
        open={wizardOpen}
        onClose={handleWizardClose}
        template={selectedTemplate}
        onSuccess={handleWizardSuccess}
      />
    )
  }

  return (
    <div className="space-y-6">
      {/* 创作模板 */}
      <Card className="bg-card/50 border-border/50">
        <CardHeader className="pb-2">
          <div className="flex items-center justify-between">
            <CardTitle className="text-base flex items-center gap-2">
              <Sparkles className="h-4 w-4" />
              智能创作模板
            </CardTitle>
            <div className="flex items-center gap-2">
              <Button variant="outline" size="sm" onClick={() => setShowTemplates(!showTemplates)}>
                {showTemplates ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
              </Button>
              <Button size="sm" onClick={() => setShowTemplates(true)}>
                <Plus className="h-4 w-4 mr-1" />
                新建创作
              </Button>
            </div>
          </div>
        </CardHeader>
        {showTemplates && (
          <CardContent>
            {templatesData ? (
              <TemplateSelector 
                templates={templatesData} 
                onSelect={handleSelectTemplate}
              />
            ) : (
              <div className="text-center py-4 text-muted-foreground text-sm">
                加载模板中...
              </div>
            )}
          </CardContent>
        )}
      </Card>

      {/* 我的创作任务 */}
      <Card className="bg-card/50 border-border/50">
        <CardHeader className="pb-2">
          <CardTitle className="text-base">我的创作任务</CardTitle>
        </CardHeader>
        <CardContent>
          <TaskList
            tasks={tasks || []}
            onView={handleViewTask}
            onPause={(id) => pauseMutation.mutate(id)}
            onResume={(id) => resumeMutation.mutate(id)}
            onStop={(id) => stopMutation.mutate(id)}
            onDelete={(id) => deleteMutation.mutate(id)}
            onRerun={handleRerunTask}
            onRetry={handleRetryTask}
          />
        </CardContent>
      </Card>

      {/* 向导弹窗 */}
      {renderWizard()}

      {/* 任务详情弹窗 */}
      <TaskDetailDialog
        open={taskDetailOpen}
        onClose={() => setTaskDetailOpen(false)}
        task={selectedTask}
      />
    </div>
  )
}
