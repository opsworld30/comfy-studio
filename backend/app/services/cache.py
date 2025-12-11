"""统一缓存服务"""
import asyncio
import time
import logging
from typing import Any, Callable, TypeVar
from functools import wraps

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
    """

    def __init__(self):
        self._cache: dict[str, CacheEntry] = {}
        self._locks: dict[str, asyncio.Lock] = {}
        self._cleanup_interval = 60  # 清理间隔（秒）
        self._last_cleanup = time.time()

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
            return entry.data
        return None

    def set(self, key: str, data: Any, ttl: int = 60):
        """设置缓存"""
        self._cache[key] = CacheEntry(data, ttl)

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
        return {
            "total_entries": total,
            "active_entries": total - expired,
            "expired_entries": expired,
        }


# 全局缓存实例
cache_service = CacheService()


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
