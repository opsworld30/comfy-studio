/**
 * 服务器离线提示横幅
 * 当熔断器打开时显示，提供手动重试按钮
 */
import { useAppStore } from '@/stores/app'
import { useQueryClient } from '@tanstack/react-query'
import { AlertTriangle, RefreshCw } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { useState } from 'react'

export function ServerOfflineBanner() {
  const { circuitBreaker, resetCircuitBreaker } = useAppStore()
  const queryClient = useQueryClient()
  const [isRetrying, setIsRetrying] = useState(false)

  if (!circuitBreaker.isOpen) {
    return null
  }

  const handleRetry = async () => {
    setIsRetrying(true)
    // 重置熔断器
    resetCircuitBreaker()
    // 重新获取关键数据
    await queryClient.invalidateQueries({ queryKey: ['comfyui', 'status'] })
    setIsRetrying(false)
  }

  // 计算下次自动重试时间
  const timeUntilRetry = Math.max(0, circuitBreaker.nextRetryTime - Date.now())
  const secondsUntilRetry = Math.ceil(timeUntilRetry / 1000)

  return (
    <div className="fixed top-0 left-0 right-0 z-50 bg-destructive/90 text-destructive-foreground px-4 py-2">
      <div className="container mx-auto flex items-center justify-between">
        <div className="flex items-center gap-2">
          <AlertTriangle className="h-4 w-4" />
          <span className="text-sm font-medium">
            后端服务连接失败，已暂停自动刷新
            {secondsUntilRetry > 0 && (
              <span className="ml-2 text-destructive-foreground/80">
                ({secondsUntilRetry}秒后自动重试)
              </span>
            )}
          </span>
        </div>
        <Button
          variant="secondary"
          size="sm"
          onClick={handleRetry}
          disabled={isRetrying}
          className="h-7"
        >
          {isRetrying ? (
            <RefreshCw className="h-3 w-3 mr-1 animate-spin" />
          ) : (
            <RefreshCw className="h-3 w-3 mr-1" />
          )}
          立即重试
        </Button>
      </div>
    </div>
  )
}
