import { useState, useEffect, useCallback, useRef, useMemo } from 'react'
import { useParams } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  ReactFlow,
  Controls,
  Background,
  BackgroundVariant,
  useNodesState,
  useEdgesState,
  addEdge,
  type Connection,
  type Node,
  type Edge,
  ReactFlowProvider,
  useReactFlow,
} from '@xyflow/react'
import '@xyflow/react/dist/style.css'

import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Input } from '@/components/ui/input'
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/tabs'
import { ScrollArea } from '@/components/ui/scroll-area'
import {
  Save,
  Play,
  Undo,
  Redo,
  Download,
  Upload,
  ChevronRight,
  ChevronDown,
  Search,
  Loader2,
  CheckCircle,
  GripVertical,
} from 'lucide-react'
import { workflowsApi, comfyuiApi, type ComfyUINodeDef } from '@/lib/api'
import ComfyNode from '@/components/workflow/ComfyNode'
import {
  comfyToReactFlow,
  comfyApiToReactFlow,
  reactFlowToComfy,
  organizeNodesByCategory,
  type ComfyNodeData,
  type ComfyUIWorkflow,
} from '@/lib/workflow-converter'
import { WORKFLOW_TEMPLATES, getAllCategories, type WorkflowTemplate } from '@/data/workflowTemplates'

// 自定义节点类型
const nodeTypes = {
  comfyNode: ComfyNode,
}

// 节点库面板
function NodeLibrary({
  nodeDefs,
  onAddNode,
}: {
  nodeDefs: Record<string, ComfyUINodeDef>
  onAddNode: (nodeType: string) => void
}) {
  const [searchQuery, setSearchQuery] = useState('')
  const [expandedCategories, setExpandedCategories] = useState<Set<string>>(new Set())

  const categorizedNodes = useMemo(() => organizeNodesByCategory(nodeDefs), [nodeDefs])

  const filteredCategories = useMemo(() => {
    if (!searchQuery) return categorizedNodes

    const filtered: Record<string, ComfyUINodeDef[]> = {}
    for (const [category, nodes] of Object.entries(categorizedNodes)) {
      const matchedNodes = nodes.filter(
        (n) =>
          n.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
          n.display_name.toLowerCase().includes(searchQuery.toLowerCase())
      )
      if (matchedNodes.length > 0) {
        filtered[category] = matchedNodes
      }
    }
    return filtered
  }, [categorizedNodes, searchQuery])

  const toggleCategory = (category: string) => {
    setExpandedCategories((prev) => {
      const next = new Set(prev)
      if (next.has(category)) {
        next.delete(category)
      } else {
        next.add(category)
      }
      return next
    })
  }

  const handleDragStart = (e: React.DragEvent, nodeType: string) => {
    e.dataTransfer.setData('application/reactflow', nodeType)
    e.dataTransfer.effectAllowed = 'move'
  }

  return (
    <div className="flex flex-col h-full">
      <div className="p-3 border-b border-border/40">
        <div className="relative">
          <Search className="absolute left-2.5 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            placeholder="搜索节点..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="pl-8 h-9 bg-muted/50"
          />
        </div>
      </div>
      <ScrollArea className="flex-1">
        <div className="p-2 space-y-1">
          {Object.entries(filteredCategories).map(([category, nodes]) => (
            <div key={category} className="rounded-lg border border-border/50 bg-card/50 overflow-hidden">
              <button
                className="flex w-full items-center justify-between p-2.5 text-sm hover:bg-accent/50 transition-colors"
                onClick={() => toggleCategory(category)}
              >
                <span className="font-medium truncate">{category}</span>
                <div className="flex items-center gap-2">
                  <span className="text-xs text-muted-foreground">{nodes.length}</span>
                  {expandedCategories.has(category) ? (
                    <ChevronDown className="h-4 w-4 text-muted-foreground" />
                  ) : (
                    <ChevronRight className="h-4 w-4 text-muted-foreground" />
                  )}
                </div>
              </button>
              {expandedCategories.has(category) && (
                <div className="border-t border-border/40 p-1 space-y-0.5">
                  {nodes.map((node) => (
                    <div
                      key={node.name}
                      className="flex items-center gap-2 px-2 py-1.5 text-xs rounded hover:bg-accent/50 cursor-grab transition-colors"
                      draggable
                      onDragStart={(e) => handleDragStart(e, node.name)}
                      onClick={() => onAddNode(node.name)}
                    >
                      <GripVertical className="h-3 w-3 text-muted-foreground" />
                      <span className="truncate">{node.display_name}</span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          ))}
        </div>
      </ScrollArea>
    </div>
  )
}

// 模板面板
function TemplateLibrary({
  onLoadTemplate,
}: {
  onLoadTemplate: (template: WorkflowTemplate) => void
}) {
  const [selectedCategory, setSelectedCategory] = useState<string>('all')
  const categories = getAllCategories()

  const filteredTemplates = selectedCategory === 'all'
    ? WORKFLOW_TEMPLATES
    : WORKFLOW_TEMPLATES.filter(t => t.category === selectedCategory)

  const getDifficultyColor = (difficulty: WorkflowTemplate['difficulty']) => {
    switch (difficulty) {
      case 'beginner': return 'bg-green-500/20 text-green-400 border-green-500/30'
      case 'intermediate': return 'bg-yellow-500/20 text-yellow-400 border-yellow-500/30'
      case 'advanced': return 'bg-red-500/20 text-red-400 border-red-500/30'
    }
  }

  return (
    <div className="flex flex-col h-full">
      <div className="p-2 border-b border-border/40">
        <select
          value={selectedCategory}
          onChange={(e) => setSelectedCategory(e.target.value)}
          className="w-full px-2 py-1.5 text-xs bg-muted/50 border border-border/50 rounded"
        >
          <option value="all">全部分类</option>
          {categories.map(cat => (
            <option key={cat} value={cat}>{cat}</option>
          ))}
        </select>
      </div>
      <ScrollArea className="flex-1">
        <div className="p-2 space-y-2">
          {filteredTemplates.map((template) => (
            <div
              key={template.id}
              className="p-3 rounded-lg border border-border/50 bg-card/50 hover:border-primary/50 cursor-pointer transition-colors"
              onClick={() => onLoadTemplate(template)}
            >
              <div className="flex items-start justify-between gap-2 mb-2">
                <h4 className="text-sm font-medium truncate">{template.name}</h4>
                <Badge variant="outline" className={`text-[10px] shrink-0 ${getDifficultyColor(template.difficulty)}`}>
                  {template.difficulty === 'beginner' ? '入门' : template.difficulty === 'intermediate' ? '进阶' : '高级'}
                </Badge>
              </div>
              <p className="text-xs text-muted-foreground line-clamp-2 mb-2">
                {template.description}
              </p>
              {template.parameters && (
                <div className="flex flex-wrap gap-1 text-[10px] text-muted-foreground">
                  <span className="px-1.5 py-0.5 bg-muted/50 rounded">
                    {template.parameters.size.width}×{template.parameters.size.height}
                  </span>
                  <span className="px-1.5 py-0.5 bg-muted/50 rounded">
                    {template.parameters.steps}步
                  </span>
                  <span className="px-1.5 py-0.5 bg-muted/50 rounded">
                    CFG {template.parameters.cfg}
                  </span>
                </div>
              )}
            </div>
          ))}
        </div>
      </ScrollArea>
    </div>
  )
}

// 主编辑器组件
function WorkflowEditorInner() {
  const { id: workflowId } = useParams()
  const queryClient = useQueryClient()
  const fileInputRef = useRef<HTMLInputElement>(null)
  const reactFlowWrapper = useRef<HTMLDivElement>(null)
  const { screenToFlowPosition } = useReactFlow()

  const [nodes, setNodes, onNodesChange] = useNodesState<Node<ComfyNodeData>>([])
  const [edges, setEdges, onEdgesChange] = useEdgesState<Edge>([])
  const [workflowName, setWorkflowName] = useState('')
  const [isSaving, setIsSaving] = useState(false)
  const [saveSuccess, setSaveSuccess] = useState(false)
  const [isExecuting, setIsExecuting] = useState(false)

  // 获取工作流详情
  const { data: workflow, isLoading: workflowLoading } = useQuery({
    queryKey: ['workflow', workflowId],
    queryFn: async () => {
      if (!workflowId) return null
      const { data } = await workflowsApi.get(parseInt(workflowId))
      return data
    },
    enabled: !!workflowId,
  })

  // 获取节点定义
  const { data: nodeDefs = {}, isLoading: nodeDefsLoading } = useQuery({
    queryKey: ['comfyui', 'object_info'],
    queryFn: async () => {
      const { data } = await comfyuiApi.getObjectInfo()
      return data
    },
    staleTime: 5 * 60 * 1000, // 5分钟缓存
  })

  // 初始化工作流
  useEffect(() => {
    if (workflow && Object.keys(nodeDefs).length > 0) {
      setWorkflowName(workflow.name)
      const workflowData = workflow.workflow_data
      
      if (workflowData) {
        // 检查是 workflow 格式还是 API 格式
        if ('nodes' in workflowData && Array.isArray((workflowData as ComfyUIWorkflow).nodes)) {
          // Workflow 格式 (有 nodes 数组)
          const { nodes: flowNodes, edges: flowEdges } = comfyToReactFlow(workflowData as ComfyUIWorkflow, nodeDefs)
          setNodes(flowNodes)
          setEdges(flowEdges)
        } else {
          // API 格式 (以节点 ID 为键的对象)
          const apiWorkflow = workflowData as Record<string, { class_type: string; inputs: Record<string, unknown> }>
          const { nodes: flowNodes, edges: flowEdges } = comfyApiToReactFlow(apiWorkflow, nodeDefs)
          setNodes(flowNodes)
          setEdges(flowEdges)
        }
      }
    }
  }, [workflow, nodeDefs, setNodes, setEdges])

  // 连接处理
  const onConnect = useCallback(
    (params: Connection) => setEdges((eds) => addEdge({ ...params, type: 'smoothstep' }, eds)),
    [setEdges]
  )

  // 添加节点
  const addNode = useCallback(
    (nodeType: string, position?: { x: number; y: number }) => {
      const nodeDef = nodeDefs[nodeType]
      if (!nodeDef) return

      const newNodeId = String(Date.now())
      const pos = position || { x: 250, y: 250 }

      // 解析输入
      const inputs: ComfyNodeData['inputs'] = []
      if (nodeDef.input?.required) {
        for (const [name, config] of Object.entries(nodeDef.input.required)) {
          const [type, options] = config
          const isWidget = !isConnectionType(type)
          inputs.push({
            name,
            type: Array.isArray(type) ? type[0] : type,
            isWidget,
            options: options as ComfyNodeData['inputs'][0]['options'],
          })
        }
      }

      // 解析输出
      const outputs: ComfyNodeData['outputs'] = nodeDef.output.map((type, index) => ({
        name: nodeDef.output_name?.[index] || type,
        type,
      }))

      const newNode: Node<ComfyNodeData> = {
        id: newNodeId,
        type: 'comfyNode',
        position: pos,
        data: {
          label: nodeDef.display_name,
          type: nodeType,
          category: nodeDef.category,
          inputs,
          outputs,
        },
      }

      setNodes((nds) => [...nds, newNode])
    },
    [nodeDefs, setNodes]
  )

  // 拖放处理
  const onDragOver = useCallback((event: React.DragEvent) => {
    event.preventDefault()
    event.dataTransfer.dropEffect = 'move'
  }, [])

  const onDrop = useCallback(
    (event: React.DragEvent) => {
      event.preventDefault()

      const nodeType = event.dataTransfer.getData('application/reactflow')
      if (!nodeType || !reactFlowWrapper.current) return

      const position = screenToFlowPosition({
        x: event.clientX,
        y: event.clientY,
      })

      addNode(nodeType, position)
    },
    [addNode, screenToFlowPosition]
  )

  // 保存工作流
  const saveWorkflow = useMutation({
    mutationFn: async () => {
      if (!workflowId) return
      setIsSaving(true)
      const workflowData = reactFlowToComfy(nodes, edges)
      await workflowsApi.update(parseInt(workflowId), {
        name: workflowName,
        workflow_data: workflowData,
      })
      await workflowsApi.createVersion(parseInt(workflowId), '手动保存')
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['workflow', workflowId] })
      setIsSaving(false)
      setSaveSuccess(true)
      setTimeout(() => setSaveSuccess(false), 2000)
    },
    onError: () => {
      setIsSaving(false)
    },
  })

  // 执行工作流
  const executeWorkflow = useMutation({
    mutationFn: async () => {
      if (!workflowId) return
      setIsExecuting(true)
      const workflowData = reactFlowToComfy(nodes, edges)
      await comfyuiApi.executeDirect(workflowData)
    },
    onSuccess: () => {
      setIsExecuting(false)
      queryClient.invalidateQueries({ queryKey: ['comfyui', 'queue'] })
    },
    onError: () => {
      setIsExecuting(false)
    },
  })

  // 导出工作流
  const handleExport = () => {
    const workflowData = reactFlowToComfy(nodes, edges)
    const blob = new Blob([JSON.stringify(workflowData, null, 2)], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `${workflowName || 'workflow'}.json`
    a.click()
    URL.revokeObjectURL(url)
  }

  // 加载模板
  const handleLoadTemplate = useCallback((template: WorkflowTemplate) => {
    if (Object.keys(nodeDefs).length === 0) return
    
    // 模板使用 API 格式 (prompt 格式)
    const apiWorkflow = template.workflowData as Record<string, { class_type: string; inputs: Record<string, unknown> }>
    const { nodes: flowNodes, edges: flowEdges } = comfyApiToReactFlow(apiWorkflow, nodeDefs)
    setNodes(flowNodes)
    setEdges(flowEdges)
    setWorkflowName(template.name)
  }, [nodeDefs, setNodes, setEdges])

  // 导入工作流
  const handleImport = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return

    const text = await file.text()
    try {
      const workflowData = JSON.parse(text) as ComfyUIWorkflow
      const { nodes: flowNodes, edges: flowEdges } = comfyToReactFlow(workflowData, nodeDefs)
      setNodes(flowNodes)
      setEdges(flowEdges)
    } catch (err) {
      console.error('Failed to import workflow:', err)
    }
  }

  const isLoading = workflowLoading || nodeDefsLoading

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-[calc(100vh-4rem)]">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    )
  }

  return (
    <div className="h-[calc(100vh-4rem)] flex flex-col -m-6">
      {/* Toolbar */}
      <div className="flex items-center justify-between border-b border-border/40 bg-card/50 px-4 py-2">
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-2">
            <Input
              value={workflowName}
              onChange={(e) => setWorkflowName(e.target.value)}
              className="font-semibold bg-transparent border-none h-8 w-48 focus-visible:ring-1"
            />
            {saveSuccess && (
              <Badge className="bg-green-500">
                <CheckCircle className="mr-1 h-3 w-3" />
                已保存
              </Badge>
            )}
          </div>
          <div className="flex items-center gap-1">
            <Button variant="ghost" size="icon" className="h-8 w-8" title="撤销">
              <Undo className="h-4 w-4" />
            </Button>
            <Button variant="ghost" size="icon" className="h-8 w-8" title="重做">
              <Redo className="h-4 w-4" />
            </Button>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <input
            ref={fileInputRef}
            type="file"
            accept=".json"
            onChange={handleImport}
            className="hidden"
          />
          <Button variant="outline" size="sm" onClick={() => fileInputRef.current?.click()}>
            <Upload className="mr-2 h-4 w-4" />
            导入
          </Button>
          <Button variant="outline" size="sm" onClick={handleExport}>
            <Download className="mr-2 h-4 w-4" />
            导出
          </Button>
          <Button
            variant="outline"
            size="sm"
            onClick={() => saveWorkflow.mutate()}
            disabled={isSaving}
          >
            {isSaving ? (
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
            ) : (
              <Save className="mr-2 h-4 w-4" />
            )}
            保存
          </Button>
          <Button
            size="sm"
            className="bg-green-600 hover:bg-green-700"
            onClick={() => executeWorkflow.mutate()}
            disabled={isExecuting}
          >
            {isExecuting ? (
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
            ) : (
              <Play className="mr-2 h-4 w-4" />
            )}
            运行
          </Button>
        </div>
      </div>

      <div className="flex flex-1 overflow-hidden">
        {/* Left Panel - Node Library */}
        <div className="w-64 border-r border-border/40 bg-card/30">
          <Tabs defaultValue="nodes" className="h-full flex flex-col">
            <TabsList className="w-full rounded-none border-b border-border/40 bg-transparent h-auto p-0">
              <TabsTrigger
                value="nodes"
                className="flex-1 rounded-none border-b-2 border-transparent data-[state=active]:border-primary data-[state=active]:bg-transparent py-2.5 text-xs"
              >
                节点库
              </TabsTrigger>
              <TabsTrigger
                value="templates"
                className="flex-1 rounded-none border-b-2 border-transparent data-[state=active]:border-primary data-[state=active]:bg-transparent py-2.5 text-xs"
              >
                模板
              </TabsTrigger>
            </TabsList>
            <TabsContent value="nodes" className="flex-1 mt-0 overflow-hidden">
              <NodeLibrary nodeDefs={nodeDefs} onAddNode={addNode} />
            </TabsContent>
            <TabsContent value="templates" className="flex-1 mt-0 overflow-hidden">
              <TemplateLibrary onLoadTemplate={handleLoadTemplate} />
            </TabsContent>
          </Tabs>
        </div>

        {/* Canvas Area */}
        <div ref={reactFlowWrapper} className="flex-1">
          <ReactFlow
            nodes={nodes}
            edges={edges}
            onNodesChange={onNodesChange}
            onEdgesChange={onEdgesChange}
            onConnect={onConnect}
            onDragOver={onDragOver}
            onDrop={onDrop}
            nodeTypes={nodeTypes}
            fitView
            snapToGrid
            snapGrid={[15, 15]}
            defaultEdgeOptions={{
              type: 'smoothstep',
              style: { strokeWidth: 2 },
            }}
            className="bg-[#0f0f1a]"
          >
            <Background variant={BackgroundVariant.Dots} gap={24} size={1} color="#333" />
            <Controls className="bg-card border border-border/50 rounded-lg" />
          </ReactFlow>
        </div>

        {/* Right Panel - Properties */}
        <div className="w-72 border-l border-border/40 bg-card/30 p-3">
          <h3 className="font-medium text-sm mb-3">节点属性</h3>
          <div className="text-sm text-muted-foreground">
            选择一个节点查看属性
          </div>
        </div>
      </div>
    </div>
  )
}

// 判断是否为连接类型
function isConnectionType(type: string | string[]): boolean {
  const connectionTypes = [
    'MODEL', 'CLIP', 'VAE', 'CONDITIONING', 'LATENT',
    'IMAGE', 'MASK', 'CONTROL_NET', 'CLIP_VISION',
    'STYLE_MODEL', 'GLIGEN', 'UPSCALE_MODEL',
  ]
  const t = Array.isArray(type) ? type[0] : type
  return connectionTypes.includes(t)
}

// 包装组件提供 ReactFlow 上下文
export default function WorkflowEditor() {
  return (
    <ReactFlowProvider>
      <WorkflowEditorInner />
    </ReactFlowProvider>
  )
}
