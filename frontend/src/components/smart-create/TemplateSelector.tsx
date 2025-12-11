import { Card, CardContent } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import type { SmartCreateTemplate } from '@/lib/api'

interface TemplateSelectorProps {
  templates: SmartCreateTemplate[]
  onSelect: (template: SmartCreateTemplate) => void
}

export function TemplateSelector({ templates, onSelect }: TemplateSelectorProps) {
  return (
    <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-2">
      {templates.map((template) => (
        <Card 
          key={template.id}
          className="bg-card/50 border-border/50 hover:border-primary/50 transition-colors cursor-pointer group"
          onClick={() => onSelect(template)}
        >
          <CardContent className="p-3">
            <div className="flex items-center gap-2 mb-1">
              <span className="text-xl">{template.icon}</span>
              <h3 className="font-medium text-sm truncate">{template.name}</h3>
            </div>
            <p className="text-xs text-muted-foreground line-clamp-2 mb-2">
              {template.description}
            </p>
            <Button 
              variant="outline" 
              size="sm" 
              className="w-full h-7 text-xs group-hover:bg-primary group-hover:text-primary-foreground"
            >
              创建
            </Button>
          </CardContent>
        </Card>
      ))}
    </div>
  )
}
