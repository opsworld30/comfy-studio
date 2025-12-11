"""批处理任务 API"""
from datetime import datetime, timezone
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from pydantic import BaseModel

from ..database import get_db
from ..models import BatchTask, Workflow

router = APIRouter(prefix="/batch", tags=["batch"])


class BatchTaskCreate(BaseModel):
    name: str
    workflow_id: Optional[int] = None
    variables: dict = {}
    config: dict = {}
    priority: int = 5


class BatchTaskUpdate(BaseModel):
    status: Optional[str] = None
    priority: Optional[int] = None


class BatchTaskResponse(BaseModel):
    id: int
    name: str
    workflow_id: Optional[int]
    status: str
    priority: int
    total_count: int
    completed_count: int
    failed_count: int
    variables: dict
    config: dict
    result: dict
    error_message: str
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    created_at: datetime
    workflow_name: Optional[str] = None
    progress: float = 0

    class Config:
        from_attributes = True


@router.get("", response_model=List[BatchTaskResponse])
async def list_batch_tasks(
    status: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
    db: AsyncSession = Depends(get_db)
):
    """获取批处理任务列表"""
    query = select(BatchTask)
    
    if status:
        query = query.where(BatchTask.status == status)
    
    query = query.order_by(BatchTask.created_at.desc()).offset(offset).limit(limit)
    result = await db.execute(query)
    tasks = result.scalars().all()
    
    response = []
    for task in tasks:
        workflow_name = None
        if task.workflow_id:
            wf_result = await db.execute(select(Workflow).where(Workflow.id == task.workflow_id))
            workflow = wf_result.scalar_one_or_none()
            workflow_name = workflow.name if workflow else None
        
        progress = (task.completed_count / task.total_count * 100) if task.total_count > 0 else 0
        
        response.append(BatchTaskResponse(
            id=task.id,
            name=task.name,
            workflow_id=task.workflow_id,
            status=task.status,
            priority=task.priority,
            total_count=task.total_count,
            completed_count=task.completed_count,
            failed_count=task.failed_count,
            variables=task.variables or {},
            config=task.config or {},
            result=task.result or {},
            error_message=task.error_message or "",
            started_at=task.started_at,
            completed_at=task.completed_at,
            created_at=task.created_at,
            workflow_name=workflow_name,
            progress=progress
        ))
    
    return response


@router.get("/stats")
async def get_batch_stats(db: AsyncSession = Depends(get_db)):
    """获取批处理统计"""
    async def count_by_status(status: str) -> int:
        result = await db.execute(
            select(func.count()).select_from(BatchTask).where(BatchTask.status == status)
        )
        return result.scalar() or 0
    
    running = await count_by_status("running")
    pending = await count_by_status("pending")
    paused = await count_by_status("paused")
    
    today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    completed_result = await db.execute(
        select(func.count()).select_from(BatchTask).where(
            BatchTask.status == "completed",
            BatchTask.completed_at >= today_start
        )
    )
    completed_today = completed_result.scalar() or 0
    
    total_result = await db.execute(select(func.count()).select_from(BatchTask))
    total = total_result.scalar() or 0
    
    return {
        "running": running,
        "pending": pending,
        "paused": paused,
        "completed_today": completed_today,
        "total": total
    }


@router.post("", response_model=BatchTaskResponse)
async def create_batch_task(
    task: BatchTaskCreate,
    db: AsyncSession = Depends(get_db)
):
    """创建批处理任务"""
    total_count = 1
    variables = task.variables
    
    if variables:
        combination_mode = task.config.get("combination_mode", "cartesian")
        if combination_mode == "cartesian":
            for var_config in variables.values():
                if isinstance(var_config, dict):
                    values = var_config.get("values", [])
                    if values:
                        total_count *= len(values)
        else:
            max_len = 0
            for var_config in variables.values():
                if isinstance(var_config, dict):
                    values = var_config.get("values", [])
                    max_len = max(max_len, len(values))
            total_count = max_len if max_len > 0 else 1
    
    db_task = BatchTask(
        name=task.name,
        workflow_id=task.workflow_id,
        variables=task.variables,
        config=task.config,
        priority=task.priority,
        total_count=total_count
    )
    
    db.add(db_task)
    await db.commit()
    await db.refresh(db_task)
    
    return BatchTaskResponse(
        id=db_task.id,
        name=db_task.name,
        workflow_id=db_task.workflow_id,
        status=db_task.status,
        priority=db_task.priority,
        total_count=db_task.total_count,
        completed_count=db_task.completed_count,
        failed_count=db_task.failed_count,
        variables=db_task.variables or {},
        config=db_task.config or {},
        result=db_task.result or {},
        error_message=db_task.error_message or "",
        started_at=db_task.started_at,
        completed_at=db_task.completed_at,
        created_at=db_task.created_at,
        progress=0
    )


@router.get("/{task_id}", response_model=BatchTaskResponse)
async def get_batch_task(task_id: int, db: AsyncSession = Depends(get_db)):
    """获取批处理任务详情"""
    result = await db.execute(select(BatchTask).where(BatchTask.id == task_id))
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    workflow_name = None
    if task.workflow_id:
        wf_result = await db.execute(select(Workflow).where(Workflow.id == task.workflow_id))
        workflow = wf_result.scalar_one_or_none()
        workflow_name = workflow.name if workflow else None
    
    progress = (task.completed_count / task.total_count * 100) if task.total_count > 0 else 0
    
    return BatchTaskResponse(
        id=task.id,
        name=task.name,
        workflow_id=task.workflow_id,
        status=task.status,
        priority=task.priority,
        total_count=task.total_count,
        completed_count=task.completed_count,
        failed_count=task.failed_count,
        variables=task.variables or {},
        config=task.config or {},
        result=task.result or {},
        error_message=task.error_message or "",
        started_at=task.started_at,
        completed_at=task.completed_at,
        created_at=task.created_at,
        workflow_name=workflow_name,
        progress=progress
    )


@router.put("/{task_id}", response_model=BatchTaskResponse)
async def update_batch_task(
    task_id: int,
    update: BatchTaskUpdate,
    db: AsyncSession = Depends(get_db)
):
    """更新批处理任务"""
    result = await db.execute(select(BatchTask).where(BatchTask.id == task_id))
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    if update.status:
        task.status = update.status
        if update.status == "running" and not task.started_at:
            task.started_at = datetime.now(timezone.utc)
        elif update.status in ["completed", "failed"]:
            task.completed_at = datetime.now(timezone.utc)
    
    if update.priority is not None:
        task.priority = update.priority
    
    await db.commit()
    await db.refresh(task)
    
    progress = (task.completed_count / task.total_count * 100) if task.total_count > 0 else 0
    
    return BatchTaskResponse(
        id=task.id,
        name=task.name,
        workflow_id=task.workflow_id,
        status=task.status,
        priority=task.priority,
        total_count=task.total_count,
        completed_count=task.completed_count,
        failed_count=task.failed_count,
        variables=task.variables or {},
        config=task.config or {},
        result=task.result or {},
        error_message=task.error_message or "",
        started_at=task.started_at,
        completed_at=task.completed_at,
        created_at=task.created_at,
        progress=progress
    )


@router.delete("/{task_id}")
async def delete_batch_task(task_id: int, db: AsyncSession = Depends(get_db)):
    """删除批处理任务"""
    result = await db.execute(select(BatchTask).where(BatchTask.id == task_id))
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    await db.delete(task)
    await db.commit()
    
    return {"message": "Task deleted"}


@router.post("/{task_id}/start")
async def start_batch_task(task_id: int, db: AsyncSession = Depends(get_db)):
    """启动批处理任务"""
    result = await db.execute(select(BatchTask).where(BatchTask.id == task_id))
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    task.status = "running"
    task.started_at = datetime.now(timezone.utc)
    await db.commit()
    
    return {"message": "Task started"}


@router.post("/{task_id}/pause")
async def pause_batch_task(task_id: int, db: AsyncSession = Depends(get_db)):
    """暂停批处理任务"""
    result = await db.execute(select(BatchTask).where(BatchTask.id == task_id))
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    task.status = "paused"
    await db.commit()
    
    return {"message": "Task paused"}


@router.post("/{task_id}/cancel")
async def cancel_batch_task(task_id: int, db: AsyncSession = Depends(get_db)):
    """取消批处理任务"""
    result = await db.execute(select(BatchTask).where(BatchTask.id == task_id))
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    task.status = "failed"
    task.error_message = "Cancelled by user"
    task.completed_at = datetime.now(timezone.utc)
    await db.commit()
    
    return {"message": "Task cancelled"}
