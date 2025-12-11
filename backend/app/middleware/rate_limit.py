"""速率限制中间件"""
import time
from collections import defaultdict
from typing import Callable
from fastapi import Request, Response, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    简单的内存速率限制中间件
    
    使用滑动窗口算法限制请求频率
    """
    
    def __init__(
        self,
        app,
        requests_per_minute: int = 60,
        requests_per_second: int = 10,
        exclude_paths: list[str] | None = None,
    ):
        super().__init__(app)
        self.requests_per_minute = requests_per_minute
        self.requests_per_second = requests_per_second
        self.exclude_paths = exclude_paths or ["/health", "/ready", "/live", "/docs", "/redoc", "/openapi.json"]
        
        # 存储请求记录: {client_ip: [(timestamp, count), ...]}
        self._requests: dict[str, list[float]] = defaultdict(list)
        self._cleanup_interval = 60  # 清理间隔（秒）
        self._last_cleanup = time.time()
    
    def _get_client_ip(self, request: Request) -> str:
        """获取客户端 IP"""
        # 优先从 X-Forwarded-For 获取
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            return forwarded.split(",")[0].strip()
        
        # 从 X-Real-IP 获取
        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip
        
        # 直接获取
        return request.client.host if request.client else "unknown"
    
    def _cleanup_old_requests(self):
        """清理过期的请求记录"""
        current_time = time.time()
        
        if current_time - self._last_cleanup < self._cleanup_interval:
            return
        
        cutoff = current_time - 60  # 保留最近 1 分钟的记录
        
        for ip in list(self._requests.keys()):
            self._requests[ip] = [
                ts for ts in self._requests[ip] if ts > cutoff
            ]
            if not self._requests[ip]:
                del self._requests[ip]
        
        self._last_cleanup = current_time
    
    def _is_rate_limited(self, client_ip: str) -> tuple[bool, str | None]:
        """检查是否超过速率限制"""
        current_time = time.time()
        requests = self._requests[client_ip]
        
        # 检查每秒限制
        one_second_ago = current_time - 1
        recent_second = sum(1 for ts in requests if ts > one_second_ago)
        if recent_second >= self.requests_per_second:
            return True, f"Rate limit exceeded: {self.requests_per_second} requests per second"
        
        # 检查每分钟限制
        one_minute_ago = current_time - 60
        recent_minute = sum(1 for ts in requests if ts > one_minute_ago)
        if recent_minute >= self.requests_per_minute:
            return True, f"Rate limit exceeded: {self.requests_per_minute} requests per minute"
        
        return False, None
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # 排除特定路径
        path = request.url.path
        if any(path.startswith(excluded) for excluded in self.exclude_paths):
            return await call_next(request)
        
        # 清理过期记录
        self._cleanup_old_requests()
        
        # 获取客户端 IP
        client_ip = self._get_client_ip(request)
        
        # 检查速率限制
        is_limited, message = self._is_rate_limited(client_ip)
        if is_limited:
            return Response(
                content=message,
                status_code=429,
                headers={
                    "Retry-After": "1",
                    "X-RateLimit-Limit": str(self.requests_per_minute),
                }
            )
        
        # 记录请求
        self._requests[client_ip].append(time.time())
        
        # 继续处理请求
        response = await call_next(request)
        
        # 添加速率限制头
        response.headers["X-RateLimit-Limit"] = str(self.requests_per_minute)
        response.headers["X-RateLimit-Remaining"] = str(
            self.requests_per_minute - len([
                ts for ts in self._requests[client_ip] if ts > time.time() - 60
            ])
        )
        
        return response
