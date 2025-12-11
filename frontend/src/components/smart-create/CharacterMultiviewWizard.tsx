import { useState } from 'react'
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
import { ScrollArea } from '@/components/ui/scroll-area'
import { Loader2, Sparkles, ChevronLeft, ChevronRight, Pencil } from 'lucide-react'
import { smartCreateApi, workflowsApi, type AnalyzedPrompt, type SmartCreateTemplate } from '@/lib/api'
import { toast } from 'sonner'

interface CharacterMultiviewWizardProps {
  open: boolean
  onClose: () => void
  template: SmartCreateTemplate
  onSuccess: () => void
}

const STYLES = [
  { value: 'realistic', label: '科幻写实' },
  { value: 'anime', label: '动漫风格' },
  { value: 'fantasy', label: '奇幻角色' },
  { value: 'modern', label: '现代写实' },
  { value: 'chibi', label: 'Q版卡通' },
]

const VIEW_OPTIONS = [
  { value: '8', label: '8视角 (前/后/左/右/左前/右前/左后/右后)' },
  { value: '16', label: '16视角 (每22.5度一个视角)' },
]

const SIZE_OPTIONS = [
  { value: '512x768', label: '512×768 (快速)' },
  { value: '768x1024', label: '768×1024 (标准)' },
  { value: '1024x1536', label: '1024×1536 (高清)' },
]

const BACKGROUND_OPTIONS = [
  { value: 'solid', label: '纯色背景 (便于抠图)' },
  { value: 'simple', label: '简单场景背景' },
  { value: 'transparent', label: '透明背景' },
]

export function CharacterMultiviewWizard({ open, onClose, template, onSuccess }: CharacterMultiviewWizardProps) {
  const [step, setStep] = useState(1)
  const [taskName, setTaskName] = useState('')
  const [content, setContent] = useState('')
  const [style, setStyle] = useState('realistic')
  const [viewCount, setViewCount] = useState('8')
  const [imageSize, setImageSize] = useState('768x1024')
  const [background, setBackground] = useState('solid')
  const [prompts, setPrompts] = useState<AnalyzedPrompt[]>([])
  const [basePrompt, setBasePrompt] = useState('')
  const [workflowId, setWorkflowId] = useState<number | undefined>()
  const [useFixedSeed, setUseFixedSeed] = useState(true)
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

  // AI 分析
  const analyzeMutation = useMutation({
    mutationFn: () => smartCreateApi.analyze({
      template_type: template.id,
      input_content: content,
      style,
      target_count: parseInt(viewCount),
    }),
    onSuccess: (response) => {
      const analyzedPrompts = response.data.prompts
      setPrompts(analyzedPrompts)
      // 提取基础提示词（第一个的正向提示词去掉视角描述）
      if (analyzedPrompts.length > 0) {
        setBasePrompt(analyzedPrompts[0].positive.split(',').slice(0, -2).join(','))
      }
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
        target_count: parseInt(viewCount),
        image_size: imageSize,
        workflow_id: workflowId,
        config: { background, use_fixed_seed: useFixedSeed },
      })
      
      await smartCreateApi.updatePrompts(task.id, prompts)
      
      await smartCreateApi.execute(task.id, {
        workflow_id: workflowId,
        images_per_prompt: 1,
        use_fixed_seed: useFixedSeed,
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
    setViewCount('8')
    setPrompts([])
    setBasePrompt('')
    onClose()
  }

  const handleAnalyze = () => {
    if (!content.trim()) {
      toast.error('请输入人物描述')
      return
    }
    analyzeMutation.mutate()
  }

  const handleUpdatePrompt = (index: number, field: keyof AnalyzedPrompt, value: string) => {
    setPrompts(prev => prev.map((p, i) => 
      i === index ? { ...p, [field]: value } : p
    ))
  }

  const VIEW_LABELS_8 = ['正面', '右前45°', '右侧', '右后45°', '背面', '左后45°', '左侧', '左前45°']
  const VIEW_ARROWS = ['↑', '↗', '→', '↘', '↓', '↙', '←', '↖']

  return (
    <Dialog open={open} onOpenChange={handleClose}>
      <DialogContent className="max-w-4xl max-h-[90vh] overflow-hidden flex flex-col">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <span className="text-2xl">{template.icon}</span>
            {template.name}
          </DialogTitle>
        </DialogHeader>

        {/* 步骤指示器 */}
        <div className="flex items-center justify-center gap-2 py-4">
          <div className={`flex items-center gap-2 ${step >= 1 ? 'text-primary' : 'text-muted-foreground'}`}>
            <div className={`w-8 h-8 rounded-full flex items-center justify-center ${step >= 1 ? 'bg-primary text-primary-foreground' : 'bg-muted'}`}>
              {step > 1 ? '✓' : '1'}
            </div>
            <span className="text-sm">人物描述</span>
          </div>
          <div className="w-12 h-px bg-border" />
          <div className={`flex items-center gap-2 ${step >= 2 ? 'text-primary' : 'text-muted-foreground'}`}>
            <div className={`w-8 h-8 rounded-full flex items-center justify-center ${step >= 2 ? 'bg-primary text-primary-foreground' : 'bg-muted'}`}>
              {step > 2 ? '✓' : '2'}
            </div>
            <span className="text-sm">AI生成</span>
          </div>
          <div className="w-12 h-px bg-border" />
          <div className={`flex items-center gap-2 ${step >= 3 ? 'text-primary' : 'text-muted-foreground'}`}>
            <div className={`w-8 h-8 rounded-full flex items-center justify-center ${step >= 3 ? 'bg-primary text-primary-foreground' : 'bg-muted'}`}>
              3
            </div>
            <span className="text-sm">确认执行</span>
          </div>
        </div>

        <ScrollArea className="flex-1 px-1 min-h-0">
          {/* 步骤 1: 输入人物描述 */}
          {step === 1 && (
            <div className="space-y-6 py-4">
              <div className="space-y-2">
                <Label>任务名称</Label>
                <Input
                  value={taskName}
                  onChange={(e) => setTaskName(e.target.value)}
                  placeholder="例如：女主角 - 林晓 角色设定"
                />
              </div>

              <div className="space-y-2">
                <Label>人物描述 *</Label>
                <Textarea
                  value={content}
                  onChange={(e) => setContent(e.target.value)}
                  placeholder="描述人物的外貌特征、服装、配饰等..."
                  className="min-h-[120px]"
                />
              </div>

              <div className="grid grid-cols-2 gap-6">
                <div className="space-y-2">
                  <Label>人物风格</Label>
                  <Select value={style} onValueChange={setStyle}>
                    <SelectTrigger>
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

                <div className="space-y-2">
                  <Label>视角模式</Label>
                  <Select value={viewCount} onValueChange={setViewCount}>
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {VIEW_OPTIONS.map((v) => (
                        <SelectItem key={v.value} value={v.value}>
                          {v.label}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
              </div>

              <div className="space-y-2">
                <Label>背景设置</Label>
                <RadioGroup value={background} onValueChange={setBackground} className="flex flex-wrap gap-4">
                  {BACKGROUND_OPTIONS.map((b) => (
                    <div key={b.value} className="flex items-center gap-2">
                      <RadioGroupItem value={b.value} id={b.value} />
                      <Label htmlFor={b.value} className="font-normal cursor-pointer text-sm">
                        {b.label}
                      </Label>
                    </div>
                  ))}
                </RadioGroup>
              </div>
            </div>
          )}

          {/* 步骤 2: AI 生成提示词 */}
          {step === 2 && (
            <div className="space-y-4 py-2">
              <div className="flex items-center justify-between">
                <p className="text-sm text-muted-foreground">
                  🤖 AI 已生成 {prompts.length} 个视角的提示词
                </p>
                <Button variant="outline" size="sm" onClick={() => analyzeMutation.mutate()}>
                  <Sparkles className="h-4 w-4 mr-1" />
                  重新生成
                </Button>
              </div>

              {/* 基础提示词 */}
              <Card className="bg-card/50">
                <CardContent className="p-4">
                  <div className="flex items-center justify-between mb-2">
                    <Label>基础人物提示词 (所有视角共用)</Label>
                    <Button variant="ghost" size="sm" onClick={() => setEditingPrompt(-1)}>
                      <Pencil className="h-4 w-4" />
                    </Button>
                  </div>
                  {editingPrompt === -1 ? (
                    <Textarea
                      value={basePrompt}
                      onChange={(e) => setBasePrompt(e.target.value)}
                      className="font-mono text-sm"
                      rows={4}
                      onBlur={() => setEditingPrompt(null)}
                    />
                  ) : (
                    <div className="bg-muted/50 p-3 rounded text-sm font-mono text-muted-foreground">
                      {basePrompt}
                    </div>
                  )}
                </CardContent>
              </Card>

              {/* 视角预览 */}
              <Card className="bg-card/50">
                <CardContent className="p-4">
                  <Label className="mb-3 block">视角预览</Label>
                  <div className="grid grid-cols-4 gap-2">
                    {prompts.slice(0, 8).map((_, index) => (
                      <div 
                        key={index}
                        className={`p-3 rounded-lg border text-center cursor-pointer transition-colors ${
                          editingPrompt === index ? 'border-primary bg-primary/10' : 'border-border hover:border-primary/50'
                        }`}
                        onClick={() => setEditingPrompt(editingPrompt === index ? null : index)}
                      >
                        <div className="text-2xl mb-1">{VIEW_ARROWS[index]}</div>
                        <div className="text-xs">{VIEW_LABELS_8[index]}</div>
                      </div>
                    ))}
                  </div>
                </CardContent>
              </Card>

              {/* 编辑选中的视角 */}
              {editingPrompt !== null && editingPrompt >= 0 && prompts[editingPrompt] && (
                <Card className="bg-card/50 border-primary">
                  <CardContent className="p-4">
                    <h4 className="font-medium mb-3">
                      编辑视角 #{editingPrompt + 1}: {prompts[editingPrompt].title}
                    </h4>
                    <div className="space-y-3">
                      <div>
                        <Label className="text-xs">视角附加提示词</Label>
                        <Input
                          value={prompts[editingPrompt].positive.split(',').slice(-2).join(',')}
                          onChange={(e) => {
                            const baseParts = prompts[editingPrompt].positive.split(',').slice(0, -2)
                            handleUpdatePrompt(editingPrompt, 'positive', [...baseParts, e.target.value].join(','))
                          }}
                          className="mt-1 font-mono text-sm"
                        />
                      </div>
                      <div>
                        <Label className="text-xs">负向提示词</Label>
                        <Textarea
                          value={prompts[editingPrompt].negative}
                          onChange={(e) => handleUpdatePrompt(editingPrompt, 'negative', e.target.value)}
                          className="mt-1 font-mono text-sm"
                          rows={2}
                        />
                      </div>
                    </div>
                  </CardContent>
                </Card>
              )}
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
                    <div className="text-muted-foreground">视角数量:</div>
                    <div>{prompts.length} 个视角</div>
                    <div className="text-muted-foreground">人物风格:</div>
                    <div>{STYLES.find(s => s.value === style)?.label}</div>
                    <div className="text-muted-foreground">背景设置:</div>
                    <div>{BACKGROUND_OPTIONS.find(b => b.value === background)?.label}</div>
                  </div>
                </CardContent>
              </Card>

              <Card className="bg-card/50">
                <CardContent className="p-4">
                  <h4 className="font-medium mb-3">执行设置</h4>
                  
                  <div className="space-y-4">
                    <div>
                      <Label>工作流选择</Label>
                      <Select 
                        value={workflowId?.toString() || ''} 
                        onValueChange={(v) => setWorkflowId(v ? parseInt(v) : undefined)}
                      >
                        <SelectTrigger className="mt-1">
                          <SelectValue placeholder="选择工作流（可选）" />
                        </SelectTrigger>
                        <SelectContent>
                          {workflows?.map((w) => (
                            <SelectItem key={w.id} value={w.id.toString()}>
                              {w.name}
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    </div>

                    <div>
                      <Label>图片尺寸</Label>
                      <RadioGroup value={imageSize} onValueChange={setImageSize} className="mt-2">
                        <div className="flex gap-4">
                          {SIZE_OPTIONS.map((s) => (
                            <div key={s.value} className="flex items-center space-x-2">
                              <RadioGroupItem value={s.value} id={`size-${s.value}`} />
                              <Label htmlFor={`size-${s.value}`} className="font-normal">
                                {s.label}
                              </Label>
                            </div>
                          ))}
                        </div>
                      </RadioGroup>
                    </div>

                    <div className="flex items-center space-x-2">
                      <input
                        type="checkbox"
                        id="fixedSeed"
                        checked={useFixedSeed}
                        onChange={(e) => setUseFixedSeed(e.target.checked)}
                        className="rounded"
                      />
                      <Label htmlFor="fixedSeed" className="font-normal cursor-pointer">
                        使用相同种子 (保持人物一致性)
                      </Label>
                    </div>
                  </div>
                </CardContent>
              </Card>

              <div className="bg-muted/50 p-3 rounded-lg text-sm">
                <p>执行顺序预览:</p>
                <p className="text-muted-foreground mt-1">
                  {VIEW_LABELS_8.slice(0, parseInt(viewCount)).join(' → ')}
                </p>
                <p className="text-muted-foreground">
                  总计: {prompts.length} 张图片
                </p>
              </div>
            </div>
          )}
        </ScrollArea>

        {/* 底部按钮 */}
        <div className="flex justify-between pt-4 border-t">
          <Button variant="outline" onClick={step === 1 ? handleClose : () => setStep(step - 1)}>
            {step === 1 ? '取消' : (
              <>
                <ChevronLeft className="h-4 w-4 mr-1" />
                上一步
              </>
            )}
          </Button>

          {step === 1 && (
            <Button onClick={handleAnalyze} disabled={analyzeMutation.isPending}>
              {analyzeMutation.isPending ? (
                <>
                  <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                  AI 生成中...
                </>
              ) : (
                <>
                  下一步: AI生成
                  <ChevronRight className="h-4 w-4 ml-1" />
                </>
              )}
            </Button>
          )}

          {step === 2 && (
            <Button onClick={() => setStep(3)} disabled={prompts.length === 0}>
              下一步: 确认执行
              <ChevronRight className="h-4 w-4 ml-1" />
            </Button>
          )}

          {step === 3 && (
            <Button onClick={() => createMutation.mutate()} disabled={createMutation.isPending}>
              {createMutation.isPending ? (
                <>
                  <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                  创建中...
                </>
              ) : (
                <>
                  🚀 开始执行
                </>
              )}
            </Button>
          )}
        </div>
      </DialogContent>
    </Dialog>
  )
}
