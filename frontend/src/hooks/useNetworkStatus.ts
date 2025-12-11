/**
 * 网络状态监听 Hook
 * 检测网络连接状态，提供离线提示
 */
import { useState, useEffect, useCallback } from 'react'
import { toast } from 'sonner'

export interface NetworkStatus {
  isOnline: boolean
  isSlowConnection: boolean
  effectiveType?: string // 4g, 3g, 2g, slow-2g
  downlink?: number // 下行速度 Mbps
  rtt?: number // 往返时间 ms
}

// 扩展 Navigator 类型以支持 connection API
interface NetworkInformation {
  effectiveType?: string
  downlink?: number
  rtt?: number
  addEventListener: (type: string, listener: () => void) => void
  removeEventListener: (type: string, listener: () => void) => void
}

declare global {
  interface Navigator {
    connection?: NetworkInformation
    mozConnection?: NetworkInformation
    webkitConnection?: NetworkInformation
  }
}

export function useNetworkStatus() {
  const [status, setStatus] = useState<NetworkStatus>(() => ({
    isOnline: typeof navigator !== 'undefined' ? navigator.onLine : true,
    isSlowConnection: false,
  }))

  const getConnectionInfo = useCallback((): Partial<NetworkStatus> => {
    const connection = navigator.connection || navigator.mozConnection || navigator.webkitConnection
    if (!connection) return {}

    const isSlowConnection = 
      connection.effectiveType === '2g' || 
      connection.effectiveType === 'slow-2g' ||
      (connection.downlink !== undefined && connection.downlink < 1)

    return {
      effectiveType: connection.effectiveType,
      downlink: connection.downlink,
      rtt: connection.rtt,
      isSlowConnection,
    }
  }, [])

  const updateStatus = useCallback(() => {
    const connectionInfo = getConnectionInfo()
    setStatus(prev => ({
      ...prev,
      isOnline: navigator.onLine,
      ...connectionInfo,
    }))
  }, [getConnectionInfo])

  useEffect(() => {
    // 初始化
    updateStatus()

    // 监听在线/离线事件
    const handleOnline = () => {
      setStatus(prev => ({ ...prev, isOnline: true }))
      toast.success('网络已恢复', { duration: 3000 })
    }

    const handleOffline = () => {
      setStatus(prev => ({ ...prev, isOnline: false }))
      toast.error('网络已断开', { 
        description: '请检查网络连接',
        duration: Infinity, // 保持显示直到网络恢复
        id: 'network-offline', // 防止重复显示
      })
    }

    window.addEventListener('online', handleOnline)
    window.addEventListener('offline', handleOffline)

    // 监听网络质量变化
    const connection = navigator.connection || navigator.mozConnection || navigator.webkitConnection
    if (connection) {
      connection.addEventListener('change', updateStatus)
    }

    return () => {
      window.removeEventListener('online', handleOnline)
      window.removeEventListener('offline', handleOffline)
      if (connection) {
        connection.removeEventListener('change', updateStatus)
      }
    }
  }, [updateStatus])

  return status
}

// 简化版：只返回是否在线
export function useIsOnline(): boolean {
  const { isOnline } = useNetworkStatus()
  return isOnline
}
