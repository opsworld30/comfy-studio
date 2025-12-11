/**
 * 性能监控 Hook
 * 
 * 提供：
 * - 组件渲染性能监控
 * - 内存使用监控
 * - 网络请求性能
 * - 长任务检测
 */
import { useEffect, useRef, useCallback } from 'react'

interface PerformanceMetrics {
  /** 首次内容绘制时间 */
  fcp?: number
  /** 最大内容绘制时间 */
  lcp?: number
  /** 首次输入延迟 */
  fid?: number
  /** 累积布局偏移 */
  cls?: number
  /** 可交互时间 */
  tti?: number
}

/**
 * 获取 Web Vitals 性能指标
 */
export function useWebVitals(onReport?: (metrics: PerformanceMetrics) => void) {
  useEffect(() => {
    const metrics: PerformanceMetrics = {}

    // 首次内容绘制 (FCP)
    const fcpObserver = new PerformanceObserver((list) => {
      const entries = list.getEntries()
      const fcpEntry = entries.find(entry => entry.name === 'first-contentful-paint')
      if (fcpEntry) {
        metrics.fcp = fcpEntry.startTime
        onReport?.({ ...metrics })
      }
    })

    // 最大内容绘制 (LCP)
    const lcpObserver = new PerformanceObserver((list) => {
      const entries = list.getEntries()
      const lastEntry = entries[entries.length - 1]
      if (lastEntry) {
        metrics.lcp = lastEntry.startTime
        onReport?.({ ...metrics })
      }
    })

    // 首次输入延迟 (FID)
    const fidObserver = new PerformanceObserver((list) => {
      const entries = list.getEntries()
      const firstEntry = entries[0] as PerformanceEventTiming
      if (firstEntry) {
        metrics.fid = firstEntry.processingStart - firstEntry.startTime
        onReport?.({ ...metrics })
      }
    })

    // 累积布局偏移 (CLS)
    let clsValue = 0
    const clsObserver = new PerformanceObserver((list) => {
      for (const entry of list.getEntries() as LayoutShiftEntry[]) {
        if (!entry.hadRecentInput) {
          clsValue += entry.value
        }
      }
      metrics.cls = clsValue
      onReport?.({ ...metrics })
    })

    try {
      fcpObserver.observe({ type: 'paint', buffered: true })
      lcpObserver.observe({ type: 'largest-contentful-paint', buffered: true })
      fidObserver.observe({ type: 'first-input', buffered: true })
      clsObserver.observe({ type: 'layout-shift', buffered: true })
    } catch (e) {
      console.warn('Performance Observer not supported:', e)
    }

    return () => {
      fcpObserver.disconnect()
      lcpObserver.disconnect()
      fidObserver.disconnect()
      clsObserver.disconnect()
    }
  }, [onReport])
}

// 类型定义
interface LayoutShiftEntry extends PerformanceEntry {
  value: number
  hadRecentInput: boolean
}

interface PerformanceEventTiming extends PerformanceEntry {
  processingStart: number
}

/**
 * 组件渲染性能监控
 */
export function useRenderPerformance(componentName: string, enabled = true) {
  const renderCount = useRef(0)
  const lastRenderTime = useRef(performance.now())

  useEffect(() => {
    if (!enabled) return

    renderCount.current++
    const now = performance.now()
    const timeSinceLastRender = now - lastRenderTime.current
    lastRenderTime.current = now

    // 只在开发环境输出
    if (import.meta.env.DEV) {
      console.log(
        `[Performance] ${componentName} rendered #${renderCount.current}`,
        `(${timeSinceLastRender.toFixed(2)}ms since last render)`
      )
    }
  })

  return {
    renderCount: renderCount.current,
  }
}

/**
 * 内存使用监控
 */
export function useMemoryMonitor(intervalMs = 5000) {
  const memoryRef = useRef<{
    usedJSHeapSize: number
    totalJSHeapSize: number
    jsHeapSizeLimit: number
  } | null>(null)

  useEffect(() => {
    // 检查是否支持 memory API
    const performance = window.performance as Performance & {
      memory?: {
        usedJSHeapSize: number
        totalJSHeapSize: number
        jsHeapSizeLimit: number
      }
    }

    if (!performance.memory) {
      console.warn('Memory API not supported')
      return
    }

    const checkMemory = () => {
      if (performance.memory) {
        memoryRef.current = {
          usedJSHeapSize: performance.memory.usedJSHeapSize,
          totalJSHeapSize: performance.memory.totalJSHeapSize,
          jsHeapSizeLimit: performance.memory.jsHeapSizeLimit,
        }

        // 内存使用超过 80% 时警告
        const usagePercent = (performance.memory.usedJSHeapSize / performance.memory.jsHeapSizeLimit) * 100
        if (usagePercent > 80) {
          console.warn(
            `[Memory Warning] High memory usage: ${usagePercent.toFixed(1)}%`,
            `(${formatBytes(performance.memory.usedJSHeapSize)} / ${formatBytes(performance.memory.jsHeapSizeLimit)})`
          )
        }
      }
    }

    checkMemory()
    const interval = setInterval(checkMemory, intervalMs)

    return () => clearInterval(interval)
  }, [intervalMs])

  return memoryRef.current
}

/**
 * 长任务检测
 */
export function useLongTaskDetector(threshold = 50, onLongTask?: (duration: number) => void) {
  useEffect(() => {
    const observer = new PerformanceObserver((list) => {
      for (const entry of list.getEntries()) {
        if (entry.duration > threshold) {
          console.warn(
            `[Long Task] Duration: ${entry.duration.toFixed(2)}ms`,
            entry
          )
          onLongTask?.(entry.duration)
        }
      }
    })

    try {
      observer.observe({ type: 'longtask', buffered: true })
    } catch (e) {
      console.warn('Long Task Observer not supported:', e)
    }

    return () => observer.disconnect()
  }, [threshold, onLongTask])
}

/**
 * 测量函数执行时间
 */
export function useMeasure() {
  const measure = useCallback(<T>(name: string, fn: () => T): T => {
    const start = performance.now()
    const result = fn()
    const end = performance.now()

    if (import.meta.env.DEV) {
      console.log(`[Measure] ${name}: ${(end - start).toFixed(2)}ms`)
    }

    return result
  }, [])

  const measureAsync = useCallback(async <T>(name: string, fn: () => Promise<T>): Promise<T> => {
    const start = performance.now()
    const result = await fn()
    const end = performance.now()

    if (import.meta.env.DEV) {
      console.log(`[Measure] ${name}: ${(end - start).toFixed(2)}ms`)
    }

    return result
  }, [])

  return { measure, measureAsync }
}

/**
 * 格式化字节数
 */
function formatBytes(bytes: number): string {
  if (bytes === 0) return '0 B'
  const k = 1024
  const sizes = ['B', 'KB', 'MB', 'GB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return `${(bytes / Math.pow(k, i)).toFixed(2)} ${sizes[i]}`
}

/**
 * 性能监控组合 Hook
 */
export function usePerformanceMonitor(options?: {
  enableWebVitals?: boolean
  enableMemory?: boolean
  enableLongTask?: boolean
  componentName?: string
}) {
  const {
    enableWebVitals = true,
    enableMemory = false,
    enableLongTask = true,
    componentName,
  } = options || {}

  // Web Vitals
  useWebVitals(enableWebVitals ? (metrics) => {
    if (import.meta.env.DEV) {
      console.log('[Web Vitals]', metrics)
    }
  } : undefined)

  // 内存监控
  const memory = useMemoryMonitor(enableMemory ? 10000 : 0)

  // 长任务检测
  useLongTaskDetector(enableLongTask ? 50 : Infinity)

  // 组件渲染性能
  const renderPerf = useRenderPerformance(componentName || 'Unknown', !!componentName)

  return {
    memory,
    renderCount: renderPerf.renderCount,
  }
}

export default usePerformanceMonitor
