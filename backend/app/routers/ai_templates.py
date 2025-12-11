"""AI 提示词模板管理 API"""
import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_

from ..database import get_db
from ..models import AIPromptTemplate

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ai-templates", tags=["ai-templates"])


# ============ 数据模型 ============

class TemplateCreate(BaseModel):
    """创建模板请求"""
    template_type: str
    name: str
    version: str = "1.0"
    prompt_template: str
    description: str = ""
    is_default: bool = False


class TemplateUpdate(BaseModel):
    """更新模板请求"""
    name: Optional[str] = None
    version: Optional[str] = None
    prompt_template: Optional[str] = None
    description: Optional[str] = None
    is_default: Optional[bool] = None


class TemplateResponse(BaseModel):
    """模板响应"""
    id: int
    template_type: str
    name: str
    version: str
    prompt_template: str
    description: str
    is_default: bool
    is_system: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# ============ 系统默认模板 ============

SYSTEM_TEMPLATES = {
    "novel_storyboard": {
        "name": "小说分镜 - 默认模板",
        "description": "适用于小说文本转分镜画面，支持人物一致性",
        "prompt_template": '''你是一个专业的小说分镜分析师和AI绘画提示词专家。

## 任务
分析以下小说文本，将其拆分为 {target_count} 个关键分镜场景，并为每个场景生成高质量的AI绘画提示词。

## 小说内容
{content}

## 画面风格
{style}

## 核心要求：人物一致性
**重要**：首先识别小说中的主要人物，为每个人物建立固定的外貌描述标签，在所有分镜中保持一致。

人物特征模板示例：
- 主角：[hair color] hair, [eye color] eyes, [age] years old, [body type], [clothing description]
- 配角：同样格式的固定描述

## 分析要求
1. **场景拆分**：通读全文，识别故事的关键转折点、情感高潮、重要场景变化
2. **均匀分布**：确保分镜覆盖故事的开头、发展、高潮、结尾，跨度要大
3. **画面提炼**：为每个分镜提取最具视觉冲击力的瞬间
4. **人物锁定**：同一人物在不同分镜中使用完全相同的外貌描述词

## 输出格式
请严格按以下 JSON 格式输出，不要有任何其他内容：
{{
  "characters": [
    {{
      "name": "人物名称",
      "appearance": "固定的英文外貌描述，包含发色、眼色、年龄、体型、标志性服装"
    }}
  ],
  "prompts": [
    {{
      "index": 1,
      "title": "简短的分镜标题（4-8字中文）",
      "description": "场景描述（中文，50-100字，描述画面内容、人物动作、环境氛围）",
      "positive": "masterpiece, best quality, {style}, [场景环境], [人物外貌-使用上面定义的固定描述], [动作姿态], [表情情绪], [光线氛围], [镜头角度], [画面构图]",
      "negative": "lowres, bad anatomy, bad hands, text, error, missing fingers, extra digit, fewer digits, cropped, worst quality, low quality, normal quality, jpeg artifacts, signature, watermark, username, blurry, deformed, ugly, duplicate, morbid, mutilated"
    }}
  ]
}}

## 重要规则
1. **人物一致性最重要**：同一人物的外貌描述在所有分镜中必须完全一致
2. **分镜跨度要大**：每个分镜应代表故事的不同阶段
3. **数量严格遵守**：必须输出恰好 {target_count} 个分镜
4. **提示词质量**：正向提示词要详细具体，80-150个英文单词
5. **英文提示词**：positive 必须是纯英文'''
    },
    "character_multiview": {
        "name": "人物多视角 - 默认模板",
        "description": "生成人物的多角度参考图，保持一致性",
        "prompt_template": '''你是一个专业的角色设计师和AI绘画提示词专家。

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
2. **视角明确**：每个提示词必须包含明确的视角描述
3. **全身展示**：使用 full body 确保展示完整人物
4. **简洁背景**：使用纯色背景便于后期使用'''
    },
    "video_storyboard": {
        "name": "视频分镜 - 默认模板",
        "description": "根据视频脚本生成分镜预览",
        "prompt_template": '''你是一个专业的视频分镜师和AI绘画提示词专家。

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
- 特写(Extreme Close-up)：细节特写'''
    },
    "scene_multiview": {
        "name": "场景多视角 - 默认模板",
        "description": "生成场景的多视角图片",
        "prompt_template": '''你是一个专业的场景设计师和AI绘画提示词专家。

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
}}'''
    },
    "fashion_design": {
        "name": "服装设计 - 默认模板",
        "description": "生成服装的多角度展示图",
        "prompt_template": '''你是一个专业的服装设计师和AI绘画提示词专家。

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
}}'''
    },
    "comic_series": {
        "name": "连续漫画 - 默认模板",
        "description": "根据剧情生成连续漫画页面",
        "prompt_template": '''你是一个专业的漫画分镜师和AI绘画提示词专家。

## 任务
根据以下剧情内容，生成 {target_count} 页连续漫画画面的AI绘画提示词。

## 剧情内容
{content}

## 画面风格
{style}

## 核心要求：角色一致性
**重要**：首先识别剧情中的主要角色，为每个角色建立固定的外貌描述，在所有页面中保持一致。

## 输出格式
请严格按以下 JSON 格式输出：
{{
  "characters": [
    {{
      "name": "角色名称",
      "appearance": "固定的英文外貌描述"
    }}
  ],
  "prompts": [
    {{
      "index": 1,
      "title": "第X页 - 场景概述",
      "description": "该页漫画的内容描述（中文，包含画面内容和剧情推进）",
      "positive": "masterpiece, best quality, manga style, comic art, {style}, [场景描述], [人物描述-使用固定外貌], [动作], [表情和情绪], dynamic composition, expressive, detailed lineart",
      "negative": "lowres, bad anatomy, worst quality, low quality, blurry, realistic photo, 3d render"
    }}
  ]
}}

## 漫画要素
1. **角色一致**：同一角色在所有页面中外貌必须一致
2. **情节连贯**：确保页面之间剧情流畅衔接
3. **表情丰富**：漫画强调人物表情和情绪表达'''
    },
}


# ============ API 路由 ============

@router.get("/types")
async def get_template_types():
    """获取所有模板类型"""
    return {
        "types": [
            {"id": "novel_storyboard", "name": "小说分镜画面", "icon": "📖"},
            {"id": "character_multiview", "name": "人物多视角设定", "icon": "🧍"},
            {"id": "video_storyboard", "name": "视频分镜脚本", "icon": "🎬"},
            {"id": "scene_multiview", "name": "场景多角度生成", "icon": "🏠"},
            {"id": "fashion_design", "name": "服装设计展示", "icon": "👗"},
            {"id": "comic_series", "name": "连续漫画生成", "icon": "📚"},
        ]
    }


@router.get("")
async def list_templates(
    template_type: Optional[str] = None,
    db: AsyncSession = Depends(get_db)
):
    """获取模板列表"""
    query = select(AIPromptTemplate)
    
    if template_type:
        query = query.where(AIPromptTemplate.template_type == template_type)
    
    query = query.order_by(AIPromptTemplate.template_type, AIPromptTemplate.is_default.desc(), AIPromptTemplate.created_at.desc())
    
    result = await db.execute(query)
    templates = result.scalars().all()
    
    return {"templates": [TemplateResponse.model_validate(t) for t in templates]}


@router.get("/default/{template_type}")
async def get_default_template(
    template_type: str,
    db: AsyncSession = Depends(get_db)
):
    """获取指定类型的默认模板（优先用户自定义，否则返回系统内置）"""
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
        return TemplateResponse.model_validate(template)
    
    # 没有用户自定义，返回系统内置
    if template_type in SYSTEM_TEMPLATES:
        system_tpl = SYSTEM_TEMPLATES[template_type]
        return {
            "id": 0,
            "template_type": template_type,
            "name": system_tpl["name"],
            "version": "1.0",
            "prompt_template": system_tpl["prompt_template"],
            "description": system_tpl["description"],
            "is_default": True,
            "is_system": True,
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
        }
    
    raise HTTPException(status_code=404, detail=f"未找到模板类型: {template_type}")


@router.get("/system/{template_type}")
async def get_system_template(template_type: str):
    """获取系统内置模板"""
    if template_type not in SYSTEM_TEMPLATES:
        raise HTTPException(status_code=404, detail=f"未找到系统模板: {template_type}")
    
    system_tpl = SYSTEM_TEMPLATES[template_type]
    return {
        "template_type": template_type,
        "name": system_tpl["name"],
        "version": "1.0",
        "prompt_template": system_tpl["prompt_template"],
        "description": system_tpl["description"],
        "is_system": True,
    }


@router.post("", response_model=TemplateResponse)
async def create_template(
    request: TemplateCreate,
    db: AsyncSession = Depends(get_db)
):
    """创建新模板"""
    # 如果设为默认，先取消其他默认
    if request.is_default:
        result = await db.execute(
            select(AIPromptTemplate).where(
                and_(
                    AIPromptTemplate.template_type == request.template_type,
                    AIPromptTemplate.is_default == True
                )
            )
        )
        for tpl in result.scalars().all():
            tpl.is_default = False
    
    template = AIPromptTemplate(
        template_type=request.template_type,
        name=request.name,
        version=request.version,
        prompt_template=request.prompt_template,
        description=request.description,
        is_default=request.is_default,
        is_system=False,
    )
    
    db.add(template)
    await db.commit()
    await db.refresh(template)
    
    return template


@router.put("/{template_id}", response_model=TemplateResponse)
async def update_template(
    template_id: int,
    request: TemplateUpdate,
    db: AsyncSession = Depends(get_db)
):
    """更新模板"""
    result = await db.execute(
        select(AIPromptTemplate).where(AIPromptTemplate.id == template_id)
    )
    template = result.scalar_one_or_none()
    
    if not template:
        raise HTTPException(status_code=404, detail="模板不存在")
    
    # 如果设为默认，先取消其他默认
    if request.is_default:
        result = await db.execute(
            select(AIPromptTemplate).where(
                and_(
                    AIPromptTemplate.template_type == template.template_type,
                    AIPromptTemplate.is_default == True,
                    AIPromptTemplate.id != template_id
                )
            )
        )
        for tpl in result.scalars().all():
            tpl.is_default = False
    
    # 更新字段
    if request.name is not None:
        template.name = request.name
    if request.version is not None:
        template.version = request.version
    if request.prompt_template is not None:
        template.prompt_template = request.prompt_template
    if request.description is not None:
        template.description = request.description
    if request.is_default is not None:
        template.is_default = request.is_default
    
    await db.commit()
    await db.refresh(template)
    
    return template


@router.delete("/{template_id}")
async def delete_template(
    template_id: int,
    db: AsyncSession = Depends(get_db)
):
    """删除模板"""
    result = await db.execute(
        select(AIPromptTemplate).where(AIPromptTemplate.id == template_id)
    )
    template = result.scalar_one_or_none()
    
    if not template:
        raise HTTPException(status_code=404, detail="模板不存在")
    
    if template.is_system:
        raise HTTPException(status_code=400, detail="系统模板不可删除")
    
    await db.delete(template)
    await db.commit()
    
    return {"success": True, "message": "模板已删除"}


@router.post("/{template_id}/set-default")
async def set_default_template(
    template_id: int,
    db: AsyncSession = Depends(get_db)
):
    """设置为默认模板"""
    result = await db.execute(
        select(AIPromptTemplate).where(AIPromptTemplate.id == template_id)
    )
    template = result.scalar_one_or_none()
    
    if not template:
        raise HTTPException(status_code=404, detail="模板不存在")
    
    # 取消同类型其他默认
    result = await db.execute(
        select(AIPromptTemplate).where(
            and_(
                AIPromptTemplate.template_type == template.template_type,
                AIPromptTemplate.is_default == True
            )
        )
    )
    for tpl in result.scalars().all():
        tpl.is_default = False
    
    template.is_default = True
    await db.commit()
    
    return {"success": True, "message": f"已将 {template.name} 设为默认模板"}


@router.post("/reset/{template_type}")
async def reset_to_system_template(
    template_type: str,
    db: AsyncSession = Depends(get_db)
):
    """重置为系统默认模板（取消所有用户自定义的默认设置）"""
    result = await db.execute(
        select(AIPromptTemplate).where(
            and_(
                AIPromptTemplate.template_type == template_type,
                AIPromptTemplate.is_default == True
            )
        )
    )
    for tpl in result.scalars().all():
        tpl.is_default = False
    
    await db.commit()
    
    return {"success": True, "message": "已重置为系统默认模板"}
