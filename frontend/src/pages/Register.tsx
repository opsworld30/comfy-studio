/**
 * 注册页面
 */
import { useState, useEffect } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import { useAuthStore } from '@/stores/auth'
import { getSystemSettings } from '@/lib/api/settings'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from '@/components/ui/card'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Loader2, UserPlus } from 'lucide-react'

export default function Register() {
  const navigate = useNavigate()
  const { register, isLoading, error, clearError } = useAuthStore()
  const [allowRegistration, setAllowRegistration] = useState(true)
  
  // 检查是否允许注册
  useEffect(() => {
    const checkRegistration = async () => {
      try {
        const settings = await getSystemSettings()
        if (!settings.allow_registration) {
          setAllowRegistration(false)
          // 如果不允许注册，跳转到登录页
          navigate('/login')
        }
      } catch (error) {
        // 获取失败时默认允许
      }
    }
    checkRegistration()
  }, [navigate])
  
  const [formData, setFormData] = useState({
    username: '',
    email: '',
    password: '',
    confirmPassword: '',
    fullName: '',
  })
  
  const [validationError, setValidationError] = useState('')

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setFormData({
      ...formData,
      [e.target.name]: e.target.value,
    })
    setValidationError('')
    clearError()
  }

  const validateForm = () => {
    if (formData.username.length < 3) {
      setValidationError('用户名至少需要3个字符')
      return false
    }
    
    if (!/^[a-zA-Z0-9_-]+$/.test(formData.username)) {
      setValidationError('用户名只能包含字母、数字、下划线和连字符')
      return false
    }
    
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(formData.email)) {
      setValidationError('请输入有效的邮箱地址')
      return false
    }
    
    if (formData.password.length < 6) {
      setValidationError('密码至少需要6个字符')
      return false
    }
    
    if (formData.password !== formData.confirmPassword) {
      setValidationError('两次输入的密码不一致')
      return false
    }
    
    return true
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    
    if (!validateForm()) {
      return
    }
    
    try {
      await register(
        formData.username,
        formData.email,
        formData.password,
        formData.fullName || undefined
      )
      navigate('/')
    } catch (error) {
      // 错误已在 store 中处理
    }
  }

  const displayError = validationError || error

  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-background to-muted p-4">
      <Card className="w-full max-w-md">
        <CardHeader className="space-y-1">
          <div className="flex items-center justify-center mb-4">
            <div className="w-12 h-12 rounded-lg bg-primary flex items-center justify-center">
              <UserPlus className="w-6 h-6 text-primary-foreground" />
            </div>
          </div>
          <CardTitle className="text-2xl text-center">创建账号</CardTitle>
          <CardDescription className="text-center">
            注册 ComfyUI Studio 账号
          </CardDescription>
        </CardHeader>
        
        <form onSubmit={handleSubmit}>
          <CardContent className="space-y-4">
            {displayError && (
              <Alert variant="destructive">
                <AlertDescription>{displayError}</AlertDescription>
              </Alert>
            )}
            
            <div className="space-y-2">
              <Label htmlFor="username">用户名 *</Label>
              <Input
                id="username"
                name="username"
                type="text"
                placeholder="3-50个字符，仅限字母数字"
                value={formData.username}
                onChange={handleChange}
                required
                disabled={isLoading}
              />
            </div>
            
            <div className="space-y-2">
              <Label htmlFor="email">邮箱 *</Label>
              <Input
                id="email"
                name="email"
                type="email"
                placeholder="your@email.com"
                value={formData.email}
                onChange={handleChange}
                required
                disabled={isLoading}
              />
            </div>
            
            <div className="space-y-2">
              <Label htmlFor="fullName">姓名（可选）</Label>
              <Input
                id="fullName"
                name="fullName"
                type="text"
                placeholder="请输入您的姓名"
                value={formData.fullName}
                onChange={handleChange}
                disabled={isLoading}
              />
            </div>
            
            <div className="space-y-2">
              <Label htmlFor="password">密码 *</Label>
              <Input
                id="password"
                name="password"
                type="password"
                placeholder="至少6个字符"
                value={formData.password}
                onChange={handleChange}
                required
                disabled={isLoading}
              />
            </div>
            
            <div className="space-y-2">
              <Label htmlFor="confirmPassword">确认密码 *</Label>
              <Input
                id="confirmPassword"
                name="confirmPassword"
                type="password"
                placeholder="再次输入密码"
                value={formData.confirmPassword}
                onChange={handleChange}
                required
                disabled={isLoading}
              />
            </div>
          </CardContent>
          
          <CardFooter className="flex flex-col space-y-4">
            <Button
              type="submit"
              className="w-full"
              disabled={isLoading}
            >
              {isLoading ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  注册中...
                </>
              ) : (
                '注册'
              )}
            </Button>
            
            <div className="text-sm text-center text-muted-foreground">
              已有账号？{' '}
              <Link to="/login" className="text-primary hover:underline">
                立即登录
              </Link>
            </div>
          </CardFooter>
        </form>
      </Card>
    </div>
  )
}
