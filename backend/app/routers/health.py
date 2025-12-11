"""健康检查路由"""
import platform
import psutil
from datetime import datetime, timezone
from fastapi import APIRouter
from pydantic import BaseModel

from ..services.comfyui import comfyui_service
from ..services.cache import cache_service

router = APIRouter(tags=["health"])


class HealthStatus(BaseModel):
    status: str
    timestamp: str
    version: str = "1.0.0"
    uptime_seconds: float | None = None


class DetailedHealthStatus(HealthStatus):
    system: dict
    comfyui: dict
    database: dict


# 记录启动时间
_start_time = datetime.now(timezone.utc)


@router.get("/health", response_model=HealthStatus)
async def health_check():
    """基础健康检查"""
    return HealthStatus(
        status="healthy",
        timestamp=datetime.now(timezone.utc).isoformat(),
        uptime_seconds=(datetime.now(timezone.utc) - _start_time).total_seconds(),
    )


@router.get("/health/detailed", response_model=DetailedHealthStatus)
async def detailed_health_check():
    """详细健康检查"""
    # 系统信息
    system_info = {
        "os": platform.system(),
        "os_version": platform.version(),
        "python_version": platform.python_version(),
        "cpu_count": psutil.cpu_count(),
        "cpu_percent": psutil.cpu_percent(interval=0.1),
        "memory_total_gb": round(psutil.virtual_memory().total / (1024**3), 2),
        "memory_used_percent": psutil.virtual_memory().percent,
        "disk_used_percent": psutil.disk_usage('/').percent if platform.system() != 'Windows' else psutil.disk_usage('C:').percent,
    }
    
    # ComfyUI 状态
    comfyui_connected = await comfyui_service.check_connection()
    comfyui_info = {
        "connected": comfyui_connected,
        "url": comfyui_service.base_url,
    }
    
    if comfyui_connected:
        try:
            system_stats = await comfyui_service.get_system_stats()
            queue = await comfyui_service.get_queue()
            comfyui_info["system_stats"] = system_stats
            comfyui_info["queue_running"] = len(queue.get("queue_running", []))
            comfyui_info["queue_pending"] = len(queue.get("queue_pending", []))
        except Exception:
            pass
    
    # 数据库状态
    database_info = {
        "status": "healthy",
        "type": "sqlite",
    }
    
    return DetailedHealthStatus(
        status="healthy" if comfyui_connected else "degraded",
        timestamp=datetime.now(timezone.utc).isoformat(),
        uptime_seconds=(datetime.now(timezone.utc) - _start_time).total_seconds(),
        system=system_info,
        comfyui=comfyui_info,
        database=database_info,
    )


@router.get("/ready")
async def readiness_check():
    """就绪检查 - 用于 K8s 等容器编排"""
    comfyui_connected = await comfyui_service.check_connection()
    
    if not comfyui_connected:
        return {"ready": False, "reason": "ComfyUI not connected"}
    
    return {"ready": True}


@router.get("/live")
async def liveness_check():
    """存活检查 - 用于 K8s 等容器编排"""
    return {"alive": True}


@router.get("/cache/stats")
async def cache_stats():
    """获取缓存统计信息"""
    return cache_service.stats()


@router.post("/cache/clear")
async def clear_cache():
    """清空所有缓存"""
    cache_service.clear()
    return {"message": "缓存已清空"}
