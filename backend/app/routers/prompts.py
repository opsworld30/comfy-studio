"""Prompt 管理路由"""
import random
from datetime import datetime
from typing import Any
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

from ..database import get_db
from ..models import SavedPrompt, Workflow, ExecutionHistory, StoredImage, UserSettings
from ..services.prompt_extractor import prompt_extractor, ExtractedPrompt
from ..services.comfyui import comfyui_service
from ..services.image_storage import image_storage_service
from ..services.prompt_crawler import prompt_crawler
from ..services.ai import ai_service

router = APIRouter(prefix="/prompts", tags=["prompts"])


# Pydantic 模型
class PromptCreate(BaseModel):
    name: str
    positive: str
    negative: str = ""
    category: str = "自定义"
    tags: list[str] = []


class PromptUpdate(BaseModel):
    name: str | None = None
    positive: str | None = None
    negative: str | None = None
    category: str | None = None
    tags: list[str] | None = None
    is_favorite: bool | None = None


class PromptResponse(BaseModel):
    id: int
    name: str
    positive: str
    negative: str
    category: str
    tags: list[str]
    source: str
    source_workflow_id: int | None
    source_image: str  # 图片 URL
    use_count: int
    is_favorite: bool
    # 生成参数
    model: str = ""
    sampler: str = ""
    steps: int = 0
    cfg: float = 0
    seed: int = 0
    width: int = 0
    height: int = 0
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ExtractedPromptResponse(BaseModel):
    positive: str
    negative: str
    source_node: str = ""
    model: str = ""
    sampler: str = ""
    steps: int = 0
    cfg: float = 0
    seed: int = 0
    width: int = 0
    height: int = 0
    suggested_name: str = ""
    suggested_category: str = ""


# ========== CRUD 接口 ==========

@router.get("", response_model=list[PromptResponse])
async def list_prompts(
    category: str | None = None,
    search: str | None = None,
    favorite_only: bool = False,
    skip: int = 0,
    limit: int = 50,
    db: AsyncSession = Depends(get_db)
):
    """获取 Prompt 列表"""
    query = select(SavedPrompt)
    
    if category:
        query = query.where(SavedPrompt.category == category)
    
    if favorite_only:
        query = query.where(SavedPrompt.is_favorite == True)
    
    if search:
        search_pattern = f"%{search}%"
        query = query.where(
            or_(
                SavedPrompt.name.ilike(search_pattern),
                SavedPrompt.positive.ilike(search_pattern),
                SavedPrompt.negative.ilike(search_pattern),
            )
        )
    
    query = query.order_by(SavedPrompt.created_at.desc())
    query = query.offset(skip).limit(limit)
    
    result = await db.execute(query)
    return result.scalars().all()


@router.get("/categories")
async def get_categories(db: AsyncSession = Depends(get_db)) -> list[dict]:
    """获取所有分类及数量"""
    query = select(
        SavedPrompt.category,
        func.count(SavedPrompt.id).label("count")
    ).group_by(SavedPrompt.category)
    
    result = await db.execute(query)
    return [{"category": row[0], "count": row[1]} for row in result.all()]


@router.get("/{prompt_id}", response_model=PromptResponse)
async def get_prompt(prompt_id: int, db: AsyncSession = Depends(get_db)):
    """获取单个 Prompt"""
    result = await db.execute(
        select(SavedPrompt).where(SavedPrompt.id == prompt_id)
    )
    prompt = result.scalar_one_or_none()
    if not prompt:
        raise HTTPException(status_code=404, detail="Prompt 不存在")
    return prompt


@router.post("", response_model=PromptResponse)
async def create_prompt(data: PromptCreate, db: AsyncSession = Depends(get_db)):
    """创建新 Prompt"""
    prompt = SavedPrompt(
        name=data.name,
        positive=data.positive,
        negative=data.negative,
        category=data.category,
        tags=data.tags,
        source="manual",
    )
    db.add(prompt)
    await db.commit()
    await db.refresh(prompt)
    return prompt


@router.put("/{prompt_id}", response_model=PromptResponse)
async def update_prompt(
    prompt_id: int,
    data: PromptUpdate,
    db: AsyncSession = Depends(get_db)
):
    """更新 Prompt"""
    result = await db.execute(
        select(SavedPrompt).where(SavedPrompt.id == prompt_id)
    )
    prompt = result.scalar_one_or_none()
    if not prompt:
        raise HTTPException(status_code=404, detail="Prompt 不存在")
    
    if data.name is not None:
        prompt.name = data.name
    if data.positive is not None:
        prompt.positive = data.positive
    if data.negative is not None:
        prompt.negative = data.negative
    if data.category is not None:
        prompt.category = data.category
    if data.tags is not None:
        prompt.tags = data.tags
    if data.is_favorite is not None:
        prompt.is_favorite = data.is_favorite
    
    await db.commit()
    await db.refresh(prompt)
    return prompt


@router.delete("/{prompt_id}")
async def delete_prompt(prompt_id: int, db: AsyncSession = Depends(get_db)):
    """删除 Prompt"""
    result = await db.execute(
        select(SavedPrompt).where(SavedPrompt.id == prompt_id)
    )
    prompt = result.scalar_one_or_none()
    if not prompt:
        raise HTTPException(status_code=404, detail="Prompt 不存在")
    
    await db.delete(prompt)
    await db.commit()
    return {"message": "删除成功"}


@router.post("/{prompt_id}/use")
async def record_use(prompt_id: int, db: AsyncSession = Depends(get_db)):
    """记录使用次数"""
    result = await db.execute(
        select(SavedPrompt).where(SavedPrompt.id == prompt_id)
    )
    prompt = result.scalar_one_or_none()
    if not prompt:
        raise HTTPException(status_code=404, detail="Prompt 不存在")
    
    prompt.use_count += 1
    await db.commit()
    return {"use_count": prompt.use_count}


@router.post("/{prompt_id}/favorite")
async def toggle_favorite(prompt_id: int, db: AsyncSession = Depends(get_db)):
    """切换收藏状态"""
    result = await db.execute(
        select(SavedPrompt).where(SavedPrompt.id == prompt_id)
    )
    prompt = result.scalar_one_or_none()
    if not prompt:
        raise HTTPException(status_code=404, detail="Prompt 不存在")
    
    prompt.is_favorite = not prompt.is_favorite
    await db.commit()
    return {"is_favorite": prompt.is_favorite}


# ========== AI 生成接口 ==========

class GeneratePromptRequest(BaseModel):
    description: str
    style: str = ""


class GeneratePromptResponse(BaseModel):
    name: str
    category: str
    positive: str
    negative: str


DEFAULT_AI_SETTINGS = {
    "api_key": "",
    "api_url": "https://api.siliconflow.cn/v1",
    "model": "Qwen/Qwen2.5-7B-Instruct",
    "enabled": False,
}


@router.post("/generate", response_model=GeneratePromptResponse)
async def generate_prompt(
    request: GeneratePromptRequest,
    db: AsyncSession = Depends(get_db)
):
    """使用 AI 生成提示词"""
    # 获取 AI 设置
    result = await db.execute(
        select(UserSettings).where(UserSettings.key == "ai_settings")
    )
    settings = result.scalar_one_or_none()
    
    if not settings or not settings.value.get("api_key"):
        raise HTTPException(
            status_code=400, 
            detail="未配置 AI API Key，请在设置页面配置 AI 服务"
        )
    
    if not settings.value.get("enabled", False):
        raise HTTPException(
            status_code=400,
            detail="AI 功能未启用，请在设置页面启用"
        )
    
    ai_config = settings.value
    
    try:
        # 调用 AI 服务生成提示词
        result = await ai_service.generate_prompt(
            description=request.description,
            api_key=ai_config["api_key"],
            api_url=ai_config.get("api_url", DEFAULT_AI_SETTINGS["api_url"]),
            model=ai_config.get("model", DEFAULT_AI_SETTINGS["model"]),
            style=request.style,
        )
        
        return GeneratePromptResponse(
            name=result.get("name", "未命名"),
            category=result.get("category", "其他"),
            positive=result.get("positive", ""),
            negative=result.get("negative", ""),
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"AI 服务错误: {str(e)}")


class RandomGenerateRequest(BaseModel):
    count: int = 5
    style: str = ""
    theme: str = ""


@router.post("/generate/random", response_model=list[GeneratePromptResponse])
async def generate_random_prompts(
    request: RandomGenerateRequest,
    db: AsyncSession = Depends(get_db)
):
    """随机生成多组提示词"""
    # 获取 AI 设置
    result = await db.execute(
        select(UserSettings).where(UserSettings.key == "ai_settings")
    )
    settings = result.scalar_one_or_none()
    
    if not settings or not settings.value.get("api_key"):
        raise HTTPException(
            status_code=400, 
            detail="未配置 AI API Key，请在设置页面配置 AI 服务"
        )
    
    if not settings.value.get("enabled", False):
        raise HTTPException(
            status_code=400,
            detail="AI 功能未启用，请在设置页面启用"
        )
    
    ai_config = settings.value
    
    # 预设的主题和风格
    themes = [
        "美丽的风景", "可爱的动物", "未来科技城市", "奇幻森林", "海底世界",
        "星空银河", "古典建筑", "赛博朋克", "蒸汽朋克", "日式动漫风格",
        "油画风格肖像", "水彩花卉", "抽象艺术", "极简主义", "复古海报",
    ]
    styles = [
        "写实摄影", "动漫风格", "油画风格", "水彩画", "3D渲染",
        "像素艺术", "插画风格", "概念艺术", "超现实主义", "印象派",
    ]
    
    results = []
    count = min(request.count, 10)  # 最多10个
    
    for i in range(count):
        # 随机选择主题和风格
        theme = request.theme or random.choice(themes)
        style = request.style or random.choice(styles)
        description = f"{theme}，{style}风格"
        
        try:
            result = await ai_service.generate_prompt(
                description=description,
                api_key=ai_config["api_key"],
                api_url=ai_config.get("api_url", DEFAULT_AI_SETTINGS["api_url"]),
                model=ai_config.get("model", DEFAULT_AI_SETTINGS["model"]),
                style=style,
            )
            
            results.append(GeneratePromptResponse(
                name=result.get("name", f"随机生成_{i+1}"),
                category=result.get("category", "AI生成"),
                positive=result.get("positive", ""),
                negative=result.get("negative", ""),
            ))
        except Exception:
            # 单个失败不影响其他
            continue
    
    if not results:
        raise HTTPException(status_code=500, detail="生成失败，请稍后重试")
    
    return results


# ========== 提取接口 ==========

@router.post("/extract/workflow/{workflow_id}")
async def extract_from_workflow(
    workflow_id: int,
    db: AsyncSession = Depends(get_db)
) -> list[ExtractedPromptResponse]:
    """从工作流中提取 Prompt"""
    result = await db.execute(
        select(Workflow).where(Workflow.id == workflow_id)
    )
    workflow = result.scalar_one_or_none()
    if not workflow:
        raise HTTPException(status_code=404, detail="工作流不存在")
    
    extracted = prompt_extractor.extract_from_workflow(workflow.workflow_data)
    
    return [
        ExtractedPromptResponse(
            positive=p.positive,
            negative=p.negative,
            source_node=p.source_node,
            model=p.model,
            sampler=p.sampler,
            steps=p.steps,
            cfg=p.cfg,
            seed=p.seed,
            width=p.width,
            height=p.height,
            suggested_name=prompt_extractor.generate_name(p),
            suggested_category=prompt_extractor.categorize_prompt(p),
        )
        for p in extracted
    ]


@router.post("/extract/history")
async def extract_from_history(
    limit: int = Query(default=10, le=100)
) -> list[ExtractedPromptResponse]:
    """从 ComfyUI 历史记录中提取 Prompt"""
    history = await comfyui_service.get_history()
    
    if not history:
        return []
    
    # 只取最近的记录
    recent_history = dict(list(history.items())[:limit])
    extracted = prompt_extractor.extract_from_history(recent_history)
    
    # 去重
    unique = prompt_extractor.deduplicate_prompts(extracted)
    
    return [
        ExtractedPromptResponse(
            positive=p.positive,
            negative=p.negative,
            source_node=p.source_node,
            model=p.model,
            sampler=p.sampler,
            steps=p.steps,
            cfg=p.cfg,
            seed=p.seed,
            width=p.width,
            height=p.height,
            suggested_name=prompt_extractor.generate_name(p),
            suggested_category=prompt_extractor.categorize_prompt(p),
        )
        for p in unique
    ]


@router.post("/extract/workflow-data")
async def extract_from_workflow_data(
    workflow_data: dict[str, Any]
) -> list[ExtractedPromptResponse]:
    """从工作流 JSON 数据中提取 Prompt"""
    extracted = prompt_extractor.extract_from_workflow(workflow_data)
    
    return [
        ExtractedPromptResponse(
            positive=p.positive,
            negative=p.negative,
            source_node=p.source_node,
            model=p.model,
            sampler=p.sampler,
            steps=p.steps,
            cfg=p.cfg,
            seed=p.seed,
            width=p.width,
            height=p.height,
            suggested_name=prompt_extractor.generate_name(p),
            suggested_category=prompt_extractor.categorize_prompt(p),
        )
        for p in extracted
    ]


@router.post("/save-extracted")
async def save_extracted_prompt(
    data: ExtractedPromptResponse,
    name: str | None = None,
    category: str | None = None,
    source_workflow_id: int | None = None,
    db: AsyncSession = Depends(get_db)
) -> PromptResponse:
    """保存提取的 Prompt 到数据库"""
    prompt = SavedPrompt(
        name=name or data.suggested_name or "未命名",
        positive=data.positive,
        negative=data.negative,
        category=category or data.suggested_category or "自定义",
        source="extracted",
        source_workflow_id=source_workflow_id,
    )
    db.add(prompt)
    await db.commit()
    await db.refresh(prompt)
    return prompt


@router.post("/batch-save")
async def batch_save_prompts(
    prompts: list[PromptCreate],
    db: AsyncSession = Depends(get_db)
) -> dict:
    """批量保存 Prompt"""
    saved_count = 0
    
    for data in prompts:
        prompt = SavedPrompt(
            name=data.name,
            positive=data.positive,
            negative=data.negative,
            category=data.category,
            tags=data.tags,
            source="imported",
        )
        db.add(prompt)
        saved_count += 1
    
    await db.commit()
    return {"saved_count": saved_count}


class RunPromptRequest(BaseModel):
    prompt_id: int | None = None
    positive: str | None = None
    negative: str | None = None
    workflow_data: dict[str, Any] | None = None


@router.post("/run")
async def run_prompt_with_workflow(
    request: RunPromptRequest,
    db: AsyncSession = Depends(get_db)
):
    """使用提示词运行工作流"""
    positive = request.positive or ""
    negative = request.negative or ""
    
    if request.prompt_id:
        result = await db.execute(
            select(SavedPrompt).where(SavedPrompt.id == request.prompt_id)
        )
        prompt = result.scalar_one_or_none()
        if prompt:
            positive = prompt.positive
            negative = prompt.negative
            prompt.use_count += 1
            await db.commit()
    
    if not request.workflow_data:
        raise HTTPException(status_code=400, detail="需要提供工作流数据")
    
    workflow_data = request.workflow_data.copy()
    replaced_nodes = []
    
    for node_id in list(workflow_data.keys()):
        node = workflow_data[node_id]
        class_type = node.get("class_type", "")
        
        if class_type in ("CLIPTextEncode", "CLIPTextEncodeSDXL"):
            inputs = node.get("inputs", {})
            if "text" in inputs:
                current_text = str(inputs.get("text", "")).lower()
                if any(kw in current_text for kw in ["negative", "bad", "worst", "ugly", "low quality"]):
                    if negative:
                        node["inputs"]["text"] = negative
                        replaced_nodes.append(f"节点{node_id}(负向)")
                else:
                    if positive:
                        node["inputs"]["text"] = positive
                        replaced_nodes.append(f"节点{node_id}(正向)")
        
        if class_type in ("KSampler", "KSamplerAdvanced", "SamplerCustom"):
            inputs = node.get("inputs", {})
            if "seed" in inputs:
                new_seed = random.randint(0, 2147483647)
                node["inputs"]["seed"] = new_seed
                replaced_nodes.append(f"节点{node_id}(种子={new_seed})")
        
        if class_type == "RandomNoise":
            inputs = node.get("inputs", {})
            if "noise_seed" in inputs:
                new_seed = random.randint(0, 999999999999999)
                node["inputs"]["noise_seed"] = new_seed
                replaced_nodes.append(f"节点{node_id}(噪声种子={new_seed})")
    
    try:
        response = await comfyui_service.queue_prompt(workflow_data)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"ComfyUI 连接失败: {str(e)}")
    
    if "error" in response:
        raise HTTPException(status_code=500, detail=f"ComfyUI 执行错误: {response['error']}")
    
    return {
        "prompt_id": response.get("prompt_id", ""),
        "message": "工作流已提交执行",
        "replaced_nodes": replaced_nodes,
    }


@router.post("/import-from-all-workflows")
async def import_from_all_workflows(
    db: AsyncSession = Depends(get_db)
) -> dict:
    """从所有工作流中批量提取并保存 Prompt"""
    result = await db.execute(select(Workflow))
    workflows = result.scalars().all()
    
    all_extracted = []
    
    for workflow in workflows:
        extracted = prompt_extractor.extract_from_workflow(workflow.workflow_data)
        for p in extracted:
            all_extracted.append({
                "prompt": p,
                "workflow_id": workflow.id,
            })
    
    # 去重
    seen = set()
    unique = []
    for item in all_extracted:
        p = item["prompt"]
        key = (p.positive.strip().lower(), p.negative.strip().lower())
        if key not in seen and p.positive.strip():
            seen.add(key)
            unique.append(item)
    
    # 保存
    saved_count = 0
    for item in unique:
        p = item["prompt"]
        prompt = SavedPrompt(
            name=prompt_extractor.generate_name(p),
            positive=p.positive,
            negative=p.negative,
            category=prompt_extractor.categorize_prompt(p),
            source="extracted",
            source_workflow_id=item["workflow_id"],
        )
        db.add(prompt)
        saved_count += 1
    
    await db.commit()
    
    return {
        "workflows_scanned": len(workflows),
        "prompts_extracted": len(all_extracted),
        "prompts_saved": saved_count,
    }


# ========== 图片关联接口 ==========

class StoredImageResponse(BaseModel):
    id: int
    filename: str
    width: int | None
    height: int | None
    positive: str
    negative: str
    seed: int | None
    steps: int | None
    cfg: float | None
    sampler: str
    model: str
    created_at: datetime
    
    class Config:
        from_attributes = True


@router.get("/{prompt_id}/images", response_model=list[StoredImageResponse])
async def get_prompt_images(
    prompt_id: int,
    limit: int = Query(default=50, le=200),
    db: AsyncSession = Depends(get_db)
):
    """获取 Prompt 关联的图片"""
    # 先检查 Prompt 是否存在
    result = await db.execute(
        select(SavedPrompt).where(SavedPrompt.id == prompt_id)
    )
    prompt = result.scalar_one_or_none()
    if not prompt:
        raise HTTPException(status_code=404, detail="Prompt 不存在")
    
    # 获取直接关联的图片
    images = await image_storage_service.get_images_by_prompt_id(prompt_id, limit)
    
    # 如果没有直接关联，尝试通过 positive 匹配
    if not images and prompt.positive:
        images = await image_storage_service.get_images_by_positive(prompt.positive, limit)
    
    return images


@router.post("/{prompt_id}/link-images")
async def link_images_to_prompt(
    prompt_id: int,
    db: AsyncSession = Depends(get_db)
):
    """将匹配的图片关联到 Prompt"""
    # 检查 Prompt 是否存在
    result = await db.execute(
        select(SavedPrompt).where(SavedPrompt.id == prompt_id)
    )
    prompt = result.scalar_one_or_none()
    if not prompt:
        raise HTTPException(status_code=404, detail="Prompt 不存在")
    
    if not prompt.positive or len(prompt.positive) < 20:
        return {"linked": 0, "message": "Prompt 内容太短，无法匹配"}
    
    # 查找匹配的图片
    search_text = prompt.positive[:50]
    images_result = await db.execute(
        select(StoredImage)
        .where(
            StoredImage.positive.contains(search_text),
            StoredImage.prompt_id.is_(None),
            StoredImage.is_deleted == False
        )
    )
    images = images_result.scalars().all()
    
    # 更新关联
    linked_count = 0
    for image in images:
        image.prompt_id = prompt_id
        linked_count += 1
    
    await db.commit()
    
    return {"linked": linked_count, "message": f"已关联 {linked_count} 张图片"}


@router.post("/migrate-images")
async def migrate_images_from_comfyui():
    """从 ComfyUI 迁移图片到本地存储"""
    # 从设置中获取是否删除原图的配置
    from ..models import UserSettings
    from ..database import async_session
    
    delete_original = True  # 默认删除
    try:
        async with async_session() as db:
            result = await db.execute(
                select(UserSettings).where(UserSettings.key == "comfyui_settings")
            )
            settings = result.scalar_one_or_none()
            if settings and settings.value:
                delete_original = settings.value.get("delete_original", True)
    except Exception:
        pass
    
    result = await image_storage_service.auto_migrate_new_images(delete_original=delete_original)
    return result


# ========== 在线提示词获取 ==========

class OnlinePromptResponse(BaseModel):
    """在线提示词响应"""
    source: str
    id: str
    positive: str
    negative: str
    model: str
    sampler: str
    steps: int
    cfg: float
    seed: int
    width: int
    height: int
    image_url: str
    page_url: str


@router.get("/online/sources")
async def get_online_sources():
    """获取支持的在线提示词网站列表"""
    return prompt_crawler.get_sources()


@router.get("/online/search")
async def search_online_prompts(
    query: str = Query(default="", description="搜索关键词"),
    source: str = Query(default="civitai", description="来源: civitai, openart, prompthero, arthub"),
    limit: int = Query(default=20, le=100, description="返回数量"),
    nsfw: bool = Query(default=False, description="是否包含 NSFW 内容 (仅 Civitai)"),
    cursor: str = Query(default="", description="分页游标 (仅 Civitai)"),
):
    """
    从在线提示词网站搜索提示词
    
    支持的来源:
    - civitai: Civitai.com - 最大的 AI 图片社区，支持分页
    - openart: OpenArt.ai - AI 艺术平台
    - prompthero: PromptHero.com - 提示词搜索引擎
    - arthub: Arthub.ai - AI 艺术社区
    """
    if source == "civitai":
        return await prompt_crawler.search_civitai(query, limit, nsfw=nsfw, cursor=cursor)
    else:
        return await prompt_crawler.search(query, source, limit, cursor)


@router.get("/online/trending")
async def get_trending_prompts(
    limit: int = Query(default=20, le=100, description="返回数量"),
    cursor: str = Query(default="", description="分页游标"),
):
    """获取热门提示词（从 Civitai），支持分页"""
    return await prompt_crawler.get_trending(limit, cursor)


@router.get("/online/random", response_model=list[OnlinePromptResponse])
async def get_random_prompts(
    category: str = Query(default="", description="分类/关键词"),
    source: str = Query(default="civitai", description="来源: civitai, lexica"),
    limit: int = Query(default=10, le=50, description="返回数量"),
):
    """
    获取随机提示词
    
    如果不指定 category，会随机选择热门分类
    """
    results = await prompt_crawler.get_random_prompts(source, category, limit)
    return results


@router.post("/online/save")
async def save_online_prompt(
    data: OnlinePromptResponse,
    name: str = Query(default="", description="自定义名称"),
    category: str = Query(default="在线收藏", description="分类"),
    db: AsyncSession = Depends(get_db),
):
    """保存在线提示词到本地，包含完整的生成参数"""
    prompt = SavedPrompt(
        name=name or f"{data.source}_{data.id[:8]}",
        positive=data.positive,
        negative=data.negative or "",
        category=category,
        source=f"online:{data.source}",
        source_image=data.image_url,
        # 保存生成参数
        model=data.model or "",
        sampler=data.sampler or "",
        steps=data.steps or 0,
        cfg=data.cfg or 0,
        seed=data.seed or 0,
        width=data.width or 0,
        height=data.height or 0,
    )
    db.add(prompt)
    await db.commit()
    await db.refresh(prompt)
    
    return {
        "id": prompt.id,
        "message": "保存成功",
    }
