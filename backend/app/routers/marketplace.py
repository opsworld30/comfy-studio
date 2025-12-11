"""工作流市场 API"""
from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, or_
from pydantic import BaseModel

from ..database import get_db
from ..models import MarketplaceWorkflow, Workflow

router = APIRouter(prefix="/marketplace", tags=["marketplace"])


class MarketplaceWorkflowResponse(BaseModel):
    id: int
    name: str
    description: str
    author: str
    thumbnail: str
    preview_images: list
    category: str
    tags: list
    base_model: str
    dependencies: list
    price: float
    download_count: int
    rating: float
    rating_count: int
    is_featured: bool
    source: str
    source_url: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class MarketplaceWorkflowCreate(BaseModel):
    name: str
    description: str = ""
    workflow_data: dict
    thumbnail: str = ""
    preview_images: list = []
    category: str = ""
    tags: list = []
    base_model: str = ""
    dependencies: list = []
    price: float = 0


@router.get("", response_model=List[MarketplaceWorkflowResponse])
async def list_marketplace_workflows(
    category: Optional[str] = None,
    base_model: Optional[str] = None,
    search: Optional[str] = None,
    featured_only: bool = False,
    free_only: bool = False,
    sort_by: str = "download_count",
    limit: int = 20,
    offset: int = 0,
    db: AsyncSession = Depends(get_db)
):
    """获取市场工作流列表"""
    query = select(MarketplaceWorkflow)
    
    if category:
        query = query.where(MarketplaceWorkflow.category == category)
    
    if base_model:
        query = query.where(MarketplaceWorkflow.base_model == base_model)
    
    if search:
        query = query.where(
            or_(
                MarketplaceWorkflow.name.ilike(f"%{search}%"),
                MarketplaceWorkflow.description.ilike(f"%{search}%")
            )
        )
    
    if featured_only:
        query = query.where(MarketplaceWorkflow.is_featured.is_(True))
    
    if free_only:
        query = query.where(MarketplaceWorkflow.price == 0)
    
    if sort_by == "download_count":
        query = query.order_by(MarketplaceWorkflow.download_count.desc())
    elif sort_by == "rating":
        query = query.order_by(MarketplaceWorkflow.rating.desc())
    elif sort_by == "created_at":
        query = query.order_by(MarketplaceWorkflow.created_at.desc())
    elif sort_by == "price":
        query = query.order_by(MarketplaceWorkflow.price)
    
    query = query.offset(offset).limit(limit)
    result = await db.execute(query)
    workflows = result.scalars().all()
    
    return workflows


@router.get("/featured", response_model=List[MarketplaceWorkflowResponse])
async def get_featured_workflows(
    limit: int = 6,
    db: AsyncSession = Depends(get_db)
):
    """获取精选工作流"""
    result = await db.execute(
        select(MarketplaceWorkflow)
        .where(MarketplaceWorkflow.is_featured.is_(True))
        .order_by(MarketplaceWorkflow.download_count.desc())
        .limit(limit)
    )
    workflows = result.scalars().all()
    
    return workflows


@router.get("/categories")
async def get_categories(db: AsyncSession = Depends(get_db)):
    """获取分类列表"""
    result = await db.execute(
        select(
            MarketplaceWorkflow.category,
            func.count(MarketplaceWorkflow.id).label("count")
        )
        .group_by(MarketplaceWorkflow.category)
    )
    categories = result.all()
    
    return [{"category": c, "count": count} for c, count in categories if c]


@router.get("/{workflow_id}", response_model=MarketplaceWorkflowResponse)
async def get_marketplace_workflow(
    workflow_id: int,
    db: AsyncSession = Depends(get_db)
):
    """获取市场工作流详情"""
    result = await db.execute(
        select(MarketplaceWorkflow).where(MarketplaceWorkflow.id == workflow_id)
    )
    workflow = result.scalar_one_or_none()
    
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")
    
    return workflow


@router.post("/{workflow_id}/download")
async def download_marketplace_workflow(
    workflow_id: int,
    db: AsyncSession = Depends(get_db)
):
    """下载市场工作流到本地"""
    result = await db.execute(
        select(MarketplaceWorkflow).where(MarketplaceWorkflow.id == workflow_id)
    )
    marketplace_workflow = result.scalar_one_or_none()
    
    if not marketplace_workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")
    
    # 创建本地工作流
    local_workflow = Workflow(
        name=f"{marketplace_workflow.name} (市场)",
        description=marketplace_workflow.description,
        workflow_data=marketplace_workflow.workflow_data,
        thumbnail=marketplace_workflow.thumbnail,
        category=marketplace_workflow.category,
        tags=marketplace_workflow.tags
    )
    
    db.add(local_workflow)
    
    # 更新下载计数
    marketplace_workflow.download_count += 1
    
    await db.commit()
    await db.refresh(local_workflow)
    
    return {
        "message": "Workflow downloaded",
        "workflow_id": local_workflow.id
    }


@router.post("")
async def publish_workflow(
    data: MarketplaceWorkflowCreate,
    db: AsyncSession = Depends(get_db)
):
    """发布工作流到市场"""
    workflow = MarketplaceWorkflow(
        name=data.name,
        description=data.description,
        author="",
        workflow_data=data.workflow_data,
        thumbnail=data.thumbnail,
        preview_images=data.preview_images,
        category=data.category,
        tags=data.tags,
        base_model=data.base_model,
        dependencies=data.dependencies,
        price=data.price
    )
    
    db.add(workflow)
    await db.commit()
    await db.refresh(workflow)
    
    return {"message": "Workflow published", "id": workflow.id}


@router.post("/{workflow_id}/rate")
async def rate_workflow(
    workflow_id: int,
    rating: int,
    db: AsyncSession = Depends(get_db)
):
    """评分工作流"""
    if rating < 1 or rating > 5:
        raise HTTPException(status_code=400, detail="Rating must be 1-5")
    
    result = await db.execute(
        select(MarketplaceWorkflow).where(MarketplaceWorkflow.id == workflow_id)
    )
    workflow = result.scalar_one_or_none()
    
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")
    
    # 更新平均评分
    total_rating = workflow.rating * workflow.rating_count + rating
    workflow.rating_count += 1
    workflow.rating = total_rating / workflow.rating_count
    
    await db.commit()
    
    return {"rating": workflow.rating, "rating_count": workflow.rating_count}


@router.delete("/{workflow_id}")
async def delete_marketplace_workflow(
    workflow_id: int,
    db: AsyncSession = Depends(get_db)
):
    """删除市场工作流"""
    result = await db.execute(
        select(MarketplaceWorkflow).where(MarketplaceWorkflow.id == workflow_id)
    )
    workflow = result.scalar_one_or_none()
    
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")
    
    await db.delete(workflow)
    await db.commit()
    
    return {"message": "Workflow deleted"}
