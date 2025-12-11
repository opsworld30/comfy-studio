"""慢查询日志和性能监控中间件

提供：
- 慢请求日志记录
- 请求耗时统计
- 数据库查询监控
- 性能指标收集
"""
import time
import logging
import asyncio
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Callable
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)
slow_query_logger = logging.getLogger("slow_query")


@dataclass
class RequestMetrics:
    """请求指标"""
    path: str
    method: str
    status_code: int
    duration_ms: float
    timestamp: datetime
    client_ip: str = ""
    user_id: str = ""
    query_count: int = 0
    query_time_ms: float = 0


@dataclass
class EndpointStats:
    """端点统计"""
    total_requests: int = 0
    total_time_ms: float = 0
    min_time_ms: float = float('inf')
    max_time_ms: float = 0
    error_count: int = 0
    slow_count: int = 0
    last_request: float = 0
    
    # 响应时间分布
    p50_times: list[float] = field(default_factory=list)
    
    def add_request(self, duration_ms: float, is_error: bool = False, is_slow: bool = False):
        self.total_requests += 1
        self.total_time_ms += duration_ms
        self.min_time_ms = min(self.min_time_ms, duration_ms)
        self.max_time_ms = max(self.max_time_ms, duration_ms)
        self.last_request = time.time()
        
        if is_error:
            self.error_count += 1
        if is_slow:
            self.slow_count += 1
        
        # 保留最近 100 个请求用于计算百分位
        self.p50_times.append(duration_ms)
        if len(self.p50_times) > 100:
            self.p50_times.pop(0)
    
    @property
    def avg_time_ms(self) -> float:
        return self.total_time_ms / max(1, self.total_requests)
    
    @property
    def p50(self) -> float:
        if not self.p50_times:
            return 0
        sorted_times = sorted(self.p50_times)
        return sorted_times[len(sorted_times) // 2]
    
    @property
    def p95(self) -> float:
        if not self.p50_times:
            return 0
        sorted_times = sorted(self.p50_times)
        idx = int(len(sorted_times) * 0.95)
        return sorted_times[min(idx, len(sorted_times) - 1)]
    
    @property
    def p99(self) -> float:
        if not self.p50_times:
            return 0
        sorted_times = sorted(self.p50_times)
        idx = int(len(sorted_times) * 0.99)
        return sorted_times[min(idx, len(sorted_times) - 1)]


class QueryCounter:
    """数据库查询计数器（线程本地存储）"""
    
    def __init__(self):
        self._local = {}
    
    def get_request_id(self) -> str:
        """获取当前请求 ID"""
        try:
            task = asyncio.current_task()
            return str(id(task)) if task else "unknown"
        except RuntimeError:
            return "unknown"
    
    def start_request(self):
        """开始请求"""
        request_id = self.get_request_id()
        self._local[request_id] = {"count": 0, "time_ms": 0}
    
    def record_query(self, duration_ms: float):
        """记录查询"""
        request_id = self.get_request_id()
        if request_id in self._local:
            self._local[request_id]["count"] += 1
            self._local[request_id]["time_ms"] += duration_ms
    
    def end_request(self) -> tuple[int, float]:
        """结束请求，返回 (查询数, 总耗时)"""
        request_id = self.get_request_id()
        data = self._local.pop(request_id, {"count": 0, "time_ms": 0})
        return data["count"], data["time_ms"]


# 全局查询计数器
query_counter = QueryCounter()


class SlowQueryMiddleware(BaseHTTPMiddleware):
    """慢查询和性能监控中间件
    
    功能：
    - 记录慢请求日志
    - 收集端点性能指标
    - 监控数据库查询
    """
    
    def __init__(
        self,
        app,
        slow_threshold_ms: float = 1000,  # 慢请求阈值（毫秒）
        very_slow_threshold_ms: float = 5000,  # 非常慢请求阈值
        log_all_requests: bool = False,  # 是否记录所有请求
        exclude_paths: list[str] = None,
        enable_stats: bool = True,
        max_slow_logs: int = 1000,  # 保留的慢查询日志数量
    ):
        super().__init__(app)
        self.slow_threshold_ms = slow_threshold_ms
        self.very_slow_threshold_ms = very_slow_threshold_ms
        self.log_all_requests = log_all_requests
        self.exclude_paths = exclude_paths or [
            "/health", "/ready", "/live",
            "/docs", "/redoc", "/openapi.json",
        ]
        self.enable_stats = enable_stats
        self.max_slow_logs = max_slow_logs
        
        # 端点统计
        self._endpoint_stats: dict[str, EndpointStats] = defaultdict(EndpointStats)
        
        # 慢查询日志
        self._slow_logs: list[RequestMetrics] = []
        
        # 全局统计
        self._global_stats = {
            "total_requests": 0,
            "total_time_ms": 0,
            "slow_requests": 0,
            "very_slow_requests": 0,
            "error_requests": 0,
        }
    
    def _get_client_ip(self, request: Request) -> str:
        """获取客户端 IP"""
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            return forwarded.split(",")[0].strip()
        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip
        return request.client.host if request.client else "unknown"
    
    def _get_user_id(self, request: Request) -> str:
        """获取用户 ID"""
        user = getattr(request.state, "user", None)
        if user and hasattr(user, "id"):
            return str(user.id)
        return ""
    
    def _get_endpoint_key(self, path: str, method: str) -> str:
        """生成端点键（规范化路径参数）"""
        # 简单的路径规范化：将数字 ID 替换为 {id}
        import re
        normalized = re.sub(r'/\d+', '/{id}', path)
        return f"{method} {normalized}"
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        path = request.url.path
        method = request.method
        
        # 排除特定路径
        if any(path.startswith(excluded) for excluded in self.exclude_paths):
            return await call_next(request)
        
        # 开始计时
        start_time = time.perf_counter()
        query_counter.start_request()
        
        # 执行请求
        response = None
        try:
            response = await call_next(request)
        except Exception:
            raise
        finally:
            # 计算耗时
            duration_ms = (time.perf_counter() - start_time) * 1000
            query_count, query_time_ms = query_counter.end_request()
            
            status_code = response.status_code if response else 500
            is_error = status_code >= 400
            is_slow = duration_ms >= self.slow_threshold_ms
            is_very_slow = duration_ms >= self.very_slow_threshold_ms
            
            # 更新统计
            if self.enable_stats:
                self._update_stats(
                    path, method, duration_ms, 
                    is_error, is_slow, is_very_slow
                )
            
            # 记录日志
            if is_slow or self.log_all_requests:
                self._log_request(
                    request, path, method, status_code, 
                    duration_ms, query_count, query_time_ms,
                    is_slow, is_very_slow
                )
            
            # 添加性能头
            if response:
                response.headers["X-Response-Time"] = f"{duration_ms:.2f}ms"
                if query_count > 0:
                    response.headers["X-DB-Queries"] = str(query_count)
        
        return response
    
    def _update_stats(
        self, 
        path: str, 
        method: str, 
        duration_ms: float,
        is_error: bool,
        is_slow: bool,
        is_very_slow: bool
    ):
        """更新统计信息"""
        # 全局统计
        self._global_stats["total_requests"] += 1
        self._global_stats["total_time_ms"] += duration_ms
        if is_error:
            self._global_stats["error_requests"] += 1
        if is_slow:
            self._global_stats["slow_requests"] += 1
        if is_very_slow:
            self._global_stats["very_slow_requests"] += 1
        
        # 端点统计
        endpoint_key = self._get_endpoint_key(path, method)
        self._endpoint_stats[endpoint_key].add_request(duration_ms, is_error, is_slow)
    
    def _log_request(
        self,
        request: Request,
        path: str,
        method: str,
        status_code: int,
        duration_ms: float,
        query_count: int,
        query_time_ms: float,
        is_slow: bool,
        is_very_slow: bool
    ):
        """记录请求日志"""
        client_ip = self._get_client_ip(request)
        user_id = self._get_user_id(request)
        
        # 创建指标
        metrics = RequestMetrics(
            path=path,
            method=method,
            status_code=status_code,
            duration_ms=duration_ms,
            timestamp=datetime.now(timezone.utc),
            client_ip=client_ip,
            user_id=user_id,
            query_count=query_count,
            query_time_ms=query_time_ms,
        )
        
        # 记录到慢查询日志
        if is_slow:
            self._slow_logs.append(metrics)
            if len(self._slow_logs) > self.max_slow_logs:
                self._slow_logs.pop(0)
        
        # 输出日志
        log_msg = (
            f"{method} {path} - {status_code} - {duration_ms:.2f}ms"
            f" [queries: {query_count}, query_time: {query_time_ms:.2f}ms]"
            f" [client: {client_ip}]"
        )
        
        if is_very_slow:
            slow_query_logger.error(f"[VERY SLOW] {log_msg}")
        elif is_slow:
            slow_query_logger.warning(f"[SLOW] {log_msg}")
        elif self.log_all_requests:
            slow_query_logger.debug(log_msg)
    
    def get_stats(self) -> dict:
        """获取性能统计"""
        total = self._global_stats["total_requests"]
        
        # 端点统计
        endpoints = []
        for key, stats in sorted(
            self._endpoint_stats.items(),
            key=lambda x: x[1].total_requests,
            reverse=True
        )[:20]:  # Top 20 端点
            endpoints.append({
                "endpoint": key,
                "requests": stats.total_requests,
                "avg_ms": round(stats.avg_time_ms, 2),
                "min_ms": round(stats.min_time_ms, 2) if stats.min_time_ms != float('inf') else 0,
                "max_ms": round(stats.max_time_ms, 2),
                "p50_ms": round(stats.p50, 2),
                "p95_ms": round(stats.p95, 2),
                "p99_ms": round(stats.p99, 2),
                "errors": stats.error_count,
                "slow": stats.slow_count,
            })
        
        return {
            "global": {
                "total_requests": total,
                "avg_time_ms": round(self._global_stats["total_time_ms"] / max(1, total), 2),
                "slow_requests": self._global_stats["slow_requests"],
                "very_slow_requests": self._global_stats["very_slow_requests"],
                "error_requests": self._global_stats["error_requests"],
                "slow_rate": f"{self._global_stats['slow_requests'] / max(1, total) * 100:.2f}%",
                "error_rate": f"{self._global_stats['error_requests'] / max(1, total) * 100:.2f}%",
            },
            "endpoints": endpoints,
            "thresholds": {
                "slow_ms": self.slow_threshold_ms,
                "very_slow_ms": self.very_slow_threshold_ms,
            }
        }
    
    def get_slow_logs(self, limit: int = 50) -> list[dict]:
        """获取慢查询日志"""
        return [
            {
                "path": m.path,
                "method": m.method,
                "status_code": m.status_code,
                "duration_ms": round(m.duration_ms, 2),
                "timestamp": m.timestamp.isoformat(),
                "client_ip": m.client_ip,
                "user_id": m.user_id,
                "query_count": m.query_count,
                "query_time_ms": round(m.query_time_ms, 2),
            }
            for m in reversed(self._slow_logs[-limit:])
        ]
    
    def get_slowest_endpoints(self, limit: int = 10) -> list[dict]:
        """获取最慢的端点"""
        sorted_endpoints = sorted(
            self._endpoint_stats.items(),
            key=lambda x: x[1].p95,
            reverse=True
        )[:limit]
        
        return [
            {
                "endpoint": key,
                "p95_ms": round(stats.p95, 2),
                "p99_ms": round(stats.p99, 2),
                "max_ms": round(stats.max_time_ms, 2),
                "requests": stats.total_requests,
            }
            for key, stats in sorted_endpoints
        ]
    
    def reset_stats(self):
        """重置统计"""
        self._endpoint_stats.clear()
        self._slow_logs.clear()
        self._global_stats = {
            "total_requests": 0,
            "total_time_ms": 0,
            "slow_requests": 0,
            "very_slow_requests": 0,
            "error_requests": 0,
        }


# 全局中间件实例（用于获取统计）
_slow_query_middleware: SlowQueryMiddleware | None = None


def get_slow_query_middleware() -> SlowQueryMiddleware | None:
    """获取慢查询中间件实例"""
    return _slow_query_middleware


def set_slow_query_middleware(middleware: SlowQueryMiddleware):
    """设置慢查询中间件实例"""
    global _slow_query_middleware
    _slow_query_middleware = middleware
