import { useState } from 'react'
import { Card, CardContent } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from '@/components/ui/dialog'
import {
  Tabs,
  TabsList,
  TabsTrigger,
  TabsContent,
} from '@/components/ui/tabs'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import {
  Search,
  Star,
  Play,
  Plus,
  Zap,
  Sparkles,
  Palette,
  Camera,
  Wrench,
  Info,
  Loader2,
} from 'lucide-react'
import { workflowsApi } from '@/lib/api'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { WORKFLOW_TEMPLATES, getAllCategories, type WorkflowTemplate } from '@/data/workflowTemplates'

interface WorkflowTemplatesProps {
  onCreateFromTemplate?: (template: WorkflowTemplate, name: string) => void
}

export default function WorkflowTemplates({ onCreateFromTemplate }: WorkflowTemplatesProps) {
  const queryClient = useQueryClient()
  const [searchQuery, setSearchQuery] = useState('')
  const [selectedCategory, setSelectedCategory] = useState<string>('all')
  const [selectedTemplate, setSelectedTemplate] = useState<WorkflowTemplate | null>(null)
  const [showCreateDialog, setShowCreateDialog] = useState(false)
  const [workflowName, setWorkflowName] = useState('')

  // 过滤模板
  const filteredTemplates = WORKFLOW_TEMPLATES.filter(template => {
    const matchesSearch = template.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
                         template.description.toLowerCase().includes(searchQuery.toLowerCase()) ||
                         template.tags.some(tag => tag.toLowerCase().includes(searchQuery.toLowerCase()))
    const matchesCategory = selectedCategory === 'all' || template.category === selectedCategory
    return matchesSearch && matchesCategory
  })

  // 从模板创建工作流
  const createFromTemplate = useMutation({
    mutationFn: async ({ template, name }: { template: WorkflowTemplate; name: string }) => {
      const { data } = await workflowsApi.create({
        name,
        description: template.description,
        workflow_data: template.workflowData,
        category: template.category,
        tags: template.tags,
      })
      return data
    },
    onSuccess: (response) => {
      queryClient.invalidateQueries({ queryKey: ['workflows'] })
      setShowCreateDialog(false)
      setWorkflowName('')
      setSelectedTemplate(null)
      if (onCreateFromTemplate) {
        onCreateFromTemplate(selectedTemplate!, workflowName)
      }
      // 跳转到编辑页面
      window.location.href = `/workflow/${response.id}`
    },
  })

  const handleCreateFromTemplate = (template: WorkflowTemplate) => {
    setSelectedTemplate(template)
    setWorkflowName(`${template.name} - ${new Date().toLocaleDateString()}`)
    setShowCreateDialog(true)
  }

  const getDifficultyColor = (difficulty: WorkflowTemplate['difficulty']) => {
    switch (difficulty) {
      case 'beginner':
        return 'bg-green-500/10 text-green-500 border-green-500/20'
      case 'intermediate':
        return 'bg-yellow-500/10 text-yellow-500 border-yellow-500/20'
      case 'advanced':
        return 'bg-red-500/10 text-red-500 border-red-500/20'
    }
  }

  const getDifficultyText = (difficulty: WorkflowTemplate['difficulty']) => {
    switch (difficulty) {
      case 'beginner':
        return '入门'
      case 'intermediate':
        return '进阶'
      case 'advanced':
        return '高级'
    }
  }

  const getCategoryIcon = (category: string) => {
    switch (category) {
      case '基础':
        return <Sparkles className="h-4 w-4" />
      case 'SDXL':
        return <Zap className="h-4 w-4" />
      case '动漫':
        return <Palette className="h-4 w-4" />
      case '写实':
        return <Camera className="h-4 w-4" />
      case 'LoRA':
        return <Wrench className="h-4 w-4" />
      case '高级':
        return <Info className="h-4 w-4" />
      default:
        return <Sparkles className="h-4 w-4" />
    }
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-medium">工作流模板</h2>
          <p className="text-sm text-muted-foreground">选择预设模板快速开始创作</p>
        </div>
        <div className="relative">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            placeholder="搜索模板..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-64 pl-9 bg-muted/50 border-border/50"
          />
        </div>
      </div>

      {/* Category Filter */}
      <Tabs value={selectedCategory} onValueChange={setSelectedCategory}>
        <TabsList className="bg-muted/50 w-full justify-start">
          <TabsTrigger value="all" className="data-[state=active]:bg-background">
            全部
          </TabsTrigger>
          {getAllCategories().map(category => (
            <TabsTrigger 
              key={category} 
              value={category} 
              className="data-[state=active]:bg-background flex items-center gap-2"
            >
              {getCategoryIcon(category)}
              {category}
            </TabsTrigger>
          ))}
        </TabsList>
      </Tabs>

      {/* Template Grid */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {filteredTemplates.map((template) => (
          <Card
            key={template.id}
            className="group overflow-hidden transition-all hover:shadow-lg hover:border-primary/50 bg-card/50 border-border/50"
          >
            <CardContent className="p-4">
              <div className="space-y-3">
                {/* Header */}
                <div className="flex items-start justify-between">
                  <div className="flex-1 min-w-0">
                    <h3 className="font-medium truncate">{template.name}</h3>
                    <div className="flex items-center gap-2 mt-1">
                      <Badge 
                        variant="outline" 
                        className={`text-xs ${getDifficultyColor(template.difficulty)}`}
                      >
                        {getDifficultyText(template.difficulty)}
                      </Badge>
                      <Badge variant="secondary" className="text-xs bg-muted/50">
                        {template.category}
                      </Badge>
                    </div>
                  </div>
                </div>

                {/* Description */}
                <p className="text-sm text-muted-foreground line-clamp-2">
                  {template.description}
                </p>

                {/* Tags */}
                <div className="flex flex-wrap gap-1">
                  {template.tags.slice(0, 3).map(tag => (
                    <Badge key={tag} variant="outline" className="text-xs">
                      {tag}
                    </Badge>
                  ))}
                  {template.tags.length > 3 && (
                    <Badge variant="outline" className="text-xs">
                      +{template.tags.length - 3}
                    </Badge>
                  )}
                </div>

                {/* Parameters */}
                {template.parameters && (
                  <div className="text-xs text-muted-foreground space-y-1">
                    <div>步数: {template.parameters.steps} | CFG: {template.parameters.cfg}</div>
                    <div>尺寸: {template.parameters.size.width}×{template.parameters.size.height}</div>
                    <div>采样: {template.parameters.sampler}</div>
                  </div>
                )}

                {/* Recommended Models */}
                {template.recommendedModels && (
                  <div className="text-xs text-muted-foreground">
                    <span className="font-medium">推荐模型:</span>
                    <div className="mt-1 space-y-1">
                      {template.recommendedModels.slice(0, 2).map(model => (
                        <div key={model} className="truncate bg-muted/50 rounded px-2 py-1">
                          {model}
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Actions */}
                <div className="flex gap-2 pt-2">
                  <Button
                    size="sm"
                    className="flex-1"
                    onClick={() => handleCreateFromTemplate(template)}
                  >
                    <Plus className="mr-1 h-4 w-4" />
                    使用模板
                  </Button>
                  <Button size="sm" variant="outline">
                    <Info className="h-4 w-4" />
                  </Button>
                </div>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>

      {/* Create from Template Dialog */}
      <Dialog open={showCreateDialog} onOpenChange={setShowCreateDialog}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>从模板创建工作流</DialogTitle>
          </DialogHeader>
          {selectedTemplate && (
            <div className="space-y-4 py-4">
              <div className="space-y-2">
                <Label htmlFor="template-name">模板</Label>
                <div className="p-3 bg-muted/50 rounded-md">
                  <h4 className="font-medium">{selectedTemplate.name}</h4>
                  <p className="text-sm text-muted-foreground">{selectedTemplate.description}</p>
                </div>
              </div>
              <div className="space-y-2">
                <Label htmlFor="workflow-name">工作流名称</Label>
                <Input
                  id="workflow-name"
                  value={workflowName}
                  onChange={(e) => setWorkflowName(e.target.value)}
                  placeholder="输入工作流名称..."
                />
              </div>
            </div>
          )}
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowCreateDialog(false)}>
              取消
            </Button>
            <Button 
              onClick={() => selectedTemplate && createFromTemplate.mutate({ 
                template: selectedTemplate, 
                name: workflowName 
              })}
              disabled={!workflowName.trim() || createFromTemplate.isPending}
            >
              {createFromTemplate.isPending ? (
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              ) : (
                <Plus className="mr-2 h-4 w-4" />
              )}
              创建
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}