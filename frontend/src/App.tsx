import { Routes, Route } from 'react-router-dom'
import { useThemeStore } from '@/stores/theme'
import { usePageModulesStore } from '@/stores/pageModules'
import { useEffect } from 'react'
import Layout from '@/components/layout/Layout'
import { Toaster } from '@/components/ui/sonner'
import { ErrorBoundary } from '@/components/ErrorBoundary'
import { useServerStatus } from '@/hooks/useServerStatus'
import { useWebSocket } from '@/hooks/useWebSocket'
import { useNetworkStatus } from '@/hooks/useNetworkStatus'
import Dashboard from '@/pages/Dashboard'
import TaskQueue from '@/pages/TaskQueue'
import Gallery from '@/pages/Gallery'
import Models from '@/pages/Models'
import Prompts from '@/pages/Prompts'
import Monitor from '@/pages/Monitor'
import Market from '@/pages/Market'
import Servers from '@/pages/Servers'
import Settings from '@/pages/Settings'
import WorkflowEditor from '@/pages/WorkflowEditor'

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
        <Routes>
          <Route path="/" element={<Layout />}>
            <Route index element={<Dashboard />} />
            <Route path="batch" element={<TaskQueue />} />
            <Route path="gallery" element={<Gallery />} />
            <Route path="models" element={<Models />} />
            <Route path="prompts" element={<Prompts />} />
            <Route path="monitor" element={<Monitor />} />
            <Route path="market" element={<Market />} />
            <Route path="servers" element={<Servers />} />
            <Route path="settings" element={<Settings />} />
            <Route path="workflow/:id" element={<WorkflowEditor />} />
          </Route>
        </Routes>
        <Toaster richColors position="top-right" />
      </AppInitializer>
    </ErrorBoundary>
  )
}

export default App
