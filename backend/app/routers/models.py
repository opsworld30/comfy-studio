"""模型资源管理 API"""
import hashlib
from pathlib import Path
from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, or_
from pydantic import BaseModel

from ..database import get_db
from ..models import ModelInfo
from ..config import settings

router = APIRouter(prefix="/models", tags=["models"])


class ModelInfoResponse(BaseModel):
    id: int
    filename: str
    model_type: str
    name: str
    description: str
    base_model: str
    size: int
    hash: str
    preview_image: str
    civitai_id: str
    civitai_version_id: str
    tags: list
    use_count: int
    is_favorite: bool
    created_at: datetime
    updated_at: datetime
    size_display: str = ""
    is_installed: bool = True

    class Config:
        from_attributes = True


class ModelInfoUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    tags: Optional[list] = None
    is_favorite: Optional[bool] = None


def format_size(size: int) -> str:
    """格式化文件大小"""
    if size < 1024:
        return f"{size} B"
    elif size < 1024 * 1024:
        return f"{size / 1024:.1f} KB"
    elif size < 1024 * 1024 * 1024:
        return f"{size / (1024 * 1024):.1f} MB"
    else:
        return f"{size / (1024 * 1024 * 1024):.2f} GB"


@router.get("/stats")
async def get_model_stats(db: AsyncSession = Depends(get_db)):
    """获取模型统计"""
    async def count_by_type(model_type: str) -> int:
        result = await db.execute(
            select(func.count()).select_from(ModelInfo).where(ModelInfo.model_type == model_type)
        )
        return result.scalar() or 0
    
    checkpoints = await count_by_type("checkpoint")
    loras = await count_by_type("lora")
    vaes = await count_by_type("vae")
    embeddings = await count_by_type("embedding")
    controlnets = await count_by_type("controlnet")
    upscalers = await count_by_type("upscale")
    
    size_result = await db.execute(select(func.sum(ModelInfo.size)))
    total_size = size_result.scalar() or 0
    
    return {
        "checkpoints": checkpoints,
        "loras": loras,
        "vaes": vaes,
        "embeddings": embeddings,
        "controlnets": controlnets,
        "upscalers": upscalers,
        "total": checkpoints + loras + vaes + embeddings + controlnets + upscalers,
        "total_size": total_size,
        "total_size_display": format_size(total_size)
    }


@router.get("", response_model=List[ModelInfoResponse])
async def list_models(
    model_type: Optional[str] = None,
    base_model: Optional[str] = None,
    search: Optional[str] = None,
    favorite_only: bool = False,
    sort_by: str = "name",
    limit: int = 100,
    offset: int = 0,
    db: AsyncSession = Depends(get_db)
):
    """获取模型列表"""
    query = select(ModelInfo)
    
    if model_type:
        query = query.where(ModelInfo.model_type == model_type)
    
    if base_model:
        query = query.where(ModelInfo.base_model == base_model)
    
    if search:
        query = query.where(
            or_(
                ModelInfo.filename.ilike(f"%{search}%"),
                ModelInfo.name.ilike(f"%{search}%")
            )
        )
    
    if favorite_only:
        query = query.where(ModelInfo.is_favorite.is_(True))
    
    if sort_by == "name":
        query = query.order_by(ModelInfo.name)
    elif sort_by == "size":
        query = query.order_by(ModelInfo.size.desc())
    elif sort_by == "use_count":
        query = query.order_by(ModelInfo.use_count.desc())
    elif sort_by == "created_at":
        query = query.order_by(ModelInfo.created_at.desc())
    
    query = query.offset(offset).limit(limit)
    result = await db.execute(query)
    models = result.scalars().all()
    
    response = []
    for model in models:
        response.append(ModelInfoResponse(
            id=model.id,
            filename=model.filename,
            model_type=model.model_type,
            name=model.name or model.filename,
            description=model.description or "",
            base_model=model.base_model or "",
            size=model.size,
            hash=model.hash or "",
            preview_image=model.preview_image or "",
            civitai_id=model.civitai_id or "",
            civitai_version_id=model.civitai_version_id or "",
            tags=model.tags or [],
            use_count=model.use_count,
            is_favorite=model.is_favorite,
            created_at=model.created_at,
            updated_at=model.updated_at,
            size_display=format_size(model.size)
        ))
    
    return response


@router.get("/{model_id}", response_model=ModelInfoResponse)
async def get_model(model_id: int, db: AsyncSession = Depends(get_db)):
    """获取模型详情"""
    result = await db.execute(select(ModelInfo).where(ModelInfo.id == model_id))
    model = result.scalar_one_or_none()
    if not model:
        raise HTTPException(status_code=404, detail="Model not found")
    
    return ModelInfoResponse(
        id=model.id,
        filename=model.filename,
        model_type=model.model_type,
        name=model.name or model.filename,
        description=model.description or "",
        base_model=model.base_model or "",
        size=model.size,
        hash=model.hash or "",
        preview_image=model.preview_image or "",
        civitai_id=model.civitai_id or "",
        civitai_version_id=model.civitai_version_id or "",
        tags=model.tags or [],
        use_count=model.use_count,
        is_favorite=model.is_favorite,
        created_at=model.created_at,
        updated_at=model.updated_at,
        size_display=format_size(model.size)
    )


@router.put("/{model_id}", response_model=ModelInfoResponse)
async def update_model(
    model_id: int,
    update: ModelInfoUpdate,
    db: AsyncSession = Depends(get_db)
):
    """更新模型信息"""
    result = await db.execute(select(ModelInfo).where(ModelInfo.id == model_id))
    model = result.scalar_one_or_none()
    if not model:
        raise HTTPException(status_code=404, detail="Model not found")
    
    if update.name is not None:
        model.name = update.name
    if update.description is not None:
        model.description = update.description
    if update.tags is not None:
        model.tags = update.tags
    if update.is_favorite is not None:
        model.is_favorite = update.is_favorite
    
    await db.commit()
    await db.refresh(model)
    
    return ModelInfoResponse(
        id=model.id,
        filename=model.filename,
        model_type=model.model_type,
        name=model.name or model.filename,
        description=model.description or "",
        base_model=model.base_model or "",
        size=model.size,
        hash=model.hash or "",
        preview_image=model.preview_image or "",
        civitai_id=model.civitai_id or "",
        civitai_version_id=model.civitai_version_id or "",
        tags=model.tags or [],
        use_count=model.use_count,
        is_favorite=model.is_favorite,
        created_at=model.created_at,
        updated_at=model.updated_at,
        size_display=format_size(model.size)
    )


@router.post("/{model_id}/favorite")
async def toggle_model_favorite(model_id: int, db: AsyncSession = Depends(get_db)):
    """切换模型收藏状态"""
    result = await db.execute(select(ModelInfo).where(ModelInfo.id == model_id))
    model = result.scalar_one_or_none()
    if not model:
        raise HTTPException(status_code=404, detail="Model not found")
    
    model.is_favorite = not model.is_favorite
    await db.commit()
    
    return {"is_favorite": model.is_favorite}


@router.post("/scan")
async def scan_models(db: AsyncSession = Depends(get_db)):
    """扫描并更新模型列表（从 ComfyUI 获取）"""
    import httpx
    
    added = 0
    updated = 0
    errors = []
    
    # 模型类型映射：ComfyUI 节点名 -> 模型类型
    model_endpoints = {
        "CheckpointLoaderSimple": ("checkpoints", "checkpoint"),
        "LoraLoader": ("loras", "lora"),
        "VAELoader": ("vae", "vae"),
        "ControlNetLoader": ("controlnet", "controlnet"),
        "UpscaleModelLoader": ("upscale_models", "upscale"),
    }
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            # 获取 object_info 来解析可用模型
            response = await client.get(f"{settings.COMFYUI_URL}/object_info")
            if response.status_code != 200:
                raise HTTPException(status_code=502, detail="无法连接到 ComfyUI")
            
            object_info = response.json()
            
            for node_name, (folder_name, model_type) in model_endpoints.items():
                if node_name not in object_info:
                    continue
                
                node_info = object_info[node_name]
                input_info = node_info.get("input", {}).get("required", {})
                
                # 查找模型名称字段
                model_field = None
                if node_name == "CheckpointLoaderSimple":
                    model_field = "ckpt_name"
                elif node_name == "LoraLoader":
                    model_field = "lora_name"
                elif node_name == "VAELoader":
                    model_field = "vae_name"
                elif node_name == "ControlNetLoader":
                    model_field = "control_net_name"
                elif node_name == "UpscaleModelLoader":
                    model_field = "model_name"
                
                if not model_field or model_field not in input_info:
                    continue
                
                model_list = input_info[model_field][0]
                if not isinstance(model_list, list):
                    continue
                
                for filename in model_list:
                    if not filename:
                        continue
                    
                    # 检查是否已存在
                    result = await db.execute(
                        select(ModelInfo).where(
                            ModelInfo.filename == filename,
                            ModelInfo.model_type == model_type
                        )
                    )
                    existing = result.scalar_one_or_none()
                    
                    if existing:
                        updated += 1
                    else:
                        # 创建新记录
                        new_model = ModelInfo(
                            filename=filename,
                            model_type=model_type,
                            name=filename.rsplit('.', 1)[0] if '.' in filename else filename,
                            size=0,  # 无法从 API 获取大小
                            base_model=_guess_base_model(filename),
                        )
                        db.add(new_model)
                        added += 1
            
            await db.commit()
            
        except httpx.RequestError as e:
            errors.append(f"连接 ComfyUI 失败: {str(e)}")
        except Exception as e:
            errors.append(f"扫描错误: {str(e)}")
    
    return {
        "added": added,
        "updated": updated,
        "errors": errors,
        "message": f"扫描完成，新增 {added} 个模型，更新 {updated} 个"
    }


def _guess_base_model(filename: str) -> str:
    """根据文件名猜测基础模型"""
    filename_lower = filename.lower()
    if "xl" in filename_lower or "sdxl" in filename_lower:
        return "SDXL"
    elif "sd3" in filename_lower:
        return "SD3"
    elif "flux" in filename_lower:
        return "Flux"
    elif "sd15" in filename_lower or "sd1.5" in filename_lower or "v1-5" in filename_lower:
        return "SD1.5"
    return ""


@router.delete("/{model_id}")
async def delete_model(model_id: int, db: AsyncSession = Depends(get_db)):
    """删除模型记录（不删除文件）"""
    result = await db.execute(select(ModelInfo).where(ModelInfo.id == model_id))
    model = result.scalar_one_or_none()
    if not model:
        raise HTTPException(status_code=404, detail="Model not found")
    
    await db.delete(model)
    await db.commit()
    
    return {"message": "Model record deleted"}


@router.get("/storage/analysis")
async def get_storage_analysis():
    """获取存储分析：重复文件、缺失依赖、文件大小等"""
    comfyui_path = Path(settings.COMFYUI_PATH)
    models_path = comfyui_path / "models"
    
    if not models_path.exists():
        return {
            "total_size": 0,
            "total_files": 0,
            "duplicates": [],
            "duplicate_count": 0,
            "duplicate_size": 0,
            "missing_dependencies": [],
            "missing_count": 0,
            "models_by_type": {},
        }
    
    # 扫描所有模型文件
    model_folders = {
        "checkpoints": ["*.safetensors", "*.ckpt", "*.pt"],
        "loras": ["*.safetensors", "*.pt"],
        "vae": ["*.safetensors", "*.pt"],
        "controlnet": ["*.safetensors", "*.pth"],
        "upscale_models": ["*.pth", "*.pt"],
        "embeddings": ["*.safetensors", "*.pt", "*.bin"],
    }
    
    all_files = []
    models_by_type = {}
    file_hashes = {}  # hash -> [files]
    
    for folder, patterns in model_folders.items():
        folder_path = models_path / folder
        if not folder_path.exists():
            models_by_type[folder] = {"count": 0, "size": 0, "files": []}
            continue
        
        files = []
        folder_size = 0
        
        for pattern in patterns:
            for file_path in folder_path.rglob(pattern):
                if file_path.is_file():
                    size = file_path.stat().st_size
                    file_info = {
                        "name": file_path.name,
                        "path": str(file_path.relative_to(comfyui_path)),
                        "size": size,
                        "size_display": format_size(size),
                        "type": folder,
                    }
                    files.append(file_info)
                    all_files.append(file_info)
                    folder_size += size
                    
                    # 计算简单哈希（文件大小+前1KB）用于检测重复
                    try:
                        with open(file_path, "rb") as f:
                            header = f.read(1024)
                        simple_hash = f"{size}_{hashlib.md5(header).hexdigest()}"
                        if simple_hash not in file_hashes:
                            file_hashes[simple_hash] = []
                        file_hashes[simple_hash].append(file_info)
                    except Exception:
                        pass
        
        models_by_type[folder] = {
            "count": len(files),
            "size": folder_size,
            "size_display": format_size(folder_size),
            "files": files,
        }
    
    # 检测重复文件
    duplicates = []
    duplicate_size = 0
    for hash_key, files in file_hashes.items():
        if len(files) > 1:
            duplicates.append({
                "files": files,
                "count": len(files),
                "size": files[0]["size"],
                "total_wasted": files[0]["size"] * (len(files) - 1),
            })
            duplicate_size += files[0]["size"] * (len(files) - 1)
    
    # 检测缺失依赖（常见的必需模型）
    required_models = [
        {"name": "VAE", "folder": "vae", "description": "VAE 解码器用于将潜空间转换为图像"},
        {"name": "CLIP", "folder": "clip", "description": "CLIP 模型用于文本编码"},
    ]
    
    missing_dependencies = []
    for req in required_models:
        folder_path = models_path / req["folder"]
        if not folder_path.exists() or not any(folder_path.iterdir()):
            missing_dependencies.append(req)
    
    total_size = sum(m["size"] for m in models_by_type.values())
    total_files = sum(m["count"] for m in models_by_type.values())
    
    return {
        "total_size": total_size,
        "total_size_display": format_size(total_size),
        "total_files": total_files,
        "duplicates": duplicates,
        "duplicate_count": len(duplicates),
        "duplicate_size": duplicate_size,
        "duplicate_size_display": format_size(duplicate_size),
        "missing_dependencies": missing_dependencies,
        "missing_count": len(missing_dependencies),
        "models_by_type": models_by_type,
    }


@router.post("/storage/cleanup")
async def cleanup_duplicates():
    """清理重复文件（保留一个，删除其他）"""
    # 这里只返回建议，不实际删除
    analysis = await get_storage_analysis()
    
    cleanup_suggestions = []
    for dup in analysis["duplicates"]:
        # 保留第一个文件，建议删除其他
        keep = dup["files"][0]
        remove = dup["files"][1:]
        cleanup_suggestions.append({
            "keep": keep,
            "remove": remove,
            "savings": dup["total_wasted"],
        })
    
    return {
        "suggestions": cleanup_suggestions,
        "total_savings": analysis["duplicate_size"],
        "total_savings_display": format_size(analysis["duplicate_size"]),
        "message": "这些是清理建议，请手动确认后删除文件",
    }


@router.get("/storage/details")
async def get_model_details():
    """获取所有模型的详细信息（包括真实文件大小）"""
    comfyui_path = Path(settings.COMFYUI_PATH)
    models_path = comfyui_path / "models"
    
    if not models_path.exists():
        return []
    
    model_folders = {
        "checkpoints": ["*.safetensors", "*.ckpt", "*.pt"],
        "loras": ["*.safetensors", "*.pt"],
        "vae": ["*.safetensors", "*.pt"],
        "controlnet": ["*.safetensors", "*.pth"],
        "upscale_models": ["*.pth", "*.pt"],
        "embeddings": ["*.safetensors", "*.pt", "*.bin"],
    }
    
    all_models = []
    
    for folder, patterns in model_folders.items():
        folder_path = models_path / folder
        if not folder_path.exists():
            continue
        
        for pattern in patterns:
            for file_path in folder_path.rglob(pattern):
                if file_path.is_file():
                    size = file_path.stat().st_size
                    name = file_path.stem
                    
                    all_models.append({
                        "name": name,
                        "filename": file_path.name,
                        "path": str(file_path.relative_to(comfyui_path)),
                        "type": folder,
                        "size": size,
                        "size_display": format_size(size),
                        "base_model": _guess_base_model(file_path.name),
                    })
    
    return all_models
