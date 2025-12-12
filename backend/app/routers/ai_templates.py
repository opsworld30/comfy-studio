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
        "name": "小说分镜 - 默认模版",
        "description": "适用于小说文本转分镜画面，支持角色锁定和结构化输出",
        "prompt_template": '''你是专业的小说分镜分析师和AI绘画提示词专家。

## 核心任务
1. 提取并固定所有角色的视觉特征
2. 将小说拆分为 {target_count} 个关键分镜
3. 为每个分镜生成高质量、一致的 AI 绘画提示词

## 小说内容
{content}

## 画面风格
{style}

---

## 第一步：角色档案建立

分析小说中的角色，为每个角色建立【固定不变】的视觉档案。

角色描述必须具体化，禁止使用的词汇：
❌ 美丽的、帅气的、可爱的、迷人的（太抽象）
✅ 改为具体特征：oval face, sharp jawline, big eyes, small nose

必须包含的特征维度：
- hair: 发型+发色+长度（如 long straight black hair, short messy brown hair）
- eyes: 眼睛颜色+形状（如 blue eyes, narrow brown eyes）
- face: 脸型特征（如 oval face, round face with freckles）
- body: 体型（如 slim, athletic, petite, tall and muscular）
- skin: 肤色（如 fair skin, tan skin, pale skin）
- age: 年龄外观（如 young woman in 20s, middle-aged man）
- outfit: 默认服装（如 white blouse and black skirt, casual hoodie and jeans）

---

## 第二步：分镜提取原则

1. **跨度要大**：分镜应覆盖故事的开头→发展→高潮→结尾
2. **视觉优先**：选择最有画面感的瞬间，跳过纯对话/心理描写
3. **动作明确**：每个分镜要有清晰的人物动作或状态
4. **场景多样**：避免连续多个分镜都在同一场景

---

## 第三步：提示词组装规范

positive 提示词必须按以下顺序组装：

```
[质量词], [风格词], [人数], [角色特征-照抄档案], [动作], [表情], [场景环境], [时间光线], [镜头构图]
```

示例：
```
masterpiece, best quality, anime style, 1girl, long black hair, blue eyes, fair skin, school uniform with red ribbon, running, happy smile, cherry blossom park, sunset, golden hour lighting, medium shot, dynamic angle
```

---

## 输出格式（严格 JSON）

```json
{{
  "characters": [
    {{
      "name": "角色中文名",
      "id": "char_01",
      "gender": "female",
      "fixed_appearance": "long straight black hair, blue eyes, oval face, fair skin, slim, young woman in 20s",
      "default_outfit": "white school uniform, red ribbon, black pleated skirt",
      "full_tags": "long straight black hair, blue eyes, oval face, fair skin, slim body, white school uniform, red ribbon, black pleated skirt"
    }}
  ],
  "global_style": {{
    "quality": "masterpiece, best quality, highly detailed",
    "art_style": "{style}",
    "negative": "lowres, bad anatomy, bad hands, text, error, missing fingers, extra digit, fewer digits, cropped, worst quality, low quality, jpeg artifacts, signature, watermark, blurry, deformed, ugly, duplicate, extra limbs, cloned face, disfigured, mutated hands, poorly drawn hands, poorly drawn face, mutation, extra fingers, fused fingers, too many fingers, long neck, malformed limbs"
  }},
  "prompts": [
    {{
      "index": 1,
      "title": "简短中文标题(4-8字)",
      "story_position": "opening/development/climax/ending",
      "description": "中文场景描述(50-100字)，说明画面内容、人物状态、环境氛围",
      "characters_present": ["char_01"],
      "scene": {{
        "location": "具体地点英文，如 modern classroom, rainy street at night",
        "time_of_day": "时间，如 morning, sunset, midnight",
        "weather_lighting": "光线氛围，如 soft natural light, dramatic shadows, neon lights"
      }},
      "action": "具体动作英文，如 sitting by window, running through crowd",
      "emotion": "表情情绪英文，如 gentle smile, tears in eyes, determined look",
      "camera": {{
        "shot": "wide shot / medium shot / close-up / extreme close-up",
        "angle": "eye level / low angle / high angle / bird eye view"
      }},
      "positive": "组装好的完整英文提示词(按上述顺序，80-120词)",
      "negative": "使用 global_style.negative，如有场景特殊需求可追加"
    }}
  ]
}}
```

---

## 关键规则（必须遵守）

1. **角色标签锁死**：同一角色在所有分镜的 positive 中，外貌描述部分必须【完全相同】，直接复制 full_tags
2. **服装变化处理**：如果剧情需要换装，在 action 中说明新服装，但 full_tags 中的外貌特征（发型、眼睛、脸型、肤色、体型）保持不变
3. **数量严格**：必须恰好输出 {target_count} 个分镜
4. **禁止抽象词**：beautiful, handsome, cute, attractive 等词禁止出现在 positive 中
5. **英文提示词**：positive 和 negative 必须是纯英文

请直接输出 JSON，不要有任何其他内容。'''
    },
    "character_multiview": {
        "name": "人物多视角 - 增强版",
        "description": "生成角色多角度参考图，保持完美一致性",
        "prompt_template": '''你是专业的角色设计师和 AI 绘画提示词专家。

## 任务
根据人物描述，生成 {target_count} 个不同视角的角色设定图提示词。

## 人物描述
{content}

## 画面风格
{style}

## 视角分配规则
- 4 视角：正面、右侧、背面、左侧
- 8 视角：正面、右前45°、右侧、右后45°、背面、左后45°、左侧、左前45°

---

## 角色档案建立

首先将人物描述转化为具体的视觉标签：

必须包含的特征维度：
- hair: 发型+发色+长度（如 long straight black hair）
- eyes: 眼睛颜色+形状（如 blue eyes, narrow eyes）
- face: 脸型特征（如 oval face, sharp jawline）
- body: 体型（如 slim, athletic, petite）
- skin: 肤色（如 fair skin, tan skin）
- age: 年龄外观（如 young woman in 20s）
- outfit: 服装详细描述

---

## 输出格式（严格 JSON）

```json
{{
  "character": {{
    "name": "角色名",
    "gender": "male/female",
    "fixed_appearance": "完整外貌描述（发型发色、眼睛、脸型、肤色、体型、年龄）",
    "outfit": "服装描述",
    "full_tags": "合并的完整标签，用于所有视角"
  }},
  "global_style": {{
    "quality": "masterpiece, best quality, highly detailed",
    "art_style": "{style}",
    "negative": "multiple views, split screen, lowres, bad anatomy, worst quality, low quality, blurry, cropped, deformed"
  }},
  "prompts": [
    {{
      "index": 1,
      "title": "正面视角",
      "view_angle": "front view",
      "description": "该视角的中文说明",
      "positive": "masterpiece, best quality, character reference sheet, {style}, full body, [full_tags], front view, standing pose, simple background, white background, solo, looking at viewer",
      "negative": "multiple views, split image, lowres, bad anatomy, worst quality, low quality, blurry, cropped"
    }}
  ]
}}
```

---

## 关键规则

1. **标签完全一致**：所有视角的 full_tags（外貌+服装）必须完全相同，只有 view_angle 不同
2. **使用 standing pose**：保持简洁的站姿
3. **白色背景**：使用 white background 便于后期使用
4. **确保 full body**：展示完整人物
5. **禁止抽象词**：beautiful, handsome 等词禁止使用

请直接输出 JSON。'''
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
        "name": "连续漫画 - 增强版",
        "description": "根据剧情生成连续漫画页面，角色高度一致",
        "prompt_template": '''你是专业的漫画分镜师和AI绘画提示词专家。

## 任务
根据剧情内容，生成 {target_count} 页连续漫画画面的AI绘画提示词。

## 剧情内容
{content}

## 画面风格
{style}

---

## 第一步：角色档案建立（最重要！）

识别剧情中的所有角色，为每个角色建立【固定不变】的视觉档案。

角色描述必须具体化：
- hair: 发型+发色+长度
- eyes: 眼睛颜色+形状
- face: 脸型特征
- body: 体型
- skin: 肤色
- outfit: 标志性服装

禁止使用：美丽的、帅气的、可爱的等抽象词

---

## 输出格式（严格 JSON）

```json
{{
  "characters": [
    {{
      "name": "角色中文名",
      "id": "char_01",
      "gender": "female",
      "fixed_appearance": "具体外貌描述",
      "default_outfit": "默认服装",
      "full_tags": "合并的完整标签"
    }}
  ],
  "global_style": {{
    "quality": "masterpiece, best quality, highly detailed",
    "art_style": "manga style, comic art, {style}",
    "negative": "lowres, bad anatomy, worst quality, low quality, blurry, realistic photo, 3d render, deformed"
  }},
  "prompts": [
    {{
      "index": 1,
      "title": "第1页 - 场景概述",
      "story_position": "opening/development/climax/ending",
      "description": "该页漫画的内容描述（中文，包含画面内容和剧情推进）",
      "characters_present": ["char_01"],
      "scene": {{
        "location": "场景地点英文",
        "time_of_day": "时间",
        "weather_lighting": "光线氛围"
      }},
      "action": "具体动作英文",
      "emotion": "表情情绪英文，漫画要夸张表现",
      "camera": {{
        "shot": "wide shot / medium shot / close-up",
        "angle": "eye level / low angle / high angle / dutch angle"
      }},
      "positive": "masterpiece, best quality, manga style, comic art, {style}, [角色full_tags], [动作], [夸张表情], [场景], dynamic composition, expressive, detailed lineart, screentone",
      "negative": "lowres, bad anatomy, worst quality, low quality, blurry, realistic photo, 3d render"
    }}
  ]
}}
```

---

## 漫画特有规则

1. **角色标签锁死**：同一角色在所有页面的外貌描述必须完全相同
2. **表情夸张化**：漫画强调表情，使用 expressive, exaggerated expression 等
3. **动态构图**：使用 dynamic composition, action lines, speed lines 增强视觉冲击
4. **情节连贯**：确保页面之间剧情流畅衔接
5. **数量严格**：必须恰好输出 {target_count} 个页面

请直接输出 JSON。'''
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
