"""路由模块"""
from .workflows import router as workflows_router
from .comfyui import router as comfyui_router
from .templates import router as templates_router
from .prompts import router as prompts_router

__all__ = ["workflows_router", "comfyui_router", "templates_router", "prompts_router"]
