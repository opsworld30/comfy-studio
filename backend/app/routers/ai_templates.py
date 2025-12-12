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


# ============ 风格映射 ============

STYLE_MAPPING = {
    # 基础风格
    "realistic": "photorealistic, ultra realistic, 8k uhd, high detail, professional photography",
    "anime": "anime style, anime artwork, vibrant colors, clean lines, anime key visual",
    "manga": "manga style, black and white, screentone, ink drawing, japanese comic style",

    # 特定风格
    "cyberpunk": "cyberpunk style, neon lights, futuristic city, dark atmosphere, sci-fi, cyber aesthetic",
    "fantasy": "fantasy art style, epic fantasy, magical atmosphere, detailed illustration, ethereal",
    "watercolor": "watercolor painting, soft colors, artistic, traditional media style, fluid",
    "oil_painting": "oil painting style, classical art, rich colors, painterly, fine art, textured",
    "comic": "western comic style, bold outlines, dynamic, superhero comic art, cel shaded",

    # 动漫特定风格
    "ghibli": "studio ghibli style, hayao miyazaki style, soft lighting, whimsical, anime movie quality",
    "makoto_shinkai": "makoto shinkai style, beautiful sky, detailed background, lighting effects, your name style",
    "kyoani": "kyoto animation style, detailed eyes, soft shading, slice of life, beautiful",

    # 其他
    "pixel": "pixel art style, retro game, 16-bit, nostalgic, pixelated",
    "3d_render": "3d render, octane render, unreal engine, high quality 3d, realistic lighting",
    "sketch": "pencil sketch, line art, hand drawn, artistic sketch, detailed linework",
}


# 风格中文名映射
STYLE_NAMES = {
    "realistic": "写实风格",
    "anime": "日系动漫",
    "manga": "黑白漫画",
    "cyberpunk": "赛博朋克",
    "fantasy": "奇幻风格",
    "watercolor": "水彩风格",
    "oil_painting": "油画风格",
    "comic": "美式漫画",
    "ghibli": "吉卜力风格",
    "makoto_shinkai": "新海诚风格",
    "kyoani": "京阿尼风格",
    "pixel": "像素风格",
    "3d_render": "3D渲染",
    "sketch": "素描风格",
}


def get_style_description(style_key: str) -> str:
    """获取风格描述"""
    return STYLE_MAPPING.get(style_key, style_key)


def list_styles() -> list:
    """获取所有可用风格列表"""
    return [
        {
            "id": key,
            "name": STYLE_NAMES.get(key, key),
            "description": desc
        }
        for key, desc in STYLE_MAPPING.items()
    ]


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
        "name": "小说分镜画面",
        "description": "分析小说生成连续分镜，支持知名IP角色识别",
        "prompt_template": '''你是专业的小说分镜分析师和AI绘画提示词专家。

## 任务流程
1. **角色分析** - 识别所有角色，判断是否为知名IP角色
2. **建立档案** - 为每个角色建立固定的视觉标签
3. **分镜拆分** - 将小说拆分为 {target_count} 个关键场景
4. **提示词生成** - 生成一致的高质量绘画提示词

## 小说内容
{content}

## 画面风格
{style}

---

## 🔴 重要规则：知名IP角色识别

### 什么是知名IP角色？
来自以下领域的广为人知的虚构角色：
- 美漫：Marvel（蜘蛛侠、钢铁侠、美队等）、DC（超人、蝙蝠侠、神奇女侠等）
- 日漫：火影、海贼王、龙珠、进击的巨人、鬼灭之刃、咒术回战等
- 游戏：塞尔达、马里奥、原神、英雄联盟、最终幻想等
- 动画电影：迪士尼、皮克斯、吉卜力等
- 虚拟歌手：初音未来、洛天依等
- 其他知名IP：哈利波特、指环王等

### 知名角色处理方式（极其重要！）

**核心原则**：知名角色必须使用「角色英文名 + IP来源」作为标签，这样AI绘画模型才能正确识别！

```
✅ 正确做法：
   character_tag: "Spider-Man, Peter Parker, Marvel"
   full_tags: "Spider-Man, Peter Parker, Marvel, red and blue spider suit, web pattern, white eye lenses on mask, athletic build"

❌ 错误做法：
   character_tag: ""
   full_tags: "young man, red and blue suit, wearing mask"
   （这样生成的只是普通人穿类似衣服，不是蜘蛛侠！）
```

### 知名角色标签构成
1. **角色英文名**：Spider-Man, Superman, Naruto Uzumaki（必须！）
2. **IP来源**：Marvel, DC Comics, naruto series（必须！）
3. **标志性特征**：该角色最具辨识度的外观特点
4. **标志性服装**：该角色的经典服装

### 常见角色示例（供参考，不限于此）

| 角色 | character_tag | 标志性特征 |
|------|---------------|-----------|
| 超人 | Superman, Clark Kent, DC Comics | 蓝色紧身衣, 红色披风, 胸口S标志 |
| 蝙蝠侠 | Batman, Bruce Wayne, DC Comics | 黑色蝙蝠战衣, 蝙蝠头罩, 黑色披风 |
| 蜘蛛侠 | Spider-Man, Peter Parker, Marvel | 红蓝蜘蛛服, 蛛网纹理, 白色大眼面罩 |
| 钢铁侠 | Iron Man, Tony Stark, Marvel | 红金色机甲, 胸口弧反应堆发光 |
| 美国队长 | Captain America, Steve Rogers, Marvel | 蓝色战服, 星形盾牌, 头盔带A |
| 初音未来 | Hatsune Miku, vocaloid | 蓝绿色超长双马尾, 黑灰色无袖服, 01耳机 |
| 鸣人 | Naruto Uzumaki, naruto series | 金色刺猬头, 脸上三道胡须印记, 橙色忍者服 |
| 路飞 | Monkey D. Luffy, one piece | 黑色乱发, 草帽, 左眼下疤痕, 红色背心 |
| 悟空 | Son Goku, dragon ball, saiyan | 黑色刺猬头(超赛金发), 橙色道服 |
| 艾莎 | Elsa, Frozen, Disney | 铂金色编发, 蓝色冰雪长裙 |

---

## 原创角色处理方式

非知名IP的原创角色，需要详细描述外貌：

**必须包含的特征维度**：
- 性别年龄：male/female, young/adult/elderly
- 发型发色：如 long straight black hair, short messy brown hair
- 眼睛：颜色和形状，如 blue eyes, narrow brown eyes
- 脸型：如 oval face, round face, sharp jawline
- 体型：如 slim, athletic, muscular, petite
- 肤色：如 fair skin, tan skin, dark skin

**禁止使用的模糊词汇**：
❌ 美丽的、帅气的、可爱的、迷人的、好看的
✅ 用具体特征替代：big eyes, small nose, defined cheekbones

---

## 场景连贯性规则

### 色调一致性
- 同一场景的多个分镜应保持相似的色调
- 白天场景：warm colors, natural lighting
- 夜晚场景：cool colors, dramatic lighting

### 构图变化
分镜之间的镜头应有变化，避免单调：
- 建立镜头：wide shot
- 人物镜头：medium shot
- 情感镜头：close-up
- 细节镜头：extreme close-up

---

## 输出格式（严格JSON）

```json
{{
  "characters": [
    {{
      "name": "角色中文名",
      "id": "char_01",
      "is_known_ip": true,
      "ip_source": "Marvel / DC Comics / naruto series / one piece / original 等",
      "character_tag": "知名角色必填：English Name, IP Source（原创角色留空字符串）",
      "gender": "male/female",
      "iconic_features": "标志性外貌特征（英文）",
      "default_outfit": "标志性/默认服装（英文）",
      "full_tags": "完整标签 = character_tag + iconic_features + default_outfit"
    }}
  ],
  "global_style": {{
    "quality": "masterpiece, best quality, highly detailed",
    "art_style": "{style}",
    "negative": "lowres, bad anatomy, bad hands, text, error, missing fingers, extra digit, fewer digits, cropped, worst quality, low quality, jpeg artifacts, signature, watermark, blurry, deformed, ugly, duplicate, extra limbs, cloned face, disfigured, malformed limbs, fused fingers, too many fingers, long neck, poorly drawn hands, poorly drawn face, mutation, mutated"
  }},
  "prompts": [
    {{
      "index": 1,
      "title": "简短中文标题（4-8字）",
      "story_position": "opening / development / climax / ending",
      "description": "中文场景描述（50-100字），包含画面内容、人物状态、环境氛围",
      "characters_present": ["char_01"],
      "scene": {{
        "location": "具体地点（英文），如 modern city street, dark forest at night",
        "time_of_day": "时间，如 sunset, midnight, early morning",
        "weather_lighting": "光线/天气/氛围，如 dramatic lighting, soft sunlight, rainy"
      }},
      "action": "具体动作（英文），如 running, sitting on bench, fighting stance",
      "emotion": "表情情绪（英文），如 determined expression, gentle smile, angry",
      "camera": {{
        "shot": "镜头类型：wide shot / medium shot / close-up / extreme close-up",
        "angle": "拍摄角度：eye level / low angle / high angle / dutch angle"
      }},
      "positive": "完整英文提示词（按下方组装规则，80-150词）",
      "negative": "负面提示词（可使用global_style.negative或针对场景调整）"
    }}
  ]
}}
```

---

## Positive 提示词组装规则

按以下顺序组装，用英文逗号分隔：

```
[quality] + [art_style] + [人数] + [角色full_tags] + [action] + [emotion] + [location] + [time] + [lighting] + [shot] + [angle]
```

### 知名角色示例

**场景**：蜘蛛侠在纽约楼顶

```
masterpiece, best quality, highly detailed, comic style, 1boy, Spider-Man, Peter Parker, Marvel, athletic build, red and blue spider suit, web pattern, white eye lenses on mask, crouching on rooftop edge, determined, new york city skyline, night time, city lights below, moonlight, dynamic pose, low angle shot
```

---

## 关键规则（必须遵守）

1. **知名角色必须识别**：不要把超人写成"穿蓝衣服的黑发男人"，要用 "Superman, DC Comics"
2. **character_tag 是关键**：知名角色的 character_tag 必须包含英文名和IP来源
3. **full_tags 保持一致**：同一角色在所有分镜中的 full_tags 必须完全相同
4. **分镜跨度要大**：覆盖故事的开头、发展、高潮、结尾
5. **数量严格**：必须恰好输出 {target_count} 个分镜
6. **纯英文提示词**：positive 和 negative 必须是纯英文
7. **具体化描述**：禁止使用"美丽"、"帅气"等抽象词

请直接输出符合格式的 JSON，不要有任何其他内容。'''
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
