"""ComfyUI 服务器管理路由"""
import asyncio
from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete
from pydantic import BaseModel
import httpx

from ..database import get_db
from ..models import ComfyUIServer
from ..schemas import ComfyUIServerCreate, ComfyUIServerUpdate, ComfyUIServerResponse
from ..services.cache import cache_service

router = APIRouter(prefix="/comfyui-servers", tags=["comfyui-servers"])

# 服务器状态缓存TTL（秒）
# 在线状态缓存较短，离线/错误状态缓存更短以便快速检测恢复
SERVER_STATUS_CACHE_TTL_ONLINE = 5   # 在线时5秒缓存
SERVER_STATUS_CACHE_TTL_OFFLINE = 3  # 离线/错误时3秒缓存


class ServerWithStatus(BaseModel):
    """带状态的服务器响应"""
    id: int
    name: str
    url: str
    is_local: bool
    is_default: bool
    is_active: bool
    description: str
    status: str  # online, offline, error
    queue_size: int = 0
    gpu_info: dict | None = None
    
    class Config:
        from_attributes = True


async def check_server_status(url: str, use_cache: bool = True) -> tuple[str, int, dict | None]:
    """检查服务器状态（带缓存）"""
    cache_key = f"server_status:{url}"

    # 检查缓存
    if use_cache:
        cached = cache_service.get(cache_key)
        if cached is not None:
            return cached

    try:
        # 使用更短的超时时间，加快离线检测
        timeout = httpx.Timeout(connect=2.0, read=3.0, write=3.0, pool=3.0)
        async with httpx.AsyncClient(timeout=timeout) as client:
            # 检查系统状态
            response = await client.get(f"{url}/system_stats")
            if response.status_code == 200:
                stats = response.json()
                gpu_info = None
                if stats.get("devices"):
                    device = stats["devices"][0]
                    gpu_info = {
                        "name": device.get("name", "Unknown"),
                        "vram_total": device.get("vram_total", 0),
                        "vram_free": device.get("vram_free", 0),
                    }

                # 获取队列大小
                queue_response = await client.get(f"{url}/queue")
                queue_size = 0
                if queue_response.status_code == 200:
                    queue_data = queue_response.json()
                    queue_size = len(queue_data.get("queue_running", [])) + len(queue_data.get("queue_pending", []))

                result = ("online", queue_size, gpu_info)
                cache_service.set(cache_key, result, ttl=SERVER_STATUS_CACHE_TTL_ONLINE)
                return result
            result = ("error", 0, None)
            cache_service.set(cache_key, result, ttl=SERVER_STATUS_CACHE_TTL_OFFLINE)
            return result
    except httpx.TimeoutException:
        result = ("offline", 0, None)
        cache_service.set(cache_key, result, ttl=SERVER_STATUS_CACHE_TTL_OFFLINE)
        return result
    except Exception:
        result = ("error", 0, None)
        cache_service.set(cache_key, result, ttl=SERVER_STATUS_CACHE_TTL_OFFLINE)
        return result


@router.get("", response_model=List[ServerWithStatus])
async def list_servers(db: AsyncSession = Depends(get_db)):
    """获取所有ComfyUI服务器列表（带实时状态，并行检查）"""
    result = await db.execute(
        select(ComfyUIServer).order_by(ComfyUIServer.is_default.desc(), ComfyUIServer.created_at)
    )
    servers = result.scalars().all()

    if not servers:
        return []

    # 并行检查所有服务器状态
    async def check_with_server(server):
        status, queue_size, gpu_info = await check_server_status(server.url)
        return ServerWithStatus(
            id=server.id,
            name=server.name,
            url=server.url,
            is_local=server.is_local,
            is_default=server.is_default,
            is_active=server.is_active,
            description=server.description or "",
            status=status,
            queue_size=queue_size,
            gpu_info=gpu_info,
        )

    # 并行执行所有检查
    tasks = [check_with_server(server) for server in servers]
    response = await asyncio.gather(*tasks)

    return response


@router.get("/{server_id}", response_model=ComfyUIServerResponse)
async def get_server(server_id: int, db: AsyncSession = Depends(get_db)):
    """获取单个ComfyUI服务器配置"""
    result = await db.execute(
        select(ComfyUIServer).where(ComfyUIServer.id == server_id)
    )
    server = result.scalar_one_or_none()
    if not server:
        raise HTTPException(status_code=404, detail="服务器配置不存在")
    return server


@router.post("", response_model=ComfyUIServerResponse)
async def create_server(
    server_data: ComfyUIServerCreate,
    db: AsyncSession = Depends(get_db)
):
    """创建新的ComfyUI服务器配置"""
    # 检查是否已有服务器，如果没有则自动设为默认
    result = await db.execute(select(ComfyUIServer).limit(1))
    existing_server = result.scalar_one_or_none()
    is_first_server = existing_server is None
    
    # 如果是第一个服务器或明确设置为默认，则设为默认
    should_be_default = is_first_server or server_data.is_default
    
    # 如果设置为默认，先取消其他默认设置
    if should_be_default and not is_first_server:
        await db.execute(
            update(ComfyUIServer).where(ComfyUIServer.is_default == True)
            .values(is_default=False)
        )
    
    server = ComfyUIServer(
        name=server_data.name,
        url=server_data.url,
        is_local=server_data.is_local,
        is_default=should_be_default,
        is_active=server_data.is_active,
        description=server_data.description,
    )
    db.add(server)
    await db.commit()
    await db.refresh(server)
    return server


@router.put("/{server_id}", response_model=ComfyUIServerResponse)
async def update_server(
    server_id: int,
    server_data: ComfyUIServerUpdate,
    db: AsyncSession = Depends(get_db)
):
    """更新ComfyUI服务器配置"""
    result = await db.execute(
        select(ComfyUIServer).where(ComfyUIServer.id == server_id)
    )
    server = result.scalar_one_or_none()
    if not server:
        raise HTTPException(status_code=404, detail="服务器配置不存在")
    
    # 如果设置为默认，先取消其他默认设置
    if server_data.is_default and not server.is_default:
        await db.execute(
            update(ComfyUIServer).where(ComfyUIServer.id != server_id)
            .values(is_default=False)
        )
    
    update_data = server_data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(server, key, value)
    
    await db.commit()
    await db.refresh(server)
    return server


@router.delete("/{server_id}")
async def delete_server(server_id: int, db: AsyncSession = Depends(get_db)):
    """删除ComfyUI服务器配置"""
    result = await db.execute(
        select(ComfyUIServer).where(ComfyUIServer.id == server_id)
    )
    server = result.scalar_one_or_none()
    if not server:
        raise HTTPException(status_code=404, detail="服务器配置不存在")
    
    # 不能删除默认服务器
    if server.is_default:
        raise HTTPException(status_code=400, detail="不能删除默认服务器")
    
    await db.delete(server)
    await db.commit()
    return {"message": "删除成功"}


@router.post("/{server_id}/set-default")
async def set_default_server(server_id: int, db: AsyncSession = Depends(get_db)):
    """设置默认服务器"""
    result = await db.execute(
        select(ComfyUIServer).where(ComfyUIServer.id == server_id)
    )
    server = result.scalar_one_or_none()
    if not server:
        raise HTTPException(status_code=404, detail="服务器配置不存在")
    
    # 取消所有默认设置
    await db.execute(
        update(ComfyUIServer).values(is_default=False)
    )
    
    # 设置新的默认服务器
    server.is_default = True
    await db.commit()
    
    return {"message": f"已设置 {server.name} 为默认服务器"}


@router.post("/{server_id}/toggle-active")
async def toggle_server_active(server_id: int, db: AsyncSession = Depends(get_db)):
    """切换服务器启用状态"""
    result = await db.execute(
        select(ComfyUIServer).where(ComfyUIServer.id == server_id)
    )
    server = result.scalar_one_or_none()
    if not server:
        raise HTTPException(status_code=404, detail="服务器配置不存在")

    # 不能禁用默认服务器
    if server.is_default and server.is_active:
        raise HTTPException(status_code=400, detail="不能禁用默认服务器")

    server.is_active = not server.is_active
    await db.commit()

    status = "启用" if server.is_active else "禁用"
    return {"message": f"已{status}服务器 {server.name}"}


@router.post("/{server_id}/check")
async def check_server_status_endpoint(server_id: int, db: AsyncSession = Depends(get_db)):
    """强制检查服务器状态（绕过缓存）"""
    result = await db.execute(
        select(ComfyUIServer).where(ComfyUIServer.id == server_id)
    )
    server = result.scalar_one_or_none()
    if not server:
        raise HTTPException(status_code=404, detail="服务器配置不存在")

    # 强制刷新，绕过缓存
    status, queue_size, gpu_info = await check_server_status(server.url, use_cache=False)

    return {
        "id": server.id,
        "name": server.name,
        "url": server.url,
        "status": status,
        "queue_size": queue_size,
        "gpu_info": gpu_info,
    }


@router.get("/active/list")
async def get_active_servers(db: AsyncSession = Depends(get_db)):
    """获取所有启用的服务器列表"""
    result = await db.execute(
        select(ComfyUIServer).where(ComfyUIServer.is_active == True)
        .order_by(ComfyUIServer.is_default.desc(), ComfyUIServer.name)
    )
    servers = result.scalars().all()
    return servers


@router.get("/default/current")
async def get_default_server(db: AsyncSession = Depends(get_db)):
    """获取当前默认服务器"""
    result = await db.execute(
        select(ComfyUIServer).where(ComfyUIServer.is_default == True)
    )
    server = result.scalar_one_or_none()
    if not server:
        raise HTTPException(status_code=404, detail="没有设置默认服务器")
    return server


@router.get("/{server_id}/models")
async def get_server_models(server_id: int, db: AsyncSession = Depends(get_db)):
    """获取指定服务器的模型列表（带缓存，5分钟TTL）"""
    result = await db.execute(
        select(ComfyUIServer).where(ComfyUIServer.id == server_id)
    )
    server = result.scalar_one_or_none()
    if not server:
        raise HTTPException(status_code=404, detail="服务器配置不存在")

    # 检查缓存
    cache_key = f"server_models:{server.url}"
    cached = cache_service.get(cache_key)
    if cached is not None:
        return cached

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(f"{server.url}/object_info")
            if response.status_code != 200:
                raise HTTPException(status_code=502, detail="无法连接到 ComfyUI 服务器")

            object_info = response.json()

            # 提取模型列表
            checkpoints = []
            loras = []
            vaes = []

            if "CheckpointLoaderSimple" in object_info:
                ckpt_input = object_info["CheckpointLoaderSimple"].get("input", {}).get("required", {})
                if "ckpt_name" in ckpt_input:
                    ckpt_list = ckpt_input["ckpt_name"]
                    if isinstance(ckpt_list, list) and len(ckpt_list) > 0:
                        checkpoints = ckpt_list[0] if isinstance(ckpt_list[0], list) else []

            if "LoraLoader" in object_info:
                lora_input = object_info["LoraLoader"].get("input", {}).get("required", {})
                if "lora_name" in lora_input:
                    lora_list = lora_input["lora_name"]
                    if isinstance(lora_list, list) and len(lora_list) > 0:
                        loras = lora_list[0] if isinstance(lora_list[0], list) else []

            if "VAELoader" in object_info:
                vae_input = object_info["VAELoader"].get("input", {}).get("required", {})
                if "vae_name" in vae_input:
                    vae_list = vae_input["vae_name"]
                    if isinstance(vae_list, list) and len(vae_list) > 0:
                        vaes = vae_list[0] if isinstance(vae_list[0], list) else []

            models_data = {
                "checkpoints": checkpoints[:20],  # 限制数量
                "loras": loras[:20],
                "vaes": vaes[:10],
            }

            # 缓存5分钟
            cache_service.set(cache_key, models_data, ttl=300)
            return models_data
    except httpx.RequestError as e:
        raise HTTPException(status_code=502, detail=f"连接服务器失败: {str(e)}")