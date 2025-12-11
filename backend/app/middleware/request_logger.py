"""请求日志中间件"""
import time
import logging
import uuid
from typing import Callable
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger("request")


class RequestLoggerMiddleware(BaseHTTPMiddleware):
    """记录 API 请求日志的中间件"""
    
    def __init__(
        self,
        app,
        exclude_paths: list[str] | None = None,
        log_request_body: bool = False,
        log_response_body: bool = False,
    ):
        super().__init__(app)
        self.exclude_paths = exclude_paths or ["/health", "/ready", "/live", "/docs", "/openapi.json"]
        self.log_request_body = log_request_body
        self.log_response_body = log_response_body
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # 跳过排除的路径
        if any(request.url.path.startswith(path) for path in self.exclude_paths):
            return await call_next(request)
        
        # 生成请求 ID
        request_id = str(uuid.uuid4())[:8]
        
        # 记录请求开始时间
        start_time = time.time()
        
        # 获取客户端信息
        client_ip = request.client.host if request.client else "unknown"
        user_agent = request.headers.get("user-agent", "unknown")[:100]
        
        # 记录请求信息
        log_data = {
            "request_id": request_id,
            "method": request.method,
            "path": request.url.path,
            "query": str(request.query_params) if request.query_params else None,
            "client_ip": client_ip,
            "user_agent": user_agent,
        }
        
        # 可选：记录请求体
        if self.log_request_body and request.method in ["POST", "PUT", "PATCH"]:
            try:
                body = await request.body()
                if len(body) < 10000:  # 限制大小
                    log_data["request_body"] = body.decode("utf-8")[:1000]
            except Exception:
                pass
        
        logger.info(f"[{request_id}] --> {request.method} {request.url.path}", extra=log_data)
        
        # 处理请求
        try:
            response = await call_next(request)
            
            # 计算耗时
            duration = time.time() - start_time
            duration_ms = round(duration * 1000, 2)
            
            # 记录响应信息
            log_data.update({
                "status_code": response.status_code,
                "duration_ms": duration_ms,
            })
            
            # 根据状态码选择日志级别
            if response.status_code >= 500:
                logger.error(
                    f"[{request_id}] <-- {response.status_code} ({duration_ms}ms)",
                    extra=log_data
                )
            elif response.status_code >= 400:
                logger.warning(
                    f"[{request_id}] <-- {response.status_code} ({duration_ms}ms)",
                    extra=log_data
                )
            else:
                logger.info(
                    f"[{request_id}] <-- {response.status_code} ({duration_ms}ms)",
                    extra=log_data
                )
            
            # 添加请求 ID 到响应头
            response.headers["X-Request-ID"] = request_id
            
            return response
            
        except Exception as e:
            duration = time.time() - start_time
            duration_ms = round(duration * 1000, 2)
            
            logger.exception(
                f"[{request_id}] <-- ERROR ({duration_ms}ms): {str(e)}",
                extra={**log_data, "error": str(e)}
            )
            raise
