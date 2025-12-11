import { create } from 'zustand'

interface ServerStatus {
  connected: boolean
  url: string
  gpuUsage: number
  vramUsed: number
  vramTotal: number
  temperature: number
  queueSize: number
}

// 熔断器状态：用于控制 API 轮询
interface CircuitBreakerState {
  isOpen: boolean           // 熔断器是否打开（true = 停止请求）
  failureCount: number      // 连续失败次数
  lastFailureTime: number   // 最后一次失败时间
  nextRetryTime: number     // 下次重试时间
}

interface AppState {
  sidebarCollapsed: boolean
  serverStatus: ServerStatus
  notifications: number
  isInitialized: boolean
  circuitBreaker: CircuitBreakerState
  toggleSidebar: () => void
  setServerStatus: (status: Partial<ServerStatus>) => void
  setNotifications: (count: number) => void
  setInitialized: (initialized: boolean) => void
  // 熔断器方法
  recordFailure: () => void
  recordSuccess: () => void
  resetCircuitBreaker: () => void
  canMakeRequest: () => boolean
}

// 初始状态：未连接，等待 API 获取真实状态
const initialServerStatus: ServerStatus = {
  connected: false,
  url: '',
  gpuUsage: 0,
  vramUsed: 0,
  vramTotal: 0,
  temperature: 0,
  queueSize: 0,
}

// 熔断器配置
const CIRCUIT_BREAKER_CONFIG = {
  failureThreshold: 10,     // 连续失败 10 次后打开熔断器（避免误报）
  resetTimeout: 60000,      // 60 秒后尝试半开状态
  maxRetryInterval: 120000, // 最大重试间隔 120 秒
}

const initialCircuitBreaker: CircuitBreakerState = {
  isOpen: false,
  failureCount: 0,
  lastFailureTime: 0,
  nextRetryTime: 0,
}

export const useAppStore = create<AppState>((set, get) => ({
  sidebarCollapsed: false,
  serverStatus: initialServerStatus,
  notifications: 0,
  isInitialized: false,
  circuitBreaker: initialCircuitBreaker,
  
  toggleSidebar: () => set((state) => ({ sidebarCollapsed: !state.sidebarCollapsed })),
  
  setServerStatus: (status) =>
    set((state) => ({ serverStatus: { ...state.serverStatus, ...status } })),
  
  setNotifications: (count) => set({ notifications: count }),
  
  setInitialized: (initialized) => set({ isInitialized: initialized }),
  
  // 记录请求失败
  recordFailure: () => set((state) => {
    const newFailureCount = state.circuitBreaker.failureCount + 1
    const now = Date.now()
    const shouldOpen = newFailureCount >= CIRCUIT_BREAKER_CONFIG.failureThreshold
    
    // 计算下次重试时间（指数退避）
    const retryDelay = Math.min(
      CIRCUIT_BREAKER_CONFIG.resetTimeout * Math.pow(2, newFailureCount - CIRCUIT_BREAKER_CONFIG.failureThreshold),
      CIRCUIT_BREAKER_CONFIG.maxRetryInterval
    )
    
    if (shouldOpen && !state.circuitBreaker.isOpen) {
      console.log('[CircuitBreaker] 熔断器打开，暂停 API 轮询')
    }
    
    return {
      circuitBreaker: {
        isOpen: shouldOpen,
        failureCount: newFailureCount,
        lastFailureTime: now,
        nextRetryTime: shouldOpen ? now + retryDelay : 0,
      },
    }
  }),
  
  // 记录请求成功
  recordSuccess: () => set((state) => {
    if (state.circuitBreaker.isOpen || state.circuitBreaker.failureCount > 0) {
      console.log('[CircuitBreaker] 请求成功，重置熔断器')
    }
    return {
      circuitBreaker: initialCircuitBreaker,
    }
  }),
  
  // 重置熔断器（手动重试时调用）
  resetCircuitBreaker: () => {
    console.log('[CircuitBreaker] 手动重置熔断器')
    set({ circuitBreaker: initialCircuitBreaker })
  },
  
  // 检查是否可以发起请求
  canMakeRequest: () => {
    const { circuitBreaker } = get()
    if (!circuitBreaker.isOpen) {
      return true
    }
    // 检查是否到了重试时间（半开状态）
    const now = Date.now()
    if (now >= circuitBreaker.nextRetryTime) {
      console.log('[CircuitBreaker] 进入半开状态，尝试请求')
      return true
    }
    return false
  },
}))
