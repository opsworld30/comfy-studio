"""统一缓存服务

提供内存缓存功能，支持：
- TTL 过期
- 手动失效
- 按前缀失效
- 异步锁防止缓存击穿
- LRU 淘汰策略
- 缓存装饰器
- 响应缓存中间件
"""
import asyncio
import time
import logging
import hashlib
from typing import Any, Callable, TypeVar
from functools import wraps
from collections import OrderedDict

logger = logging.getLogger(__name__)

T = TypeVar('T')


class CacheEntry:
    """缓存条目"""
    __slots__ = ('data', 'expires_at', 'created_at')

    def __init__(self, data: Any, ttl: int = 60):
        self.data = data
        self.created_at = time.time()
        self.expires_at = self.created_at + ttl

    def is_expired(self) -> bool:
        return time.time() > self.expires_at

    @property
    def age(self) -> float:
        """缓存年龄（秒）"""
        return time.time() - self.created_at


class CacheService:
    """内存缓存服务

    支持:
    - TTL 过期
    - 手动失效
    - 按前缀失效
    - 异步锁防止缓存击穿
    - LRU 淘汰策略
    - 命中率统计
    """

    def __init__(self, max_size: int = 1000):
        self._cache: OrderedDict[str, CacheEntry] = OrderedDict()
        self._locks: dict[str, asyncio.Lock] = {}
        self._cleanup_interval = 60  # 清理间隔（秒）
        self._last_cleanup = time.time()
        self._max_size = max_size
        # 统计信息
        self._hits = 0
        self._misses = 0

    def _maybe_cleanup(self):
        """定期清理过期缓存"""
        now = time.time()
        if now - self._last_cleanup < self._cleanup_interval:
            return

        self._last_cleanup = now
        expired_keys = [k for k, v in self._cache.items() if v.is_expired()]
        for key in expired_keys:
            del self._cache[key]
            if key in self._locks:
                del self._locks[key]

        if expired_keys:
            logger.debug("Cleaned up %d expired cache entries", len(expired_keys))

    def get(self, key: str) -> Any | None:
        """获取缓存"""
        self._maybe_cleanup()
        entry = self._cache.get(key)
        if entry and not entry.is_expired():
            # LRU: 移动到末尾
            self._cache.move_to_end(key)
            self._hits += 1
            return entry.data
        self._misses += 1
        return None

    def set(self, key: str, data: Any, ttl: int = 60):
        """设置缓存"""
        # LRU 淘汰
        while len(self._cache) >= self._max_size:
            oldest_key = next(iter(self._cache))
            del self._cache[oldest_key]
            if oldest_key in self._locks:
                del self._locks[oldest_key]
            logger.debug("LRU evicted cache entry: %s", oldest_key)
        
        self._cache[key] = CacheEntry(data, ttl)
        self._cache.move_to_end(key)

    def delete(self, key: str):
        """删除缓存"""
        self._cache.pop(key, None)
        self._locks.pop(key, None)

    def delete_prefix(self, prefix: str):
        """删除指定前缀的所有缓存"""
        keys_to_delete = [k for k in self._cache.keys() if k.startswith(prefix)]
        for key in keys_to_delete:
            del self._cache[key]
            if key in self._locks:
                del self._locks[key]
        logger.debug("Deleted %d cache entries with prefix: %s", len(keys_to_delete), prefix)

    def clear(self):
        """清空所有缓存"""
        self._cache.clear()
        self._locks.clear()

    async def get_or_set(
        self,
        key: str,
        factory: Callable[[], Any],
        ttl: int = 60,
        stale_ttl: int = 0
    ) -> Any:
        """获取缓存，如果不存在则调用 factory 生成

        Args:
            key: 缓存键
            factory: 生成数据的异步函数
            ttl: 缓存时间（秒）
            stale_ttl: 允许返回过期数据的额外时间（用于防止缓存雪崩）
        """
        # 检查缓存
        entry = self._cache.get(key)
        if entry:
            if not entry.is_expired():
                return entry.data
            # 如果在 stale_ttl 内，返回旧数据但后台刷新
            elif stale_ttl > 0 and entry.age < (entry.expires_at - entry.created_at + stale_ttl):
                # 启动后台刷新
                asyncio.create_task(self._refresh_cache(key, factory, ttl))
                return entry.data

        # 获取锁防止缓存击穿
        if key not in self._locks:
            self._locks[key] = asyncio.Lock()

        async with self._locks[key]:
            # 双重检查
            entry = self._cache.get(key)
            if entry and not entry.is_expired():
                return entry.data

            # 调用 factory 生成数据
            if asyncio.iscoroutinefunction(factory):
                data = await factory()
            else:
                data = factory()

            self.set(key, data, ttl)
            return data

    async def _refresh_cache(self, key: str, factory: Callable, ttl: int):
        """后台刷新缓存"""
        try:
            if asyncio.iscoroutinefunction(factory):
                data = await factory()
            else:
                data = factory()
            self.set(key, data, ttl)
            logger.debug("Background refreshed cache: %s", key)
        except Exception as e:
            logger.warning("Failed to refresh cache %s: %s", key, e)

    def stats(self) -> dict:
        """获取缓存统计信息"""
        total = len(self._cache)
        expired = sum(1 for v in self._cache.values() if v.is_expired())
        total_requests = self._hits + self._misses
        hit_rate = (self._hits / total_requests * 100) if total_requests > 0 else 0
        
        # 按前缀统计
        prefix_stats = {}
        for key in self._cache.keys():
            prefix = key.split(":")[0] if ":" in key else "other"
            prefix_stats[prefix] = prefix_stats.get(prefix, 0) + 1
        
        return {
            "total_entries": total,
            "active_entries": total - expired,
            "expired_entries": expired,
            "max_size": self._max_size,
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate": f"{hit_rate:.1f}%",
            "prefix_stats": prefix_stats,
        }
    
    def reset_stats(self):
        """重置统计信息"""
        self._hits = 0
        self._misses = 0


# 全局缓存实例
cache_service = CacheService(max_size=2000)


# 缓存装饰器
def cached(key_prefix: str, ttl: int = 60, stale_ttl: int = 0):
    """缓存装饰器

    Args:
        key_prefix: 缓存键前缀
        ttl: 缓存时间（秒）
        stale_ttl: 允许返回过期数据的额外时间
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # 生成缓存键（包含参数）
            key_parts = [key_prefix]
            if args:
                key_parts.extend(str(a) for a in args)
            if kwargs:
                key_parts.extend(f"{k}={v}" for k, v in sorted(kwargs.items()))
            cache_key = ":".join(key_parts)

            return await cache_service.get_or_set(
                cache_key,
                lambda: func(*args, **kwargs),
                ttl=ttl,
                stale_ttl=stale_ttl
            )
        return wrapper
    return decorator


def cached_sync(key_prefix: str, ttl: int = 60):
    """同步函数缓存装饰器

    Args:
        key_prefix: 缓存键前缀
        ttl: 缓存时间（秒）
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # 生成缓存键
            key_parts = [key_prefix]
            if args:
                key_parts.extend(str(a) for a in args)
            if kwargs:
                key_parts.extend(f"{k}={v}" for k, v in sorted(kwargs.items()))
            cache_key = ":".join(key_parts)

            # 检查缓存
            cached_value = cache_service.get(cache_key)
            if cached_value is not None:
                return cached_value
            
            # 执行函数
            result = func(*args, **kwargs)
            cache_service.set(cache_key, result, ttl)
            return result
        return wrapper
    return decorator


def make_cache_key(*args, **kwargs) -> str:
    """生成缓存键"""
    key_parts = [str(a) for a in args]
    key_parts.extend(f"{k}={v}" for k, v in sorted(kwargs.items()))
    return ":".join(key_parts)


def hash_cache_key(data: str) -> str:
    """对长字符串生成哈希缓存键"""
    return hashlib.md5(data.encode()).hexdigest()


# ========== 常用缓存 TTL 常量 ==========
CACHE_TTL_SHORT = 10       # 10秒，用于频繁变化的数据
CACHE_TTL_MEDIUM = 60      # 1分钟，用于一般数据
CACHE_TTL_LONG = 300       # 5分钟，用于较稳定的数据
CACHE_TTL_VERY_LONG = 3600 # 1小时，用于很少变化的数据
