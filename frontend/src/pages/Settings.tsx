import { useState, useEffect } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Switch } from '@/components/ui/switch'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
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
  Shield,
  UserPlus,
} from 'lucide-react'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { settingsApi, type AppSettings, type PageModuleSettings } from '@/lib/api'
import { getSystemSettings, updateSystemSettings, type SystemSettings } from '@/lib/api/settings'
import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from '@/components/ui/accordion'
import { useThemeStore } from '@/stores/theme'

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

  // 获取系统设置
  const { data: systemSettings } = useQuery({
    queryKey: ['settings', 'system'],
    queryFn: getSystemSettings,
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

  // 更新系统设置
  const updateSystem = useMutation({
    mutationFn: (data: Partial<SystemSettings>) => updateSystemSettings(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['settings', 'system'] })
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

      {/* Tabs Layout */}
      <Tabs defaultValue="general" className="w-full">
        <TabsList className="grid w-full grid-cols-4 lg:w-[600px]">
          <TabsTrigger value="general" className="flex items-center gap-2">
            <Palette className="h-4 w-4" />
            <span className="hidden sm:inline">通用</span>
          </TabsTrigger>
          <TabsTrigger value="modules" className="flex items-center gap-2">
            <LayoutGrid className="h-4 w-4" />
            <span className="hidden sm:inline">模块</span>
          </TabsTrigger>
          <TabsTrigger value="ai" className="flex items-center gap-2">
            <Brain className="h-4 w-4" />
            <span className="hidden sm:inline">AI</span>
          </TabsTrigger>
          <TabsTrigger value="system" className="flex items-center gap-2">
            <Shield className="h-4 w-4" />
            <span className="hidden sm:inline">系统</span>
          </TabsTrigger>
        </TabsList>

        {/* 通用设置 */}
        <TabsContent value="general" className="mt-6">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {/* 外观 */}
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

            {/* 通知 */}
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

            {/* 备份 */}
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

            {/* 存储 */}
            <Card className="bg-card/50 border-border/50">
              <CardHeader>
                <CardTitle className="text-base flex items-center gap-2">
                  <HardDrive className="h-4 w-4" />
                  存储管理
                </CardTitle>
                <CardDescription>查看和管理存储空间</CardDescription>
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
                    清理临时
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
        </TabsContent>

        {/* 模块设置 */}
        <TabsContent value="modules" className="mt-6">
          <Card className="bg-card/50 border-border/50">
            <CardHeader>
              <CardTitle className="text-base flex items-center gap-2">
                <LayoutGrid className="h-4 w-4" />
                页面与模块
              </CardTitle>
              <CardDescription>控制页面和组件的显示/隐藏</CardDescription>
            </CardHeader>
            <CardContent>
              <Accordion type="multiple" className="w-full" defaultValue={['pages']}>
                <AccordionItem value="pages">
                  <AccordionTrigger className="text-sm font-medium">侧边栏页面</AccordionTrigger>
                  <AccordionContent>
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4 pt-2">
                      {[
                        { key: 'showDashboard', label: '工作流', desc: '工作流管理页面' },
                        { key: 'showBatch', label: '任务队列', desc: '批量任务管理' },
                        { key: 'showGallery', label: '画廊', desc: '图片画廊页面' },
                        // { key: 'showModels', label: '模型库', desc: '模型管理页面' },
                        { key: 'showPrompts', label: '提示词', desc: '提示词管理页面' },
                        { key: 'showMonitor', label: '监控', desc: '系统监控页面' },
                        // { key: 'showMarket', label: '市场', desc: '工作流市场' },
                      ].map((item) => (
                        <div key={item.key} className="flex items-center justify-between p-3 rounded-lg bg-muted/30">
                          <div>
                            <Label className="text-sm">{item.label}</Label>
                            <p className="text-xs text-muted-foreground">{item.desc}</p>
                          </div>
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
                  <AccordionTrigger className="text-sm font-medium">仪表盘模块</AccordionTrigger>
                  <AccordionContent>
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4 pt-2">
                      {[
                        { key: 'showQuickActions', label: '快捷操作', desc: '常用操作入口' },
                        { key: 'showRecentImages', label: '最近生成', desc: '最近生成的图片' },
                        { key: 'showSystemStatus', label: '系统状态', desc: '服务器状态信息' },
                        { key: 'showStatistics', label: '统计信息', desc: '使用统计数据' },
                      ].map((item) => (
                        <div key={item.key} className="flex items-center justify-between p-3 rounded-lg bg-muted/30">
                          <div>
                            <Label className="text-sm">{item.label}</Label>
                            <p className="text-xs text-muted-foreground">{item.desc}</p>
                          </div>
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
                  <AccordionTrigger className="text-sm font-medium">图片画廊模块</AccordionTrigger>
                  <AccordionContent>
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4 pt-2">
                      {[
                        { key: 'showSearchBar', label: '搜索栏', desc: '图片搜索功能' },
                        { key: 'showLayoutToggle', label: '布局切换', desc: '网格/列表切换' },
                        { key: 'showCategories', label: '智能分类', desc: '自动分类筛选' },
                        { key: 'showFavorites', label: '收藏筛选', desc: '收藏图片筛选' },
                      ].map((item) => (
                        <div key={item.key} className="flex items-center justify-between p-3 rounded-lg bg-muted/30">
                          <div>
                            <Label className="text-sm">{item.label}</Label>
                            <p className="text-xs text-muted-foreground">{item.desc}</p>
                          </div>
                          <Switch
                            checked={pageModules?.gallery?.[item.key] ?? true}
                            onCheckedChange={(checked) => handleModuleChange('gallery', item.key, checked)}
                          />
                        </div>
                      ))}
                    </div>
                  </AccordionContent>
                </AccordionItem>

                <AccordionItem value="other">
                  <AccordionTrigger className="text-sm font-medium">其他模块</AccordionTrigger>
                  <AccordionContent>
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4 pt-2">
                      {[
                        // { section: 'models', key: 'showLocalModels', label: '本地模型', desc: '本地模型管理' },
                        // { section: 'models', key: 'showCivitai', label: 'Civitai', desc: 'Civitai 模型库' },
                        { section: 'prompts', key: 'showCategories', label: '提示词分类', desc: '分类筛选功能' },
                        { section: 'prompts', key: 'showAIGenerate', label: 'AI 生成', desc: 'AI 生成提示词' },
                      ].map((item) => (
                        <div key={`${item.section}-${item.key}`} className="flex items-center justify-between p-3 rounded-lg bg-muted/30">
                          <div>
                            <Label className="text-sm">{item.label}</Label>
                            <p className="text-xs text-muted-foreground">{item.desc}</p>
                          </div>
                          <Switch
                            checked={pageModules?.[item.section as keyof PageModuleSettings]?.[item.key] ?? true}
                            onCheckedChange={(checked) => handleModuleChange(item.section as keyof PageModuleSettings, item.key, checked)}
                          />
                        </div>
                      ))}
                    </div>
                  </AccordionContent>
                </AccordionItem>
              </Accordion>
            </CardContent>
          </Card>
        </TabsContent>

        {/* AI 设置 */}
        <TabsContent value="ai" className="mt-6">
          <Card className="bg-card/50 border-border/50 max-w-2xl">
            <CardHeader>
              <CardTitle className="text-base flex items-center gap-2">
                <Brain className="h-4 w-4" />
                AI 服务配置
              </CardTitle>
              <CardDescription>配置 AI 服务用于 Prompt 优化和内容生成</CardDescription>
            </CardHeader>
            <CardContent className="space-y-6">
              <div className="flex items-center justify-between p-4 rounded-lg bg-muted/30">
                <div>
                  <Label className="text-base">启用 AI 功能</Label>
                  <p className="text-sm text-muted-foreground">开启后可使用 AI 生成和优化提示词</p>
                </div>
                <Switch
                  checked={localAISettings.enabled}
                  onCheckedChange={(checked) => handleAISettingChange('enabled', checked)}
                />
              </div>

              <div className="space-y-4">
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
        </TabsContent>

        {/* 系统设置 */}
        <TabsContent value="system" className="mt-6">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {/* 用户注册 */}
            <Card className="bg-card/50 border-border/50">
              <CardHeader>
                <CardTitle className="text-base flex items-center gap-2">
                  <UserPlus className="h-4 w-4" />
                  用户注册
                </CardTitle>
                <CardDescription>管理用户注册权限</CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="flex items-center justify-between p-4 rounded-lg bg-muted/30">
                  <div className="space-y-0.5">
                    <Label className="text-sm">允许新用户注册</Label>
                    <p className="text-xs text-muted-foreground">
                      关闭后，登录页面将隐藏注册入口，注册接口也将被禁用
                    </p>
                  </div>
                  <Switch
                    checked={systemSettings?.allow_registration ?? true}
                    onCheckedChange={(checked) => updateSystem.mutate({ allow_registration: checked })}
                  />
                </div>
              </CardContent>
            </Card>

            {/* 安全设置 */}
            <Card className="bg-card/50 border-border/50">
              <CardHeader>
                <CardTitle className="text-base flex items-center gap-2">
                  <Shield className="h-4 w-4" />
                  安全设置
                </CardTitle>
                <CardDescription>系统安全相关配置</CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="p-4 rounded-lg bg-muted/30">
                  <p className="text-sm text-muted-foreground">
                    更多安全设置即将推出，包括：
                  </p>
                  <ul className="mt-2 text-xs text-muted-foreground list-disc list-inside space-y-1">
                    <li>登录失败锁定</li>
                    <li>密码强度要求</li>
                    <li>会话超时设置</li>
                    <li>IP 白名单</li>
                  </ul>
                </div>
              </CardContent>
            </Card>
          </div>
        </TabsContent>
      </Tabs>
    </div>
  )
}
