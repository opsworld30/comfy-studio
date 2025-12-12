"""智能创作 API"""
import json
import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc

from ..database import get_db
from ..models import SmartCreateTask, UserSettings, AIPromptTemplate
from ..services.smart_create_executor import smart_create_executor
from ..services.prompt_processor import prompt_processor
from .ai_templates import SYSTEM_TEMPLATES

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/smart-create", tags=["smart-create"])


# ============ 数据模型 ============

class TemplateType:
    """创作模板类型"""
    NOVEL_STORYBOARD = "novel_storyboard"  # 小说分镜画面
    CHARACTER_MULTIVIEW = "character_multiview"  # 人物多视角设定
    VIDEO_STORYBOARD = "video_storyboard"  # 视频分镜脚本
    SCENE_MULTIVIEW = "scene_multiview"  # 场景多角度生成
    FASHION_DESIGN = "fashion_design"  # 服装设计展示
    COMIC_SERIES = "comic_series"  # 连续漫画生成


class AnalyzedPrompt(BaseModel):
    """AI分析生成的提示词"""
    index: int
    title: str  # 分镜标题/视角名称
    description: str  # 场景描述
    positive: str  # 正向提示词
    negative: str = ""  # 负向提示词


class CreateTaskRequest(BaseModel):
    """创建任务请求"""
    name: str
    template_type: str
    input_content: str
    style: str = "realistic"
    target_count: int = 0  # 0=AI自动分析
    image_size: str = "1024x768"
    workflow_id: Optional[int] = None
    config: dict = {}


class AnalyzeRequest(BaseModel):
    """AI分析请求"""
    template_type: str
    input_content: str
    style: str = "realistic"
    target_count: int = 0


class UpdatePromptsRequest(BaseModel):
    """更新提示词请求"""
    prompts: list[AnalyzedPrompt]


class ExecuteTaskRequest(BaseModel):
    """执行任务请求"""
    workflow_id: Optional[int] = None
    images_per_prompt: int = 1
    use_fixed_seed: bool = False
    save_to_gallery: bool = True


class TaskResponse(BaseModel):
    """任务响应"""
    id: int
    name: str
    template_type: str
    status: str
    input_content: str
    style: str
    target_count: int
    image_size: str
    workflow_id: Optional[int]
    config: dict
    analyzed_prompts: list
    total_count: int
    completed_count: int
    failed_count: int
    result_images: list
    error_message: str
    created_at: datetime
    started_at: Optional[datetime]
    completed_at: Optional[datetime]

    class Config:
        from_attributes = True


# ============ AI 分析提示词模板 ============

NOVEL_STORYBOARD_PROMPT = """你是一个专业的小说分镜分析师和AI绘画提示词专家。

## 任务
分析以下小说文本，将其拆分为 {target_count} 个关键分镜场景，并为每个场景生成高质量的AI绘画提示词。

## 小说内容
{content}

## 画面风格
{style}

## 分析要求
1. **场景拆分**：通读全文，识别故事的关键转折点、情感高潮、重要场景变化
2. **均匀分布**：确保分镜覆盖故事的开头、发展、高潮、结尾，跨度要大，避免集中在某一段
3. **画面提炼**：为每个分镜提取最具视觉冲击力的瞬间
4. **提示词生成**：生成详细的英文提示词，包含构图、光影、氛围

## 输出格式
请严格按以下 JSON 格式输出，不要有任何其他内容：
{{
  "prompts": [
    {{
      "index": 1,
      "title": "简短的分镜标题（4-8字中文）",
      "description": "场景描述（中文，50-100字，描述画面内容、人物动作、环境氛围）",
      "positive": "masterpiece, best quality, {style}, [详细的英文提示词，必须包含：1.场景环境描述 2.人物外貌服装 3.动作姿态 4.表情情绪 5.光线氛围 6.镜头角度 7.画面构图，总计80-150个英文单词]",
      "negative": "lowres, bad anatomy, bad hands, text, error, missing fingers, extra digit, fewer digits, cropped, worst quality, low quality, normal quality, jpeg artifacts, signature, watermark, username, blurry, deformed, ugly, duplicate, morbid, mutilated"
    }}
  ]
}}

## 重要规则
1. **分镜跨度要大**：每个分镜应代表故事的不同阶段，不要连续描述相邻的小动作
2. **数量严格遵守**：必须输出恰好 {target_count} 个分镜
3. **人物一致性**：如果同一人物出现在多个分镜，保持其外貌描述一致（发色、服装、体型等）
4. **提示词质量**：正向提示词要详细具体，包含足够的视觉细节，避免抽象描述
5. **英文提示词**：positive 必须是纯英文，用逗号分隔各个描述元素
6. **场景多样性**：尽量包含不同类型的场景（室内/室外、白天/夜晚、动态/静态）"""

CHARACTER_MULTIVIEW_PROMPT = """你是一个专业的角色设计师和AI绘画提示词专家。

## 任务
根据以下人物描述，生成 {target_count} 个不同视角的角色参考图提示词。

## 人物描述
{content}

## 画面风格
{style}

## 视角安排
- 8视角：正面、右前45度、右侧90度、右后135度、背面、左后135度、左侧90度、左前45度
- 4视角：正面、右侧90度、背面、左侧90度
- 其他数量：均匀分布在360度范围内

## 输出格式
请严格按以下 JSON 格式输出：
{{
  "prompts": [
    {{
      "index": 1,
      "title": "视角名称（如：正面视角）",
      "description": "该视角下的人物描述（中文）",
      "positive": "masterpiece, best quality, character reference sheet, {style}, [人物完整描述：发型发色、五官特征、身材体型、服装配饰、姿态表情], [视角描述：front view/side view/back view等], full body, simple background, white background, standing pose",
      "negative": "lowres, bad anatomy, bad hands, text, error, missing fingers, cropped, worst quality, low quality, blurry, deformed, multiple views in one image"
    }}
  ]
}}

## 重要规则
1. **特征一致**：所有视角必须保持人物特征完全一致
2. **视角明确**：每个提示词必须包含明确的视角描述（front/side/back/three-quarter等）
3. **全身展示**：使用 full body 确保展示完整人物
4. **简洁背景**：使用纯色背景便于后期抠图使用
5. **姿态统一**：建议使用标准站姿，便于对比不同视角"""

VIDEO_STORYBOARD_PROMPT = """你是一个专业的视频分镜师和AI绘画提示词专家。

## 任务
分析以下视频脚本，生成 {target_count} 个分镜画面的AI绘画提示词。

## 视频脚本
{content}

## 画面风格
{style}

## 输出格式
请严格按以下 JSON 格式输出：
{{
  "prompts": [
    {{
      "index": 1,
      "title": "镜头编号和类型（如：Scene 1 - 全景建立镜头）",
      "description": "镜头描述（中文，包含画面内容、镜头运动、时长建议）",
      "positive": "masterpiece, best quality, cinematic, {style}, [场景描述], [人物描述], [动作描述], [镜头类型：wide shot/medium shot/close-up/extreme close-up], [光线：natural lighting/dramatic lighting/soft lighting], film grain, cinematic composition",
      "negative": "lowres, bad anatomy, text, watermark, worst quality, low quality, blurry, amateur, poorly composed"
    }}
  ]
}}

## 镜头类型参考
- 全景(Wide Shot)：展示整体环境
- 中景(Medium Shot)：人物膝盖以上
- 近景(Close-up)：人物面部或重要物品
- 特写(Extreme Close-up)：细节特写
- 俯拍(High Angle)：从上往下拍摄
- 仰拍(Low Angle)：从下往上拍摄"""

SCENE_MULTIVIEW_PROMPT = """你是一个专业的场景设计师和AI绘画提示词专家。

## 任务
根据以下场景描述，生成 {target_count} 个不同视角的场景渲染图提示词。

## 场景描述
{content}

## 画面风格
{style}

## 输出格式
请严格按以下 JSON 格式输出：
{{
  "prompts": [
    {{
      "index": 1,
      "title": "视角名称（如：入口正视图）",
      "description": "该视角下的场景描述（中文）",
      "positive": "masterpiece, best quality, {style}, interior design/exterior design, [详细场景描述：建筑结构、家具摆设、材质纹理、色彩搭配], [视角：front view/bird eye view/corner view], [光线：natural daylight/warm lighting/ambient lighting], architectural photography, high detail",
      "negative": "lowres, blurry, worst quality, low quality, watermark, text, deformed architecture, impossible geometry"
    }}
  ]
}}

## 建议视角
- 正视图、俯视图、透视图、角落视角、入口视角、窗边视角等"""

FASHION_DESIGN_PROMPT = """你是一个专业的服装设计师和AI绘画提示词专家。

## 任务
根据以下服装描述，生成 {target_count} 个不同视角的服装展示图提示词。

## 服装描述
{content}

## 画面风格
{style}

## 输出格式
请严格按以下 JSON 格式输出：
{{
  "prompts": [
    {{
      "index": 1,
      "title": "视角名称（如：正面全身展示）",
      "description": "该视角下的服装展示描述（中文）",
      "positive": "masterpiece, best quality, fashion photography, {style}, [服装详细描述：款式、面料、颜色、细节设计、配饰], [模特描述：姿态、表情], [视角], professional fashion shoot, studio lighting, clean background",
      "negative": "lowres, bad anatomy, worst quality, low quality, blurry, deformed, ugly clothes, wrinkled fabric"
    }}
  ]
}}

## 建议视角
- 正面全身、背面全身、侧面全身、上半身特写、细节特写、动态展示"""

COMIC_SERIES_PROMPT = """你是一个专业的漫画分镜师和AI绘画提示词专家。

## 任务
根据以下剧情内容，生成 {target_count} 页连续漫画画面的AI绘画提示词。

## 剧情内容
{content}

## 画面风格
{style}

## 输出格式
请严格按以下 JSON 格式输出：
{{
  "prompts": [
    {{
      "index": 1,
      "title": "第X页 - 场景概述",
      "description": "该页漫画的内容描述（中文，包含画面内容和剧情推进）",
      "positive": "masterpiece, best quality, manga style, comic art, {style}, [场景描述], [人物描述和动作], [表情和情绪], [构图：单格/多格], dynamic composition, expressive, detailed lineart",
      "negative": "lowres, bad anatomy, worst quality, low quality, blurry, realistic photo, 3d render"
    }}
  ]
}}

## 漫画要素
1. **情节连贯**：确保页面之间剧情流畅衔接
2. **表情丰富**：漫画强调人物表情和情绪表达
3. **动态构图**：使用动态线条和夸张透视增强视觉冲击
4. **分格建议**：可在描述中说明建议的分格方式"""

TEMPLATE_PROMPTS = {
    TemplateType.NOVEL_STORYBOARD: NOVEL_STORYBOARD_PROMPT,
    TemplateType.CHARACTER_MULTIVIEW: CHARACTER_MULTIVIEW_PROMPT,
    TemplateType.VIDEO_STORYBOARD: VIDEO_STORYBOARD_PROMPT,
    TemplateType.SCENE_MULTIVIEW: SCENE_MULTIVIEW_PROMPT,
    TemplateType.FASHION_DESIGN: FASHION_DESIGN_PROMPT,
    TemplateType.COMIC_SERIES: COMIC_SERIES_PROMPT,
}

STYLE_MAPPING = {
    "realistic": "photorealistic, highly detailed, 8k",
    "anime": "anime style, vibrant colors, detailed",
    "cyberpunk": "cyberpunk style, neon lights, futuristic",
    "fantasy": "fantasy art, epic, magical atmosphere",
    "watercolor": "watercolor painting style, soft colors",
    "comic": "comic book style, bold lines, dynamic",
}


# ============ 辅助函数 ============

async def get_template_prompt(template_type: str, db: AsyncSession) -> str:
    """获取模板提示词（优先用户自定义，否则使用系统内置）"""
    from sqlalchemy import and_
    
    # 先查找用户设置的默认模板
    result = await db.execute(
        select(AIPromptTemplate).where(
            and_(
                AIPromptTemplate.template_type == template_type,
                AIPromptTemplate.is_default == True
            )
        )
    )
    template = result.scalar_one_or_none()
    
    if template:
        logger.info(f"使用用户自定义模板: {template.name}")
        return template.prompt_template
    
    # 使用系统内置模板
    if template_type in SYSTEM_TEMPLATES:
        logger.info(f"使用系统内置模板: {template_type}")
        return SYSTEM_TEMPLATES[template_type]["prompt_template"]
    
    # 兼容旧的 TEMPLATE_PROMPTS
    if template_type in TEMPLATE_PROMPTS:
        logger.info(f"使用旧版模板: {template_type}")
        return TEMPLATE_PROMPTS[template_type]
    
    return None


async def get_ai_settings(db: AsyncSession) -> dict:
    """获取 AI 设置"""
    result = await db.execute(
        select(UserSettings).where(UserSettings.key == "ai_settings")
    )
    setting = result.scalar_one_or_none()
    
    if setting and setting.value:
        return setting.value
    return {}


async def call_ai_api(
    prompt: str,
    ai_settings: dict,
) -> str:
    """调用 AI API"""
    import httpx
    
    api_key = ai_settings.get('api_key', '')
    api_url = ai_settings.get('api_url', 'https://api.openai.com/v1')
    model = ai_settings.get('model', 'gpt-4o-mini')
    
    # 限制 prompt 长度，避免超时
    max_prompt_len = 8000
    if len(prompt) > max_prompt_len:
        logger.warning(f"Prompt 过长 ({len(prompt)} 字符)，截断到 {max_prompt_len}")
        prompt = prompt[:max_prompt_len] + "\n\n[内容已截断，请基于以上内容分析]"
    
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    
    payload = {
        "model": model,
        "messages": [
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.7,
        "max_tokens": 4000,  # 限制输出长度
    }
    
    logger.info(f"调用 AI API: model={model}, prompt_len={len(prompt)}")
    
    async with httpx.AsyncClient(timeout=180.0) as client:
        response = await client.post(
            f"{api_url}/chat/completions",
            headers=headers,
            json=payload
        )
        response.raise_for_status()
        data = response.json()
    
    return data["choices"][0]["message"]["content"]


def parse_ai_response(content: str) -> dict:
    """解析 AI 响应，返回完整的结构化数据"""
    original_content = content  # 保存原始内容用于调试

    try:
        # 使用 PromptProcessor 解析
        result = prompt_processor.process_ai_response(content)
        return result
    except json.JSONDecodeError as e:
        # JSON 解析失败，记录详细信息
        logger.error(f"JSON 解析失败: {e}")
        logger.error(f"原始 AI 响应（前500字符）: {original_content[:500]}")

        # 尝试旧的解析方式作为兜底
        try:
            # 清理 markdown 代码块
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0]
            elif "```" in content:
                content = content.split("```")[1].split("```")[0]

            content = content.strip()

            # 移除控制字符
            import re
            cleaned = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', content)
            data = json.loads(cleaned)

            # 兼容旧格式
            prompts = data.get("prompts", [])
            characters = data.get("characters", [])
            global_style = data.get("global_style", {})

            return {
                "prompts": prompts,
                "characters": characters,
                "global_style": global_style
            }
        except Exception:
            pass

        # 如果还是失败，抛出原始错误
        raise


# ============ API 路由 ============

@router.get("/templates")
async def get_templates():
    """获取可用的创作模板列表"""
    return {
        "templates": [
            {
                "id": TemplateType.NOVEL_STORYBOARD,
                "name": "小说分镜画面",
                "icon": "📖",
                "description": "根据小说文本自动生成分镜画面",
                "features": ["AI分析小说场景", "自动生成分镜", "按顺序执行"],
            },
            {
                "id": TemplateType.CHARACTER_MULTIVIEW,
                "name": "人物多视角设定",
                "icon": "🧍",
                "description": "生成人物的多角度参考图",
                "features": ["8/16视角参考图", "3D建模参考", "保持一致性"],
            },
            {
                "id": TemplateType.VIDEO_STORYBOARD,
                "name": "视频分镜脚本",
                "icon": "🎬",
                "description": "根据视频脚本生成分镜预览",
                "features": ["视频脚本转分镜", "镜头分析", "预览画面效果"],
            },
            {
                "id": TemplateType.SCENE_MULTIVIEW,
                "name": "场景多角度生成",
                "icon": "🏠",
                "description": "生成场景的多视角图片",
                "features": ["场景多视角渲染", "建筑/室内设计", "环境概念图"],
            },
            {
                "id": TemplateType.FASHION_DESIGN,
                "name": "服装设计展示",
                "icon": "👗",
                "description": "生成服装的多角度展示图",
                "features": ["服装多角度展示", "时装设计参考", "模特展示"],
            },
            {
                "id": TemplateType.COMIC_SERIES,
                "name": "连续漫画生成",
                "icon": "📚",
                "description": "根据剧情生成连续漫画页面",
                "features": ["剧情连续漫画", "自动分格排版", "风格一致"],
            },
        ]
    }


@router.post("/analyze")
async def analyze_content(
    request: AnalyzeRequest,
    db: AsyncSession = Depends(get_db)
):
    """AI 分析内容并生成提示词 - 返回角色信息和结构化提示词"""
    # 获取 AI 设置
    ai_settings = await get_ai_settings(db)

    ai_enabled = ai_settings.get('enabled', False)
    api_key = ai_settings.get('api_key', '')
    if not ai_enabled or not api_key:
        raise HTTPException(status_code=400, detail="AI 功能未启用，请先在设置中配置 AI API")

    # 获取模板提示词（优先用户自定义）
    template_prompt = await get_template_prompt(request.template_type, db)
    if not template_prompt:
        raise HTTPException(status_code=400, detail=f"不支持的模板类型: {request.template_type}")

    # 处理目标数量
    target_count = request.target_count
    content_len = len(request.input_content)

    if target_count == 0:
        # 根据内容长度自动估算合理的分镜数量
        if content_len < 500:
            target_count = 4
        elif content_len < 1500:
            target_count = 6
        elif content_len < 3000:
            target_count = 8
        else:
            target_count = 12

    style_desc = STYLE_MAPPING.get(request.style, request.style)

    # 构建提示词（使用 replace 避免 JSON 中的花括号与 format 冲突）
    prompt = template_prompt.replace("{content}", request.input_content)
    prompt = prompt.replace("{style}", style_desc)
    prompt = prompt.replace("{target_count}", str(target_count))

    try:
        logger.info(f"开始 AI 分析: template={request.template_type}, target_count={target_count}, content_len={content_len}")
        response = await call_ai_api(prompt, ai_settings)
        logger.info(f"AI 响应长度: {len(response)} 字符")

        # 解析并处理响应
        result = parse_ai_response(response)

        prompts = result.get("prompts", [])
        characters = result.get("characters", [])
        global_style = result.get("global_style", {})

        logger.info(f"解析出 {len(prompts)} 个分镜, {len(characters)} 个角色")

        return {
            "prompts": prompts,
            "characters": characters,
            "global_style": global_style
        }
    except json.JSONDecodeError as e:
        logger.error(f"AI 响应解析失败: {e}")
        raise HTTPException(status_code=500, detail=f"AI 响应解析失败: {str(e)}")
    except Exception as e:
        logger.error(f"AI 分析失败: {e}")
        raise HTTPException(status_code=500, detail=f"AI 分析失败: {str(e)}")


@router.post("", response_model=TaskResponse)
async def create_task(
    request: CreateTaskRequest,
    db: AsyncSession = Depends(get_db)
):
    """创建智能创作任务"""
    task = SmartCreateTask(
        name=request.name,
        template_type=request.template_type,
        input_content=request.input_content,
        style=request.style,
        target_count=request.target_count,
        image_size=request.image_size,
        workflow_id=request.workflow_id,
        config=request.config,
        status="pending"
    )
    
    db.add(task)
    await db.commit()
    await db.refresh(task)
    
    return task


@router.get("", response_model=list[TaskResponse])
async def list_tasks(
    status: Optional[str] = None,
    template_type: Optional[str] = None,
    limit: int = 50,
    db: AsyncSession = Depends(get_db)
):
    """获取任务列表"""
    query = select(SmartCreateTask).order_by(desc(SmartCreateTask.created_at))
    
    if status:
        query = query.where(SmartCreateTask.status == status)
    if template_type:
        query = query.where(SmartCreateTask.template_type == template_type)
    
    query = query.limit(limit)
    result = await db.execute(query)
    return result.scalars().all()


@router.get("/{task_id}", response_model=TaskResponse)
async def get_task(
    task_id: int,
    db: AsyncSession = Depends(get_db)
):
    """获取任务详情"""
    result = await db.execute(
        select(SmartCreateTask).where(SmartCreateTask.id == task_id)
    )
    task = result.scalar_one_or_none()
    
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    
    return task


@router.put("/{task_id}/prompts")
async def update_prompts(
    task_id: int,
    request: UpdatePromptsRequest,
    db: AsyncSession = Depends(get_db)
):
    """更新任务的提示词列表"""
    result = await db.execute(
        select(SmartCreateTask).where(SmartCreateTask.id == task_id)
    )
    task = result.scalar_one_or_none()
    
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    
    task.analyzed_prompts = [p.model_dump() for p in request.prompts]
    # 预设 total_count 为分镜数量（执行时会根据 images_per_prompt 重新计算）
    task.total_count = len(request.prompts)

    await db.commit()
    await db.refresh(task)
    
    return {"success": True, "total_count": task.total_count}


@router.post("/{task_id}/execute")
async def execute_task(
    task_id: int,
    request: ExecuteTaskRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db)
):
    """开始执行任务"""
    result = await db.execute(
        select(SmartCreateTask).where(SmartCreateTask.id == task_id)
    )
    task = result.scalar_one_or_none()
    
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    
    if task.status in ["generating", "analyzing"]:
        raise HTTPException(status_code=400, detail="任务正在执行中")
    
    if not task.analyzed_prompts:
        raise HTTPException(status_code=400, detail="请先进行 AI 分析生成提示词")
    
    # 更新任务状态
    task.status = "generating"
    task.started_at = datetime.now(timezone.utc)
    task.workflow_id = request.workflow_id
    task.config = {
        **task.config,
        "images_per_prompt": request.images_per_prompt,
        "use_fixed_seed": request.use_fixed_seed,
        "save_to_gallery": request.save_to_gallery,
    }
    # 预先设置 total_count，这样前端能立即看到正确的总数
    task.total_count = len(task.analyzed_prompts) * request.images_per_prompt
    task.completed_count = 0
    task.failed_count = 0

    await db.commit()
    
    # 添加后台任务执行
    background_tasks.add_task(smart_create_executor.execute_task, task_id)
    
    return {"success": True, "message": "任务已开始执行", "task_id": task_id}


@router.put("/{task_id}/pause")
async def pause_task(
    task_id: int,
    db: AsyncSession = Depends(get_db)
):
    """暂停任务"""
    result = await db.execute(
        select(SmartCreateTask).where(SmartCreateTask.id == task_id)
    )
    task = result.scalar_one_or_none()
    
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    
    if task.status != "generating":
        raise HTTPException(status_code=400, detail="只能暂停执行中的任务")
    
    task.status = "paused"
    smart_create_executor.pause_task(task_id)
    await db.commit()
    
    return {"success": True, "message": "任务已暂停"}


@router.put("/{task_id}/resume")
async def resume_task(
    task_id: int,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db)
):
    """恢复任务"""
    result = await db.execute(
        select(SmartCreateTask).where(SmartCreateTask.id == task_id)
    )
    task = result.scalar_one_or_none()

    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")

    if task.status != "paused":
        raise HTTPException(status_code=400, detail="只能恢复已暂停的任务")

    task.status = "generating"
    smart_create_executor.resume_task(task_id)
    await db.commit()

    # 检查是否有已提交的 jobs，如果有则继续监控，否则重新执行
    jobs = task.result_images or []
    if jobs and any(j.get("prompt_id") for j in jobs if isinstance(j, dict)):
        # 有已提交的任务，继续监控（监控循环会自动在 resume 后继续工作）
        # 如果监控循环已经结束（服务重启等情况），需要重新启动监控
        background_tasks.add_task(smart_create_executor.resume_monitoring, task_id, jobs)
    else:
        # 没有已提交的任务，重新执行
        background_tasks.add_task(smart_create_executor.execute_task, task_id)

    return {"success": True, "message": "任务已恢复"}


@router.put("/{task_id}/stop")
async def stop_task(
    task_id: int,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db)
):
    """停止任务"""
    result = await db.execute(
        select(SmartCreateTask).where(SmartCreateTask.id == task_id)
    )
    task = result.scalar_one_or_none()

    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")

    if task.status not in ["generating", "paused"]:
        raise HTTPException(status_code=400, detail="只能停止执行中或已暂停的任务")

    # 获取已提交的任务列表，用于取消 ComfyUI 队列
    jobs = task.result_images or []

    task.status = "failed"
    task.error_message = "任务已被用户停止"
    smart_create_executor.stop_task(task_id)
    await db.commit()

    # 在后台取消 ComfyUI 队列中的任务
    if jobs:
        background_tasks.add_task(smart_create_executor.cancel_comfyui_jobs_by_task, task_id, jobs)

    return {"success": True, "message": "任务已停止"}


@router.post("/recover")
async def recover_tasks():
    """手动恢复中断的任务"""
    smart_create_executor._recovery_done = False  # 重置标志
    await smart_create_executor.recover_interrupted_tasks()
    return {"success": True, "message": "已触发任务恢复"}


@router.post("/{task_id}/retry")
async def retry_task(
    task_id: int,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db)
):
    """重试失败的任务 - 只重试失败的分镜"""
    result = await db.execute(
        select(SmartCreateTask).where(SmartCreateTask.id == task_id)
    )
    task = result.scalar_one_or_none()

    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")

    if task.status not in ["failed", "completed"]:
        raise HTTPException(status_code=400, detail="只能重试已完成或失败的任务")

    # 检查是否有失败的分镜需要重试
    jobs = task.result_images or []
    failed_jobs = [j for j in jobs if isinstance(j, dict) and j.get("status") == "failed"]

    if not failed_jobs:
        raise HTTPException(status_code=400, detail="没有需要重试的失败分镜")

    # 更新任务状态
    task.status = "generating"
    task.error_message = ""
    await db.commit()

    # 启动重试
    background_tasks.add_task(smart_create_executor.retry_failed_jobs, task_id)

    return {"success": True, "message": f"开始重试 {len(failed_jobs)} 个失败的分镜"}


@router.delete("/{task_id}")
async def delete_task(
    task_id: int,
    db: AsyncSession = Depends(get_db)
):
    """删除任务"""
    result = await db.execute(
        select(SmartCreateTask).where(SmartCreateTask.id == task_id)
    )
    task = result.scalar_one_or_none()
    
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    
    if task.status == "generating":
        # 先停止任务
        smart_create_executor.stop_task(task_id)
        task.status = "failed"
        task.error_message = "任务已被删除"
        await db.commit()
    
    await db.delete(task)
    await db.commit()
    
    return {"success": True, "message": "任务已删除"}
