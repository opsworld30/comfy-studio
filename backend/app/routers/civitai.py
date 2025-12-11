"""Civitai API 集成"""
import logging
from typing import Optional, List
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
import httpx

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/civitai", tags=["civitai"])

CIVITAI_API_BASE = "https://civitai.com/api/v1"


class CivitaiModel(BaseModel):
    id: int
    name: str
    description: str = ""
    type: str  # Checkpoint, LORA, TextualInversion, etc.
    nsfw: bool = False
    tags: List[str] = []
    creator: dict = {}
    stats: dict = {}
    modelVersions: List[dict] = []


class CivitaiModelVersion(BaseModel):
    id: int
    name: str
    description: str = ""
    baseModel: str = ""
    downloadUrl: str = ""
    images: List[dict] = []
    files: List[dict] = []
    stats: dict = {}


class CivitaiSearchResult(BaseModel):
    items: List[dict]
    metadata: dict = {}


@router.get("/search")
async def search_civitai(
    query: str = Query("", description="搜索关键词"),
    types: Optional[str] = Query(None, description="模型类型: Checkpoint, LORA, TextualInversion, Hypernetwork, AestheticGradient, Controlnet, Poses"),
    sort: str = Query("Highest Rated", description="排序: Highest Rated, Most Downloaded, Newest"),
    period: str = Query("AllTime", description="时间范围: AllTime, Year, Month, Week, Day"),
    nsfw: bool = Query(False, description="是否包含 NSFW"),
    limit: int = Query(20, ge=1, le=100),
    page: int = Query(1, ge=1),
):
    """搜索 Civitai 模型"""
    params = {
        "sort": sort,
        "period": period,
        "nsfw": str(nsfw).lower(),
        "limit": limit,
        "page": page,
    }
    
    # 只有有搜索词时才添加 query 参数
    if query:
        params["query"] = query
    
    if types:
        params["types"] = types
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.get(f"{CIVITAI_API_BASE}/models", params=params)
            response.raise_for_status()
            data = response.json()
            
            # 简化返回数据
            items = []
            for model in data.get("items", []):
                # 获取最新版本
                versions = model.get("modelVersions", [])
                latest_version = versions[0] if versions else {}
                
                # 获取预览图
                images = latest_version.get("images", [])
                preview_url = images[0].get("url") if images else ""
                
                # 获取下载信息
                files = latest_version.get("files", [])
                primary_file = next((f for f in files if f.get("primary")), files[0] if files else {})
                
                items.append({
                    "id": model.get("id"),
                    "name": model.get("name"),
                    "type": model.get("type"),
                    "nsfw": model.get("nsfw", False),
                    "description": (model.get("description") or "")[:200],
                    "tags": model.get("tags", [])[:5],
                    "creator": model.get("creator", {}).get("username", ""),
                    "stats": {
                        "downloadCount": model.get("stats", {}).get("downloadCount", 0),
                        "favoriteCount": model.get("stats", {}).get("favoriteCount", 0),
                        "commentCount": model.get("stats", {}).get("commentCount", 0),
                        "rating": model.get("stats", {}).get("rating", 0),
                        "ratingCount": model.get("stats", {}).get("ratingCount", 0),
                    },
                    "version": {
                        "id": latest_version.get("id"),
                        "name": latest_version.get("name"),
                        "baseModel": latest_version.get("baseModel", ""),
                        "downloadUrl": latest_version.get("downloadUrl", ""),
                    },
                    "previewUrl": preview_url,
                    "fileSize": primary_file.get("sizeKB", 0) * 1024,
                })
            
            return {
                "items": items,
                "metadata": data.get("metadata", {}),
            }
            
        except httpx.HTTPStatusError as e:
            logger.error(f"Civitai API error: {e}")
            raise HTTPException(status_code=e.response.status_code, detail="Civitai API 请求失败")
        except httpx.RequestError as e:
            logger.error(f"Civitai connection error: {e}")
            raise HTTPException(status_code=502, detail="无法连接到 Civitai")


@router.get("/models/{model_id}")
async def get_civitai_model(model_id: int):
    """获取 Civitai 模型详情"""
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.get(f"{CIVITAI_API_BASE}/models/{model_id}")
            response.raise_for_status()
            model = response.json()
            
            versions = []
            for v in model.get("modelVersions", []):
                images = v.get("images", [])
                files = v.get("files", [])
                primary_file = next((f for f in files if f.get("primary")), files[0] if files else {})
                
                versions.append({
                    "id": v.get("id"),
                    "name": v.get("name"),
                    "description": v.get("description", ""),
                    "baseModel": v.get("baseModel", ""),
                    "downloadUrl": v.get("downloadUrl", ""),
                    "trainedWords": v.get("trainedWords", []),
                    "images": [{"url": img.get("url"), "nsfw": img.get("nsfw")} for img in images[:6]],
                    "file": {
                        "name": primary_file.get("name", ""),
                        "sizeKB": primary_file.get("sizeKB", 0),
                        "downloadUrl": primary_file.get("downloadUrl", ""),
                    },
                    "stats": v.get("stats", {}),
                })
            
            return {
                "id": model.get("id"),
                "name": model.get("name"),
                "description": model.get("description", ""),
                "type": model.get("type"),
                "nsfw": model.get("nsfw", False),
                "tags": model.get("tags", []),
                "creator": {
                    "username": model.get("creator", {}).get("username", ""),
                    "image": model.get("creator", {}).get("image", ""),
                },
                "stats": model.get("stats", {}),
                "versions": versions,
            }
            
        except httpx.HTTPStatusError as e:
            raise HTTPException(status_code=e.response.status_code, detail="Civitai API 请求失败")
        except httpx.RequestError as e:
            raise HTTPException(status_code=502, detail="无法连接到 Civitai")


@router.get("/models/{model_id}/versions/{version_id}")
async def get_civitai_version(model_id: int, version_id: int):
    """获取 Civitai 模型版本详情"""
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.get(f"{CIVITAI_API_BASE}/model-versions/{version_id}")
            response.raise_for_status()
            version = response.json()
            
            files = version.get("files", [])
            images = version.get("images", [])
            
            return {
                "id": version.get("id"),
                "modelId": version.get("modelId"),
                "name": version.get("name"),
                "description": version.get("description", ""),
                "baseModel": version.get("baseModel", ""),
                "trainedWords": version.get("trainedWords", []),
                "downloadUrl": version.get("downloadUrl", ""),
                "files": [{
                    "name": f.get("name"),
                    "sizeKB": f.get("sizeKB"),
                    "type": f.get("type"),
                    "primary": f.get("primary", False),
                    "downloadUrl": f.get("downloadUrl", ""),
                } for f in files],
                "images": [{"url": img.get("url"), "nsfw": img.get("nsfw")} for img in images],
                "stats": version.get("stats", {}),
            }
            
        except httpx.HTTPStatusError as e:
            raise HTTPException(status_code=e.response.status_code, detail="Civitai API 请求失败")
        except httpx.RequestError as e:
            raise HTTPException(status_code=502, detail="无法连接到 Civitai")


@router.get("/popular")
async def get_popular_models(
    types: Optional[str] = Query(None, description="模型类型"),
    period: str = Query("Week", description="时间范围"),
    limit: int = Query(10, ge=1, le=50),
):
    """获取热门模型"""
    return await search_civitai(
        query="",
        types=types,
        sort="Most Downloaded",
        period=period,
        nsfw=False,
        limit=limit,
        page=1,
    )
