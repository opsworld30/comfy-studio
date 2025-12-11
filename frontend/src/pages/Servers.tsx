import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useCircuitBreaker } from '@/hooks/useCircuitBreaker'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Input } from '@/components/ui/input'
import { Progress } from '@/components/ui/progress'
import {
  Server,
  Plus,
  RefreshCw,
  Trash2,
  Settings,
  CheckCircle,
  XCircle,
  Loader2,
  Wifi,
  WifiOff,
  Cpu,
  Star,
} from 'lucide-react'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from '@/components/ui/dialog'
import { Label } from '@/components/ui/label'
import { serversApi, type ComfyUIServer } from '@/lib/api'

export default function Servers() {
  const queryClient = useQueryClient()
  const [showAddDialog, setShowAddDialog] = useState(false)
  const [showEditDialog, setShowEditDialog] = useState(false)
  const [showSetDefaultDialog, setShowSetDefaultDialog] = useState(false)
  const [showDeleteDialog, setShowDeleteDialog] = useState(false)
  const [editingServer, setEditingServer] = useState<ComfyUIServer | null>(null)
  const [targetServer, setTargetServer] = useState<ComfyUIServer | null>(null)
  const [newServerName, setNewServerName] = useState('')
  const [newServerUrl, setNewServerUrl] = useState('')

  // 熔断器：控制轮询，防止后端离线时无限重试
  const { createRefetchInterval, shouldEnableQuery, wrapQueryFn } = useCircuitBreaker()

  // 获取服务器列表（带熔断器保护）
  const { data: servers = [], isLoading } = useQuery({
    queryKey: ['servers'],
    queryFn: wrapQueryFn(async () => {
      const { data } = await serversApi.list()
      return data
    }),
    refetchInterval: createRefetchInterval(10000),
    staleTime: 3000, // 3秒内数据视为新鲜，与后端缓存同步
    gcTime: 60000, // 缓存保留60秒
    enabled: shouldEnableQuery(),
    retry: 1,
    // 使用上次成功的数据作为占位，避免闪烁
    placeholderData: (previousData) => previousData,
  })

  // 添加服务器
  const addServer = useMutation({
    mutationFn: (data: { name: string; url: string }) => serversApi.create(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['servers'] })
      setShowAddDialog(false)
      setNewServerName('')
      setNewServerUrl('')
    },
  })

  // 删除服务器
  const deleteServer = useMutation({
    mutationFn: (id: number) => serversApi.delete(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['servers'] }),
  })

  // 检查服务器状态
  const checkServer = useMutation({
    mutationFn: (id: number) => serversApi.check(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['servers'] }),
  })

  // 设为默认
  const setDefault = useMutation({
    mutationFn: (id: number) => serversApi.setDefault(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['servers'] })
      setShowSetDefaultDialog(false)
      setTargetServer(null)
    },
  })

  // 打开设为默认弹窗
  const handleSetDefault = (server: ComfyUIServer) => {
    setTargetServer(server)
    setShowSetDefaultDialog(true)
  }

  // 打开删除弹窗
  const handleDelete = (server: ComfyUIServer) => {
    setTargetServer(server)
    setShowDeleteDialog(true)
  }

  // 确认删除
  const confirmDelete = () => {
    if (targetServer) {
      deleteServer.mutate(targetServer.id, {
        onSuccess: () => {
          setShowDeleteDialog(false)
          setTargetServer(null)
        }
      })
    }
  }

  // 更新服务器
  const updateServer = useMutation({
    mutationFn: ({ id, data }: { id: number; data: Partial<{ name: string; url: string }> }) => 
      serversApi.update(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['servers'] })
      setShowEditDialog(false)
      setEditingServer(null)
    },
  })

  const handleEditServer = (server: ComfyUIServer) => {
    setEditingServer(server)
    setNewServerName(server.name)
    setNewServerUrl(server.url)
    setShowEditDialog(true)
  }

  const handleUpdateServer = () => {
    if (editingServer && newServerName && newServerUrl) {
      updateServer.mutate({ 
        id: editingServer.id, 
        data: { name: newServerName, url: newServerUrl } 
      })
    }
  }

  const handleAddServer = () => {
    if (newServerName && newServerUrl) {
      addServer.mutate({ name: newServerName, url: newServerUrl })
    }
  }

  const getStatusBadge = (status: string) => {
    switch (status) {
      case 'online':
        return <Badge className="bg-green-500">在线</Badge>
      case 'offline':
        return <Badge variant="secondary">离线</Badge>
      case 'error':
        return <Badge variant="destructive">错误</Badge>
      default:
        return <Badge variant="secondary">{status}</Badge>
    }
  }

  // 统计
  const onlineCount = (servers || []).filter((s: ComfyUIServer) => s.status === 'online').length
  const totalVram = (servers || []).reduce((acc: number, s: ComfyUIServer) => {
    return acc + (s.gpu_info?.vram_total || 0) / (1024 * 1024 * 1024)
  }, 0)

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
        <h2 className="text-lg font-medium">服务器管理</h2>
        <div className="flex items-center gap-2">
          <Button 
            variant="outline" 
            size="sm"
            onClick={() => queryClient.invalidateQueries({ queryKey: ['servers'] })}
          >
            <RefreshCw className="mr-2 h-4 w-4" />
            刷新
          </Button>
          <Button size="sm" onClick={() => setShowAddDialog(true)}>
            <Plus className="mr-2 h-4 w-4" />
            添加服务器
          </Button>
        </div>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-4 gap-4">
        <Card className="bg-card/50 border-border/50">
          <CardContent className="pt-6">
            <div className="flex items-center gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-full bg-blue-500/10">
                <Server className="h-5 w-5 text-blue-500" />
              </div>
              <div>
                <p className="text-2xl font-bold">{(servers || []).length}</p>
                <p className="text-sm text-muted-foreground">总服务器</p>
              </div>
            </div>
          </CardContent>
        </Card>
        <Card className="bg-card/50 border-border/50">
          <CardContent className="pt-6">
            <div className="flex items-center gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-full bg-green-500/10">
                <CheckCircle className="h-5 w-5 text-green-500" />
              </div>
              <div>
                <p className="text-2xl font-bold text-green-500">{onlineCount}</p>
                <p className="text-sm text-muted-foreground">在线</p>
              </div>
            </div>
          </CardContent>
        </Card>
        <Card className="bg-card/50 border-border/50">
          <CardContent className="pt-6">
            <div className="flex items-center gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-full bg-red-500/10">
                <XCircle className="h-5 w-5 text-red-500" />
              </div>
              <div>
                <p className="text-2xl font-bold text-red-500">{(servers || []).length - onlineCount}</p>
                <p className="text-sm text-muted-foreground">离线</p>
              </div>
            </div>
          </CardContent>
        </Card>
        <Card className="bg-card/50 border-border/50">
          <CardContent className="pt-6">
            <div className="flex items-center gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-full bg-purple-500/10">
                <Cpu className="h-5 w-5 text-purple-500" />
              </div>
              <div>
                <p className="text-2xl font-bold">{totalVram.toFixed(0)}GB</p>
                <p className="text-sm text-muted-foreground">总显存</p>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Server List */}
      <Card className="bg-card/50 border-border/50">
        <CardHeader>
          <CardTitle className="text-base">服务器列表</CardTitle>
        </CardHeader>
        <CardContent>
          {(servers || []).length === 0 ? (
            <div className="flex flex-col items-center justify-center py-12 text-muted-foreground">
              <Server className="h-12 w-12 mb-4" />
              <p>暂无服务器</p>
              <Button 
                variant="outline" 
                size="sm" 
                className="mt-4"
                onClick={() => setShowAddDialog(true)}
              >
                <Plus className="mr-2 h-4 w-4" />
                添加第一个服务器
              </Button>
            </div>
          ) : (
            <div className="space-y-4">
              {(servers || []).map((server: ComfyUIServer) => (
                <div 
                  key={server.id} 
                  className="flex items-center justify-between p-4 rounded-lg bg-muted/50 border border-border/50"
                >
                  <div className="flex items-center gap-4">
                    <div className={`flex h-10 w-10 items-center justify-center rounded-full ${
                      server.status === 'online' ? 'bg-green-500/10' : 'bg-muted'
                    }`}>
                      {server.status === 'online' ? (
                        <Wifi className="h-5 w-5 text-green-500" />
                      ) : (
                        <WifiOff className="h-5 w-5 text-muted-foreground" />
                      )}
                    </div>
                    <div>
                      <div className="flex items-center gap-2">
                        <span className="font-medium">{server.name}</span>
                        {server.is_default && (
                          <Star className="h-4 w-4 text-yellow-500 fill-yellow-500" />
                        )}
                        {getStatusBadge(server.status)}
                      </div>
                      <p className="text-sm text-muted-foreground">{server.url}</p>
                    </div>
                  </div>

                  {/* GPU Info */}
                  {server.gpu_info && server.status === 'online' && (
                    <div className="flex-1 max-w-xs mx-8">
                      <div className="flex items-center justify-between text-sm mb-1">
                        <span className="text-muted-foreground">{server.gpu_info.name}</span>
                        <span>
                          {(server.gpu_info.vram_used / (1024 * 1024 * 1024)).toFixed(1)} / 
                          {(server.gpu_info.vram_total / (1024 * 1024 * 1024)).toFixed(0)} GB
                        </span>
                      </div>
                      <Progress 
                        value={(server.gpu_info.vram_used / server.gpu_info.vram_total) * 100} 
                        className="h-2"
                      />
                    </div>
                  )}

                  {/* Queue */}
                  {server.queue_size !== undefined && server.status === 'online' && (
                    <div className="text-center px-4">
                      <p className="text-lg font-bold">{server.queue_size}</p>
                      <p className="text-xs text-muted-foreground">队列</p>
                    </div>
                  )}

                  {/* Actions */}
                  <div className="flex items-center gap-2">
                    {server.is_default ? (
                      <Badge className="bg-yellow-500/20 text-yellow-500 border-yellow-500/30">
                        <Star className="h-3 w-3 mr-1 fill-yellow-500" />
                        默认
                      </Badge>
                    ) : (
                      <Button 
                        variant="outline" 
                        size="sm"
                        onClick={() => handleSetDefault(server)}
                      >
                        设为默认
                      </Button>
                    )}
                    <Button 
                      variant="ghost" 
                      size="icon"
                      onClick={() => checkServer.mutate(server.id)}
                      disabled={checkServer.isPending}
                    >
                      {checkServer.isPending ? (
                        <Loader2 className="h-4 w-4 animate-spin" />
                      ) : (
                        <RefreshCw className="h-4 w-4" />
                      )}
                    </Button>
                    <Button 
                      variant="ghost" 
                      size="icon"
                      onClick={() => handleEditServer(server)}
                    >
                      <Settings className="h-4 w-4" />
                    </Button>
                    <Button 
                      variant="ghost" 
                      size="icon"
                      onClick={() => handleDelete(server)}
                      disabled={server.is_default}
                    >
                      <Trash2 className="h-4 w-4" />
                    </Button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Add Server Dialog */}
      <Dialog open={showAddDialog} onOpenChange={setShowAddDialog}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>添加服务器</DialogTitle>
          </DialogHeader>
          <div className="space-y-4 py-4">
            <div className="space-y-2">
              <Label htmlFor="name">服务器名称</Label>
              <Input
                id="name"
                placeholder="例如: 本地服务器"
                value={newServerName}
                onChange={(e) => setNewServerName(e.target.value)}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="url">服务器地址</Label>
              <Input
                id="url"
                placeholder="例如: http://127.0.0.1:8188"
                value={newServerUrl}
                onChange={(e) => setNewServerUrl(e.target.value)}
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowAddDialog(false)}>
              取消
            </Button>
            <Button 
              onClick={handleAddServer}
              disabled={!newServerName || !newServerUrl || addServer.isPending}
            >
              {addServer.isPending && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              添加
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Set Default Dialog */}
      <Dialog open={showSetDefaultDialog} onOpenChange={setShowSetDefaultDialog}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>设为默认服务器</DialogTitle>
          </DialogHeader>
          <div className="py-4">
            <p className="text-muted-foreground">
              确定要将 <span className="font-medium text-foreground">{targetServer?.name}</span> 设为默认服务器吗？
            </p>
            <p className="text-sm text-muted-foreground mt-2">
              设为默认后，所有工作流将优先使用此服务器执行。
            </p>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowSetDefaultDialog(false)}>
              取消
            </Button>
            <Button 
              onClick={() => targetServer && setDefault.mutate(targetServer.id)}
              disabled={setDefault.isPending}
            >
              {setDefault.isPending && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              确认设为默认
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Delete Confirm Dialog */}
      <Dialog open={showDeleteDialog} onOpenChange={setShowDeleteDialog}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>删除服务器</DialogTitle>
          </DialogHeader>
          <div className="py-4">
            <p className="text-muted-foreground">
              确定要删除服务器 <span className="font-medium text-foreground">{targetServer?.name}</span> 吗？
            </p>
            <p className="text-sm text-destructive mt-2">
              此操作不可撤销。
            </p>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowDeleteDialog(false)}>
              取消
            </Button>
            <Button 
              variant="destructive"
              onClick={confirmDelete}
              disabled={deleteServer.isPending}
            >
              {deleteServer.isPending && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              确认删除
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Edit Server Dialog */}
      <Dialog open={showEditDialog} onOpenChange={setShowEditDialog}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>编辑服务器</DialogTitle>
          </DialogHeader>
          <div className="space-y-4 py-4">
            <div className="space-y-2">
              <Label htmlFor="edit-name">服务器名称</Label>
              <Input
                id="edit-name"
                value={newServerName}
                onChange={(e) => setNewServerName(e.target.value)}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="edit-url">服务器地址</Label>
              <Input
                id="edit-url"
                value={newServerUrl}
                onChange={(e) => setNewServerUrl(e.target.value)}
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowEditDialog(false)}>
              取消
            </Button>
            <Button 
              onClick={handleUpdateServer}
              disabled={!newServerName || !newServerUrl || updateServer.isPending}
            >
              {updateServer.isPending && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              保存
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}
