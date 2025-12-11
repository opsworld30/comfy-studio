"""用户设置路由"""
import logging
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from ..database import get_db
from ..models import UserSettings
from ..schemas import PageModuleSettings, AISettings, PromptOptimizeRequest, PromptOptimizeResponse
from ..services.ai import ai_service
from ..services.cache import cache_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/settings", tags=["settings"])

# 缓存键前缀
CACHE_PREFIX_SETTINGS = "settings"


# ========== 通用应用设置 ==========

DEFAULT_APP_SETTINGS = {
    "language": "zh-CN",
    "theme": "dark",
    "auto_save_interval": 30,
    "default_server_id": None,
    "notification_enabled": True,
    "sound_enabled": False,
    "auto_backup_enabled": True,
    "backup_interval_hours": 24,
    "max_backup_count": 10,
}


@router.get("")
async def get_app_settings(db: AsyncSession = Depends(get_db)):
    """获取应用设置（带缓存）"""
    cache_key = f"{CACHE_PREFIX_SETTINGS}:app"
    cached = cache_service.get(cache_key)
    if cached is not None:
        return cached
    
    result = await db.execute(
        select(UserSettings).where(UserSettings.key == "app_settings")
    )
    settings = result.scalar_one_or_none()
    
    if settings:
        result_data = {**DEFAULT_APP_SETTINGS, **settings.value}
    else:
        result_data = DEFAULT_APP_SETTINGS
    
    cache_service.set(cache_key, result_data, ttl=60)
    return result_data


@router.put("")
async def update_app_settings(
    settings_data: dict,
    db: AsyncSession = Depends(get_db)
):
    """更新应用设置"""
    result = await db.execute(
        select(UserSettings).where(UserSettings.key == "app_settings")
    )
    settings = result.scalar_one_or_none()
    
    # 合并设置
    if settings:
        value = {**settings.value, **settings_data}
    else:
        value = {**DEFAULT_APP_SETTINGS, **settings_data}
    
    if settings:
        settings.value = value
    else:
        settings = UserSettings(key="app_settings", value=value)
        db.add(settings)
    
    await db.commit()
    await db.refresh(settings)
    
    # 失效缓存
    cache_service.delete(f"{CACHE_PREFIX_SETTINGS}:app")
    
    return settings.value


@router.get("/storage")
async def get_storage_stats(db: AsyncSession = Depends(get_db)):
    """获取存储统计（带缓存，30秒TTL）"""
    cache_key = f"{CACHE_PREFIX_SETTINGS}:storage"
    cached = cache_service.get(cache_key)
    if cached is not None:
        return cached
    
    from pathlib import Path
    from sqlalchemy import func
    from ..models import StoredImage
    
    data_dir = Path("data")
    images_dir = data_dir / "images"
    thumbnails_dir = data_dir / "thumbnails"
    backups_dir = data_dir / "backups"
    temp_dir = data_dir / "temp"
    
    def get_dir_size(path: Path) -> int:
        if not path.exists():
            return 0
        return sum(f.stat().st_size for f in path.rglob("*") if f.is_file())
    
    def get_file_count(path: Path) -> int:
        if not path.exists():
            return 0
        return sum(1 for f in path.rglob("*") if f.is_file())
    
    # 获取块存储图片统计
    result = await db.execute(
        select(func.count(), func.sum(StoredImage.size))
        .where(StoredImage.is_deleted.is_(False))
    )
    row = result.one()
    images_count = row[0] or 0
    images_size = row[1] or 0
    
    # 块存储文件实际大小
    block_storage_size = get_dir_size(images_dir)
    
    stats = {
        "images_size": block_storage_size,  # 块存储实际占用
        "images_count": images_count,  # 数据库中的图片数量
        "images_db_size": images_size,  # 数据库记录的图片总大小
        "cache_size": get_dir_size(thumbnails_dir),
        "cache_count": get_file_count(thumbnails_dir),
        "temp_size": get_dir_size(temp_dir),
        "temp_count": get_file_count(temp_dir),
        "backup_size": get_dir_size(backups_dir),
        "backup_count": get_file_count(backups_dir),
        "total_size": get_dir_size(data_dir),
    }
    
    cache_service.set(cache_key, stats, ttl=30)
    return stats


@router.post("/cleanup/temp")
async def cleanup_temp_files():
    """清理临时文件"""
    from pathlib import Path
    import shutil
    
    temp_dir = Path("data/temp")
    cleaned = 0
    
    if temp_dir.exists():
        for f in temp_dir.iterdir():
            if f.is_file():
                f.unlink()
                cleaned += 1
            elif f.is_dir():
                shutil.rmtree(f)
                cleaned += 1
    
    return {"cleaned": cleaned, "message": f"已清理 {cleaned} 个临时文件"}


@router.post("/cleanup/cache")
async def cleanup_cache_files():
    """清理缓存文件"""
    from pathlib import Path
    
    thumbnails_dir = Path("data/thumbnails")
    cleaned = 0
    
    if thumbnails_dir.exists():
        for f in thumbnails_dir.iterdir():
            if f.is_file():
                f.unlink()
                cleaned += 1
    
    return {"cleaned": cleaned, "message": f"已清理 {cleaned} 个缓存文件"}


# 默认设置
DEFAULT_PAGE_SETTINGS = {
    "pages": {
        "showDashboard": True,
        "showWorkflows": True,
        "showGallery": True,
        "showPrompts": True,
        "showModels": False,
        "showMarket": False,
        "showMonitor": True,
        "showBatch": True,
        "showSettings": True,
    },
    "dashboard": {
        "showQuickActions": True,
        "showRecentImages": True,
        "showSystemStatus": True,
        "showStatistics": True,
    },
    "workflows": {
        "showCategories": True,
        "showFavorites": True,
        "showSearch": True,
    },
    "gallery": {
        "showSearchBar": True,
        "showLayoutToggle": True,
        "showCategories": True,
        "showFavorites": True,
    },
    "prompts": {
        "showCategories": True,
        "showAIGenerate": True,
        "showFavorites": True,
    },
    "models": {
        "showLocalModels": True,
        "showCivitai": True,
    },
    "monitor": {
        "showSystemStatus": True,
        "showExecutionQueue": True,
        "showPerformanceChart": True,
        "showExecutionHistory": True,
    },
    "batch": {
        "showPending": True,
        "showRunning": True,
        "showCompleted": True,
        "showFailed": True,
    },
}


@router.get("/page-modules", response_model=PageModuleSettings)
async def get_page_settings(db: AsyncSession = Depends(get_db)):
    """获取页面模块设置"""
    result = await db.execute(
        select(UserSettings).where(UserSettings.key == "page_modules")
    )
    settings = result.scalar_one_or_none()
    
    if settings:
        # 合并默认设置，确保新增的配置项有默认值
        merged = {}
        for key in DEFAULT_PAGE_SETTINGS:
            merged[key] = {**DEFAULT_PAGE_SETTINGS[key], **settings.value.get(key, {})}
        return PageModuleSettings(**merged)
    
    return PageModuleSettings(**DEFAULT_PAGE_SETTINGS)


@router.put("/page-modules", response_model=PageModuleSettings)
async def update_page_settings(
    settings_data: PageModuleSettings,
    db: AsyncSession = Depends(get_db)
):
    """更新页面模块设置"""
    result = await db.execute(
        select(UserSettings).where(UserSettings.key == "page_modules")
    )
    settings = result.scalar_one_or_none()
    
    value = settings_data.model_dump()
    
    if settings:
        settings.value = value
    else:
        settings = UserSettings(key="page_modules", value=value)
        db.add(settings)
    
    await db.commit()
    await db.refresh(settings)
    
    return PageModuleSettings(**settings.value)


@router.post("/page-modules/reset", response_model=PageModuleSettings)
async def reset_page_settings(db: AsyncSession = Depends(get_db)):
    """重置页面模块设置为默认值"""
    result = await db.execute(
        select(UserSettings).where(UserSettings.key == "page_modules")
    )
    settings = result.scalar_one_or_none()
    
    if settings:
        settings.value = DEFAULT_PAGE_SETTINGS
        await db.commit()
    
    return PageModuleSettings(**DEFAULT_PAGE_SETTINGS)


# ========== AI 设置 ==========

DEFAULT_AI_SETTINGS = {
    "api_key": "",
    "api_url": "https://api.siliconflow.cn/v1",
    "model": "Qwen/Qwen2.5-7B-Instruct",  # SiliconFlow 免费模型
    "enabled": False,
}


@router.get("/ai", response_model=AISettings)
async def get_ai_settings(db: AsyncSession = Depends(get_db)):
    """获取 AI 设置"""
    result = await db.execute(
        select(UserSettings).where(UserSettings.key == "ai_settings")
    )
    settings = result.scalar_one_or_none()
    
    if settings:
        merged = {**DEFAULT_AI_SETTINGS, **settings.value}
        # 不返回完整的 API Key，只返回是否已配置
        if merged.get("api_key"):
            merged["api_key"] = "***" + merged["api_key"][-4:] if len(merged["api_key"]) > 4 else "****"
        return AISettings(**merged)
    
    return AISettings(**DEFAULT_AI_SETTINGS)


@router.put("/ai", response_model=AISettings)
async def update_ai_settings(
    settings_data: AISettings,
    db: AsyncSession = Depends(get_db)
):
    """更新 AI 设置"""
    result = await db.execute(
        select(UserSettings).where(UserSettings.key == "ai_settings")
    )
    settings = result.scalar_one_or_none()
    
    value = settings_data.model_dump()
    
    # 如果传入的是掩码，保留原来的 key
    if value.get("api_key", "").startswith("***") and settings:
        value["api_key"] = settings.value.get("api_key", "")
    
    if settings:
        settings.value = value
    else:
        settings = UserSettings(key="ai_settings", value=value)
        db.add(settings)
    
    await db.commit()
    await db.refresh(settings)
    
    # 返回时隐藏 API Key
    response_value = {**settings.value}
    if response_value.get("api_key"):
        response_value["api_key"] = "***" + response_value["api_key"][-4:] if len(response_value["api_key"]) > 4 else "****"
    
    return AISettings(**response_value)


@router.post("/ai/optimize", response_model=PromptOptimizeResponse)
async def optimize_prompt(
    request: PromptOptimizeRequest,
    db: AsyncSession = Depends(get_db)
):
    """使用 AI 优化 Prompt"""
    logger.info(f"AI optimize request: action={request.action}, prompt={request.prompt[:50]}...")
    
    # 获取 AI 设置
    result = await db.execute(
        select(UserSettings).where(UserSettings.key == "ai_settings")
    )
    settings = result.scalar_one_or_none()
    
    if not settings:
        logger.error("AI settings not found in database")
        raise HTTPException(status_code=400, detail="未配置 AI 设置，请在设置中配置")
    
    if not settings.value.get("api_key"):
        logger.error("AI API key not configured")
        raise HTTPException(status_code=400, detail="未配置 AI API Key，请在设置中配置")
    
    ai_config = settings.value
    logger.info(f"AI config: url={ai_config.get('api_url')}, model={ai_config.get('model')}, key=***{ai_config.get('api_key', '')[-4:]}")
    
    try:
        # 调用 AI 服务
        optimized = await ai_service.optimize_prompt(
            prompt=request.prompt,
            action=request.action,
            api_key=ai_config["api_key"],
            api_url=ai_config.get("api_url", DEFAULT_AI_SETTINGS["api_url"]),
            model=ai_config.get("model", DEFAULT_AI_SETTINGS["model"]),
            style=request.style,
        )
        
        logger.info(f"AI optimize success: {optimized[:50]}...")
        return PromptOptimizeResponse(
            original=request.prompt,
            optimized=optimized,
            action=request.action,
        )
    except ValueError as e:
        logger.error(f"AI ValueError: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"AI Exception: {type(e).__name__}: {e}")
        raise HTTPException(status_code=500, detail=f"AI 服务错误: {str(e)}")


# ========== ComfyUI 设置 ==========

DEFAULT_COMFYUI_SETTINGS = {
    "url": "http://127.0.0.1:8188",  # ComfyUI 服务地址
    "output_dir": "",  # ComfyUI 输出目录，用于删除原图
    "auto_migrate": True,  # 是否自动迁移图片
    "delete_original": True,  # 迁移后是否删除原图
}


@router.get("/comfyui")
async def get_comfyui_settings(db: AsyncSession = Depends(get_db)):
    """获取 ComfyUI 设置"""
    result = await db.execute(
        select(UserSettings).where(UserSettings.key == "comfyui_settings")
    )
    settings = result.scalar_one_or_none()
    
    if settings:
        return {**DEFAULT_COMFYUI_SETTINGS, **settings.value}
    
    return DEFAULT_COMFYUI_SETTINGS


@router.put("/comfyui")
async def update_comfyui_settings(
    settings_data: dict,
    db: AsyncSession = Depends(get_db)
):
    """更新 ComfyUI 设置"""
    result = await db.execute(
        select(UserSettings).where(UserSettings.key == "comfyui_settings")
    )
    settings = result.scalar_one_or_none()
    
    # 只保留允许的字段
    value = {
        "url": settings_data.get("url", DEFAULT_COMFYUI_SETTINGS["url"]),
        "output_dir": settings_data.get("output_dir", ""),
        "auto_migrate": settings_data.get("auto_migrate", True),
        "delete_original": settings_data.get("delete_original", True),
    }
    
    if settings:
        settings.value = value
    else:
        settings = UserSettings(key="comfyui_settings", value=value)
        db.add(settings)
    
    await db.commit()
    await db.refresh(settings)
    
    return settings.value


# ========== 系统设置（认证相关） ==========

DEFAULT_SYSTEM_SETTINGS = {
    "allow_registration": True,  # 是否允许新用户注册
    "site_name": "ComfyUI Studio",  # 站点名称
}


@router.get("/system")
async def get_system_settings(db: AsyncSession = Depends(get_db)):
    """获取系统设置（公开接口，无需认证）"""
    result = await db.execute(
        select(UserSettings).where(UserSettings.key == "system_settings")
    )
    settings = result.scalar_one_or_none()
    
    if settings:
        return {**DEFAULT_SYSTEM_SETTINGS, **settings.value}
    
    return DEFAULT_SYSTEM_SETTINGS


@router.put("/system")
async def update_system_settings(
    settings_data: dict,
    db: AsyncSession = Depends(get_db)
):
    """更新系统设置（需要管理员权限）"""
    # TODO: 添加管理员权限检查
    result = await db.execute(
        select(UserSettings).where(UserSettings.key == "system_settings")
    )
    settings = result.scalar_one_or_none()
    
    # 只保留允许的字段
    value = {
        "allow_registration": settings_data.get("allow_registration", DEFAULT_SYSTEM_SETTINGS["allow_registration"]),
        "site_name": settings_data.get("site_name", DEFAULT_SYSTEM_SETTINGS["site_name"]),
    }
    
    if settings:
        settings.value = value
    else:
        settings = UserSettings(key="system_settings", value=value)
        db.add(settings)
    
    await db.commit()
    await db.refresh(settings)
    
    return settings.value
