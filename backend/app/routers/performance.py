"""性能监控 API"""
from datetime import datetime, timedelta, timezone
from typing import List
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, case
from pydantic import BaseModel

from ..database import get_db
from ..models import PerformanceLog, ExecutionHistory, Workflow
from ..middleware import get_slow_query_middleware
from ..services.task_queue import get_all_queue_stats

router = APIRouter(prefix="/performance", tags=["performance"])


class PerformanceSnapshot(BaseModel):
    gpu_usage: float = 0
    vram_used: float = 0
    vram_total: float = 0
    cpu_usage: float = 0
    ram_used: float = 0
    ram_total: float = 0
    temperature: float = 0
    queue_size: int = 0


class PerformanceLogResponse(BaseModel):
    timestamp: datetime
    gpu_usage: float
    vram_used: float
    vram_total: float
    cpu_usage: float
    ram_used: float
    ram_total: float
    temperature: float
    queue_size: int

    class Config:
        from_attributes = True


class ExecutionStats(BaseModel):
    success_count: int = 0
    failed_count: int = 0
    cancelled_count: int = 0
    avg_duration: float = 0
    total_images: int = 0
    gpu_hours: float = 0


@router.get("/current", response_model=PerformanceSnapshot)
async def get_current_performance():
    """获取当前性能快照"""
    import psutil
    
    # CPU 和内存
    cpu_usage = psutil.cpu_percent(interval=0.1)
    memory = psutil.virtual_memory()
    ram_used = memory.used / (1024 ** 3)  # GB
    ram_total = memory.total / (1024 ** 3)  # GB
    
    # 磁盘（预留，暂未使用）
    # disk = psutil.disk_usage('/')
    
    # GPU 信息 (尝试使用 pynvml)
    gpu_usage = 0.0
    vram_used = 0.0
    vram_total = 0.0
    temperature = 0.0
    
    try:
        from pynvml import smi
        nvidia_smi = smi.nvidia_smi.getInstance()
        gpu_query = nvidia_smi.DeviceQuery('utilization.gpu, memory.used, memory.total, temperature.gpu')
        gpu_info = gpu_query.get('gpu', [{}])[0]
        
        gpu_usage = gpu_info.get('utilization', {}).get('gpu_util', 0)
        mem = gpu_info.get('fb_memory_usage', {})
        vram_used = mem.get('used', 0) / 1024  # MB to GB
        vram_total = mem.get('total', 0) / 1024
        temperature = gpu_info.get('temperature', {}).get('gpu_temp', 0)
    except Exception:
        # 如果没有 NVIDIA GPU，使用默认值
        pass
    
    return PerformanceSnapshot(
        gpu_usage=gpu_usage,
        vram_used=vram_used,
        vram_total=vram_total if vram_total > 0 else 24,
        cpu_usage=cpu_usage,
        ram_used=ram_used,
        ram_total=ram_total,
        temperature=temperature,
        queue_size=0
    )


@router.get("/stats")
async def get_performance_stats():
    """获取当前性能统计（前端使用）"""
    import psutil
    
    # CPU 和内存 - 使用 None 获取上次调用以来的平均值，避免阻塞
    cpu_usage = psutil.cpu_percent(interval=None)
    if cpu_usage == 0:
        # 首次调用时 interval=None 返回 0，使用短间隔获取
        cpu_usage = psutil.cpu_percent(interval=0.5)
    memory = psutil.virtual_memory()
    memory_used = memory.used / (1024 ** 3)  # GB
    memory_total = memory.total / (1024 ** 3)  # GB
    
    # 磁盘 - macOS 上用户数据在 /System/Volumes/Data，使用用户目录获取正确的磁盘使用量
    import os
    home_dir = os.path.expanduser('~')
    disk = psutil.disk_usage(home_dir)
    disk_used = disk.used / (1024 ** 3)  # GB
    disk_total = disk.total / (1024 ** 3)  # GB
    
    # GPU 信息 (尝试使用 pynvml)
    gpu_usage = 0.0
    gpu_memory_used = 0.0
    gpu_memory_total = 0.0
    gpu_temperature = 0.0
    
    try:
        from pynvml import smi
        nvidia_smi = smi.nvidia_smi.getInstance()
        gpu_query = nvidia_smi.DeviceQuery('utilization.gpu, memory.used, memory.total, temperature.gpu')
        gpu_info = gpu_query.get('gpu', [{}])[0]
        
        gpu_usage = gpu_info.get('utilization', {}).get('gpu_util', 0)
        mem = gpu_info.get('fb_memory_usage', {})
        gpu_memory_used = mem.get('used', 0) * 1024 * 1024  # MB to bytes
        gpu_memory_total = mem.get('total', 0) * 1024 * 1024
        gpu_temperature = gpu_info.get('temperature', {}).get('gpu_temp', 0)
    except Exception:
        pass
    
    return {
        "gpu_usage": gpu_usage,
        "gpu_memory_used": gpu_memory_used,
        "gpu_memory_total": gpu_memory_total,
        "gpu_temperature": gpu_temperature,
        "cpu_usage": cpu_usage,
        "memory_used": memory_used,
        "memory_total": memory_total,
        "disk_used": disk_used,
        "disk_total": disk_total,
    }


@router.get("/execution-stats")
async def get_execution_stats(days: int = 7, db: AsyncSession = Depends(get_db)):
    """获取执行统计"""
    since = datetime.now(timezone.utc) - timedelta(days=days)
    
    success_result = await db.execute(
        select(func.count()).select_from(ExecutionHistory).where(
            ExecutionHistory.status == "completed",
            ExecutionHistory.started_at >= since
        )
    )
    success = success_result.scalar() or 0
    
    failed_result = await db.execute(
        select(func.count()).select_from(ExecutionHistory).where(
            ExecutionHistory.status == "failed",
            ExecutionHistory.started_at >= since
        )
    )
    failed = failed_result.scalar() or 0
    
    cancelled_result = await db.execute(
        select(func.count()).select_from(ExecutionHistory).where(
            ExecutionHistory.status == "cancelled",
            ExecutionHistory.started_at >= since
        )
    )
    cancelled = cancelled_result.scalar() or 0
    
    total = success + failed + cancelled
    
    # 计算平均耗时
    completed_result = await db.execute(
        select(ExecutionHistory).where(
            ExecutionHistory.status == "completed",
            ExecutionHistory.started_at >= since,
            ExecutionHistory.completed_at.isnot(None)
        )
    )
    completed_tasks = completed_result.scalars().all()
    
    total_duration = 0.0
    total_images = 0
    for task in completed_tasks:
        if task.completed_at and task.started_at:
            total_duration += (task.completed_at - task.started_at).total_seconds()
        total_images += getattr(task, 'image_count', 1)
    
    avg_time = total_duration / len(completed_tasks) if completed_tasks else 0
    
    return {
        "total_executions": total,
        "successful": success,
        "failed": failed,
        "cancelled": cancelled,
        "total_images": total_images,
        "avg_time": avg_time,
        "total_time": total_duration,
    }


@router.get("/history", response_model=List[PerformanceLogResponse])
async def get_performance_history(
    hours: int = 24,
    db: AsyncSession = Depends(get_db)
):
    """获取性能历史数据"""
    since = datetime.now(timezone.utc) - timedelta(hours=hours)
    
    result = await db.execute(
        select(PerformanceLog)
        .where(PerformanceLog.timestamp >= since)
        .order_by(PerformanceLog.timestamp)
    )
    logs = result.scalars().all()
    
    return logs


@router.get("/stats/today", response_model=ExecutionStats)
async def get_today_stats(db: AsyncSession = Depends(get_db)):
    """获取今日执行统计"""
    today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    
    success_result = await db.execute(
        select(func.count()).select_from(ExecutionHistory).where(
            ExecutionHistory.status == "completed",
            ExecutionHistory.started_at >= today_start
        )
    )
    success = success_result.scalar() or 0
    
    failed_result = await db.execute(
        select(func.count()).select_from(ExecutionHistory).where(
            ExecutionHistory.status == "failed",
            ExecutionHistory.started_at >= today_start
        )
    )
    failed = failed_result.scalar() or 0
    
    # 计算平均耗时
    completed_result = await db.execute(
        select(ExecutionHistory).where(
            ExecutionHistory.status == "completed",
            ExecutionHistory.started_at >= today_start,
            ExecutionHistory.completed_at.isnot(None)
        )
    )
    completed_tasks = completed_result.scalars().all()
    
    total_duration = 0
    for task in completed_tasks:
        if task.completed_at and task.started_at:
            total_duration += (task.completed_at - task.started_at).total_seconds()
    
    avg_duration = total_duration / len(completed_tasks) if completed_tasks else 0
    
    return ExecutionStats(
        success_count=success,
        failed_count=failed,
        avg_duration=avg_duration,
        total_images=success * 2,  # 估算
        gpu_hours=total_duration / 3600
    )


@router.get("/stats/week")
async def get_week_stats(db: AsyncSession = Depends(get_db)):
    """获取本周执行统计"""
    daily_stats = []
    
    for i in range(7):
        day_start = (datetime.now(timezone.utc) - timedelta(days=6-i)).replace(hour=0, minute=0, second=0, microsecond=0)
        day_end = day_start + timedelta(days=1)
        
        success_result = await db.execute(
            select(func.count()).select_from(ExecutionHistory).where(
                ExecutionHistory.status == "completed",
                ExecutionHistory.started_at >= day_start,
                ExecutionHistory.started_at < day_end
            )
        )
        success = success_result.scalar() or 0
        
        failed_result = await db.execute(
            select(func.count()).select_from(ExecutionHistory).where(
                ExecutionHistory.status == "failed",
                ExecutionHistory.started_at >= day_start,
                ExecutionHistory.started_at < day_end
            )
        )
        failed = failed_result.scalar() or 0
        
        daily_stats.append({
            "date": day_start.strftime("%Y-%m-%d"),
            "success": success,
            "failed": failed,
            "total": success + failed
        })
    
    return daily_stats


@router.get("/top-workflows")
async def get_top_workflows(limit: int = 5, db: AsyncSession = Depends(get_db)):
    """获取热门工作流（优化：批量查询避免 N+1）"""
    week_start = datetime.now(timezone.utc) - timedelta(days=7)
    
    result = await db.execute(
        select(
            ExecutionHistory.workflow_id,
            func.count(ExecutionHistory.id).label("count"),
            func.sum(
                case(
                    (ExecutionHistory.status == "completed", 1),
                    else_=0
                )
            ).label("success_count")
        )
        .where(
            ExecutionHistory.started_at >= week_start,
            ExecutionHistory.workflow_id.isnot(None)
        )
        .group_by(ExecutionHistory.workflow_id)
        .order_by(func.count(ExecutionHistory.id).desc())
        .limit(limit)
    )
    
    results = result.all()
    
    # 批量查询所有工作流信息
    workflow_ids = [row[0] for row in results if row[0]]
    workflow_map: dict[int, str] = {}
    if workflow_ids:
        wf_result = await db.execute(
            select(Workflow.id, Workflow.name).where(Workflow.id.in_(workflow_ids))
        )
        workflow_map = {row[0]: row[1] for row in wf_result.all()}
    
    # 构建响应
    top_workflows = []
    for workflow_id, count, success_count in results:
        if workflow_id in workflow_map:
            success_rate = (success_count / count * 100) if count > 0 else 0
            top_workflows.append({
                "id": workflow_id,
                "name": workflow_map[workflow_id],
                "count": count,
                "success_rate": round(success_rate, 1)
            })
    
    return top_workflows


@router.get("/alerts")
async def get_alerts(db: AsyncSession = Depends(get_db)):
    """获取性能告警"""
    alerts = []
    
    result = await db.execute(
        select(PerformanceLog).order_by(PerformanceLog.timestamp.desc()).limit(1)
    )
    latest_log = result.scalar_one_or_none()
    
    if latest_log:
        if latest_log.gpu_usage > 90:
            alerts.append({
                "type": "warning",
                "title": "GPU 负载过高",
                "message": f"当前 GPU 使用率 {latest_log.gpu_usage:.1f}%",
                "time": latest_log.timestamp.isoformat()
            })
        
        if latest_log.temperature > 80:
            alerts.append({
                "type": "error",
                "title": "GPU 温度过高",
                "message": f"当前温度 {latest_log.temperature:.1f}°C，建议降低负载",
                "time": latest_log.timestamp.isoformat()
            })
        
        vram_percent = (latest_log.vram_used / latest_log.vram_total * 100) if latest_log.vram_total > 0 else 0
        if vram_percent > 90:
            alerts.append({
                "type": "warning",
                "title": "显存即将耗尽",
                "message": f"已使用 {latest_log.vram_used:.1f}GB / {latest_log.vram_total:.1f}GB",
                "time": latest_log.timestamp.isoformat()
            })
    
    return alerts


@router.get("/slow-queries")
async def get_slow_queries(limit: int = 50):
    """获取慢查询日志"""
    middleware = get_slow_query_middleware()
    if not middleware:
        return {"logs": [], "message": "慢查询中间件未启用"}
    
    return {
        "logs": middleware.get_slow_logs(limit),
        "slowest_endpoints": middleware.get_slowest_endpoints(10),
    }


@router.get("/request-stats")
async def get_request_stats():
    """获取请求性能统计"""
    middleware = get_slow_query_middleware()
    if not middleware:
        return {"message": "慢查询中间件未启用"}
    
    return middleware.get_stats()


@router.get("/task-queues")
async def get_task_queue_stats():
    """获取任务队列统计"""
    return get_all_queue_stats()
