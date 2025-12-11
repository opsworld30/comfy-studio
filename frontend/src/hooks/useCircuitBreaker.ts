/**
 * 熔断器 Hook - 用于控制 React Query 轮询
 * 当后端服务不可用时，自动停止轮询，防止无限重试
 */
import { useCallback } from 'react'
import { useAppStore } from '@/stores/app'

/**
 * 获取熔断器状态和控制方法
 */
export function useCircuitBreaker() {
  const {
    circuitBreaker,
    recordFailure,
    recordSuccess,
    resetCircuitBreaker,
    canMakeRequest,
  } = useAppStore()

  /**
   * 创建带熔断器保护的 refetchInterval 函数
   * 用于 React Query 的 refetchInterval 选项
   */
  const createRefetchInterval = useCallback(
    (normalInterval: number) => {
      return (query: { state: { status: string } }) => {
        // 如果查询失败或熔断器打开，停止轮询
        if (query.state.status === 'error' || circuitBreaker.isOpen) {
          return false
        }
        return normalInterval
      }
    },
    [circuitBreaker.isOpen]
  )

  /**
   * 检查是否应该启用查询
   */
  const shouldEnableQuery = useCallback(() => {
    return !circuitBreaker.isOpen || canMakeRequest()
  }, [circuitBreaker.isOpen, canMakeRequest])

  /**
   * 包装 queryFn，自动处理成功/失败记录
   */
  const wrapQueryFn = useCallback(
    <T>(queryFn: () => Promise<T>, options?: { recordOnSuccess?: boolean }) => {
      return async (): Promise<T> => {
        try {
          const result = await queryFn()
          // 默认记录成功
          if (options?.recordOnSuccess !== false) {
            recordSuccess()
          }
          return result
        } catch (error) {
          // 检查是否是网络错误或服务器不可用
          const axiosError = error as { code?: string; response?: { status?: number } }
          const isNetworkError =
            axiosError.code === 'ERR_NETWORK' ||
            axiosError.code === 'ECONNABORTED' ||
            !axiosError.response
          const isServerError =
            axiosError.response?.status && axiosError.response.status >= 500

          if (isNetworkError || isServerError) {
            recordFailure()
          }
          throw error
        }
      }
    },
    [recordFailure, recordSuccess]
  )

  return {
    // 状态
    isOpen: circuitBreaker.isOpen,
    failureCount: circuitBreaker.failureCount,
    nextRetryTime: circuitBreaker.nextRetryTime,
    
    // 方法
    recordFailure,
    recordSuccess,
    resetCircuitBreaker,
    canMakeRequest,
    
    // 辅助函数
    createRefetchInterval,
    shouldEnableQuery,
    wrapQueryFn,
  }
}

/**
 * 简化版：只返回是否应该轮询
 */
export function useShouldPoll(): boolean {
  const { circuitBreaker, canMakeRequest } = useAppStore()
  return !circuitBreaker.isOpen || canMakeRequest()
}
