"""内置工作流模板 API"""
import json
from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..services.cache import cache_service

router = APIRouter(prefix="/builtin-workflows", tags=["builtin-workflows"])

# 数据文件路径
DATA_FILE = Path(__file__).parent.parent / "data" / "builtin_workflows.json"

# 缓存 TTL（内置工作流很少变化，缓存10分钟）
BUILTIN_CACHE_TTL = 600


class WorkflowTemplate(BaseModel):
    """工作流模板"""
    id: str
    name: str
    description: str
    category: str
    baseModel: str
    author: str
    tags: List[str]
    workflow_data: dict


class WorkflowListItem(BaseModel):
    """工作流列表项（不含完整数据）"""
    id: str
    name: str
    description: str
    category: str
    baseModel: str
    author: str
    tags: List[str]


def load_workflows() -> List[dict]:
    """加载内置工作流数据（带缓存）"""
    cache_key = "builtin_workflows"
    cached = cache_service.get(cache_key)
    if cached is not None:
        return cached

    if not DATA_FILE.exists():
        return []

    with open(DATA_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)

    workflows = data.get("workflows", [])
    cache_service.set(cache_key, workflows, ttl=BUILTIN_CACHE_TTL)
    return workflows


@router.get("/", response_model=List[WorkflowListItem])
async def list_builtin_workflows(
    category: Optional[str] = None,
    base_model: Optional[str] = None
):
    """获取内置工作流列表"""
    workflows = load_workflows()
    
    # 过滤
    if category:
        workflows = [w for w in workflows if w.get("category") == category]
    if base_model:
        workflows = [w for w in workflows if w.get("baseModel") == base_model]
    
    # 返回不含 workflow_data 的列表
    return [
        {
            "id": w["id"],
            "name": w["name"],
            "description": w["description"],
            "category": w["category"],
            "baseModel": w["baseModel"],
            "author": w.get("author", "Unknown"),
            "tags": w.get("tags", [])
        }
        for w in workflows
    ]


@router.get("/{workflow_id}", response_model=WorkflowTemplate)
async def get_builtin_workflow(workflow_id: str):
    """获取单个内置工作流（含完整数据）"""
    workflows = load_workflows()
    
    for w in workflows:
        if w["id"] == workflow_id:
            return w
    
    raise HTTPException(status_code=404, detail="工作流不存在")


@router.get("/{workflow_id}/download")
async def download_builtin_workflow(workflow_id: str):
    """下载内置工作流 JSON"""
    workflows = load_workflows()
    
    for w in workflows:
        if w["id"] == workflow_id:
            return w["workflow_data"]
    
    raise HTTPException(status_code=404, detail="工作流不存在")


@router.get("/categories/list")
async def list_categories():
    """获取所有分类"""
    workflows = load_workflows()
    categories = list(set(w.get("category", "") for w in workflows))
    return sorted([c for c in categories if c])


@router.get("/base-models/list")
async def list_base_models():
    """获取所有基础模型"""
    workflows = load_workflows()
    models = list(set(w.get("baseModel", "") for w in workflows))
    return sorted([m for m in models if m])
