import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import { Switch } from '@/components/ui/switch'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import {
  FileText,
  Plus,
  Edit,
  Trash2,
  CheckCircle,
  RotateCcw,
  Loader2,
  Copy,
  Check,
} from 'lucide-react'
import { aiTemplatesApi, type AIPromptTemplate } from '@/lib/api'
import { toast } from 'sonner'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Badge } from '@/components/ui/badge'

export function AITemplateManager() {
  const queryClient = useQueryClient()
  const [selectedType, setSelectedType] = useState<string>('novel_storyboard')
  const [editingTemplate, setEditingTemplate] = useState<AIPromptTemplate | null>(null)
  const [isCreateDialogOpen, setIsCreateDialogOpen] = useState(false)
  const [deleteConfirmId, setDeleteConfirmId] = useState<number | null>(null)
  
  // 表单状态
  const [formData, setFormData] = useState({
    name: '',
    version: '1.0',
    prompt_template: '',
    description: '',
    is_default: false,
  })

  // 获取模板类型列表
  const { data: typesData } = useQuery({
    queryKey: ['ai-templates', 'types'],
    queryFn: async () => {
      const { data } = await aiTemplatesApi.getTypes()
      return data.types
    },
  })

  // 获取当前类型的模板列表
  const { data: templatesData, isLoading } = useQuery({
    queryKey: ['ai-templates', 'list', selectedType],
    queryFn: async () => {
      const { data } = await aiTemplatesApi.list(selectedType)
      return data.templates
    },
  })

  // 获取系统默认模板
  const { data: systemTemplate } = useQuery({
    queryKey: ['ai-templates', 'system', selectedType],
    queryFn: async () => {
      const { data } = await aiTemplatesApi.getSystem(selectedType)
      return data
    },
  })

  // 创建模板
  const createMutation = useMutation({
    mutationFn: (data: Parameters<typeof aiTemplatesApi.create>[0]) => 
      aiTemplatesApi.create(data),
    onSuccess: () => {
      toast.success('模板创建成功')
      queryClient.invalidateQueries({ queryKey: ['ai-templates'] })
      setIsCreateDialogOpen(false)
      resetForm()
    },
    onError: (error: Error) => {
      toast.error('创建失败: ' + error.message)
    },
  })

  // 更新模板
  const updateMutation = useMutation({
    mutationFn: ({ id, data }: { id: number; data: Parameters<typeof aiTemplatesApi.update>[1] }) =>
      aiTemplatesApi.update(id, data),
    onSuccess: () => {
      toast.success('模板更新成功')
      queryClient.invalidateQueries({ queryKey: ['ai-templates'] })
      setEditingTemplate(null)
      resetForm()
    },
    onError: (error: Error) => {
      toast.error('更新失败: ' + error.message)
    },
  })

  // 删除模板
  const deleteMutation = useMutation({
    mutationFn: (id: number) => aiTemplatesApi.delete(id),
    onSuccess: () => {
      toast.success('模板已删除')
      queryClient.invalidateQueries({ queryKey: ['ai-templates'] })
      setDeleteConfirmId(null)
    },
    onError: (error: Error) => {
      toast.error('删除失败: ' + error.message)
    },
  })

  // 设为默认
  const setDefaultMutation = useMutation({
    mutationFn: (id: number) => aiTemplatesApi.setDefault(id),
    onSuccess: () => {
      toast.success('已设为默认模板')
      queryClient.invalidateQueries({ queryKey: ['ai-templates'] })
    },
    onError: (error: Error) => {
      toast.error('设置失败: ' + error.message)
    },
  })

  // 重置为系统默认
  const resetMutation = useMutation({
    mutationFn: (templateType: string) => aiTemplatesApi.reset(templateType),
    onSuccess: () => {
      toast.success('已重置为系统默认模板')
      queryClient.invalidateQueries({ queryKey: ['ai-templates'] })
    },
    onError: (error: Error) => {
      toast.error('重置失败: ' + error.message)
    },
  })

  const resetForm = () => {
    setFormData({
      name: '',
      version: '1.0',
      prompt_template: '',
      description: '',
      is_default: false,
    })
  }

  const handleCreate = () => {
    if (!formData.name || !formData.prompt_template) {
      toast.error('请填写模板名称和内容')
      return
    }
    createMutation.mutate({
      template_type: selectedType,
      ...formData,
    })
  }

  const handleUpdate = () => {
    if (!editingTemplate) return
    updateMutation.mutate({
      id: editingTemplate.id,
      data: formData,
    })
  }

  const handleEdit = (template: AIPromptTemplate) => {
    setEditingTemplate(template)
    setFormData({
      name: template.name,
      version: template.version,
      prompt_template: template.prompt_template,
      description: template.description,
      is_default: template.is_default,
    })
  }

  const handleCopyFromSystem = () => {
    if (systemTemplate) {
      setFormData({
        ...formData,
        prompt_template: systemTemplate.prompt_template,
      })
      toast.success('已复制系统模板内容')
    }
  }

  const getTypeName = (typeId: string) => {
    return typesData?.find(t => t.id === typeId)?.name || typeId
  }

  return (
    <Card className="bg-card/50 border-border/50">
      <CardHeader>
        <CardTitle className="text-base flex items-center gap-2">
          <FileText className="h-4 w-4" />
          AI 提示词模板
        </CardTitle>
        <CardDescription>
          自定义智能创作使用的 AI 提示词模板，支持多版本管理
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        {/* 模板类型选择 */}
        <div className="flex items-center gap-4">
          <div className="flex-1">
            <Label>模板类型</Label>
            <Select value={selectedType} onValueChange={setSelectedType}>
              <SelectTrigger className="mt-1">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {typesData?.map((type) => (
                  <SelectItem key={type.id} value={type.id}>
                    {type.icon} {type.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="flex gap-2 pt-6">
            <Button
              variant="outline"
              size="sm"
              onClick={() => resetMutation.mutate(selectedType)}
              disabled={resetMutation.isPending}
            >
              <RotateCcw className="h-4 w-4 mr-1" />
              重置为系统默认
            </Button>
            <Button
              size="sm"
              onClick={() => {
                resetForm()
                setIsCreateDialogOpen(true)
              }}
            >
              <Plus className="h-4 w-4 mr-1" />
              新建模板
            </Button>
          </div>
        </div>

        {/* 模板列表 */}
        <div className="space-y-2">
          {isLoading ? (
            <div className="flex items-center justify-center py-8">
              <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
            </div>
          ) : templatesData && templatesData.length > 0 ? (
            templatesData.map((template) => (
              <div
                key={template.id}
                className="flex items-center justify-between p-3 rounded-lg bg-muted/30 hover:bg-muted/50 transition-colors"
              >
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="font-medium truncate">{template.name}</span>
                    <Badge variant="outline" className="text-xs">
                      v{template.version}
                    </Badge>
                    {template.is_default && (
                      <Badge className="bg-primary/20 text-primary text-xs">
                        <CheckCircle className="h-3 w-3 mr-1" />
                        默认
                      </Badge>
                    )}
                    {template.is_system && (
                      <Badge variant="secondary" className="text-xs">
                        系统
                      </Badge>
                    )}
                  </div>
                  {template.description && (
                    <p className="text-xs text-muted-foreground mt-1 truncate">
                      {template.description}
                    </p>
                  )}
                </div>
                <div className="flex items-center gap-1 ml-2">
                  {!template.is_default && (
                    <Button
                      variant="ghost"
                      size="icon"
                      className="h-8 w-8"
                      onClick={() => setDefaultMutation.mutate(template.id)}
                      disabled={setDefaultMutation.isPending}
                      title="设为默认"
                    >
                      <CheckCircle className="h-4 w-4" />
                    </Button>
                  )}
                  <Button
                    variant="ghost"
                    size="icon"
                    className="h-8 w-8"
                    onClick={() => handleEdit(template)}
                    title="编辑"
                  >
                    <Edit className="h-4 w-4" />
                  </Button>
                  {!template.is_system && (
                    <Button
                      variant="ghost"
                      size="icon"
                      className="h-8 w-8 text-destructive hover:text-destructive"
                      onClick={() => setDeleteConfirmId(template.id)}
                      title="删除"
                    >
                      <Trash2 className="h-4 w-4" />
                    </Button>
                  )}
                </div>
              </div>
            ))
          ) : (
            <div className="text-center py-8 text-muted-foreground">
              <p>暂无自定义模板</p>
              <p className="text-sm mt-1">当前使用系统内置模板</p>
            </div>
          )}
        </div>

        {/* 系统模板预览 */}
        {systemTemplate && (
          <div className="mt-4 p-3 rounded-lg bg-muted/20 border border-dashed">
            <div className="flex items-center justify-between mb-2">
              <span className="text-sm font-medium">系统内置模板预览</span>
              <Button variant="ghost" size="sm" onClick={handleCopyFromSystem}>
                <Copy className="h-4 w-4 mr-1" />
                复制内容
              </Button>
            </div>
            <ScrollArea className="h-32">
              <pre className="text-xs text-muted-foreground whitespace-pre-wrap">
                {systemTemplate.prompt_template?.slice(0, 500)}
                {systemTemplate.prompt_template?.length > 500 && '...'}
              </pre>
            </ScrollArea>
          </div>
        )}
      </CardContent>

      {/* 创建/编辑对话框 */}
      <Dialog
        open={isCreateDialogOpen || !!editingTemplate}
        onOpenChange={(open) => {
          if (!open) {
            setIsCreateDialogOpen(false)
            setEditingTemplate(null)
            resetForm()
          }
        }}
      >
        <DialogContent className="max-w-3xl max-h-[90vh] overflow-hidden flex flex-col">
          <DialogHeader>
            <DialogTitle>
              {editingTemplate ? '编辑模板' : '新建模板'}
            </DialogTitle>
            <DialogDescription>
              {editingTemplate
                ? '修改 AI 提示词模板内容'
                : `为 ${getTypeName(selectedType)} 创建新的提示词模板`}
            </DialogDescription>
          </DialogHeader>

          <div className="flex-1 overflow-y-auto space-y-4 py-4">
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="name">模板名称</Label>
                <Input
                  id="name"
                  value={formData.name}
                  onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                  placeholder="例如：小说分镜 - 增强版"
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="version">版本号</Label>
                <Input
                  id="version"
                  value={formData.version}
                  onChange={(e) => setFormData({ ...formData, version: e.target.value })}
                  placeholder="1.0"
                />
              </div>
            </div>

            <div className="space-y-2">
              <Label htmlFor="description">模板说明</Label>
              <Input
                id="description"
                value={formData.description}
                onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                placeholder="简要描述模板的特点和适用场景"
              />
            </div>

            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <Label htmlFor="prompt_template">提示词模板内容</Label>
                <Button variant="ghost" size="sm" onClick={handleCopyFromSystem}>
                  <Copy className="h-4 w-4 mr-1" />
                  从系统模板复制
                </Button>
              </div>
              <Textarea
                id="prompt_template"
                value={formData.prompt_template}
                onChange={(e) => setFormData({ ...formData, prompt_template: e.target.value })}
                placeholder="输入 AI 提示词模板内容，支持 {content}、{style}、{target_count} 等变量"
                className="min-h-[300px] font-mono text-sm"
              />
              <p className="text-xs text-muted-foreground">
                可用变量：{'{content}'} - 用户输入内容，{'{style}'} - 画面风格，{'{target_count}'} - 目标数量
              </p>
            </div>

            <div className="flex items-center justify-between p-3 rounded-lg bg-muted/30">
              <div>
                <Label>设为默认模板</Label>
                <p className="text-xs text-muted-foreground">
                  智能创作将优先使用此模板
                </p>
              </div>
              <Switch
                checked={formData.is_default}
                onCheckedChange={(checked) => setFormData({ ...formData, is_default: checked })}
              />
            </div>
          </div>

          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => {
                setIsCreateDialogOpen(false)
                setEditingTemplate(null)
                resetForm()
              }}
            >
              取消
            </Button>
            <Button
              onClick={editingTemplate ? handleUpdate : handleCreate}
              disabled={createMutation.isPending || updateMutation.isPending}
            >
              {(createMutation.isPending || updateMutation.isPending) ? (
                <Loader2 className="h-4 w-4 mr-2 animate-spin" />
              ) : (
                <Check className="h-4 w-4 mr-2" />
              )}
              {editingTemplate ? '保存修改' : '创建模板'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* 删除确认对话框 */}
      <Dialog open={!!deleteConfirmId} onOpenChange={() => setDeleteConfirmId(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>确认删除</DialogTitle>
            <DialogDescription>
              确定要删除这个模板吗？此操作无法撤销。
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDeleteConfirmId(null)}>
              取消
            </Button>
            <Button
              variant="destructive"
              onClick={() => {
                if (deleteConfirmId) {
                  deleteMutation.mutate(deleteConfirmId)
                }
              }}
            >
              删除
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </Card>
  )
}
