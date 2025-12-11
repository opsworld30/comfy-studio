/**
 * 虚拟滚动列表组件
 * 
 * 特性：
 * - 只渲染可见区域的元素
 * - 支持固定高度和动态高度
 * - 支持网格布局
 * - 滚动性能优化
 */
import { useState, useRef, useEffect, useCallback, ReactNode, CSSProperties } from 'react'
import { cn } from '@/lib/utils'

interface VirtualListProps<T> {
  /** 数据列表 */
  items: T[]
  /** 每项高度（固定高度模式） */
  itemHeight: number
  /** 容器高度 */
  height: number | string
  /** 渲染单个项目 */
  renderItem: (item: T, index: number) => ReactNode
  /** 缓冲区大小（额外渲染的项目数） */
  overscan?: number
  /** 容器类名 */
  className?: string
  /** 获取项目唯一键 */
  getItemKey?: (item: T, index: number) => string | number
  /** 滚动到底部回调（用于无限滚动） */
  onEndReached?: () => void
  /** 触发 onEndReached 的阈值（距离底部的像素数） */
  endReachedThreshold?: number
  /** 是否正在加载更多 */
  isLoadingMore?: boolean
  /** 加载更多时显示的组件 */
  loadingComponent?: ReactNode
  /** 空状态组件 */
  emptyComponent?: ReactNode
}

export function VirtualList<T>({
  items,
  itemHeight,
  height,
  renderItem,
  overscan = 3,
  className,
  getItemKey = (_, index) => index,
  onEndReached,
  endReachedThreshold = 200,
  isLoadingMore = false,
  loadingComponent,
  emptyComponent,
}: VirtualListProps<T>) {
  const containerRef = useRef<HTMLDivElement>(null)
  const [scrollTop, setScrollTop] = useState(0)
  const [containerHeight, setContainerHeight] = useState(0)

  // 计算可见范围
  const totalHeight = items.length * itemHeight
  const startIndex = Math.max(0, Math.floor(scrollTop / itemHeight) - overscan)
  const endIndex = Math.min(
    items.length,
    Math.ceil((scrollTop + containerHeight) / itemHeight) + overscan
  )
  const visibleItems = items.slice(startIndex, endIndex)
  const offsetY = startIndex * itemHeight

  // 监听容器高度变化
  useEffect(() => {
    const container = containerRef.current
    if (!container) return

    const updateHeight = () => {
      setContainerHeight(container.clientHeight)
    }

    updateHeight()
    const resizeObserver = new ResizeObserver(updateHeight)
    resizeObserver.observe(container)

    return () => resizeObserver.disconnect()
  }, [])

  // 滚动处理
  const handleScroll = useCallback((e: React.UIEvent<HTMLDivElement>) => {
    const target = e.currentTarget
    setScrollTop(target.scrollTop)

    // 检查是否到达底部
    if (onEndReached && !isLoadingMore) {
      const distanceToBottom = target.scrollHeight - target.scrollTop - target.clientHeight
      if (distanceToBottom < endReachedThreshold) {
        onEndReached()
      }
    }
  }, [onEndReached, isLoadingMore, endReachedThreshold])

  // 空状态
  if (items.length === 0 && emptyComponent) {
    return <div className={className}>{emptyComponent}</div>
  }

  return (
    <div
      ref={containerRef}
      className={cn('overflow-auto', className)}
      style={{ height }}
      onScroll={handleScroll}
    >
      <div style={{ height: totalHeight, position: 'relative' }}>
        <div
          style={{
            position: 'absolute',
            top: 0,
            left: 0,
            right: 0,
            transform: `translateY(${offsetY}px)`,
          }}
        >
          {visibleItems.map((item, index) => (
            <div
              key={getItemKey(item, startIndex + index)}
              style={{ height: itemHeight }}
            >
              {renderItem(item, startIndex + index)}
            </div>
          ))}
        </div>
      </div>
      {isLoadingMore && loadingComponent}
    </div>
  )
}

/**
 * 虚拟网格组件
 * 用于图片画廊等网格布局场景
 */
interface VirtualGridProps<T> {
  /** 数据列表 */
  items: T[]
  /** 列数 */
  columns: number
  /** 每项高度 */
  itemHeight: number
  /** 容器高度 */
  height: number | string
  /** 间距 */
  gap?: number
  /** 渲染单个项目 */
  renderItem: (item: T, index: number) => ReactNode
  /** 缓冲区大小（额外渲染的行数） */
  overscan?: number
  /** 容器类名 */
  className?: string
  /** 获取项目唯一键 */
  getItemKey?: (item: T, index: number) => string | number
  /** 滚动到底部回调 */
  onEndReached?: () => void
  /** 触发 onEndReached 的阈值 */
  endReachedThreshold?: number
  /** 是否正在加载更多 */
  isLoadingMore?: boolean
  /** 加载更多时显示的组件 */
  loadingComponent?: ReactNode
  /** 空状态组件 */
  emptyComponent?: ReactNode
}

export function VirtualGrid<T>({
  items,
  columns,
  itemHeight,
  height,
  gap = 16,
  renderItem,
  overscan = 2,
  className,
  getItemKey = (_, index) => index,
  onEndReached,
  endReachedThreshold = 200,
  isLoadingMore = false,
  loadingComponent,
  emptyComponent,
}: VirtualGridProps<T>) {
  const containerRef = useRef<HTMLDivElement>(null)
  const [scrollTop, setScrollTop] = useState(0)
  const [containerHeight, setContainerHeight] = useState(0)

  // 计算行数和总高度
  const rowCount = Math.ceil(items.length / columns)
  const rowHeight = itemHeight + gap
  const totalHeight = rowCount * rowHeight - gap // 最后一行不需要 gap

  // 计算可见范围（按行）
  const startRow = Math.max(0, Math.floor(scrollTop / rowHeight) - overscan)
  const endRow = Math.min(
    rowCount,
    Math.ceil((scrollTop + containerHeight) / rowHeight) + overscan
  )
  const startIndex = startRow * columns
  const endIndex = Math.min(items.length, endRow * columns)
  const visibleItems = items.slice(startIndex, endIndex)
  const offsetY = startRow * rowHeight

  // 监听容器高度变化
  useEffect(() => {
    const container = containerRef.current
    if (!container) return

    const updateHeight = () => {
      setContainerHeight(container.clientHeight)
    }

    updateHeight()
    const resizeObserver = new ResizeObserver(updateHeight)
    resizeObserver.observe(container)

    return () => resizeObserver.disconnect()
  }, [])

  // 滚动处理
  const handleScroll = useCallback((e: React.UIEvent<HTMLDivElement>) => {
    const target = e.currentTarget
    setScrollTop(target.scrollTop)

    // 检查是否到达底部
    if (onEndReached && !isLoadingMore) {
      const distanceToBottom = target.scrollHeight - target.scrollTop - target.clientHeight
      if (distanceToBottom < endReachedThreshold) {
        onEndReached()
      }
    }
  }, [onEndReached, isLoadingMore, endReachedThreshold])

  // 空状态
  if (items.length === 0 && emptyComponent) {
    return <div className={className}>{emptyComponent}</div>
  }

  // 计算每个项目的样式
  const getItemStyle = (index: number): CSSProperties => {
    const localIndex = index - startIndex
    const row = Math.floor(localIndex / columns)
    const col = localIndex % columns
    const itemWidth = `calc((100% - ${(columns - 1) * gap}px) / ${columns})`

    return {
      position: 'absolute',
      width: itemWidth,
      height: itemHeight,
      left: `calc(${col} * (${itemWidth} + ${gap}px))`,
      top: row * rowHeight,
    }
  }

  return (
    <div
      ref={containerRef}
      className={cn('overflow-auto', className)}
      style={{ height }}
      onScroll={handleScroll}
    >
      <div style={{ height: totalHeight, position: 'relative' }}>
        <div
          style={{
            position: 'absolute',
            top: 0,
            left: 0,
            right: 0,
            transform: `translateY(${offsetY}px)`,
          }}
        >
          {visibleItems.map((item, localIndex) => {
            const globalIndex = startIndex + localIndex
            return (
              <div
                key={getItemKey(item, globalIndex)}
                style={getItemStyle(globalIndex)}
              >
                {renderItem(item, globalIndex)}
              </div>
            )
          })}
        </div>
      </div>
      {isLoadingMore && loadingComponent}
    </div>
  )
}

export default VirtualList
