import { Routes, Route } from 'react-router-dom'
import { useThemeStore } from '@/stores/theme'
import { usePageModulesStore } from '@/stores/pageModules'
import { useEffect, lazy, Suspense } from 'react'
import Layout from '@/components/layout/Layout'
import { Toaster } from '@/components/ui/sonner'
import { ErrorBoundary } from '@/components/ErrorBoundary'
import { ProtectedRoute } from '@/components/ProtectedRoute'
import { useServerStatus } from '@/hooks/useServerStatus'
import { useWebSocket } from '@/hooks/useWebSocket'
import { useNetworkStatus } from '@/hooks/useNetworkStatus'
import { Loader2 } from 'lucide-react'

// 路由懒加载 - 核心页面
const Dashboard = lazy(() => import('@/pages/Dashboard'))
const Login = lazy(() => import('@/pages/Login'))
const Register = lazy(() => import('@/pages/Register'))

// 路由懒加载 - 功能页面（按需加载）
const TaskQueue = lazy(() => import('@/pages/TaskQueue'))
const Gallery = lazy(() => import('@/pages/Gallery'))
const Models = lazy(() => import('@/pages/Models'))
const Prompts = lazy(() => import('@/pages/Prompts'))
const Monitor = lazy(() => import('@/pages/Monitor'))
const Market = lazy(() => import('@/pages/Market'))
const Servers = lazy(() => import('@/pages/Servers'))
const Settings = lazy(() => import('@/pages/Settings'))
const Profile = lazy(() => import('@/pages/Profile'))

// 路由懒加载 - 重型页面（流程图编辑器）
const WorkflowEditor = lazy(() => import('@/pages/WorkflowEditor'))

// 页面加载骨架屏
function PageLoader() {
  return (
    <div className="flex items-center justify-center h-[calc(100vh-4rem)]">
      <div className="flex flex-col items-center gap-3">
        <Loader2 className="h-8 w-8 animate-spin text-primary" />
        <p className="text-sm text-muted-foreground">加载中...</p>
      </div>
    </div>
  )
}

// 应用初始化组件
function AppInitializer({ children }: { children: React.ReactNode }) {
  // 初始化服务器状态
  useServerStatus()
  
  // 监听网络状态（离线提示）
  const { isOnline, isSlowConnection } = useNetworkStatus()
  
  // 初始化 WebSocket 连接（带自动重连）
  useWebSocket({
    enabled: isOnline, // 离线时不尝试连接
    onConnect: () => console.log('[App] WebSocket 已连接'),
    onDisconnect: () => console.log('[App] WebSocket 已断开'),
    onMessage: (msg) => {
      // 处理全局 WebSocket 消息（如执行完成通知等）
      if (msg.type === 'executed') {
        console.log('[App] 执行完成:', msg.data)
      }
    },
  })

  // 慢网络提示
  useEffect(() => {
    if (isSlowConnection) {
      console.log('[App] 检测到慢速网络连接')
    }
  }, [isSlowConnection])

  return <>{children}</>
}

function App() {
  const { theme } = useThemeStore()
  const { fetchModules } = usePageModulesStore()

  // 加载页面模块设置
  useEffect(() => {
    fetchModules()
  }, [fetchModules])

  useEffect(() => {
    const root = window.document.documentElement
    root.classList.remove('light', 'dark')
    if (theme === 'system') {
      const systemTheme = window.matchMedia('(prefers-color-scheme: dark)').matches
        ? 'dark'
        : 'light'
      root.classList.add(systemTheme)
    } else {
      root.classList.add(theme)
    }
  }, [theme])

  return (
    <ErrorBoundary>
      <AppInitializer>
        <Suspense fallback={<PageLoader />}>
          <Routes>
            {/* 公开路由 */}
            <Route path="/login" element={<Login />} />
            <Route path="/register" element={<Register />} />
            
            {/* 受保护的路由 */}
            <Route path="/" element={<ProtectedRoute><Layout /></ProtectedRoute>}>
              <Route index element={<Dashboard />} />
              <Route path="batch" element={<TaskQueue />} />
              <Route path="gallery" element={<Gallery />} />
              <Route path="models" element={<Models />} />
              <Route path="prompts" element={<Prompts />} />
              <Route path="monitor" element={<Monitor />} />
              <Route path="market" element={<Market />} />
              <Route path="servers" element={<Servers />} />
              <Route path="settings" element={<Settings />} />
              <Route path="profile" element={<Profile />} />
              <Route path="workflow/:id" element={<WorkflowEditor />} />
            </Route>
          </Routes>
        </Suspense>
        <Toaster richColors position="top-right" />
      </AppInitializer>
    </ErrorBoundary>
  )
}

export default App
