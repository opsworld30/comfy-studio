"""Pydantic 模式"""
from datetime import datetime
from pydantic import BaseModel, Field
from typing import Any


# ========== Workflow Schemas ==========

class WorkflowBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: str = ""
    workflow_data: dict[str, Any]
    thumbnail: str = ""
    category: str = "default"
    tags: list[str] = []
    is_favorite: bool = False
    is_default: bool = False


class WorkflowCreate(WorkflowBase):
    pass


class WorkflowUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    workflow_data: dict[str, Any] | None = None
    thumbnail: str | None = None
    category: str | None = None
    tags: list[str] | None = None
    is_favorite: bool | None = None
    is_default: bool | None = None


class WorkflowResponse(WorkflowBase):
    id: int
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class WorkflowListResponse(BaseModel):
    id: int
    name: str
    description: str
    workflow_data: dict[str, Any]
    thumbnail: str
    category: str
    tags: list[str]
    is_favorite: bool
    is_default: bool
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


# ========== Backup Schemas ==========

class BackupCreate(BaseModel):
    backup_note: str = ""


class BackupResponse(BaseModel):
    id: int
    workflow_id: int
    name: str
    backup_note: str
    created_at: datetime
    
    class Config:
        from_attributes = True


# ========== Execution Schemas ==========

class ExecuteWorkflowRequest(BaseModel):
    workflow_data: dict[str, Any] | None = None  # 可选，不传则使用保存的工作流


class ExecutionResponse(BaseModel):
    id: int
    workflow_id: int
    prompt_id: str
    status: str
    result: dict[str, Any]
    error_message: str
    started_at: datetime
    completed_at: datetime | None
    workflow_name: str | None = None
    
    class Config:
        from_attributes = True


class ExecutionListResponse(BaseModel):
    id: int
    workflow_id: int
    prompt_id: str
    status: str
    started_at: datetime
    completed_at: datetime | None
    workflow_name: str | None = None
    
    class Config:
        from_attributes = True


class ImageInfo(BaseModel):
    filename: str
    subfolder: str = ""
    type: str = "output"


class ExecutionProgress(BaseModel):
    prompt_id: str
    node: str | None = None
    max: int = 0
    value: int = 0
    status: str = "pending"  # pending, running, completed, failed


class QueueItem(BaseModel):
    prompt_id: str
    workflow_id: int | None = None
    workflow_name: str | None = None
    number: int = 0


# ========== ComfyUI Schemas ==========

class ComfyUIStatus(BaseModel):
    connected: bool
    queue_remaining: int = 0
    system_stats: dict[str, Any] = {}


# ========== Settings Schemas ==========

class PageModuleSettings(BaseModel):
    """页面模块显示设置"""
    # 页面显示控制
    pages: dict[str, bool] = {
        "showDashboard": True,
        "showWorkflows": True,
        "showGallery": True,
        "showPrompts": True,
        "showModels": False,
        "showMarket": False,
        "showMonitor": True,
        "showBatch": True,
        "showSettings": True,
    }
    # 仪表盘页面
    dashboard: dict[str, bool] = {
        "showQuickActions": True,
        "showRecentImages": True,
        "showSystemStatus": True,
        "showStatistics": True,
    }
    # 工作流页面
    workflows: dict[str, bool] = {
        "showCategories": True,
        "showFavorites": True,
        "showSearch": True,
    }
    # 图片画廊页面
    gallery: dict[str, bool] = {
        "showSearchBar": True,
        "showLayoutToggle": True,
        "showCategories": True,
        "showFavorites": True,
    }
    # 提示词页面
    prompts: dict[str, bool] = {
        "showCategories": True,
        "showAIGenerate": True,
        "showFavorites": True,
    }
    # 模型页面
    models: dict[str, bool] = {
        "showLocalModels": True,
        "showCivitai": True,
    }
    # 执行监控页面
    monitor: dict[str, bool] = {
        "showSystemStatus": True,
        "showExecutionQueue": True,
        "showPerformanceChart": True,
        "showExecutionHistory": True,
    }
    # 批处理页面
    batch: dict[str, bool] = {
        "showPending": True,
        "showRunning": True,
        "showCompleted": True,
        "showFailed": True,
    }


class AISettings(BaseModel):
    """AI 配置"""
    api_key: str = ""
    api_url: str = "https://openrouter.ai/api/v1"
    model: str = "google/gemini-2.0-flash-exp:free"
    enabled: bool = False


class PromptOptimizeRequest(BaseModel):
    """Prompt 优化请求"""
    prompt: str
    action: str = "optimize"  # optimize, translate, expand, negative, style
    style: str | None = None  # 风格转换时使用


class PromptOptimizeResponse(BaseModel):
    """Prompt 优化响应"""
    original: str
    optimized: str
    action: str


class SettingsResponse(BaseModel):
    key: str
    value: dict[str, Any]
    updated_at: datetime | None = None
    
    class Config:
        from_attributes = True


# ========== Export/Import Schemas ==========

class ExportData(BaseModel):
    version: str = "1.0"
    exported_at: datetime
    workflows: list[WorkflowResponse]


class ImportResult(BaseModel):
    success: int
    failed: int
    errors: list[str]


# ========== ComfyUI Server Schemas ==========

class ComfyUIServerBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    url: str = Field(..., min_length=1, max_length=255)
    is_local: bool = True
    is_default: bool = False
    is_active: bool = True
    description: str = ""


class ComfyUIServerCreate(ComfyUIServerBase):
    pass


class ComfyUIServerUpdate(BaseModel):
    name: str | None = None
    url: str | None = None
    is_local: bool | None = None
    is_default: bool | None = None
    is_active: bool | None = None
    description: str | None = None


class ComfyUIServerResponse(ComfyUIServerBase):
    id: int
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True
