"""模板路由"""
from fastapi import APIRouter
from typing import Any

from ..data import PROMPT_TEMPLATES, WORKFLOW_TEMPLATES, SAMPLER_PRESETS, RESOLUTION_PRESETS, POPULAR_PLUGINS

router = APIRouter(prefix="/templates", tags=["templates"])


@router.get("/prompts")
async def get_prompt_templates() -> dict[str, Any]:
    """获取所有 Prompt 模板"""
    return {
        "templates": PROMPT_TEMPLATES,
        "categories": list(set(t["category"] for t in PROMPT_TEMPLATES.values()))
    }


@router.get("/prompts/{template_id}")
async def get_prompt_template(template_id: str) -> dict[str, Any]:
    """获取单个 Prompt 模板"""
    if template_id not in PROMPT_TEMPLATES:
        return {"error": "模板不存在"}
    return PROMPT_TEMPLATES[template_id]


@router.get("/prompts/category/{category}")
async def get_prompts_by_category(category: str) -> list[dict[str, Any]]:
    """按分类获取 Prompt 模板"""
    return [
        {"id": k, **v} 
        for k, v in PROMPT_TEMPLATES.items() 
        if v["category"] == category
    ]


@router.get("/workflows")
async def get_workflow_templates() -> dict[str, Any]:
    """获取所有工作流模板"""
    # 返回模板列表（不包含完整工作流数据）
    templates = {
        k: {
            "name": v["name"],
            "description": v["description"],
            "category": v["category"]
        }
        for k, v in WORKFLOW_TEMPLATES.items()
    }
    return {
        "templates": templates,
        "categories": list(set(t["category"] for t in WORKFLOW_TEMPLATES.values()))
    }


@router.get("/workflows/{template_id}")
async def get_workflow_template(template_id: str) -> dict[str, Any]:
    """获取单个工作流模板（包含完整数据）"""
    if template_id not in WORKFLOW_TEMPLATES:
        return {"error": "模板不存在"}
    return WORKFLOW_TEMPLATES[template_id]


@router.get("/samplers")
async def get_sampler_presets() -> dict[str, Any]:
    """获取采样器预设"""
    return {"presets": SAMPLER_PRESETS}


@router.get("/resolutions")
async def get_resolution_presets() -> dict[str, Any]:
    """获取分辨率预设"""
    return {"presets": RESOLUTION_PRESETS}


@router.get("/plugins")
async def get_popular_plugins() -> dict[str, Any]:
    """获取常用插件列表"""
    return {
        "plugins": POPULAR_PLUGINS,
        "categories": list(set(p["category"] for p in POPULAR_PLUGINS.values()))
    }


@router.get("/all")
async def get_all_templates() -> dict[str, Any]:
    """获取所有模板和预设"""
    return {
        "prompts": PROMPT_TEMPLATES,
        "workflows": {
            k: {
                "name": v["name"],
                "description": v["description"],
                "category": v["category"]
            }
            for k, v in WORKFLOW_TEMPLATES.items()
        },
        "samplers": SAMPLER_PRESETS,
        "resolutions": RESOLUTION_PRESETS,
        "plugins": POPULAR_PLUGINS,
    }
