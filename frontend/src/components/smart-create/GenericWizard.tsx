import { useState, useEffect } from 'react'
import { useMutation, useQuery } from '@tanstack/react-query'
import { useCircuitBreaker } from '@/hooks/useCircuitBreaker'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Textarea } from '@/components/ui/textarea'
import { Label } from '@/components/ui/label'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { RadioGroup, RadioGroupItem } from '@/components/ui/radio-group'
import { Card, CardContent } from '@/components/ui/card'
import { Loader2, Sparkles, ChevronLeft, ChevronRight, Pencil, Trash2, Plus } from 'lucide-react'
import { smartCreateApi, workflowsApi, type AnalyzedPrompt, type SmartCreateTemplate } from '@/lib/api'
import { toast } from 'sonner'

interface GenericWizardProps {
  open: boolean
  onClose: () => void
  template: SmartCreateTemplate
  onSuccess: () => void
}

// 不同模板的配置
const TEMPLATE_CONFIG: Record<string, {
  inputLabel: string
  inputPlaceholder: string
  countLabel: string
  countOptions: { value: string; label: string }[]
}> = {
  novel_storyboard: {
    inputLabel: '小说内容',
    inputPlaceholder: '粘贴小说章节内容...',
    countLabel: '分镜数量',
    countOptions: [
      { value: '0', label: 'AI自动分析' },
      { value: '4', label: '4个分镜' },
      { value: '8', label: '8个分镜' },
      { value: '12', label: '12个分镜' },
    ],
  },
  character_multiview: {
    inputLabel: '人物描述',
    inputPlaceholder: '描述人物的外貌特征、服装、发型等...',
    countLabel: '视角数量',
    countOptions: [
      { value: '8', label: '8视角' },
      { value: '16', label: '16视角' },
    ],
  },
  video_storyboard: {
    inputLabel: '视频脚本',
    inputPlaceholder: '粘贴视频脚本或分镜描述...',
    countLabel: '分镜数量',
    countOptions: [
      { value: '0', label: 'AI自动分析' },
      { value: '6', label: '6个分镜' },
      { value: '12', label: '12个分镜' },
      { value: '24', label: '24个分镜' },
    ],
  },
  scene_multiview: {
    inputLabel: '场景描述',
    inputPlaceholder: '描述场景的环境、建筑、氛围等...',
    countLabel: '视角数量',
    countOptions: [
      { value: '4', label: '4个视角' },
      { value: '8', label: '8个视角' },
    ],
  },
  fashion_design: {
    inputLabel: '服装描述',
    inputPlaceholder: '描述服装的款式、颜色、材质等...',
    countLabel: '展示数量',
    countOptions: [
      { value: '4', label: '4个展示' },
      { value: '8', label: '8个展示' },
    ],
  },
  comic_series: {
    inputLabel: '剧情内容',
    inputPlaceholder: '描述漫画的剧情故事...',
    countLabel: '页数',
    countOptions: [
      { value: '0', label: 'AI自动分析' },
      { value: '4', label: '4页' },
      { value: '8', label: '8页' },
      { value: '12', label: '12页' },
    ],
  },
}

const STYLES = [
  { value: 'realistic', label: '写实风格' },
  { value: 'anime', label: '动漫风格' },
  { value: 'cyberpunk', label: '赛博朋克' },
  { value: 'fantasy', label: '奇幻史诗' },
  { value: 'watercolor', label: '水彩风格' },
  { value: 'comic', label: '漫画风格' },
]

const SIZE_OPTIONS = [
  { value: '1920x1080', label: '16:9 横版' },
  { value: '1024x1024', label: '1:1 方形' },
  { value: '768x1024', label: '3:4 竖版' },
  { value: '1080x1920', label: '9:16 竖版' },
]

export function GenericWizard({ open, onClose, template, onSuccess }: GenericWizardProps) {
  const config = TEMPLATE_CONFIG[template.id] || TEMPLATE_CONFIG.novel_storyboard
  
  const [step, setStep] = useState(1)
  const [taskName, setTaskName] = useState('')
  const [content, setContent] = useState('')
  const [style, setStyle] = useState('realistic')
  const [targetCount, setTargetCount] = useState(config.countOptions[0]?.value || '0')
  const [imageSize, setImageSize] = useState('1024x1024')
  const [prompts, setPrompts] = useState<AnalyzedPrompt[]>([])
  const [workflowId, setWorkflowId] = useState<number | undefined>()
  const [imagesPerPrompt, setImagesPerPrompt] = useState('1')
  const [editingPrompt, setEditingPrompt] = useState<number | null>(null)

  // 熔断器保护
  const { wrapQueryFn, shouldEnableQuery } = useCircuitBreaker()

  // 获取工作流列表（带熔断器保护）
  const { data: workflows } = useQuery({
    queryKey: ['workflows'],
    queryFn: wrapQueryFn(async () => {
      const { data } = await workflowsApi.list()
      return data
    }),
    staleTime: 2 * 60 * 1000,
    retry: 1,
    enabled: shouldEnableQuery(),
  })

  // 默认选中第一个工作流
  useEffect(() => {
    if (workflows && workflows.length > 0 && !workflowId) {
      setWorkflowId(workflows[0].id)
    }
  }, [workflows, workflowId])

  // AI 分析
  const analyzeMutation = useMutation({
    mutationFn: () => smartCreateApi.analyze({
      template_type: template.id,
      input_content: content,
      style,
      target_count: parseInt(targetCount),
    }),
    onSuccess: (response) => {
      setPrompts(response.data.prompts)
      setStep(2)
    },
    onError: (error: Error) => {
      toast.error('AI 分析失败: ' + error.message)
    },
  })

  // 创建任务
  const createMutation = useMutation({
    mutationFn: async () => {
      const { data: task } = await smartCreateApi.create({
        name: taskName || `${template.name} - ${new Date().toLocaleString()}`,
        template_type: template.id,
        input_content: content,
        style,
        target_count: parseInt(targetCount),
        image_size: imageSize,
        workflow_id: workflowId,
      })
      await smartCreateApi.updatePrompts(task.id, prompts)
      await smartCreateApi.execute(task.id, {
        workflow_id: workflowId,
        images_per_prompt: parseInt(imagesPerPrompt),
        save_to_gallery: true,
      })
      return task
    },
    onSuccess: () => {
      toast.success('创作任务已开始执行')
      onSuccess()
      handleClose()
    },
    onError: (error: Error) => {
      toast.error('创建任务失败: ' + error.message)
    },
  })

  const handleClose = () => {
    setStep(1)
    setTaskName('')
    setContent('')
    setStyle('realistic')
    setTargetCount(config.countOptions[0]?.value || '0')
    setPrompts([])
    onClose()
  }

  const handleAnalyze = () => {
    if (!content.trim()) {
      toast.error('请输入内容')
      return
    }
    analyzeMutation.mutate()
  }

  const handleUpdatePrompt = (index: number, field: keyof AnalyzedPrompt, value: string) => {
    setPrompts(prev => prev.map((p, i) => 
      i === index ? { ...p, [field]: value } : p
    ))
  }

  const handleDeletePrompt = (index: number) => {
    setPrompts(prev => prev.filter((_, i) => i !== index))
  }

  const handleAddPrompt = () => {
    setPrompts(prev => [...prev, {
      index: prev.length + 1,
      title: `分镜 ${prev.length + 1}`,
      description: '',
      positive: '',
      negative: '',
    }])
  }

  return (
    <Dialog open={open} onOpenChange={handleClose}>
      <DialogContent className="max-w-3xl max-h-[85vh] flex flex-col">
        <DialogHeader className="flex-shrink-0">
          <DialogTitle className="flex items-center gap-2">
            <span className="text-2xl">{template.icon}</span>
            {template.name}
          </DialogTitle>
        </DialogHeader>

        {/* 步骤指示器 */}
        <div className="flex items-center justify-center gap-1 py-2 flex-shrink-0">
          {[1, 2, 3].map((s) => (
            <div key={s} className="flex items-center">
              <div className={`w-6 h-6 rounded-full flex items-center justify-center text-xs ${
                step >= s ? 'bg-primary text-primary-foreground' : 'bg-muted text-muted-foreground'
              }`}>
                {step > s ? '✓' : s}
              </div>
              {s < 3 && <div className="w-6 h-px bg-border mx-1" />}
            </div>
          ))}
        </div>

        <div className="flex-1 overflow-y-auto min-h-0 px-1">
          {/* 步骤 1: 输入内容 */}
          {step === 1 && (
            <div className="space-y-3 py-1">
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <Label className="text-xs">任务名称（可选）</Label>
                  <Input
                    value={taskName}
                    onChange={(e) => setTaskName(e.target.value)}
                    placeholder="给任务起个名字..."
                    className="mt-1 h-8"
                  />
                </div>
                <div className="flex items-end">
                  <p className="text-xs text-muted-foreground">
                    字数: {content.length}
                  </p>
                </div>
              </div>

              <div>
                <Label className="text-xs">{config.inputLabel} *</Label>
                <Textarea
                  value={content}
                  onChange={(e) => setContent(e.target.value)}
                  placeholder={config.inputPlaceholder}
                  className="mt-1 min-h-[100px]"
                />
              </div>

              <div className="grid grid-cols-3 gap-3">
                <div>
                  <Label>画面风格</Label>
                  <Select value={style} onValueChange={setStyle}>
                    <SelectTrigger className="mt-1">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {STYLES.map((s) => (
                        <SelectItem key={s.value} value={s.value}>
                          {s.label}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>

                <div>
                  <Label>{config.countLabel}</Label>
                  <Select value={targetCount} onValueChange={setTargetCount}>
                    <SelectTrigger className="mt-1">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {config.countOptions.map((p) => (
                        <SelectItem key={p.value} value={p.value}>
                          {p.label}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>

                <div>
                  <Label>图片尺寸</Label>
                  <Select value={imageSize} onValueChange={setImageSize}>
                    <SelectTrigger className="mt-1">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {SIZE_OPTIONS.map((s) => (
                        <SelectItem key={s.value} value={s.value}>
                          {s.label}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
              </div>
            </div>
          )}

          {/* 步骤 2: AI 分析结果 */}
          {step === 2 && (
            <div className="space-y-3 py-2">
              <div className="flex items-center justify-between sticky top-0 bg-background z-10 pb-2">
                <p className="text-sm text-muted-foreground">
                  🤖 AI 已分析出 {prompts.length} 个画面
                </p>
                <div className="flex gap-2">
                  <Button variant="outline" size="sm" onClick={handleAddPrompt}>
                    <Plus className="h-4 w-4 mr-1" />
                    添加
                  </Button>
                  <Button variant="outline" size="sm" onClick={() => analyzeMutation.mutate()}>
                    <Sparkles className="h-4 w-4 mr-1" />
                    重新分析
                  </Button>
                </div>
              </div>

              <div className="space-y-2 max-h-[350px] overflow-y-auto pr-2 pb-4">
                {prompts.map((prompt, index) => (
                  <Card key={index} className="bg-card/50">
                    <CardContent className="p-3">
                      <div className="flex items-start justify-between gap-2">
                        <div className="flex-1">
                          {editingPrompt === index ? (
                            <Input
                              value={prompt.title}
                              onChange={(e) => handleUpdatePrompt(index, 'title', e.target.value)}
                              className="mb-2 h-8"
                            />
                          ) : (
                            <h4 className="font-medium text-sm">#{index + 1}: {prompt.title}</h4>
                          )}
                        </div>
                        <div className="flex gap-1">
                          <Button
                            variant="ghost"
                            size="icon"
                            className="h-7 w-7"
                            onClick={() => setEditingPrompt(editingPrompt === index ? null : index)}
                          >
                            <Pencil className="h-3 w-3" />
                          </Button>
                          <Button
                            variant="ghost"
                            size="icon"
                            className="h-7 w-7 text-red-400"
                            onClick={() => handleDeletePrompt(index)}
                          >
                            <Trash2 className="h-3 w-3" />
                          </Button>
                        </div>
                      </div>

                      {editingPrompt === index ? (
                        <div className="space-y-2 mt-2">
                          <Textarea
                            value={prompt.description}
                            onChange={(e) => handleUpdatePrompt(index, 'description', e.target.value)}
                            placeholder="场景描述"
                            rows={2}
                            className="text-sm"
                          />
                          <Textarea
                            value={prompt.positive}
                            onChange={(e) => handleUpdatePrompt(index, 'positive', e.target.value)}
                            placeholder="正向提示词"
                            rows={3}
                            className="text-sm font-mono"
                          />
                        </div>
                      ) : (
                        <p className="text-xs text-muted-foreground mt-1 line-clamp-2">
                          {prompt.description || prompt.positive.substring(0, 100) + '...'}
                        </p>
                      )}
                    </CardContent>
                  </Card>
                ))}
              </div>
            </div>
          )}

          {/* 步骤 3: 确认执行 */}
          {step === 3 && (
            <div className="space-y-4 py-2">
              <Card className="bg-card/50">
                <CardContent className="p-4">
                  <h4 className="font-medium mb-3">任务摘要</h4>
                  <div className="grid grid-cols-2 gap-2 text-sm">
                    <div className="text-muted-foreground">任务名称:</div>
                    <div>{taskName || `${template.name} - ${new Date().toLocaleString()}`}</div>
                    <div className="text-muted-foreground">画面数量:</div>
                    <div>{prompts.length} 个</div>
                    <div className="text-muted-foreground">画面风格:</div>
                    <div>{STYLES.find(s => s.value === style)?.label}</div>
                    <div className="text-muted-foreground">图片尺寸:</div>
                    <div>{imageSize}</div>
                  </div>
                </CardContent>
              </Card>

              <Card className="bg-card/50">
                <CardContent className="p-4">
                  <h4 className="font-medium mb-3">执行设置</h4>
                  <div className="space-y-3">
                    <div>
                      <Label>工作流 *</Label>
                      <Select 
                        value={workflowId?.toString() || ''} 
                        onValueChange={(v) => setWorkflowId(v ? parseInt(v) : undefined)}
                      >
                        <SelectTrigger className="mt-1">
                          <SelectValue placeholder="请选择工作流" />
                        </SelectTrigger>
                        <SelectContent>
                          {workflows?.map((w) => (
                            <SelectItem key={w.id} value={w.id.toString()}>
                              {w.name}
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                      {!workflowId && (
                        <p className="text-xs text-red-400 mt-1">请选择一个工作流</p>
                      )}
                    </div>

                    <div>
                      <Label>每个画面生成数量</Label>
                      <RadioGroup value={imagesPerPrompt} onValueChange={setImagesPerPrompt} className="mt-2 flex gap-4">
                        {['1', '2', '4'].map((n) => (
                          <div key={n} className="flex items-center space-x-2">
                            <RadioGroupItem value={n} id={`img${n}`} />
                            <Label htmlFor={`img${n}`} className="font-normal">{n}张</Label>
                          </div>
                        ))}
                      </RadioGroup>
                    </div>
                  </div>
                </CardContent>
              </Card>

              <div className="bg-muted/50 p-3 rounded text-sm">
                总计将生成: <strong>{prompts.length * parseInt(imagesPerPrompt)}</strong> 张图片
              </div>
            </div>
          )}
        </div>

        {/* 底部按钮 */}
        <div className="flex justify-between pt-3 border-t flex-shrink-0">
          <Button variant="outline" onClick={step === 1 ? handleClose : () => setStep(step - 1)}>
            {step === 1 ? '取消' : <><ChevronLeft className="h-4 w-4 mr-1" />上一步</>}
          </Button>

          {step === 1 && (
            <Button onClick={handleAnalyze} disabled={analyzeMutation.isPending}>
              {analyzeMutation.isPending ? (
                <><Loader2 className="h-4 w-4 mr-2 animate-spin" />AI 分析中...</>
              ) : (
                <>下一步: AI分析<ChevronRight className="h-4 w-4 ml-1" /></>
              )}
            </Button>
          )}

          {step === 2 && (
            <Button onClick={() => setStep(3)} disabled={prompts.length === 0}>
              下一步: 确认执行<ChevronRight className="h-4 w-4 ml-1" />
            </Button>
          )}

          {step === 3 && (
            <Button onClick={() => createMutation.mutate()} disabled={createMutation.isPending || !workflowId}>
              {createMutation.isPending ? (
                <><Loader2 className="h-4 w-4 mr-2 animate-spin" />创建中...</>
              ) : '🚀 开始执行'}
            </Button>
          )}
        </div>
      </DialogContent>
    </Dialog>
  )
}
