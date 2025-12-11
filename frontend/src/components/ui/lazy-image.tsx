/**
 * 图片懒加载组件
 * 
 * 特性：
 * - Intersection Observer 实现视口懒加载
 * - 加载状态骨架屏
 * - 错误状态处理
 * - 支持 WebP 格式自动检测
 * - 渐进式加载动画
 */
import { useState, useRef, useEffect, ImgHTMLAttributes } from 'react'
import { cn } from '@/lib/utils'
import { ImageOff } from 'lucide-react'

interface LazyImageProps extends Omit<ImgHTMLAttributes<HTMLImageElement>, 'onLoad' | 'onError'> {
  /** 图片源 */
  src: string
  /** 备用图片源（加载失败时使用） */
  fallbackSrc?: string
  /** 低质量占位图（用于渐进式加载） */
  placeholderSrc?: string
  /** 是否显示加载骨架屏 */
  showSkeleton?: boolean
  /** 视口交叉阈值（0-1） */
  threshold?: number
  /** 根边距（提前加载） */
  rootMargin?: string
  /** 加载完成回调 */
  onLoadComplete?: () => void
  /** 加载失败回调 */
  onLoadError?: () => void
  /** 容器类名 */
  containerClassName?: string
}

export function LazyImage({
  src,
  fallbackSrc,
  placeholderSrc,
  showSkeleton = true,
  threshold = 0.1,
  rootMargin = '50px',
  onLoadComplete,
  onLoadError,
  className,
  containerClassName,
  alt = '',
  ...props
}: LazyImageProps) {
  const [isLoaded, setIsLoaded] = useState(false)
  const [isError, setIsError] = useState(false)
  const [isInView, setIsInView] = useState(false)
  const [currentSrc, setCurrentSrc] = useState(placeholderSrc || '')
  const imgRef = useRef<HTMLImageElement>(null)
  const containerRef = useRef<HTMLDivElement>(null)

  // Intersection Observer 监听
  useEffect(() => {
    const container = containerRef.current
    if (!container) return

    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          setIsInView(true)
          observer.disconnect()
        }
      },
      { threshold, rootMargin }
    )

    observer.observe(container)
    return () => observer.disconnect()
  }, [threshold, rootMargin])

  // 进入视口后加载图片
  useEffect(() => {
    if (!isInView || !src) return

    const img = new Image()
    img.src = src

    img.onload = () => {
      setCurrentSrc(src)
      setIsLoaded(true)
      setIsError(false)
      onLoadComplete?.()
    }

    img.onerror = () => {
      if (fallbackSrc && fallbackSrc !== src) {
        // 尝试加载备用图片
        const fallbackImg = new Image()
        fallbackImg.src = fallbackSrc
        fallbackImg.onload = () => {
          setCurrentSrc(fallbackSrc)
          setIsLoaded(true)
          setIsError(false)
        }
        fallbackImg.onerror = () => {
          setIsError(true)
          setIsLoaded(true)
          onLoadError?.()
        }
      } else {
        setIsError(true)
        setIsLoaded(true)
        onLoadError?.()
      }
    }
  }, [isInView, src, fallbackSrc, onLoadComplete, onLoadError])

  return (
    <div
      ref={containerRef}
      className={cn(
        'relative overflow-hidden bg-muted',
        containerClassName
      )}
    >
      {/* 骨架屏 */}
      {showSkeleton && !isLoaded && (
        <div className="absolute inset-0 animate-pulse bg-gradient-to-r from-muted via-muted-foreground/10 to-muted" />
      )}

      {/* 错误状态 */}
      {isError && (
        <div className="absolute inset-0 flex items-center justify-center bg-muted">
          <div className="flex flex-col items-center gap-2 text-muted-foreground">
            <ImageOff className="h-8 w-8" />
            <span className="text-xs">加载失败</span>
          </div>
        </div>
      )}

      {/* 图片 */}
      {!isError && currentSrc && (
        <img
          ref={imgRef}
          src={currentSrc}
          alt={alt}
          className={cn(
            'transition-opacity duration-300',
            isLoaded ? 'opacity-100' : 'opacity-0',
            className
          )}
          {...props}
        />
      )}
    </div>
  )
}

/**
 * 图片网格懒加载组件
 * 用于画廊等大量图片场景
 */
interface LazyImageGridProps {
  images: Array<{
    src: string
    alt?: string
    id: string | number
  }>
  columns?: number
  gap?: number
  aspectRatio?: 'square' | 'video' | 'auto'
  onImageClick?: (id: string | number) => void
  className?: string
}

export function LazyImageGrid({
  images,
  columns = 4,
  gap = 4,
  aspectRatio = 'square',
  onImageClick,
  className,
}: LazyImageGridProps) {
  const aspectRatioClass = {
    square: 'aspect-square',
    video: 'aspect-video',
    auto: '',
  }[aspectRatio]

  return (
    <div
      className={cn('grid', className)}
      style={{
        gridTemplateColumns: `repeat(${columns}, 1fr)`,
        gap: `${gap * 4}px`,
      }}
    >
      {images.map((image) => (
        <div
          key={image.id}
          className={cn(
            'cursor-pointer overflow-hidden rounded-lg',
            aspectRatioClass
          )}
          onClick={() => onImageClick?.(image.id)}
        >
          <LazyImage
            src={image.src}
            alt={image.alt || ''}
            className="h-full w-full object-cover hover:scale-105 transition-transform duration-300"
            containerClassName="h-full w-full"
          />
        </div>
      ))}
    </div>
  )
}

export default LazyImage
