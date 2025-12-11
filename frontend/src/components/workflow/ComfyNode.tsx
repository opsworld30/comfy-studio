import { memo, useMemo } from 'react'
import { Handle, Position } from '@xyflow/react'
import { cn } from '@/lib/utils'
import type { ComfyNodeData } from '@/lib/workflow-converter'

// 类型颜色映射
const typeColors: Record<string, string> = {
  MODEL: 'bg-purple-500',
  CLIP: 'bg-yellow-500',
  VAE: 'bg-red-500',
  CONDITIONING: 'bg-orange-500',
  LATENT: 'bg-pink-500',
  IMAGE: 'bg-blue-500',
  MASK: 'bg-green-500',
  INT: 'bg-cyan-500',
  FLOAT: 'bg-teal-500',
  STRING: 'bg-gray-500',
  CONTROL_NET: 'bg-emerald-500',
}

// 分类颜色映射
const categoryColors: Record<string, string> = {
  loaders: 'from-blue-500/20 to-blue-600/10',
  sampling: 'from-purple-500/20 to-purple-600/10',
  conditioning: 'from-orange-500/20 to-orange-600/10',
  latent: 'from-pink-500/20 to-pink-600/10',
  image: 'from-green-500/20 to-green-600/10',
  _for_testing: 'from-gray-500/20 to-gray-600/10',
  advanced: 'from-red-500/20 to-red-600/10',
}

export type { ComfyNodeData }

// React Flow 节点组件 props
interface ComfyNodeProps {
  id: string
  data: ComfyNodeData
  selected?: boolean
}

function ComfyNode({ data, selected }: ComfyNodeProps) {
  const categoryColor = useMemo(() => {
    const cat = data.category?.split('/')[0] || ''
    return categoryColors[cat] || 'from-slate-500/20 to-slate-600/10'
  }, [data.category])

  // 分离连接输入和widget输入
  const connectionInputs = data.inputs.filter(i => !i.isWidget)
  const widgetInputs = data.inputs.filter(i => i.isWidget)

  return (
    <div
      className={cn(
        'min-w-[200px] max-w-[300px] rounded-xl border bg-card shadow-xl transition-shadow',
        selected ? 'border-primary shadow-primary/20' : 'border-border/50'
      )}
    >
      {/* Header */}
      <div
        className={cn(
          'flex items-center justify-between border-b border-border/40 px-3 py-2 rounded-t-xl bg-gradient-to-r',
          categoryColor
        )}
      >
        <span className="text-sm font-medium truncate">{data.label}</span>
        <span className="text-xs text-muted-foreground">{data.type}</span>
      </div>

      {/* Body */}
      <div className="p-2 space-y-1">
        {/* Connection Inputs */}
        {connectionInputs.map((input) => (
          <div key={`input-${input.name}`} className="relative flex items-center gap-2 py-1">
            <Handle
              type="target"
              position={Position.Left}
              id={input.name}
              className={cn(
                'w-3 h-3 !border-2 !border-background',
                typeColors[input.type] || 'bg-gray-400'
              )}
              style={{ left: -6 }}
            />
            <div
              className={cn(
                'w-2 h-2 rounded-full',
                typeColors[input.type] || 'bg-gray-400'
              )}
            />
            <span className="text-xs text-muted-foreground">{input.name}</span>
          </div>
        ))}

        {/* Widget Inputs */}
        {widgetInputs.map((widget, index) => (
          <div key={`widget-${widget.name}`} className="py-1">
            <label className="text-xs text-muted-foreground block mb-1">
              {widget.name}
            </label>
            {renderWidget(widget, data.widgets_values?.[index])}
          </div>
        ))}

        {/* Outputs */}
        {data.outputs.map((output) => (
          <div
            key={`output-${output.name}`}
            className="relative flex items-center justify-end gap-2 py-1"
          >
            <span className="text-xs text-muted-foreground">{output.name}</span>
            <div
              className={cn(
                'w-2 h-2 rounded-full',
                typeColors[output.type] || 'bg-gray-400'
              )}
            />
            <Handle
              type="source"
              position={Position.Right}
              id={output.name}
              className={cn(
                'w-3 h-3 !border-2 !border-background',
                typeColors[output.type] || 'bg-gray-400'
              )}
              style={{ right: -6 }}
            />
          </div>
        ))}
      </div>
    </div>
  )
}

function renderWidget(
  widget: ComfyNodeData['inputs'][0],
  value?: unknown
) {
  const displayValue = value ?? widget.options?.default ?? ''

  // 下拉选择
  if (widget.options?.values && widget.options.values.length > 0) {
    return (
      <select
        className="w-full rounded border border-border/50 bg-muted/30 px-2 py-1 text-xs"
        defaultValue={String(displayValue)}
      >
        {widget.options.values.map((v) => (
          <option key={v} value={v}>
            {v}
          </option>
        ))}
      </select>
    )
  }

  // 数字输入
  if (widget.type === 'INT' || widget.type === 'FLOAT') {
    return (
      <input
        type="number"
        className="w-full rounded border border-border/50 bg-muted/30 px-2 py-1 text-xs"
        defaultValue={Number(displayValue) || 0}
        min={widget.options?.min}
        max={widget.options?.max}
        step={widget.options?.step || (widget.type === 'FLOAT' ? 0.1 : 1)}
      />
    )
  }

  // 多行文本
  if (widget.type === 'STRING' && widget.name.toLowerCase().includes('prompt')) {
    return (
      <textarea
        className="w-full rounded border border-border/50 bg-muted/30 px-2 py-1 text-xs resize-none"
        rows={3}
        defaultValue={String(displayValue)}
      />
    )
  }

  // 单行文本
  return (
    <input
      type="text"
      className="w-full rounded border border-border/50 bg-muted/30 px-2 py-1 text-xs"
      defaultValue={String(displayValue)}
    />
  )
}

export default memo(ComfyNode)
