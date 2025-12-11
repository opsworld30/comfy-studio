"""工作流路由"""
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete, update
import json

from ..database import get_db
from ..models import Workflow, WorkflowBackup, WorkflowVersion
from ..schemas import (
    WorkflowCreate, WorkflowUpdate, WorkflowResponse, 
    WorkflowListResponse, BackupCreate, BackupResponse,
    ExportData, ImportResult
)

router = APIRouter(prefix="/workflows", tags=["workflows"])


@router.get("", response_model=list[WorkflowListResponse])
async def list_workflows(
    category: str | None = None,
    search: str | None = None,
    favorite_only: bool = False,
    db: AsyncSession = Depends(get_db)
):
    """获取工作流列表"""
    query = select(Workflow)
    
    if category:
        query = query.where(Workflow.category == category)
    if favorite_only:
        query = query.where(Workflow.is_favorite == True)
    if search:
        query = query.where(Workflow.name.ilike(f"%{search}%"))
    
    query = query.order_by(Workflow.updated_at.desc())
    result = await db.execute(query)
    workflows = result.scalars().all()
    return workflows


@router.post("", response_model=WorkflowResponse)
async def create_workflow(
    workflow: WorkflowCreate,
    db: AsyncSession = Depends(get_db)
):
    """创建工作流"""
    db_workflow = Workflow(
        name=workflow.name,
        description=workflow.description,
        workflow_data=workflow.workflow_data,
        thumbnail=workflow.thumbnail,
        category=workflow.category,
        tags=workflow.tags,
        is_favorite=workflow.is_favorite,
    )
    db.add(db_workflow)
    await db.commit()
    await db.refresh(db_workflow)
    return db_workflow


@router.get("/default/current", response_model=WorkflowListResponse | None)
async def get_default_workflow(db: AsyncSession = Depends(get_db)):
    """获取默认工作流"""
    result = await db.execute(
        select(Workflow).where(Workflow.is_default == True)
    )
    workflow = result.scalar_one_or_none()
    return workflow


@router.get("/categories/list")
async def list_categories(db: AsyncSession = Depends(get_db)):
    """获取所有分类"""
    result = await db.execute(
        select(Workflow.category).distinct()
    )
    categories = [row[0] for row in result.fetchall()]
    return categories


@router.get("/export/all")
async def export_all_workflows(db: AsyncSession = Depends(get_db)):
    """导出所有工作流"""
    result = await db.execute(select(Workflow))
    workflows = result.scalars().all()
    
    export_data = {
        "version": "1.0",
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "workflows": [
            {
                "id": w.id,
                "name": w.name,
                "description": w.description,
                "workflow_data": w.workflow_data,
                "thumbnail": w.thumbnail,
                "category": w.category,
                "tags": w.tags,
                "is_favorite": w.is_favorite,
                "created_at": w.created_at.isoformat(),
                "updated_at": w.updated_at.isoformat(),
            }
            for w in workflows
        ]
    }
    
    return JSONResponse(
        content=export_data,
        headers={
            "Content-Disposition": f"attachment; filename=workflows_export_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.json"
        }
    )


@router.post("/import", response_model=ImportResult)
async def import_workflows(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db)
):
    """导入工作流"""
    try:
        content = await file.read()
        data = json.loads(content.decode("utf-8"))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"无效的 JSON 文件: {str(e)}")
    
    success = 0
    failed = 0
    errors = []
    
    # 判断是批量导入还是单个工作流
    if "workflows" in data:
        # 批量导入
        workflows_data = data["workflows"]
    else:
        # 单个 ComfyUI 工作流
        workflows_data = [{
            "name": file.filename.replace(".json", "") if file.filename else "Imported Workflow",
            "workflow_data": data,
        }]
    
    for wf_data in workflows_data:
        try:
            workflow = Workflow(
                name=wf_data.get("name", "Imported Workflow"),
                description=wf_data.get("description", ""),
                workflow_data=wf_data.get("workflow_data", wf_data),
                thumbnail=wf_data.get("thumbnail", ""),
                category=wf_data.get("category", "imported"),
                tags=wf_data.get("tags", []),
                is_favorite=wf_data.get("is_favorite", False),
            )
            db.add(workflow)
            success += 1
        except Exception as e:
            failed += 1
            errors.append(str(e))
    
    await db.commit()
    
    return ImportResult(success=success, failed=failed, errors=errors)


@router.get("/{workflow_id}", response_model=WorkflowResponse)
async def get_workflow(
    workflow_id: int,
    db: AsyncSession = Depends(get_db)
):
    """获取单个工作流"""
    result = await db.execute(
        select(Workflow).where(Workflow.id == workflow_id)
    )
    workflow = result.scalar_one_or_none()
    if not workflow:
        raise HTTPException(status_code=404, detail="工作流不存在")
    return workflow


@router.put("/{workflow_id}", response_model=WorkflowResponse)
async def update_workflow(
    workflow_id: int,
    workflow_update: WorkflowUpdate,
    db: AsyncSession = Depends(get_db)
):
    """更新工作流"""
    result = await db.execute(
        select(Workflow).where(Workflow.id == workflow_id)
    )
    workflow = result.scalar_one_or_none()
    if not workflow:
        raise HTTPException(status_code=404, detail="工作流不存在")
    
    update_data = workflow_update.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(workflow, key, value)
    
    workflow.updated_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(workflow)
    return workflow


@router.delete("/{workflow_id}")
async def delete_workflow(
    workflow_id: int,
    db: AsyncSession = Depends(get_db)
):
    """删除工作流"""
    result = await db.execute(
        select(Workflow).where(Workflow.id == workflow_id)
    )
    workflow = result.scalar_one_or_none()
    if not workflow:
        raise HTTPException(status_code=404, detail="工作流不存在")
    
    # 同时删除备份
    await db.execute(
        delete(WorkflowBackup).where(WorkflowBackup.workflow_id == workflow_id)
    )
    await db.delete(workflow)
    await db.commit()
    return {"message": "删除成功"}


@router.post("/{workflow_id}/favorite")
async def toggle_favorite(
    workflow_id: int,
    db: AsyncSession = Depends(get_db)
):
    """切换收藏状态"""
    result = await db.execute(
        select(Workflow).where(Workflow.id == workflow_id)
    )
    workflow = result.scalar_one_or_none()
    if not workflow:
        raise HTTPException(status_code=404, detail="工作流不存在")
    
    workflow.is_favorite = not workflow.is_favorite
    await db.commit()
    return {"is_favorite": workflow.is_favorite}


@router.post("/{workflow_id}/set-default")
async def set_default_workflow(
    workflow_id: int,
    db: AsyncSession = Depends(get_db)
):
    """设置默认工作流"""
    result = await db.execute(
        select(Workflow).where(Workflow.id == workflow_id)
    )
    workflow = result.scalar_one_or_none()
    if not workflow:
        raise HTTPException(status_code=404, detail="工作流不存在")
    
    # 取消所有默认设置
    await db.execute(
        update(Workflow).values(is_default=False)
    )
    
    # 设置新的默认工作流
    workflow.is_default = True
    await db.commit()
    
    return {"message": f"已设置 {workflow.name} 为默认工作流"}


@router.get("/{workflow_id}/export")
async def export_workflow(
    workflow_id: int,
    db: AsyncSession = Depends(get_db)
):
    """导出单个工作流"""
    result = await db.execute(
        select(Workflow).where(Workflow.id == workflow_id)
    )
    workflow = result.scalar_one_or_none()
    if not workflow:
        raise HTTPException(status_code=404, detail="工作流不存在")
    
    return JSONResponse(
        content=workflow.workflow_data,
        headers={
            "Content-Disposition": f"attachment; filename={workflow.name}.json"
        }
    )


# ========== 备份相关 ==========

@router.get("/{workflow_id}/backups", response_model=list[BackupResponse])
async def list_backups(
    workflow_id: int,
    db: AsyncSession = Depends(get_db)
):
    """获取工作流备份列表"""
    result = await db.execute(
        select(WorkflowBackup)
        .where(WorkflowBackup.workflow_id == workflow_id)
        .order_by(WorkflowBackup.created_at.desc())
    )
    return result.scalars().all()


@router.post("/{workflow_id}/backups", response_model=BackupResponse)
async def create_backup(
    workflow_id: int,
    backup: BackupCreate,
    db: AsyncSession = Depends(get_db)
):
    """创建工作流备份"""
    result = await db.execute(
        select(Workflow).where(Workflow.id == workflow_id)
    )
    workflow = result.scalar_one_or_none()
    if not workflow:
        raise HTTPException(status_code=404, detail="工作流不存在")
    
    db_backup = WorkflowBackup(
        workflow_id=workflow_id,
        name=workflow.name,
        workflow_data=workflow.workflow_data,
        backup_note=backup.backup_note,
    )
    db.add(db_backup)
    await db.commit()
    await db.refresh(db_backup)
    return db_backup


@router.post("/{workflow_id}/backups/{backup_id}/restore", response_model=WorkflowResponse)
async def restore_backup(
    workflow_id: int,
    backup_id: int,
    db: AsyncSession = Depends(get_db)
):
    """从备份恢复工作流"""
    result = await db.execute(
        select(WorkflowBackup).where(
            WorkflowBackup.id == backup_id,
            WorkflowBackup.workflow_id == workflow_id
        )
    )
    backup = result.scalar_one_or_none()
    if not backup:
        raise HTTPException(status_code=404, detail="备份不存在")
    
    result = await db.execute(
        select(Workflow).where(Workflow.id == workflow_id)
    )
    workflow = result.scalar_one_or_none()
    if not workflow:
        raise HTTPException(status_code=404, detail="工作流不存在")
    
    workflow.workflow_data = backup.workflow_data
    workflow.updated_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(workflow)
    return workflow


@router.delete("/{workflow_id}/backups/{backup_id}")
async def delete_backup(
    workflow_id: int,
    backup_id: int,
    db: AsyncSession = Depends(get_db)
):
    """删除备份"""
    result = await db.execute(
        select(WorkflowBackup).where(
            WorkflowBackup.id == backup_id,
            WorkflowBackup.workflow_id == workflow_id
        )
    )
    backup = result.scalar_one_or_none()
    if not backup:
        raise HTTPException(status_code=404, detail="备份不存在")
    
    await db.delete(backup)
    await db.commit()
    return {"message": "删除成功"}


# ==================== 版本历史 API ====================

@router.get("/{workflow_id}/versions")
async def list_versions(
    workflow_id: int,
    db: AsyncSession = Depends(get_db)
):
    """获取工作流版本历史"""
    result = await db.execute(
        select(WorkflowVersion)
        .where(WorkflowVersion.workflow_id == workflow_id)
        .order_by(WorkflowVersion.created_at.desc())
    )
    versions = result.scalars().all()
    
    return [
        {
            "id": v.id,
            "version": v.version,
            "change_note": v.change_note,
            "change_type": v.change_type,
            "author": v.author,
            "created_at": v.created_at
        }
        for v in versions
    ]


@router.post("/{workflow_id}/versions")
async def create_version(
    workflow_id: int,
    change_note: str = "",
    db: AsyncSession = Depends(get_db)
):
    """创建工作流版本"""
    # 获取工作流
    result = await db.execute(
        select(Workflow).where(Workflow.id == workflow_id)
    )
    workflow = result.scalar_one_or_none()
    
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")
    
    # 获取最新版本号
    result = await db.execute(
        select(WorkflowVersion)
        .where(WorkflowVersion.workflow_id == workflow_id)
        .order_by(WorkflowVersion.created_at.desc())
        .limit(1)
    )
    latest = result.scalar_one_or_none()
    
    if latest:
        # 解析版本号并递增
        try:
            parts = latest.version.replace("v", "").split(".")
            major = int(parts[0])
            minor = int(parts[1]) if len(parts) > 1 else 0
            new_version = f"v{major}.{minor + 1}"
        except:
            new_version = "v1.1"
    else:
        new_version = "v1.0"
    
    # 创建版本
    version = WorkflowVersion(
        workflow_id=workflow_id,
        version=new_version,
        workflow_data=workflow.workflow_data,
        change_note=change_note,
        change_type="manual"
    )
    
    db.add(version)
    await db.commit()
    await db.refresh(version)
    
    return {
        "id": version.id,
        "version": version.version,
        "change_note": version.change_note,
        "created_at": version.created_at
    }


@router.get("/{workflow_id}/versions/{version_id}")
async def get_version(
    workflow_id: int,
    version_id: int,
    db: AsyncSession = Depends(get_db)
):
    """获取版本详情"""
    result = await db.execute(
        select(WorkflowVersion)
        .where(
            WorkflowVersion.id == version_id,
            WorkflowVersion.workflow_id == workflow_id
        )
    )
    version = result.scalar_one_or_none()
    
    if not version:
        raise HTTPException(status_code=404, detail="Version not found")
    
    return {
        "id": version.id,
        "version": version.version,
        "workflow_data": version.workflow_data,
        "change_note": version.change_note,
        "change_type": version.change_type,
        "author": version.author,
        "created_at": version.created_at
    }


@router.post("/{workflow_id}/versions/{version_id}/restore")
async def restore_version(
    workflow_id: int,
    version_id: int,
    db: AsyncSession = Depends(get_db)
):
    """恢复到指定版本"""
    # 获取版本
    result = await db.execute(
        select(WorkflowVersion)
        .where(
            WorkflowVersion.id == version_id,
            WorkflowVersion.workflow_id == workflow_id
        )
    )
    version = result.scalar_one_or_none()
    
    if not version:
        raise HTTPException(status_code=404, detail="Version not found")
    
    # 获取工作流
    result = await db.execute(
        select(Workflow).where(Workflow.id == workflow_id)
    )
    workflow = result.scalar_one_or_none()
    
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")
    
    # 先保存当前版本
    current_version = WorkflowVersion(
        workflow_id=workflow_id,
        version=f"v{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}",
        workflow_data=workflow.workflow_data,
        change_note=f"Auto backup before restore to {version.version}",
        change_type="auto"
    )
    db.add(current_version)
    
    # 恢复版本
    workflow.workflow_data = version.workflow_data
    workflow.updated_at = datetime.now(timezone.utc)
    
    await db.commit()
    
    return {"message": f"Restored to {version.version}"}
