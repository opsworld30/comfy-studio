/**
 * 登录页面
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
import { Loader2, LogIn } from 'lucide-react'

export default function Login() {
  const navigate = useNavigate()
  const { login, isLoading, error, clearError } = useAuthStore()
  
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [allowRegistration, setAllowRegistration] = useState(true)
  
  // 获取系统设置
  useEffect(() => {
    const fetchSettings = async () => {
      try {
        const settings = await getSystemSettings()
        setAllowRegistration(settings.allow_registration)
      } catch (error) {
        // 获取失败时默认允许注册
        setAllowRegistration(true)
      }
    }
    fetchSettings()
  }, [])

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    clearError()
    
    try {
      await login(username, password)
      navigate('/')
    } catch (error) {
      // 错误已在 store 中处理
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-background to-muted p-4">
      <Card className="w-full max-w-md">
        <CardHeader className="space-y-1">
          <div className="flex items-center justify-center mb-4">
            <div className="w-12 h-12 rounded-lg bg-primary flex items-center justify-center">
              <LogIn className="w-6 h-6 text-primary-foreground" />
            </div>
          </div>
          <CardTitle className="text-2xl text-center">欢迎回来</CardTitle>
          <CardDescription className="text-center">
            登录到 ComfyUI Studio
          </CardDescription>
        </CardHeader>
        
        <form onSubmit={handleSubmit}>
          <CardContent className="space-y-4">
            {error && (
              <Alert variant="destructive">
                <AlertDescription>{error}</AlertDescription>
              </Alert>
            )}
            
            <div className="space-y-2">
              <Label htmlFor="username">用户名</Label>
              <Input
                id="username"
                type="text"
                placeholder="请输入用户名"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                required
                disabled={isLoading}
              />
            </div>
            
            <div className="space-y-2">
              <Label htmlFor="password">密码</Label>
              <Input
                id="password"
                type="password"
                placeholder="请输入密码"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                disabled={isLoading}
              />
            </div>
          </CardContent>
          
          <CardFooter className="flex flex-col space-y-4">
            <Button
              type="submit"
              className="w-full"
              disabled={isLoading || !username || !password}
            >
              {isLoading ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  登录中...
                </>
              ) : (
                '登录'
              )}
            </Button>
            
            {allowRegistration && (
              <div className="text-sm text-center text-muted-foreground">
                还没有账号？{' '}
                <Link to="/register" className="text-primary hover:underline">
                  立即注册
                </Link>
              </div>
            )}
          </CardFooter>
        </form>
      </Card>
    </div>
  )
}
