/**
 * 路由守卫组件 - 保护需要登录的页面
 */
import { useEffect } from 'react'
import { Navigate, useLocation } from 'react-router-dom'
import { useAuthStore } from '@/stores/auth'
import { Loader2 } from 'lucide-react'

interface ProtectedRouteProps {
  children: React.ReactNode
}

export function ProtectedRoute({ children }: ProtectedRouteProps) {
  const location = useLocation()
  const { isAuthenticated, isLoading, fetchCurrentUser } = useAuthStore()

  useEffect(() => {
    // 尝试获取当前用户信息
    if (!isAuthenticated) {
      fetchCurrentUser()
    }
  }, [isAuthenticated, fetchCurrentUser])

  // 加载中显示加载动画
  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-center">
          <Loader2 className="w-8 h-8 animate-spin mx-auto mb-4 text-primary" />
          <p className="text-muted-foreground">加载中...</p>
        </div>
      </div>
    )
  }

  // 未认证则跳转到登录页
  if (!isAuthenticated) {
    return <Navigate to="/login" state={{ from: location }} replace />
  }

  return <>{children}</>
}
