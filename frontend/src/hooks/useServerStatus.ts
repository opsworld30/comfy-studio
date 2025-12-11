/**
 * 服务器状态管理 Hook - 初始化和实时更新
 * 集成熔断器模式，防止后端离线时无限重试
 */
import { useEffect } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useAppStore } from '@/stores/app'
import { comfyuiApi, performanceApi } from '@/lib/api'

/**
 * 获取并同步服务器状态到全局 store
 */
export function useServerStatus() {
  const { 
    setServerStatus, 
    setInitialized, 
    serverStatus, 
    isInitialized,
    circuitBreaker,
    recordFailure,
    recordSuccess,
    canMakeRequest,
  } = useAppStore()

  // 获取 ComfyUI 连接状态
  const { data: comfyStatus, isError: comfyError, error: comfyErrorDetail } = useQuery({
    queryKey: ['comfyui', 'status'],
    queryFn: async () => {
      const { data } = await comfyuiApi.getStatus()
      // 请求成功，重置熔断器
      recordSuccess()
      return data
    },
    // 动态控制轮询间隔：熔断器打开时停止轮询
    refetchInterval: (query) => {
      // 如果查询失败或熔断器打开，停止轮询
      if (query.state.status === 'error' || circuitBreaker.isOpen) {
        return false
      }
      return 5000 // 正常情况下每 5 秒刷新
    },
    staleTime: 2000, // 2秒内数据视为新鲜，与后端缓存同步
    gcTime: 30000, // 缓存保留30秒
    retry: 2, // 减少重试次数，加快失败判定
    retryDelay: (attemptIndex) => Math.min(500 * Math.pow(2, attemptIndex), 3000), // 更快的重试
    // 熔断器打开时禁用查询
    enabled: !circuitBreaker.isOpen || canMakeRequest(),
    // 使用上次成功的数据作为占位，避免闪烁
    placeholderData: (previousData) => previousData,
  })

  // 获取性能统计
  const { data: perfStats } = useQuery({
    queryKey: ['performance', 'stats'],
    queryFn: async () => {
      const { data } = await performanceApi.getStats()
      return data
    },
    // 动态控制轮询间隔
    refetchInterval: (query) => {
      if (query.state.status === 'error' || circuitBreaker.isOpen) {
        return false
      }
      return 10000 // 每 10 秒刷新
    },
    staleTime: 5000,
    retry: 2, // 性能统计失败影响较小，重试 2 次
    // 熔断器打开时禁用查询
    enabled: !circuitBreaker.isOpen || canMakeRequest(),
  })

  // 监听错误并更新熔断器（仅在真正的网络/服务器错误时记录）
  useEffect(() => {
    if (comfyError && comfyErrorDetail) {
      const axiosError = comfyErrorDetail as { 
        code?: string; 
        response?: { status?: number };
        message?: string;
      }
      
      // 只记录严重的网络错误（排除超时等临时问题）
      const isNetworkError = axiosError.code === 'ERR_NETWORK' || 
                            (!axiosError.response && axiosError.code !== 'ECONNABORTED')
      const isServerError = axiosError.response?.status && axiosError.response.status >= 500
      
      // 只有在确认是持续性错误时才记录失败
      if (isNetworkError || isServerError) {
        console.log('[ServerStatus] 检测到服务器错误:', axiosError.code, axiosError.response?.status)
        recordFailure()
      }
    }
  }, [comfyError, comfyErrorDetail, recordFailure])

  // 同步状态到 store
  useEffect(() => {
    if (comfyStatus !== undefined) {
      const connected = comfyStatus?.connected ?? false
      
      // 从 system_stats 提取 GPU 信息
      const devices = comfyStatus?.system_stats?.devices || []
      const gpu = devices[0] || {}
      
      // 计算 VRAM 使用量（GB）
      const vramTotal = (gpu.vram_total || 0) / (1024 * 1024 * 1024)
      const vramFree = (gpu.vram_free || 0) / (1024 * 1024 * 1024)
      const vramUsed = vramTotal - vramFree

      setServerStatus({
        connected,
        queueSize: comfyStatus?.queue_remaining || 0,
        vramTotal: vramTotal || serverStatus.vramTotal,
        vramUsed: vramUsed || serverStatus.vramUsed,
      })

      if (!isInitialized) {
        setInitialized(true)
      }
    } else if (comfyError) {
      setServerStatus({ connected: false })
      if (!isInitialized) {
        setInitialized(true)
      }
    }
  }, [comfyStatus, comfyError, setServerStatus, setInitialized, isInitialized, serverStatus.vramTotal, serverStatus.vramUsed])

  // 同步性能统计
  useEffect(() => {
    if (perfStats) {
      setServerStatus({
        gpuUsage: perfStats.gpu_usage || 0,
        temperature: perfStats.gpu_temperature || 0,
        // 如果有更精确的 GPU 内存数据，使用它
        ...(perfStats.gpu_memory_total > 0 && {
          vramTotal: perfStats.gpu_memory_total / (1024 * 1024 * 1024),
          vramUsed: perfStats.gpu_memory_used / (1024 * 1024 * 1024),
        }),
      })
    }
  }, [perfStats, setServerStatus])

  return {
    isInitialized,
    serverStatus,
    isConnected: serverStatus.connected,
    // 熔断器状态
    isCircuitOpen: circuitBreaker.isOpen,
    failureCount: circuitBreaker.failureCount,
  }
}

/**
 * 简化版：仅检查连接状态
 */
export function useConnectionStatus() {
  const serverStatus = useAppStore((s) => s.serverStatus)
  return serverStatus.connected
}
