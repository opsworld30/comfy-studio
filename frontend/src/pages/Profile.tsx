/**
 * 个人设置页面
 */
import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuthStore } from '@/stores/auth'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Avatar, AvatarFallback, AvatarImage } from '@/components/ui/avatar'
import { Separator } from '@/components/ui/separator'
import { toast } from 'sonner'
import { 
  User, 
  Mail, 
  Lock, 
  Shield, 
  Calendar,
  Loader2,
  Save,
  KeyRound
} from 'lucide-react'

export default function Profile() {
  const navigate = useNavigate()
  const { user, updateUser, changePassword, logout, isLoading } = useAuthStore()
  
  // 个人信息表单
  const [profileForm, setProfileForm] = useState({
    email: user?.email || '',
    full_name: user?.full_name || '',
    avatar: user?.avatar || '',
  })
  
  // 修改密码表单
  const [passwordForm, setPasswordForm] = useState({
    oldPassword: '',
    newPassword: '',
    confirmPassword: '',
  })
  
  const [profileError, setProfileError] = useState('')
  const [passwordError, setPasswordError] = useState('')
  const [profileSuccess, setProfileSuccess] = useState(false)

  // 更新个人信息
  const handleUpdateProfile = async (e: React.FormEvent) => {
    e.preventDefault()
    setProfileError('')
    setProfileSuccess(false)
    
    try {
      await updateUser({
        email: profileForm.email,
        full_name: profileForm.full_name,
        avatar: profileForm.avatar,
      })
      setProfileSuccess(true)
      toast.success('个人信息更新成功')
    } catch (error: any) {
      const errorMessage = error.response?.data?.detail || '更新失败'
      setProfileError(errorMessage)
      toast.error(errorMessage)
    }
  }

  // 修改密码
  const handleChangePassword = async (e: React.FormEvent) => {
    e.preventDefault()
    setPasswordError('')
    
    // 验证
    if (passwordForm.newPassword.length < 6) {
      setPasswordError('新密码至少需要6个字符')
      return
    }
    
    if (passwordForm.newPassword !== passwordForm.confirmPassword) {
      setPasswordError('两次输入的密码不一致')
      return
    }
    
    try {
      await changePassword(passwordForm.oldPassword, passwordForm.newPassword)
      toast.success('密码修改成功，请重新登录')
      // 清空表单
      setPasswordForm({
        oldPassword: '',
        newPassword: '',
        confirmPassword: '',
      })
      // 密码修改成功后自动注销，跳转到登录页
      setTimeout(async () => {
        await logout()
        navigate('/login')
      }, 1500)
    } catch (error: any) {
      const errorMessage = error.response?.data?.detail || '修改密码失败'
      setPasswordError(errorMessage)
      toast.error(errorMessage)
    }
  }

  // 获取用户名首字母
  const getInitials = (name: string) => {
    return name?.charAt(0).toUpperCase() || 'U'
  }

  // 格式化日期
  const formatDate = (dateString: string | null) => {
    if (!dateString) return '从未'
    return new Date(dateString).toLocaleString('zh-CN')
  }

  return (
    <div className="space-y-6">
      {/* 页面标题 */}
      <div>
        <h1 className="text-2xl font-bold">个人设置</h1>
        <p className="text-muted-foreground">管理您的账户信息和安全设置</p>
      </div>

      <div className="grid gap-6 md:grid-cols-3">
        {/* 左侧：用户概览卡片 */}
        <Card className="md:col-span-1">
          <CardHeader className="text-center">
            <div className="flex justify-center mb-4">
              <Avatar className="h-24 w-24">
                <AvatarImage src={user?.avatar} alt={user?.username} />
                <AvatarFallback className="text-2xl bg-gradient-to-br from-blue-500 to-purple-500 text-white">
                  {getInitials(user?.full_name || user?.username || '')}
                </AvatarFallback>
              </Avatar>
            </div>
            <CardTitle>{user?.full_name || user?.username}</CardTitle>
            <CardDescription>@{user?.username}</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <Separator />
            <div className="space-y-3 text-sm">
              <div className="flex items-center gap-2 text-muted-foreground">
                <Mail className="h-4 w-4" />
                <span>{user?.email}</span>
              </div>
              <div className="flex items-center gap-2 text-muted-foreground">
                <Shield className="h-4 w-4" />
                <span>{user?.is_superuser ? '管理员' : '普通用户'}</span>
              </div>
              <div className="flex items-center gap-2 text-muted-foreground">
                <Calendar className="h-4 w-4" />
                <span>注册于 {formatDate(user?.created_at || null)}</span>
              </div>
              <div className="flex items-center gap-2 text-muted-foreground">
                <Calendar className="h-4 w-4" />
                <span>上次登录 {formatDate(user?.last_login || null)}</span>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* 右侧：设置标签页 */}
        <Card className="md:col-span-2">
          <Tabs defaultValue="profile" className="w-full">
            <CardHeader>
              <TabsList className="grid w-full grid-cols-2">
                <TabsTrigger value="profile" className="flex items-center gap-2">
                  <User className="h-4 w-4" />
                  个人信息
                </TabsTrigger>
                <TabsTrigger value="security" className="flex items-center gap-2">
                  <Lock className="h-4 w-4" />
                  安全设置
                </TabsTrigger>
              </TabsList>
            </CardHeader>
            
            <CardContent>
              {/* 个人信息标签 */}
              <TabsContent value="profile" className="mt-0">
                <form onSubmit={handleUpdateProfile} className="space-y-4">
                  {profileError && (
                    <Alert variant="destructive">
                      <AlertDescription>{profileError}</AlertDescription>
                    </Alert>
                  )}
                  
                  {profileSuccess && (
                    <Alert className="border-green-500 text-green-500">
                      <AlertDescription>个人信息更新成功！</AlertDescription>
                    </Alert>
                  )}
                  
                  <div className="space-y-2">
                    <Label htmlFor="username">用户名</Label>
                    <Input
                      id="username"
                      value={user?.username || ''}
                      disabled
                      className="bg-muted"
                    />
                    <p className="text-xs text-muted-foreground">用户名不可修改</p>
                  </div>
                  
                  <div className="space-y-2">
                    <Label htmlFor="email">邮箱</Label>
                    <Input
                      id="email"
                      type="email"
                      value={profileForm.email}
                      onChange={(e) => setProfileForm({ ...profileForm, email: e.target.value })}
                      placeholder="your@email.com"
                    />
                  </div>
                  
                  <div className="space-y-2">
                    <Label htmlFor="full_name">姓名</Label>
                    <Input
                      id="full_name"
                      value={profileForm.full_name}
                      onChange={(e) => setProfileForm({ ...profileForm, full_name: e.target.value })}
                      placeholder="请输入您的姓名"
                    />
                  </div>
                  
                  <div className="space-y-2">
                    <Label htmlFor="avatar">头像 URL</Label>
                    <Input
                      id="avatar"
                      value={profileForm.avatar}
                      onChange={(e) => setProfileForm({ ...profileForm, avatar: e.target.value })}
                      placeholder="https://example.com/avatar.jpg"
                    />
                    <p className="text-xs text-muted-foreground">输入头像图片的URL地址</p>
                  </div>
                  
                  <Button type="submit" disabled={isLoading} className="w-full">
                    {isLoading ? (
                      <>
                        <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                        保存中...
                      </>
                    ) : (
                      <>
                        <Save className="mr-2 h-4 w-4" />
                        保存更改
                      </>
                    )}
                  </Button>
                </form>
              </TabsContent>
              
              {/* 安全设置标签 */}
              <TabsContent value="security" className="mt-0">
                <form onSubmit={handleChangePassword} className="space-y-4">
                  <div className="flex items-center gap-2 mb-4">
                    <KeyRound className="h-5 w-5 text-muted-foreground" />
                    <h3 className="font-medium">修改密码</h3>
                  </div>
                  
                  {passwordError && (
                    <Alert variant="destructive">
                      <AlertDescription>{passwordError}</AlertDescription>
                    </Alert>
                  )}
                  
                  <div className="space-y-2">
                    <Label htmlFor="oldPassword">当前密码</Label>
                    <Input
                      id="oldPassword"
                      type="password"
                      value={passwordForm.oldPassword}
                      onChange={(e) => setPasswordForm({ ...passwordForm, oldPassword: e.target.value })}
                      placeholder="请输入当前密码"
                      required
                    />
                  </div>
                  
                  <div className="space-y-2">
                    <Label htmlFor="newPassword">新密码</Label>
                    <Input
                      id="newPassword"
                      type="password"
                      value={passwordForm.newPassword}
                      onChange={(e) => setPasswordForm({ ...passwordForm, newPassword: e.target.value })}
                      placeholder="至少6个字符"
                      required
                    />
                  </div>
                  
                  <div className="space-y-2">
                    <Label htmlFor="confirmPassword">确认新密码</Label>
                    <Input
                      id="confirmPassword"
                      type="password"
                      value={passwordForm.confirmPassword}
                      onChange={(e) => setPasswordForm({ ...passwordForm, confirmPassword: e.target.value })}
                      placeholder="再次输入新密码"
                      required
                    />
                  </div>
                  
                  <Button type="submit" disabled={isLoading} className="w-full">
                    {isLoading ? (
                      <>
                        <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                        修改中...
                      </>
                    ) : (
                      <>
                        <Lock className="mr-2 h-4 w-4" />
                        修改密码
                      </>
                    )}
                  </Button>
                </form>
              </TabsContent>
            </CardContent>
          </Tabs>
        </Card>
      </div>
    </div>
  )
}
