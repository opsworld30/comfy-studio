"""速率限制中间件

支持：
- 全局限流
- 按路径限流
- 按用户/IP 限流
- 令牌桶算法
- 滑动窗口算法
"""
import time
import re
import logging
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Callable
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)


@dataclass
class RateLimitRule:
    """限流规则"""
    path_pattern: str  # 路径正则表达式
    requests_per_second: int = 10
    requests_per_minute: int = 60
    burst: int = 20  # 突发容量
    by_user: bool = False  # 是否按用户限流（需要认证）
    methods: list[str] = field(default_factory=lambda: ["GET", "POST", "PUT", "DELETE"])
    
    def __post_init__(self):
        self._pattern = re.compile(self.path_pattern)
    
    def matches(self, path: str, method: str) -> bool:
        """检查是否匹配规则"""
        return self._pattern.match(path) is not None and method.upper() in self.methods


class TokenBucket:
    """令牌桶算法实现"""
    
    def __init__(self, rate: float, capacity: int):
        """
        Args:
            rate: 每秒生成的令牌数
            capacity: 桶容量
        """
        self.rate = rate
        self.capacity = capacity
        self.tokens = capacity
        self.last_update = time.time()
    
    def consume(self, tokens: int = 1) -> bool:
        """消费令牌"""
        now = time.time()
        
        # 添加新令牌
        elapsed = now - self.last_update
        self.tokens = min(self.capacity, self.tokens + elapsed * self.rate)
        self.last_update = now
        
        # 检查是否有足够令牌
        if self.tokens >= tokens:
            self.tokens -= tokens
            return True
        return False
    
    @property
    def available(self) -> float:
        """当前可用令牌数"""
        now = time.time()
        elapsed = now - self.last_update
        return min(self.capacity, self.tokens + elapsed * self.rate)


class SlidingWindowCounter:
    """滑动窗口计数器"""
    
    def __init__(self, window_size: int = 60, max_requests: int = 60):
        """
        Args:
            window_size: 窗口大小（秒）
            max_requests: 窗口内最大请求数
        """
        self.window_size = window_size
        self.max_requests = max_requests
        self.requests: list[float] = []
    
    def is_allowed(self) -> bool:
        """检查是否允许请求"""
        now = time.time()
        cutoff = now - self.window_size
        
        # 清理过期请求
        self.requests = [ts for ts in self.requests if ts > cutoff]
        
        if len(self.requests) < self.max_requests:
            self.requests.append(now)
            return True
        return False
    
    @property
    def remaining(self) -> int:
        """剩余请求数"""
        now = time.time()
        cutoff = now - self.window_size
        current = sum(1 for ts in self.requests if ts > cutoff)
        return max(0, self.max_requests - current)


class AdvancedRateLimitMiddleware(BaseHTTPMiddleware):
    """
    高级速率限制中间件
    
    支持：
    - 多级限流规则
    - 令牌桶 + 滑动窗口
    - 按路径/用户精细控制
    - 限流统计
    """
    
    # 默认规则
    DEFAULT_RULES = [
        # AI 相关接口 - 严格限流
        RateLimitRule(
            path_pattern=r"^/api/(smart-create/analyze|ai-workflow)",
            requests_per_second=2,
            requests_per_minute=20,
            burst=5,
        ),
        # 图片上传/下载 - 中等限流
        RateLimitRule(
            path_pattern=r"^/api/(gallery|comfyui/image)",
            requests_per_second=10,
            requests_per_minute=100,
            burst=30,
        ),
        # 执行工作流 - 中等限流
        RateLimitRule(
            path_pattern=r"^/api/comfyui/execute",
            requests_per_second=5,
            requests_per_minute=50,
            burst=10,
            methods=["POST"],
        ),
        # 批量操作 - 严格限流
        RateLimitRule(
            path_pattern=r"^/api/batch",
            requests_per_second=3,
            requests_per_minute=30,
            burst=5,
        ),
        # 认证接口 - 防暴力破解
        RateLimitRule(
            path_pattern=r"^/api/auth/(login|register)",
            requests_per_second=1,
            requests_per_minute=10,
            burst=3,
            methods=["POST"],
        ),
    ]
    
    def __init__(
        self,
        app,
        requests_per_minute: int = 120,
        requests_per_second: int = 20,
        rules: list[RateLimitRule] = None,
        exclude_paths: list[str] = None,
        enable_stats: bool = True,
    ):
        super().__init__(app)
        self.global_rpm = requests_per_minute
        self.global_rps = requests_per_second
        self.rules = rules or self.DEFAULT_RULES
        self.exclude_paths = exclude_paths or [
            "/health", "/ready", "/live", 
            "/docs", "/redoc", "/openapi.json",
            "/ws",  # WebSocket 不限流
        ]
        self.enable_stats = enable_stats
        
        # 全局限流器（令牌桶）
        self._global_buckets: dict[str, TokenBucket] = defaultdict(
            lambda: TokenBucket(rate=self.global_rps, capacity=self.global_rps * 2)
        )
        
        # 规则限流器（滑动窗口）
        self._rule_counters: dict[str, dict[str, SlidingWindowCounter]] = defaultdict(dict)
        
        # 统计信息
        self._stats = {
            "total_requests": 0,
            "blocked_requests": 0,
            "blocked_by_rule": defaultdict(int),
        }
        
        # 清理计时器
        self._cleanup_interval = 300  # 5 分钟清理一次
        self._last_cleanup = time.time()
    
    def _get_client_id(self, request: Request) -> str:
        """获取客户端标识"""
        # 优先使用认证用户 ID
        user = getattr(request.state, "user", None)
        if user and hasattr(user, "id"):
            return f"user:{user.id}"
        
        # 使用 IP
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            return f"ip:{forwarded.split(',')[0].strip()}"
        
        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return f"ip:{real_ip}"
        
        return f"ip:{request.client.host if request.client else 'unknown'}"
    
    def _find_matching_rule(self, path: str, method: str) -> RateLimitRule | None:
        """查找匹配的限流规则"""
        for rule in self.rules:
            if rule.matches(path, method):
                return rule
        return None
    
    def _cleanup(self):
        """清理过期数据"""
        now = time.time()
        if now - self._last_cleanup < self._cleanup_interval:
            return
        
        # 清理不活跃的令牌桶
        inactive_threshold = 300  # 5 分钟不活跃
        inactive_clients = [
            client_id for client_id, bucket in self._global_buckets.items()
            if now - bucket.last_update > inactive_threshold
        ]
        for client_id in inactive_clients:
            del self._global_buckets[client_id]
        
        self._last_cleanup = now
        
        if inactive_clients:
            logger.debug(f"Cleaned up {len(inactive_clients)} inactive rate limit buckets")
    
    def _check_rate_limit(
        self, 
        client_id: str, 
        path: str, 
        method: str
    ) -> tuple[bool, str | None, RateLimitRule | None]:
        """检查速率限制
        
        Returns:
            (is_allowed, error_message, matched_rule)
        """
        # 1. 检查全局限流
        bucket = self._global_buckets[client_id]
        if not bucket.consume():
            return False, "Global rate limit exceeded", None
        
        # 2. 检查规则限流
        rule = self._find_matching_rule(path, method)
        if rule:
            rule_key = rule.path_pattern
            if client_id not in self._rule_counters[rule_key]:
                self._rule_counters[rule_key][client_id] = SlidingWindowCounter(
                    window_size=60,
                    max_requests=rule.requests_per_minute
                )
            
            counter = self._rule_counters[rule_key][client_id]
            if not counter.is_allowed():
                return False, f"Rate limit exceeded for {rule.path_pattern}", rule
        
        return True, None, rule
    
    def get_stats(self) -> dict:
        """获取限流统计"""
        return {
            "total_requests": self._stats["total_requests"],
            "blocked_requests": self._stats["blocked_requests"],
            "block_rate": f"{self._stats['blocked_requests'] / max(1, self._stats['total_requests']) * 100:.2f}%",
            "blocked_by_rule": dict(self._stats["blocked_by_rule"]),
            "active_clients": len(self._global_buckets),
        }
    
    def reset_stats(self):
        """重置统计"""
        self._stats = {
            "total_requests": 0,
            "blocked_requests": 0,
            "blocked_by_rule": defaultdict(int),
        }
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        path = request.url.path
        method = request.method
        
        # 排除特定路径
        if any(path.startswith(excluded) for excluded in self.exclude_paths):
            return await call_next(request)
        
        # 定期清理
        self._cleanup()
        
        # 获取客户端标识
        client_id = self._get_client_id(request)
        
        # 统计
        if self.enable_stats:
            self._stats["total_requests"] += 1
        
        # 检查速率限制
        is_allowed, message, rule = self._check_rate_limit(client_id, path, method)
        
        if not is_allowed:
            if self.enable_stats:
                self._stats["blocked_requests"] += 1
                if rule:
                    self._stats["blocked_by_rule"][rule.path_pattern] += 1
            
            logger.warning(f"Rate limited: {client_id} - {path} - {message}")
            
            return Response(
                content=message,
                status_code=429,
                headers={
                    "Retry-After": "1",
                    "X-RateLimit-Limit": str(rule.requests_per_minute if rule else self.global_rpm),
                }
            )
        
        # 继续处理请求
        response = await call_next(request)
        
        # 添加限流头
        bucket = self._global_buckets[client_id]
        response.headers["X-RateLimit-Limit"] = str(self.global_rpm)
        response.headers["X-RateLimit-Remaining"] = str(int(bucket.available))
        
        return response


# 保持向后兼容
class RateLimitMiddleware(AdvancedRateLimitMiddleware):
    """向后兼容的速率限制中间件"""
    pass
