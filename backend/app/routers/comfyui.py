"""ComfyUI 代理路由"""
import hashlib
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from PIL import Image

from ..database import get_db
from ..models import Workflow, ExecutionHistory, StoredImage
from ..schemas import (
    ComfyUIStatus, 
    ExecuteWorkflowRequest, 
    ExecutionResponse,
    ExecutionListResponse,
    ImageInfo,
)
from ..services.comfyui import comfyui_service
from ..services.image_storage import image_storage_service
from ..services.storage import storage_service
from ..services.cache import cache_service

# 缩略图缓存目录
THUMBNAIL_CACHE_DIR = Path("data/thumbnails")
THUMBNAIL_CACHE_DIR.mkdir(parents=True, exist_ok=True)

# 简单的 XOR 加密密钥（防止直接查看缓存文件）
CACHE_XOR_KEY = b"ComfyUIHelper2024"

def xor_encrypt(data: bytes) -> bytes:
    """简单 XOR 加密/解密"""
    key = CACHE_XOR_KEY
    return bytes(b ^ key[i % len(key)] for i, b in enumerate(data))


def _generate_thumbnail(image_data: bytes, size: int) -> bytes:
    """
    生成缩略图
    
    Args:
        image_data: 原始图片数据
        size: 缩略图尺寸
        
    Returns:
        WebP 格式的缩略图数据
    """
    img = Image.open(BytesIO(image_data))
    img.thumbnail((size, size), Image.Resampling.LANCZOS)
    
    # 转换为 WebP 格式（更小的文件大小）
    output = BytesIO()
    
    # 处理不同的图片模式
    if img.mode == 'RGBA':
        # RGBA 模式：使用 alpha 通道作为 mask
        background = Image.new('RGB', img.size, (255, 255, 255))
        background.paste(img, mask=img.split()[3])  # 第 4 个通道是 alpha
        img = background
    elif img.mode == 'LA':
        # LA 模式 (Luminance + Alpha)：先转换为 RGBA
        img = img.convert('RGBA')
        background = Image.new('RGB', img.size, (255, 255, 255))
        background.paste(img, mask=img.split()[3])
        img = background
    elif img.mode == 'P':
        # 调色板模式：检查是否有透明度
        if 'transparency' in img.info:
            img = img.convert('RGBA')
            background = Image.new('RGB', img.size, (255, 255, 255))
            background.paste(img, mask=img.split()[3])
            img = background
        else:
            img = img.convert('RGB')
    elif img.mode != 'RGB':
        img = img.convert('RGB')
    
    img.save(output, format='WEBP', quality=80)
    return output.getvalue()


router = APIRouter(prefix="/comfyui", tags=["comfyui"])


# 状态缓存 TTL（秒）
STATUS_CACHE_TTL = 2  # 2秒缓存，快速响应同时保持实时性


@router.get("/status", response_model=ComfyUIStatus)
async def get_status():
    """获取 ComfyUI 状态（带缓存，2秒TTL）"""
    base_url = await comfyui_service.get_base_url()
    cache_key = f"comfyui_status:{base_url}"
    
    # 检查缓存
    cached = cache_service.get(cache_key)
    if cached is not None:
        return ComfyUIStatus(**cached)
    
    connected = await comfyui_service.check_connection()
    
    if not connected:
        result = {"connected": False}
        cache_service.set(cache_key, result, ttl=STATUS_CACHE_TTL)
        return ComfyUIStatus(connected=False)
    
    system_stats = await comfyui_service.get_system_stats()
    queue = await comfyui_service.get_queue()
    
    queue_remaining = len(queue.get("queue_running", [])) + len(queue.get("queue_pending", []))
    
    result = {
        "connected": True,
        "queue_remaining": queue_remaining,
        "system_stats": system_stats,
    }
    cache_service.set(cache_key, result, ttl=STATUS_CACHE_TTL)
    
    return ComfyUIStatus(
        connected=True,
        queue_remaining=queue_remaining,
        system_stats=system_stats,
    )


@router.get("/queue")
async def get_queue():
    """获取队列状态"""
    return await comfyui_service.get_queue()


@router.post("/queue/clear")
async def clear_queue():
    """清空队列"""
    success = await comfyui_service.clear_queue()
    if not success:
        raise HTTPException(status_code=500, detail="清空队列失败")
    return {"message": "队列已清空"}


@router.post("/interrupt")
async def interrupt():
    """中断当前执行"""
    success = await comfyui_service.interrupt()
    if not success:
        raise HTTPException(status_code=500, detail="中断失败")
    return {"message": "已中断"}


@router.get("/object_info")
async def get_object_info():
    """获取节点信息"""
    return await comfyui_service.get_object_info()


@router.get("/models")
async def get_models():
    """获取可用的模型列表"""
    return await comfyui_service.get_models()


@router.get("/unets")
async def get_unets():
    """获取可用的 UNET 模型列表"""
    return await comfyui_service.get_unets()


@router.get("/vaes")
async def get_vaes():
    """获取可用的 VAE 列表"""
    return await comfyui_service.get_vaes()


@router.get("/loras")
async def get_loras():
    """获取可用的 LoRA 列表"""
    return await comfyui_service.get_loras()


@router.get("/samplers")
async def get_samplers():
    """获取可用的采样器列表"""
    return await comfyui_service.get_samplers()


@router.get("/schedulers")
async def get_schedulers():
    """获取可用的调度器列表"""
    return await comfyui_service.get_schedulers()


@router.get("/last-prompt")
async def get_last_prompt():
    """获取最后一次执行的工作流"""
    return await comfyui_service.get_last_prompt()


@router.get("/history")
async def get_history(prompt_id: str = ""):
    """获取执行历史"""
    return await comfyui_service.get_history(prompt_id)


@router.get("/history/formatted")
async def get_formatted_history(
    limit: int = Query(default=50, le=200),
):
    """获取格式化的执行历史，包含提示词"""
    from ..services.prompt_extractor import prompt_extractor
    
    history = await comfyui_service.get_history()
    
    result = []
    # 按执行完成时间排序，最新的在前面
    sorted_history = sorted(
        history.items(),
        key=lambda x: x[1].get("prompt", [0])[0] if isinstance(x[1].get("prompt"), list) and len(x[1].get("prompt", [])) > 0 else 0,
        reverse=True
    )
    
    for prompt_id, prompt_data in sorted_history[:limit]:
        status_info = prompt_data.get("status", {})
        outputs = prompt_data.get("outputs", {})
        
        # 提取提示词
        positive = ""
        negative = ""
        
        prompt_info = prompt_data.get("prompt", [])
        timestamp = None
        if isinstance(prompt_info, list) and len(prompt_info) >= 3:
            # prompt[0] 是时间戳
            if len(prompt_info) > 0:
                timestamp = prompt_info[0]
            # prompt[2] 是 workflow 数据
            workflow_data = prompt_info[2]
            if isinstance(workflow_data, dict):
                extracted = prompt_extractor.extract_from_workflow(workflow_data)
                if extracted:
                    p = extracted[0]
                    positive = p.positive
                    negative = p.negative
        
        # 统计图片数量
        image_count = 0
        for node_id, node_output in outputs.items():
            if "images" in node_output:
                image_count += len(node_output["images"])
        
        result.append({
            "prompt_id": prompt_id,
            "status": "completed" if status_info.get("completed") else "running",
            "timestamp": timestamp,
            "positive": positive,
            "negative": negative,
            "image_count": image_count,
        })
    
    return result


@router.post("/execute/{workflow_id}", response_model=ExecutionResponse)
async def execute_workflow(
    workflow_id: int,
    request: ExecuteWorkflowRequest | None = None,
    db: AsyncSession = Depends(get_db)
):
    """执行工作流"""
    result = await db.execute(
        select(Workflow).where(Workflow.id == workflow_id)
    )
    workflow = result.scalar_one_or_none()
    if not workflow:
        raise HTTPException(status_code=404, detail="工作流不存在")
    
    # 使用请求中的工作流数据或保存的数据
    workflow_data = request.workflow_data if request and request.workflow_data else workflow.workflow_data
    
    # 提交到 ComfyUI
    response = await comfyui_service.queue_prompt(workflow_data)
    
    if "error" in response:
        raise HTTPException(status_code=500, detail=response["error"])
    
    prompt_id = response.get("prompt_id", "")
    
    # 记录执行历史
    execution = ExecutionHistory(
        workflow_id=workflow_id,
        prompt_id=prompt_id,
        status="pending",
    )
    db.add(execution)
    await db.commit()
    await db.refresh(execution)
    
    return execution


@router.post("/execute/direct")
async def execute_direct(workflow_data: dict):
    """直接执行工作流（不保存）"""
    response = await comfyui_service.queue_prompt(workflow_data)
    
    if "error" in response:
        raise HTTPException(status_code=500, detail=response["error"])
    
    return response


@router.get("/execution/{execution_id}", response_model=ExecutionResponse)
async def get_execution(
    execution_id: int,
    db: AsyncSession = Depends(get_db)
):
    """获取执行状态"""
    result = await db.execute(
        select(ExecutionHistory).where(ExecutionHistory.id == execution_id)
    )
    execution = result.scalar_one_or_none()
    if not execution:
        raise HTTPException(status_code=404, detail="执行记录不存在")
    
    # 从 ComfyUI 获取最新状态
    if execution.prompt_id and execution.status not in ["completed", "failed"]:
        history = await comfyui_service.get_history(execution.prompt_id)
        if execution.prompt_id in history:
            prompt_history = history[execution.prompt_id]
            if "outputs" in prompt_history:
                execution.status = "completed"
                execution.result = prompt_history["outputs"]
                execution.completed_at = datetime.now(timezone.utc)
                await db.commit()
    
    return execution


@router.get("/image/{filename}")
async def get_image(
    filename: str,
    subfolder: str = "",
    folder_type: str = "output"
):
    """获取生成的图片"""
    image_data = await comfyui_service.get_image(filename, subfolder, folder_type)
    if not image_data:
        raise HTTPException(status_code=404, detail="图片不存在")
    
    # 根据文件扩展名确定 MIME 类型
    if filename.lower().endswith(".png"):
        media_type = "image/png"
    elif filename.lower().endswith((".jpg", ".jpeg")):
        media_type = "image/jpeg"
    elif filename.lower().endswith(".webp"):
        media_type = "image/webp"
    else:
        media_type = "application/octet-stream"
    
    return Response(content=image_data, media_type=media_type)


@router.get("/thumbnail/{filename}")
async def get_thumbnail(
    filename: str,
    subfolder: str = "",
    folder_type: str = "output",
    size: int = Query(default=256, ge=64, le=512),
):
    """获取图片缩略图（带缓存）"""
    # 生成缓存文件名（使用 .cache 扩展名，Windows 不会预览）
    cache_key = hashlib.md5(f"{filename}:{subfolder}:{folder_type}:{size}".encode()).hexdigest()
    cache_path = THUMBNAIL_CACHE_DIR / f"{cache_key}.cache"
    
    # 检查缓存
    if cache_path.exists():
        # 解密缓存数据
        encrypted_data = cache_path.read_bytes()
        thumbnail_data = xor_encrypt(encrypted_data)
        return Response(
            content=thumbnail_data,
            media_type="image/webp",
            headers={"Cache-Control": "public, max-age=86400"}  # 缓存1天
        )
    
    # 获取原图
    image_data = await comfyui_service.get_image(filename, subfolder, folder_type)
    if not image_data:
        raise HTTPException(status_code=404, detail="图片不存在")
    
    try:
        thumbnail_data = _generate_thumbnail(image_data, size)
        
        # 加密后保存到缓存
        encrypted_data = xor_encrypt(thumbnail_data)
        cache_path.write_bytes(encrypted_data)
        
        return Response(
            content=thumbnail_data,
            media_type="image/webp",
            headers={"Cache-Control": "public, max-age=86400"}
        )
    except Exception as e:
        # 如果生成缩略图失败，返回原图
        raise HTTPException(status_code=500, detail=f"生成缩略图失败: {str(e)}")


@router.get("/executions", response_model=list[ExecutionListResponse])
async def list_executions(
    limit: int = Query(default=50, le=200),
    offset: int = Query(default=0, ge=0),
    status: str | None = None,
    db: AsyncSession = Depends(get_db)
):
    """获取执行历史列表（优化：批量查询工作流名称，避免 N+1）"""
    query = select(ExecutionHistory).order_by(desc(ExecutionHistory.started_at))
    
    if status:
        query = query.where(ExecutionHistory.status == status)
    
    query = query.offset(offset).limit(limit)
    result = await db.execute(query)
    executions = result.scalars().all()
    
    # 批量获取所有相关的工作流 ID
    workflow_ids = {exec.workflow_id for exec in executions if exec.workflow_id}
    
    # 一次性查询所有工作流名称
    workflow_names: dict[int, str] = {}
    if workflow_ids:
        wf_result = await db.execute(
            select(Workflow.id, Workflow.name).where(Workflow.id.in_(workflow_ids))
        )
        workflow_names = {row[0]: row[1] for row in wf_result.all()}
    
    # 构建响应
    response = [
        ExecutionListResponse(
            id=exec.id,
            workflow_id=exec.workflow_id,
            prompt_id=exec.prompt_id,
            status=exec.status,
            started_at=exec.started_at,
            completed_at=exec.completed_at,
            workflow_name=workflow_names.get(exec.workflow_id) if exec.workflow_id else None,
        )
        for exec in executions
    ]
    
    return response


@router.get("/executions/{execution_id}/images", response_model=list[ImageInfo])
async def get_execution_images(
    execution_id: int,
    db: AsyncSession = Depends(get_db)
):
    """获取执行结果中的图片列表"""
    result = await db.execute(
        select(ExecutionHistory).where(ExecutionHistory.id == execution_id)
    )
    execution = result.scalar_one_or_none()
    if not execution:
        raise HTTPException(status_code=404, detail="执行记录不存在")
    
    images = []
    
    # 如果本地没有结果，尝试从 ComfyUI 获取
    if execution.prompt_id:
        history = await comfyui_service.get_history(execution.prompt_id)
        if execution.prompt_id in history:
            prompt_history = history[execution.prompt_id]
            outputs = prompt_history.get("outputs", {})
            
            # 遍历所有输出节点
            for node_id, node_output in outputs.items():
                if "images" in node_output:
                    for img in node_output["images"]:
                        images.append(ImageInfo(
                            filename=img.get("filename", ""),
                            subfolder=img.get("subfolder", ""),
                            type=img.get("type", "output"),
                        ))
            
            # 更新本地记录
            if outputs and execution.status != "completed":
                execution.status = "completed"
                execution.result = outputs
                execution.completed_at = datetime.now(timezone.utc)
                await db.commit()
    
    return images


@router.get("/queue/detailed")
async def get_detailed_queue(db: AsyncSession = Depends(get_db)):
    """获取详细的队列信息，包含工作流名称（优化：批量查询避免 N+1）"""
    queue = await comfyui_service.get_queue()
    
    # 收集所有 prompt_id
    all_prompt_ids = set()
    for item in queue.get("queue_running", []):
        if len(item) >= 2 and item[1]:
            all_prompt_ids.add(item[1])
    for item in queue.get("queue_pending", []):
        if len(item) >= 2 and item[1]:
            all_prompt_ids.add(item[1])
    
    # 批量查询执行记录
    exec_map: dict[str, tuple[int | None, int | None]] = {}  # prompt_id -> (exec_id, workflow_id)
    if all_prompt_ids:
        exec_result = await db.execute(
            select(ExecutionHistory.prompt_id, ExecutionHistory.id, ExecutionHistory.workflow_id)
            .where(ExecutionHistory.prompt_id.in_(all_prompt_ids))
        )
        for row in exec_result.all():
            exec_map[row[0]] = (row[1], row[2])
    
    # 批量查询工作流名称
    workflow_ids = {wf_id for _, wf_id in exec_map.values() if wf_id}
    workflow_names: dict[int, str] = {}
    if workflow_ids:
        wf_result = await db.execute(
            select(Workflow.id, Workflow.name).where(Workflow.id.in_(workflow_ids))
        )
        workflow_names = {row[0]: row[1] for row in wf_result.all()}
    
    # 构建响应
    running = []
    for item in queue.get("queue_running", []):
        if len(item) >= 2:
            prompt_id = item[1] if len(item) > 1 else ""
            exec_info = exec_map.get(prompt_id, (None, None))
            workflow_id = exec_info[1]
            running.append({
                "prompt_id": prompt_id,
                "workflow_id": workflow_id,
                "workflow_name": workflow_names.get(workflow_id) if workflow_id else None,
                "number": item[0] if len(item) > 0 else 0,
            })
    
    pending = []
    for item in queue.get("queue_pending", []):
        if len(item) >= 2:
            prompt_id = item[1] if len(item) > 1 else ""
            exec_info = exec_map.get(prompt_id, (None, None))
            workflow_id = exec_info[1]
            pending.append({
                "prompt_id": prompt_id,
                "workflow_id": workflow_id,
                "workflow_name": workflow_names.get(workflow_id) if workflow_id else None,
                "number": item[0] if len(item) > 0 else 0,
            })
    
    return {
        "running": running,
        "pending": pending,
    }


class ImageWithPrompt(ImageInfo):
    prompt_id: str = ""
    positive: str = ""
    negative: str = ""
    model: str = ""
    sampler: str = ""
    steps: int = 0
    cfg: float = 0
    seed: int = 0
    width: int = 0
    height: int = 0


@router.get("/history/images", response_model=list[ImageInfo])
async def get_recent_images(
    limit: int = Query(default=20, le=100),
):
    """获取最近生成的图片"""
    history = await comfyui_service.get_history()
    
    images = []
    # 按执行完成时间排序，最新的在前面
    # ComfyUI history 中 prompt 数组的第一个元素是队列号，数字越大越新
    sorted_history = sorted(
        history.items(),
        key=lambda x: x[1].get("prompt", [0])[0] if isinstance(x[1].get("prompt"), list) and len(x[1].get("prompt", [])) > 0 else 0,
        reverse=True
    )
    
    for prompt_id, prompt_data in sorted_history:
        outputs = prompt_data.get("outputs", {})
        for node_id, node_output in outputs.items():
            if "images" in node_output:
                for img in node_output["images"]:
                    images.append(ImageInfo(
                        filename=img.get("filename", ""),
                        subfolder=img.get("subfolder", ""),
                        type=img.get("type", "output"),
                    ))
                    if len(images) >= limit:
                        return images
    
    return images


@router.get("/history/images-with-prompt", response_model=list[ImageWithPrompt])
async def get_recent_images_with_prompt(
    limit: int = Query(default=50, le=200),
):
    """获取最近生成的图片及其对应的 prompt"""
    from ..services.prompt_extractor import prompt_extractor
    
    history = await comfyui_service.get_history()
    
    images = []
    # 按执行完成时间排序，最新的在前面
    sorted_history = sorted(
        history.items(),
        key=lambda x: x[1].get("prompt", [0])[0] if isinstance(x[1].get("prompt"), list) and len(x[1].get("prompt", [])) > 0 else 0,
        reverse=True
    )
    
    for prompt_id, prompt_data in sorted_history:
        outputs = prompt_data.get("outputs", {})
        
        positive = ""
        negative = ""
        model = ""
        sampler = ""
        steps = 0
        cfg = 0.0
        seed = 0
        width = 0
        height = 0
        
        prompt_info = prompt_data.get("prompt", [])
        if isinstance(prompt_info, list) and len(prompt_info) >= 3:
            workflow_data = prompt_info[2]
            if isinstance(workflow_data, dict):
                extracted = prompt_extractor.extract_from_workflow(workflow_data)
                if extracted:
                    p = extracted[0]
                    positive = p.positive
                    negative = p.negative
                    model = p.model
                    sampler = p.sampler
                    steps = p.steps
                    cfg = p.cfg
                    seed = p.seed
                    width = p.width
                    height = p.height
        
        for node_id, node_output in outputs.items():
            if "images" in node_output:
                for img in node_output["images"]:
                    images.append(ImageWithPrompt(
                        filename=img.get("filename", ""),
                        subfolder=img.get("subfolder", ""),
                        type=img.get("type", "output"),
                        prompt_id=prompt_id,
                        positive=positive,
                        negative=negative,
                        model=model,
                        sampler=sampler,
                        steps=steps,
                        cfg=cfg,
                        seed=seed,
                        width=width,
                        height=height,
                    ))
                    if len(images) >= limit:
                        return images
    
    return images


# ==================== 图片存储 API ====================

@router.post("/storage/migrate")
async def migrate_images():
    """从 ComfyUI 迁移所有图片到本地存储"""
    result = await image_storage_service.migrate_from_comfyui(delete_original=False)
    return result


@router.get("/storage/stats")
async def get_storage_stats():
    """获取存储统计信息"""
    return storage_service.get_stats()


@router.get("/storage/images")
async def list_stored_images(
    limit: int = Query(default=100, le=2000),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    """获取已存储的图片列表"""
    result = await db.execute(
        select(StoredImage)
        .where(StoredImage.is_deleted.is_(False))
        .order_by(desc(StoredImage.created_at))
        .offset(offset)
        .limit(limit)
    )
    images = result.scalars().all()
    
    return [
        {
            "id": img.id,
            "filename": img.filename,
            "width": img.width,
            "height": img.height,
            "size": img.size,
            "positive": img.positive,
            "negative": img.negative,
            "seed": img.seed,
            "steps": img.steps,
            "cfg": img.cfg,
            "sampler": img.sampler,
            "model": img.model,
            "created_at": img.created_at.isoformat() if img.created_at else None,
        }
        for img in images
    ]


@router.get("/storage/image/{image_id}")
async def get_stored_image(image_id: int):
    """获取存储的图片"""
    result = await image_storage_service.get_image(image_id)
    if not result:
        raise HTTPException(status_code=404, detail="图片不存在")
    
    data, mimetype = result
    return Response(content=data, media_type=mimetype)


@router.get("/storage/image/by-name/{filename}")
async def get_stored_image_by_name(filename: str):
    """根据文件名获取存储的图片"""
    result = await image_storage_service.get_image_by_filename(filename)
    if not result:
        raise HTTPException(status_code=404, detail="图片不存在")
    
    data, mimetype = result
    return Response(content=data, media_type=mimetype)


@router.get("/storage/thumbnail/{image_id}")
async def get_stored_image_thumbnail(
    image_id: int,
    size: int = Query(default=256, ge=64, le=512),
):
    """获取存储图片的缩略图"""
    # 生成缓存文件名
    cache_key = hashlib.md5(f"stored:{image_id}:{size}".encode()).hexdigest()
    cache_path = THUMBNAIL_CACHE_DIR / f"{cache_key}.cache"
    
    # 检查缓存
    if cache_path.exists():
        encrypted_data = cache_path.read_bytes()
        thumbnail_data = xor_encrypt(encrypted_data)
        return Response(
            content=thumbnail_data,
            media_type="image/webp",
            headers={"Cache-Control": "public, max-age=86400"}
        )
    
    # 获取原图
    result = await image_storage_service.get_image(image_id)
    if not result:
        raise HTTPException(status_code=404, detail="图片不存在")
    
    image_data, _ = result
    
    try:
        thumbnail_data = _generate_thumbnail(image_data, size)
        
        # 加密后保存到缓存
        encrypted_data = xor_encrypt(thumbnail_data)
        cache_path.write_bytes(encrypted_data)
        
        return Response(
            content=thumbnail_data,
            media_type="image/webp",
            headers={"Cache-Control": "public, max-age=86400"}
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"生成缩略图失败: {str(e)}")
