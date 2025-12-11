/**
 * WebSocket 连接管理 Hook - 带自动重连机制
 * 修复：避免 useEffect 依赖循环导致无限重连
 */
import { useEffect, useRef, useState } from 'react'
import { useAppStore } from '@/stores/app'

interface WebSocketMessage {
  type: string
  data?: unknown
}

interface UseWebSocketOptions {
  onMessage?: (message: WebSocketMessage) => void
  onConnect?: () => void
  onDisconnect?: () => void
  onError?: (error: Event) => void
  autoConnect?: boolean
  enabled?: boolean
}

interface WebSocketState {
  isConnected: boolean
  isConnecting: boolean
  reconnectAttempts: number
  lastError: string | null
}

const MAX_RECONNECT_ATTEMPTS = 5
const INITIAL_RECONNECT_DELAY = 1000
const MAX_RECONNECT_DELAY = 30000
const HEARTBEAT_INTERVAL = 30000

export function useWebSocket(options: UseWebSocketOptions = {}) {
  const { autoConnect = true, enabled = true } = options

  // 使用 ref 存储所有回调和配置，避免依赖变化
  const optionsRef = useRef(options)
  optionsRef.current = options

  const wsRef = useRef<WebSocket | null>(null)
  const reconnectTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const heartbeatIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null)
  const reconnectAttemptsRef = useRef(0)
  const isManualDisconnectRef = useRef(false)
  
  const [state, setState] = useState<WebSocketState>({
    isConnected: false,
    isConnecting: false,
    reconnectAttempts: 0,
    lastError: null,
  })

  const setServerStatus = useAppStore((s) => s.setServerStatus)

  // 主要的连接逻辑放在 useEffect 中
  useEffect(() => {
    if (!autoConnect || !enabled) {
      return
    }

    const getWsUrl = () => {
      const apiUrl = import.meta.env.VITE_API_URL || 'http://localhost:8001/api'
      const baseUrl = apiUrl.replace('/api', '').replace('http://', 'ws://').replace('https://', 'wss://')
      return `${baseUrl}/ws`
    }

    const cleanup = () => {
      if (heartbeatIntervalRef.current) {
        clearInterval(heartbeatIntervalRef.current)
        heartbeatIntervalRef.current = null
      }
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current)
        reconnectTimeoutRef.current = null
      }
    }

    const sendHeartbeat = () => {
      if (wsRef.current?.readyState === WebSocket.OPEN) {
        wsRef.current.send(JSON.stringify({ type: 'ping' }))
      }
    }

    const getReconnectDelay = () => {
      return Math.min(
        INITIAL_RECONNECT_DELAY * Math.pow(2, reconnectAttemptsRef.current),
        MAX_RECONNECT_DELAY
      )
    }

    const connect = () => {
      // 防止重复连接
      if (wsRef.current?.readyState === WebSocket.OPEN || 
          wsRef.current?.readyState === WebSocket.CONNECTING) {
        return
      }

      cleanup()
      isManualDisconnectRef.current = false
      setState((s) => ({ ...s, isConnecting: true, lastError: null }))

      try {
        const ws = new WebSocket(getWsUrl())
        wsRef.current = ws

        ws.onopen = () => {
          console.log('[WebSocket] 连接成功')
          reconnectAttemptsRef.current = 0
          setState({
            isConnected: true,
            isConnecting: false,
            reconnectAttempts: 0,
            lastError: null,
          })
          setServerStatus({ connected: true })
          optionsRef.current.onConnect?.()

          // 启动心跳
          heartbeatIntervalRef.current = setInterval(sendHeartbeat, HEARTBEAT_INTERVAL)
        }

        ws.onmessage = (event) => {
          try {
            const message = JSON.parse(event.data) as WebSocketMessage
            if (message.type === 'pong' || message.type === 'heartbeat') {
              return
            }
            optionsRef.current.onMessage?.(message)
          } catch (e) {
            console.warn('[WebSocket] 消息解析失败:', e)
          }
        }

        ws.onclose = (event) => {
          console.log('[WebSocket] 连接关闭:', event.code, event.reason)
          cleanup()
          wsRef.current = null
          setState((s) => ({ ...s, isConnected: false, isConnecting: false }))
          setServerStatus({ connected: false })
          optionsRef.current.onDisconnect?.()

          // 如果是手动断开或已达到最大重连次数，不再重连
          if (isManualDisconnectRef.current) {
            return
          }

          if (reconnectAttemptsRef.current < MAX_RECONNECT_ATTEMPTS) {
            const delay = getReconnectDelay()
            console.log(`[WebSocket] ${delay}ms 后尝试重连 (${reconnectAttemptsRef.current + 1}/${MAX_RECONNECT_ATTEMPTS})`)
            
            reconnectTimeoutRef.current = setTimeout(() => {
              reconnectAttemptsRef.current++
              setState((s) => ({ ...s, reconnectAttempts: reconnectAttemptsRef.current }))
              connect()
            }, delay)
          } else {
            console.error('[WebSocket] 达到最大重连次数，停止重连')
            setState((s) => ({ ...s, lastError: '连接失败，请刷新页面重试' }))
          }
        }

        ws.onerror = (error) => {
          console.error('[WebSocket] 连接错误:', error)
          setState((s) => ({ ...s, lastError: '连接错误' }))
          optionsRef.current.onError?.(error)
        }
      } catch (error) {
        console.error('[WebSocket] 创建连接失败:', error)
        setState((s) => ({ ...s, isConnecting: false, lastError: '创建连接失败' }))
      }
    }

    // 初始连接
    connect()

    // 清理函数
    return () => {
      isManualDisconnectRef.current = true
      cleanup()
      if (wsRef.current) {
        wsRef.current.close()
        wsRef.current = null
      }
    }
  }, [autoConnect, enabled, setServerStatus]) // 只依赖这三个稳定的值

  // 手动控制方法
  const disconnect = () => {
    isManualDisconnectRef.current = true
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current)
      reconnectTimeoutRef.current = null
    }
    if (heartbeatIntervalRef.current) {
      clearInterval(heartbeatIntervalRef.current)
      heartbeatIntervalRef.current = null
    }
    if (wsRef.current) {
      wsRef.current.close()
      wsRef.current = null
    }
    setState({
      isConnected: false,
      isConnecting: false,
      reconnectAttempts: 0,
      lastError: null,
    })
  }

  const send = (data: unknown) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(data))
      return true
    }
    return false
  }

  return {
    ...state,
    disconnect,
    send,
  }
}
