import { useState, useEffect } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Switch } from '@/components/ui/switch'
import {
  Settings as SettingsIcon,
  Save,
  Loader2,
  Trash2,
  HardDrive,
  Bell,
  Palette,
  Database,
  RefreshCw,
  LayoutGrid,
  Brain,
} from 'lucide-react'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { settingsApi, type AppSettings, type PageModuleSettings } from '@/lib/api'
import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from '@/components/ui/accordion'
import { useThemeStore } from '@/stores/theme'
import { usePageModulesStore } from '@/stores/pageModules'

export default function Settings() {
  const queryClient = useQueryClient()
  const { theme, setTheme } = useThemeStore()

  // 获取设置
  const { data: settings, isLoading } = useQuery({
    queryKey: ['settings'],
    queryFn: async () => {
      const { data } = await settingsApi.get()
      return data
    },
  })

  // 获取存储统计
  const { data: storageStats } = useQuery({
    queryKey: ['settings', 'storage'],
    queryFn: async () => {
      const { data } = await settingsApi.getStorageStats()
      return data
    },
  })

  // 获取页面模块设置
  const { data: pageModules } = useQuery({
    queryKey: ['settings', 'page-modules'],
    queryFn: async () => {
      const { data } = await settingsApi.getPageModules()
      return data
    },
  })

  // 获取 AI 设置
  const { data: aiSettings } = useQuery({
    queryKey: ['settings', 'ai'],
    queryFn: async () => {
      const { data } = await settingsApi.getAISettings()
      return data
    },
  })

  // AI 设置本地状态
  const [localAISettings, setLocalAISettings] = useState({
    api_key: '',
    api_url: 'https://api.siliconflow.cn/v1',
    model: 'Qwen/Qwen2.5-7B-Instruct',
    enabled: false,
  })

  // 同步远程数据到本地状态
  useEffect(() => {
    if (aiSettings) {
      setLocalAISettings({
        api_key: aiSettings.api_key || '',
        api_url: aiSettings.api_url || 'https://api.siliconflow.cn/v1',
        model: aiSettings.model || 'Qwen/Qwen2.5-7B-Instruct',
        enabled: aiSettings.enabled ?? false,
      })
    }
  }, [aiSettings])

  // 更新 AI 设置
  const updateAISettings = useMutation({
    mutationFn: (data: { api_key?: string; api_url?: string; model?: string; enabled?: boolean }) => 
      settingsApi.updateAISettings(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['settings', 'ai'] })
    },
  })

  const handleAISettingChange = (key: string, value: unknown) => {
    setLocalAISettings(prev => ({ ...prev, [key]: value }))
  }

  const saveAISettings = () => {
    updateAISettings.mutate(localAISettings)
  }

  // 更新页面模块设置
  const updatePageModules = useMutation({
    mutationFn: (data: PageModuleSettings) => settingsApi.updatePageModules(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['settings', 'page-modules'] })
    },
  })

  const handleModuleChange = (section: keyof PageModuleSettings, key: string, value: boolean) => {
    if (!pageModules) return
    const updated = {
      ...pageModules,
      [section]: {
        ...pageModules[section],
        [key]: value,
      },
    }
    updatePageModules.mutate(updated)
  }

  // 更新设置
  const updateSettings = useMutation({
    mutationFn: (data: Partial<AppSettings>) => settingsApi.update(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['settings'] })
    },
  })

  // 清理临时文件
  const cleanupTemp = useMutation({
    mutationFn: () => settingsApi.cleanupTemp(),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['settings', 'storage'] })
    },
  })

  // 清理缓存
  const cleanupCache = useMutation({
    mutationFn: () => settingsApi.cleanupCache(),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['settings', 'storage'] })
    },
  })

  const handleSettingChange = (key: keyof AppSettings, value: unknown) => {
    updateSettings.mutate({ [key]: value })
  }

  // 格式化文件大小
  const formatSize = (bytes: number) => {
    if (!bytes) return '0 B'
    if (bytes >= 1024 * 1024 * 1024) {
      return `${(bytes / (1024 * 1024 * 1024)).toFixed(2)} GB`
    }
    if (bytes >= 1024 * 1024) {
      return `${(bytes / (1024 * 1024)).toFixed(0)} MB`
    }
    return `${(bytes / 1024).toFixed(0)} KB`
  }

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-96">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-medium flex items-center gap-2">
          <SettingsIcon className="h-5 w-5" />
          设置
        </h2>
      </div>

      {/* Two Column Layout */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Left Column */}
        <div className="space-y-6">
          {/* Page Modules */}
          <Card className="bg-card/50 border-border/50">
            <CardHeader>
              <CardTitle className="text-base flex items-center gap-2">
                <LayoutGrid className="h-4 w-4" />
                页面与模块
              </CardTitle>
              <CardDescription>控制页面和组件的显示/隐藏</CardDescription>
            </CardHeader>
            <CardContent>
              <Accordion type="multiple" className="w-full">
                <AccordionItem value="pages">
                  <AccordionTrigger className="text-sm">侧边栏页面</AccordionTrigger>
                  <AccordionContent>
                    <div className="space-y-3 pt-2">
                      {[
                        { key: 'showDashboard', label: '工作流' },
                        { key: 'showBatch', label: '任务队列' },
                        { key: 'showGallery', label: '画廊' },
                        { key: 'showModels', label: '模型库' },
                        { key: 'showPrompts', label: '提示词' },
                        { key: 'showMonitor', label: '监控' },
                        { key: 'showMarket', label: '市场' },
                      ].map((item) => (
                        <div key={item.key} className="flex items-center justify-between">
                          <Label className="text-sm">{item.label}</Label>
                          <Switch
                            checked={pageModules?.pages?.[item.key] ?? true}
                            onCheckedChange={(checked) => handleModuleChange('pages', item.key, checked)}
                          />
                        </div>
                      ))}
                    </div>
                  </AccordionContent>
                </AccordionItem>

                <AccordionItem value="dashboard">
                  <AccordionTrigger className="text-sm">仪表盘模块</AccordionTrigger>
                  <AccordionContent>
                    <div className="space-y-3 pt-2">
                      {[
                        { key: 'showQuickActions', label: '快捷操作' },
                        { key: 'showRecentImages', label: '最近生成' },
                        { key: 'showSystemStatus', label: '系统状态' },
                        { key: 'showStatistics', label: '统计信息' },
                      ].map((item) => (
                        <div key={item.key} className="flex items-center justify-between">
                          <Label className="text-sm">{item.label}</Label>
                          <Switch
                            checked={pageModules?.dashboard?.[item.key] ?? true}
                            onCheckedChange={(checked) => handleModuleChange('dashboard', item.key, checked)}
                          />
                        </div>
                      ))}
                    </div>
                  </AccordionContent>
                </AccordionItem>

                <AccordionItem value="gallery">
                  <AccordionTrigger className="text-sm">图片画廊模块</AccordionTrigger>
                  <AccordionContent>
                    <div className="space-y-3 pt-2">
                      {[
                        { key: 'showSearchBar', label: '搜索栏' },
                        { key: 'showLayoutToggle', label: '布局切换' },
                        { key: 'showCategories', label: '智能分类' },
                        { key: 'showFavorites', label: '收藏筛选' },
                      ].map((item) => (
                        <div key={item.key} className="flex items-center justify-between">
                          <Label className="text-sm">{item.label}</Label>
                          <Switch
                            checked={pageModules?.gallery?.[item.key] ?? true}
                            onCheckedChange={(checked) => handleModuleChange('gallery', item.key, checked)}
                          />
                        </div>
                      ))}
                    </div>
                  </AccordionContent>
                </AccordionItem>

                <AccordionItem value="models">
                  <AccordionTrigger className="text-sm">模型管理模块</AccordionTrigger>
                  <AccordionContent>
                    <div className="space-y-3 pt-2">
                      {[
                        { key: 'showLocalModels', label: '本地模型' },
                        { key: 'showCivitai', label: 'Civitai 模型库' },
                      ].map((item) => (
                        <div key={item.key} className="flex items-center justify-between">
                          <Label className="text-sm">{item.label}</Label>
                          <Switch
                            checked={pageModules?.models?.[item.key] ?? true}
                            onCheckedChange={(checked) => handleModuleChange('models', item.key, checked)}
                          />
                        </div>
                      ))}
                    </div>
                  </AccordionContent>
                </AccordionItem>

                <AccordionItem value="monitor">
                  <AccordionTrigger className="text-sm">执行监控模块</AccordionTrigger>
                  <AccordionContent>
                    <div className="space-y-3 pt-2">
                      {[
                        { key: 'showSystemStatus', label: '系统状态' },
                        { key: 'showExecutionQueue', label: '执行队列' },
                        { key: 'showPerformanceChart', label: '性能图表' },
                        { key: 'showExecutionHistory', label: '执行历史' },
                      ].map((item) => (
                        <div key={item.key} className="flex items-center justify-between">
                          <Label className="text-sm">{item.label}</Label>
                          <Switch
                            checked={pageModules?.monitor?.[item.key] ?? true}
                            onCheckedChange={(checked) => handleModuleChange('monitor', item.key, checked)}
                          />
                        </div>
                      ))}
                    </div>
                  </AccordionContent>
                </AccordionItem>

                <AccordionItem value="prompts">
                  <AccordionTrigger className="text-sm">提示词模块</AccordionTrigger>
                  <AccordionContent>
                    <div className="space-y-3 pt-2">
                      {[
                        { key: 'showCategories', label: '分类筛选' },
                        { key: 'showAIGenerate', label: 'AI 生成' },
                        { key: 'showFavorites', label: '收藏筛选' },
                      ].map((item) => (
                        <div key={item.key} className="flex items-center justify-between">
                          <Label className="text-sm">{item.label}</Label>
                          <Switch
                            checked={pageModules?.prompts?.[item.key] ?? true}
                            onCheckedChange={(checked) => handleModuleChange('prompts', item.key, checked)}
                          />
                        </div>
                      ))}
                    </div>
                  </AccordionContent>
                </AccordionItem>
              </Accordion>
            </CardContent>
          </Card>

          {/* AI Configuration */}
          <Card className="bg-card/50 border-border/50">
            <CardHeader>
              <CardTitle className="text-base flex items-center gap-2">
                <Brain className="h-4 w-4" />
                AI 服务配置
              </CardTitle>
              <CardDescription>配置 AI 服务用于 Prompt 优化和内容生成</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="flex items-center justify-between">
                <div>
                  <Label>启用 AI 功能</Label>
                  <p className="text-sm text-muted-foreground">开启后可使用 AI 生成和优化提示词</p>
                </div>
                <Switch
                  checked={localAISettings.enabled}
                  onCheckedChange={(checked) => handleAISettingChange('enabled', checked)}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="api-key">API Key</Label>
                <Input
                  id="api-key"
                  type="password"
                  value={localAISettings.api_key}
                  onChange={(e) => handleAISettingChange('api_key', e.target.value)}
                  placeholder="输入您的 API 密钥"
                />
                <p className="text-xs text-muted-foreground">
                  在 <a href="https://cloud.siliconflow.cn" target="_blank" rel="noopener noreferrer" className="text-primary hover:underline">SiliconFlow</a> 注册获取免费 API Key
                </p>
              </div>
              <div className="space-y-2">
                <Label htmlFor="api-url">API 地址</Label>
                <Input
                  id="api-url"
                  value={localAISettings.api_url}
                  onChange={(e) => handleAISettingChange('api_url', e.target.value)}
                  placeholder="https://api.siliconflow.cn/v1"
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="model">模型</Label>
                <Select
                  value={localAISettings.model}
                  onValueChange={(value) => handleAISettingChange('model', value)}
                >
                  <SelectTrigger>
                    <SelectValue placeholder="选择 AI 模型" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="Qwen/Qwen2.5-7B-Instruct">Qwen2.5-7B-Instruct (免费)</SelectItem>
                    <SelectItem value="THUDM/glm-4-9b-chat">GLM-4-9B-Chat (免费)</SelectItem>
                    <SelectItem value="internlm/internlm2_5-7b-chat">InternLM2.5-7B-Chat (免费)</SelectItem>
                    <SelectItem value="01-ai/Yi-1.5-9B-Chat-16K">Yi-1.5-9B-Chat (免费)</SelectItem>
                    <SelectItem value="deepseek-ai/DeepSeek-V2.5">DeepSeek-V2.5 (免费)</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <Button 
                onClick={saveAISettings}
                disabled={updateAISettings.isPending}
                className="w-full"
              >
                {updateAISettings.isPending ? (
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                ) : (
                  <Save className="mr-2 h-4 w-4" />
                )}
                保存 AI 设置
              </Button>
            </CardContent>
          </Card>

          {/* Backup */}
          <Card className="bg-card/50 border-border/50">
            <CardHeader>
              <CardTitle className="text-base flex items-center gap-2">
                <Database className="h-4 w-4" />
                备份
              </CardTitle>
              <CardDescription>自动备份设置</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="flex items-center justify-between">
                <div>
                  <Label>自动备份</Label>
                  <p className="text-sm text-muted-foreground">定期自动备份工作流和设置</p>
                </div>
                <Switch
                  checked={settings?.auto_backup_enabled ?? true}
                  onCheckedChange={(checked) => handleSettingChange('auto_backup_enabled', checked)}
                />
              </div>
              <div className="flex items-center justify-between">
                <div>
                  <Label>备份间隔</Label>
                  <p className="text-sm text-muted-foreground">自动备份的时间间隔（小时）</p>
                </div>
                <Input
                  type="number"
                  className="w-24"
                  value={settings?.backup_interval_hours ?? 24}
                  onChange={(e) => handleSettingChange('backup_interval_hours', parseInt(e.target.value))}
                />
              </div>
              <div className="flex items-center justify-between">
                <div>
                  <Label>最大备份数</Label>
                  <p className="text-sm text-muted-foreground">保留的最大备份数量</p>
                </div>
                <Input
                  type="number"
                  className="w-24"
                  value={settings?.max_backup_count ?? 10}
                  onChange={(e) => handleSettingChange('max_backup_count', parseInt(e.target.value))}
                />
              </div>
            </CardContent>
          </Card>
        </div>

        {/* Right Column */}
        <div className="space-y-6">
          {/* Appearance */}
          <Card className="bg-card/50 border-border/50">
            <CardHeader>
              <CardTitle className="text-base flex items-center gap-2">
                <Palette className="h-4 w-4" />
                外观
              </CardTitle>
              <CardDescription>自定义应用外观和主题</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="flex items-center justify-between">
                <div>
                  <Label>主题</Label>
                  <p className="text-sm text-muted-foreground">选择应用主题</p>
                </div>
                <div className="flex items-center gap-2">
                  <Button
                    variant={theme === 'light' ? 'default' : 'outline'}
                    size="sm"
                    onClick={() => setTheme('light')}
                  >
                    浅色
                  </Button>
                  <Button
                    variant={theme === 'dark' ? 'default' : 'outline'}
                    size="sm"
                    onClick={() => setTheme('dark')}
                  >
                    深色
                  </Button>
                  <Button
                    variant={theme === 'system' ? 'default' : 'outline'}
                    size="sm"
                    onClick={() => setTheme('system')}
                  >
                    跟随系统
                  </Button>
                </div>
              </div>
            </CardContent>
          </Card>

          {/* Notifications */}
          <Card className="bg-card/50 border-border/50">
            <CardHeader>
              <CardTitle className="text-base flex items-center gap-2">
                <Bell className="h-4 w-4" />
                通知
              </CardTitle>
              <CardDescription>配置通知和提醒</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="flex items-center justify-between">
                <div>
                  <Label>启用通知</Label>
                  <p className="text-sm text-muted-foreground">任务完成时显示通知</p>
                </div>
                <Switch
                  checked={settings?.notification_enabled ?? true}
                  onCheckedChange={(checked) => handleSettingChange('notification_enabled', checked)}
                />
              </div>
              <div className="flex items-center justify-between">
                <div>
                  <Label>声音提醒</Label>
                  <p className="text-sm text-muted-foreground">播放提示音</p>
                </div>
                <Switch
                  checked={settings?.sound_enabled ?? true}
                  onCheckedChange={(checked) => handleSettingChange('sound_enabled', checked)}
                />
              </div>
            </CardContent>
          </Card>

          {/* Storage */}
          <Card className="bg-card/50 border-border/50">
            <CardHeader>
              <CardTitle className="text-base flex items-center gap-2">
                <HardDrive className="h-4 w-4" />
                存储
              </CardTitle>
              <CardDescription>管理存储空间</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid grid-cols-2 gap-3">
                <div className="p-3 rounded-lg bg-muted/50">
                  <p className="text-xs text-muted-foreground">图片存储</p>
                  <p className="text-lg font-bold">{formatSize(storageStats?.images_size || 0)}</p>
                  <p className="text-xs text-muted-foreground">{storageStats?.images_count || 0} 张</p>
                </div>
                <div className="p-3 rounded-lg bg-muted/50">
                  <p className="text-xs text-muted-foreground">缓存</p>
                  <p className="text-lg font-bold">{formatSize(storageStats?.cache_size || 0)}</p>
                </div>
                <div className="p-3 rounded-lg bg-muted/50">
                  <p className="text-xs text-muted-foreground">临时文件</p>
                  <p className="text-lg font-bold">{formatSize(storageStats?.temp_size || 0)}</p>
                </div>
                <div className="p-3 rounded-lg bg-muted/50">
                  <p className="text-xs text-muted-foreground">备份</p>
                  <p className="text-lg font-bold">{formatSize(storageStats?.backup_size || 0)}</p>
                </div>
              </div>
              <div className="p-3 rounded-lg bg-primary/10 border border-primary/20">
                <p className="text-xs text-muted-foreground">总存储空间</p>
                <p className="text-xl font-bold text-primary">{formatSize(storageStats?.total_size || 0)}</p>
              </div>
              <div className="flex items-center gap-2">
                <Button 
                  variant="outline" 
                  size="sm"
                  className="flex-1"
                  onClick={() => cleanupTemp.mutate()}
                  disabled={cleanupTemp.isPending}
                >
                  {cleanupTemp.isPending ? (
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  ) : (
                    <Trash2 className="mr-2 h-4 w-4" />
                  )}
                  清理临时文件
                </Button>
                <Button 
                  variant="outline" 
                  size="sm"
                  className="flex-1"
                  onClick={() => cleanupCache.mutate()}
                  disabled={cleanupCache.isPending}
                >
                  {cleanupCache.isPending ? (
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  ) : (
                    <RefreshCw className="mr-2 h-4 w-4" />
                  )}
                  清理缓存
                </Button>
              </div>
            </CardContent>
          </Card>
        </div>
      </div>

      {/* Save Button */}
      <div className="flex justify-end">
        <Button disabled={updateSettings.isPending}>
          {updateSettings.isPending ? (
            <Loader2 className="mr-2 h-4 w-4 animate-spin" />
          ) : (
            <Save className="mr-2 h-4 w-4" />
          )}
          保存设置
        </Button>
      </div>
    </div>
  )
}
