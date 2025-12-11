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
import { Loader2, Sparkles, ChevronLeft, ChevronRight, Pencil, Trash2, Plus } from 'lucide-react'
import { smartCreateApi, workflowsApi, type AnalyzedPrompt, type SmartCreateTemplate } from '@/lib/api'
import { toast } from 'sonner'

interface NovelStoryboardWizardProps {
  open: boolean
  onClose: () => void
  template: SmartCreateTemplate
  onSuccess: () => void
}

const STYLES = [
  { value: 'realistic', label: '科幻写实' },
  { value: 'anime', label: '动漫风格' },
  { value: 'cyberpunk', label: '赛博朋克' },
  { value: 'fantasy', label: '奇幻史诗' },
  { value: 'watercolor', label: '水墨风格' },
]

const PAGE_OPTIONS = [
  { value: '0', label: 'AI自动分析' },
  { value: '4', label: '4页 (精简版)' },
  { value: '8', label: '8页 (标准版)' },
  { value: '12', label: '12页 (详细版)' },
  { value: '16', label: '16页 (完整版)' },
]

const SIZE_OPTIONS = [
  { value: '1920x1080', label: '16:9 横版 (1920×1080)' },
  { value: '1024x768', label: '4:3 标准 (1024×768)' },
  { value: '1024x1024', label: '1:1 方形 (1024×1024)' },
  { value: '768x1024', label: '9:16 竖版 (768×1024)' },
]

export function NovelStoryboardWizard({ open, onClose, template, onSuccess }: NovelStoryboardWizardProps) {
  const [step, setStep] = useState(1)
  const [taskName, setTaskName] = useState('')
  const [content, setContent] = useState('')
  const [style, setStyle] = useState('realistic')
  const [targetCount, setTargetCount] = useState('0')
  const [imageSize, setImageSize] = useState('1024x768')
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
      // 先创建任务
      const { data: task } = await smartCreateApi.create({
        name: taskName || `${template.name} - ${new Date().toLocaleString()}`,
        template_type: template.id,
        input_content: content,
        style,
        target_count: parseInt(targetCount),
        image_size: imageSize,
        workflow_id: workflowId,
      })
      
      // 更新提示词
      await smartCreateApi.updatePrompts(task.id, prompts)
      
      // 执行任务
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
    setTargetCount('0')
    setPrompts([])
    onClose()
  }

  const handleAnalyze = () => {
    if (!content.trim()) {
      toast.error('请输入小说内容')
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
            <span className="text-sm">输入内容</span>
          </div>
          <div className="w-12 h-px bg-border" />
          <div className={`flex items-center gap-2 ${step >= 2 ? 'text-primary' : 'text-muted-foreground'}`}>
            <div className={`w-8 h-8 rounded-full flex items-center justify-center ${step >= 2 ? 'bg-primary text-primary-foreground' : 'bg-muted'}`}>
              {step > 2 ? '✓' : '2'}
            </div>
            <span className="text-sm">AI分析</span>
          </div>
          <div className="w-12 h-px bg-border" />
          <div className={`flex items-center gap-2 ${step >= 3 ? 'text-primary' : 'text-muted-foreground'}`}>
            <div className={`w-8 h-8 rounded-full flex items-center justify-center ${step >= 3 ? 'bg-primary text-primary-foreground' : 'bg-muted'}`}>
              3
            </div>
            <span className="text-sm">确认执行</span>
          </div>
        </div>

        <ScrollArea className="flex-1 px-1">
          {/* 步骤 1: 输入内容 */}
          {step === 1 && (
            <div className="space-y-4 py-2">
              <div>
                <Label>任务名称</Label>
                <Input
                  value={taskName}
                  onChange={(e) => setTaskName(e.target.value)}
                  placeholder="例如：《星际迷途》第三章分镜"
                  className="mt-1"
                />
              </div>

              <div>
                <Label>小说内容 *</Label>
                <Textarea
                  value={content}
                  onChange={(e) => setContent(e.target.value)}
                  placeholder="粘贴小说章节内容..."
                  className="mt-1 min-h-[200px]"
                />
                <p className="text-xs text-muted-foreground mt-1">
                  字数: {content.length} / 建议 500-5000 字
                </p>
              </div>

              <div className="grid grid-cols-2 gap-4">
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
                  <Label>预计生成页数</Label>
                  <Select value={targetCount} onValueChange={setTargetCount}>
                    <SelectTrigger className="mt-1">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {PAGE_OPTIONS.map((p) => (
                        <SelectItem key={p.value} value={p.value}>
                          {p.label}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
              </div>

              <div>
                <Label>图片尺寸</Label>
                <RadioGroup value={imageSize} onValueChange={setImageSize} className="mt-2">
                  <div className="grid grid-cols-2 gap-2">
                    {SIZE_OPTIONS.map((s) => (
                      <div key={s.value} className="flex items-center space-x-2">
                        <RadioGroupItem value={s.value} id={s.value} />
                        <Label htmlFor={s.value} className="text-sm font-normal cursor-pointer">
                          {s.label}
                        </Label>
                      </div>
                    ))}
                  </div>
                </RadioGroup>
              </div>

              <p className="text-sm text-muted-foreground bg-muted/50 p-3 rounded-lg">
                💡 提示: AI自动分析会根据小说内容智能判断分镜数量，也可手动指定页数
              </p>
            </div>
          )}

          {/* 步骤 2: AI 分析结果 */}
          {step === 2 && (
            <div className="space-y-4 py-2">
              <div className="flex items-center justify-between sticky top-0 bg-background z-10 pb-2">
                <p className="text-sm text-muted-foreground">
                  🤖 AI 已分析出 {prompts.length} 个分镜画面
                </p>
                <div className="flex gap-2">
                  <Button variant="outline" size="sm" onClick={handleAddPrompt}>
                    <Plus className="h-4 w-4 mr-1" />
                    添加分镜
                  </Button>
                  <Button variant="outline" size="sm" onClick={() => analyzeMutation.mutate()}>
                    <Sparkles className="h-4 w-4 mr-1" />
                    重新分析
                  </Button>
                </div>
              </div>

              <div className="space-y-3 max-h-[400px] overflow-y-auto pr-2 pb-4">
                {prompts.map((prompt, index) => (
                  <Card key={index} className="bg-card/50">
                    <CardContent className="p-4">
                      <div className="flex items-start justify-between gap-2 mb-2">
                        <div className="flex-1">
                          {editingPrompt === index ? (
                            <Input
                              value={prompt.title}
                              onChange={(e) => handleUpdatePrompt(index, 'title', e.target.value)}
                              className="mb-2"
                            />
                          ) : (
                            <h4 className="font-medium">分镜 #{index + 1}: {prompt.title}</h4>
                          )}
                        </div>
                        <div className="flex gap-1">
                          <Button
                            variant="ghost"
                            size="icon"
                            onClick={() => setEditingPrompt(editingPrompt === index ? null : index)}
                          >
                            <Pencil className="h-4 w-4" />
                          </Button>
                          <Button
                            variant="ghost"
                            size="icon"
                            onClick={() => handleDeletePrompt(index)}
                            className="text-red-400"
                          >
                            <Trash2 className="h-4 w-4" />
                          </Button>
                        </div>
                      </div>

                      <p className="text-sm text-muted-foreground mb-2">
                        {prompt.description}
                      </p>

                      {editingPrompt === index ? (
                        <div className="space-y-2">
                          <div>
                            <Label className="text-xs">场景描述</Label>
                            <Textarea
                              value={prompt.description}
                              onChange={(e) => handleUpdatePrompt(index, 'description', e.target.value)}
                              className="mt-1 text-sm"
                              rows={2}
                            />
                          </div>
                          <div>
                            <Label className="text-xs">正向提示词</Label>
                            <Textarea
                              value={prompt.positive}
                              onChange={(e) => handleUpdatePrompt(index, 'positive', e.target.value)}
                              className="mt-1 text-sm font-mono"
                              rows={3}
                            />
                          </div>
                          <div>
                            <Label className="text-xs">负向提示词</Label>
                            <Textarea
                              value={prompt.negative}
                              onChange={(e) => handleUpdatePrompt(index, 'negative', e.target.value)}
                              className="mt-1 text-sm font-mono"
                              rows={2}
                            />
                          </div>
                        </div>
                      ) : (
                        <div className="bg-muted/50 p-2 rounded text-xs font-mono text-muted-foreground max-h-20 overflow-hidden">
                          {prompt.positive.substring(0, 150)}...
                        </div>
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
                    <div className="text-muted-foreground">分镜数量:</div>
                    <div>{prompts.length} 个画面</div>
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
                      <Label>每张分镜生成数量</Label>
                      <RadioGroup value={imagesPerPrompt} onValueChange={setImagesPerPrompt} className="mt-2">
                        <div className="flex gap-4">
                          <div className="flex items-center space-x-2">
                            <RadioGroupItem value="1" id="img1" />
                            <Label htmlFor="img1" className="font-normal">1张</Label>
                          </div>
                          <div className="flex items-center space-x-2">
                            <RadioGroupItem value="2" id="img2" />
                            <Label htmlFor="img2" className="font-normal">2张</Label>
                          </div>
                          <div className="flex items-center space-x-2">
                            <RadioGroupItem value="4" id="img4" />
                            <Label htmlFor="img4" className="font-normal">4张</Label>
                          </div>
                        </div>
                      </RadioGroup>
                    </div>
                  </div>
                </CardContent>
              </Card>

              <div className="bg-muted/50 p-3 rounded-lg text-sm">
                <p>执行顺序预览:</p>
                <p className="text-muted-foreground mt-1">
                  {prompts.map((_, i) => `分镜#${i + 1}`).join(' → ')}
                </p>
                <p className="text-muted-foreground">
                  总计: {prompts.length * parseInt(imagesPerPrompt)} 张图片
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
                  AI 分析中...
                </>
              ) : (
                <>
                  下一步: AI分析
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
