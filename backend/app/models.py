"""数据库模型"""
from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, JSON, Float, ForeignKey
from sqlalchemy.orm import relationship
from .database import Base


def utc_now():
    """获取当前 UTC 时间（兼容 Python 3.12+）"""
    return datetime.now(timezone.utc)


class Workflow(Base):
    """工作流模型"""
    __tablename__ = "workflows"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False, index=True)
    description = Column(Text, default="")
    workflow_data = Column(JSON, nullable=False)  # ComfyUI 工作流 JSON
    thumbnail = Column(Text, default="")  # Base64 缩略图
    category = Column(String(100), default="default")
    tags = Column(JSON, default=list)  # 标签列表
    is_favorite = Column(Boolean, default=False)
    is_default = Column(Boolean, default=False)  # 是否默认工作流
    created_at = Column(DateTime, default=utc_now)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now)


class WorkflowBackup(Base):
    """工作流备份模型"""
    __tablename__ = "workflow_backups"
    
    id = Column(Integer, primary_key=True, index=True)
    workflow_id = Column(Integer, index=True)
    name = Column(String(255), nullable=False)
    workflow_data = Column(JSON, nullable=False)
    backup_note = Column(Text, default="")
    created_at = Column(DateTime, default=utc_now)


class ExecutionHistory(Base):
    """执行历史模型"""
    __tablename__ = "execution_history"
    
    id = Column(Integer, primary_key=True, index=True)
    workflow_id = Column(Integer, index=True)
    prompt_id = Column(String(100), index=True)  # ComfyUI prompt ID
    status = Column(String(50), default="pending")  # pending, running, completed, failed
    result = Column(JSON, default=dict)
    error_message = Column(Text, default="")
    started_at = Column(DateTime, default=utc_now)
    completed_at = Column(DateTime, nullable=True)


class UserSettings(Base):
    """用户设置"""
    __tablename__ = "user_settings"
    
    id = Column(Integer, primary_key=True, index=True)
    key = Column(String(100), unique=True, nullable=False, index=True)
    value = Column(JSON, nullable=False)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now)


class ComfyUIServer(Base):
    """ComfyUI 服务器配置"""
    __tablename__ = "comfyui_servers"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)  # 服务器名称
    url = Column(String(255), nullable=False)  # 服务器地址
    is_local = Column(Boolean, default=True)  # 是否本地服务器
    is_default = Column(Boolean, default=False)  # 是否默认服务器
    is_active = Column(Boolean, default=True)  # 是否启用
    description = Column(Text, default="")  # 描述
    created_at = Column(DateTime, default=utc_now)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now)


class SavedPrompt(Base):
    """保存的 Prompt 模板"""
    __tablename__ = "saved_prompts"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False, index=True)
    positive = Column(Text, nullable=False)  # 正向提示词
    negative = Column(Text, default="")  # 负向提示词
    category = Column(String(100), default="自定义", index=True)
    tags = Column(JSON, default=list)  # 标签
    source = Column(String(50), default="manual")  # manual, extracted, imported, online:civitai
    source_workflow_id = Column(Integer, nullable=True)  # 来源工作流ID
    source_image = Column(String(500), default="")  # 来源图片 URL
    use_count = Column(Integer, default=0)  # 使用次数
    is_favorite = Column(Boolean, default=False)
    rating = Column(Integer, default=0)  # 评分: -1=踩, 0=未评, 1=赞
    # 生成参数元数据
    model = Column(String(255), default="")  # 模型名称
    sampler = Column(String(100), default="")  # 采样器
    steps = Column(Integer, default=0)  # 步数
    cfg = Column(Float, default=0)  # CFG Scale
    seed = Column(Integer, default=0)  # 种子
    width = Column(Integer, default=0)  # 宽度
    height = Column(Integer, default=0)  # 高度
    created_at = Column(DateTime, default=utc_now)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now)
    
    # 关联图片
    images = relationship("StoredImage", back_populates="prompt")


class WorkflowVersion(Base):
    """工作流版本历史"""
    __tablename__ = "workflow_versions"
    
    id = Column(Integer, primary_key=True, index=True)
    workflow_id = Column(Integer, ForeignKey("workflows.id"), nullable=False, index=True)
    version = Column(String(20), nullable=False)  # v1.0, v1.1, etc.
    workflow_data = Column(JSON, nullable=False)
    change_note = Column(Text, default="")  # 变更说明
    change_type = Column(String(20), default="manual")  # manual, auto
    author = Column(String(100), default="")
    created_at = Column(DateTime, default=utc_now)


class BatchTask(Base):
    """批处理任务"""
    __tablename__ = "batch_tasks"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    workflow_id = Column(Integer, ForeignKey("workflows.id"), nullable=True)
    status = Column(String(20), default="pending")  # pending, running, paused, completed, failed
    priority = Column(Integer, default=5)  # 1-10, 10 最高
    total_count = Column(Integer, default=0)  # 总任务数
    completed_count = Column(Integer, default=0)  # 已完成数
    failed_count = Column(Integer, default=0)  # 失败数
    variables = Column(JSON, default=dict)  # 变量配置
    config = Column(JSON, default=dict)  # 执行配置
    result = Column(JSON, default=dict)  # 执行结果
    error_message = Column(Text, default="")
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=utc_now)


class ModelInfo(Base):
    """模型信息缓存"""
    __tablename__ = "model_info"
    
    id = Column(Integer, primary_key=True, index=True)
    filename = Column(String(255), nullable=False, unique=True, index=True)
    model_type = Column(String(50), nullable=False)  # checkpoint, lora, vae, embedding, controlnet, upscale
    name = Column(String(255), default="")
    description = Column(Text, default="")
    base_model = Column(String(50), default="")  # SD1.5, SDXL, etc.
    size = Column(Integer, default=0)  # 文件大小 bytes
    hash = Column(String(64), default="")  # SHA256 hash
    preview_image = Column(Text, default="")  # Base64 预览图
    civitai_id = Column(String(50), default="")  # Civitai 模型 ID
    civitai_version_id = Column(String(50), default="")
    tags = Column(JSON, default=list)
    use_count = Column(Integer, default=0)
    is_favorite = Column(Boolean, default=False)
    created_at = Column(DateTime, default=utc_now)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now)


class PerformanceLog(Base):
    """性能日志"""
    __tablename__ = "performance_logs"
    
    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, default=utc_now, index=True)
    gpu_usage = Column(Float, default=0)  # GPU 使用率 %
    vram_used = Column(Float, default=0)  # 显存使用 GB
    vram_total = Column(Float, default=0)  # 显存总量 GB
    cpu_usage = Column(Float, default=0)  # CPU 使用率 %
    ram_used = Column(Float, default=0)  # 内存使用 GB
    ram_total = Column(Float, default=0)  # 内存总量 GB
    temperature = Column(Float, default=0)  # GPU 温度
    queue_size = Column(Integer, default=0)  # 队列大小


class MarketplaceWorkflow(Base):
    """工作流市场"""
    __tablename__ = "marketplace_workflows"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False, index=True)
    description = Column(Text, default="")
    author = Column(String(100), default="")
    workflow_data = Column(JSON, nullable=False)
    thumbnail = Column(Text, default="")
    preview_images = Column(JSON, default=list)  # 预览图列表
    category = Column(String(100), default="")
    tags = Column(JSON, default=list)
    base_model = Column(String(50), default="")  # SD1.5, SDXL
    dependencies = Column(JSON, default=list)  # 依赖的模型列表
    price = Column(Float, default=0)  # 0 = 免费
    download_count = Column(Integer, default=0)
    rating = Column(Float, default=0)  # 平均评分
    rating_count = Column(Integer, default=0)  # 评分数
    is_featured = Column(Boolean, default=False)  # 是否精选
    source = Column(String(50), default="local")  # local, civitai, etc.
    source_url = Column(String(500), default="")
    created_at = Column(DateTime, default=utc_now)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now)


class StoredImage(Base):
    """存储的图片"""
    __tablename__ = "stored_images"
    
    id = Column(Integer, primary_key=True, index=True)
    filename = Column(String(255), nullable=False, index=True)  # 原始文件名
    original_path = Column(String(500), default="")  # ComfyUI 原始路径
    comfyui_prompt_id = Column(String(100), default="", index=True)  # ComfyUI 执行的 prompt_id
    
    # 块存储字段
    block_id = Column(Integer, nullable=False)
    offset = Column(Integer, nullable=False)
    size = Column(Integer, nullable=False)
    
    # 图片信息
    width = Column(Integer, nullable=True)
    height = Column(Integer, nullable=True)
    mimetype = Column(String(100), default="image/png")
    content_hash = Column(String(32), nullable=True, index=True)  # MD5 哈希值，用于内容去重
    
    # Prompt 信息
    positive = Column(Text, default="")
    negative = Column(Text, default="")
    
    # 关联到 SavedPrompt（可选）
    prompt_id = Column(Integer, ForeignKey("saved_prompts.id"), nullable=True, index=True)
    prompt = relationship("SavedPrompt", back_populates="images")
    
    # 生成参数
    seed = Column(Integer, nullable=True)
    steps = Column(Integer, nullable=True)
    cfg = Column(Float, nullable=True)
    sampler = Column(String(100), default="")
    model = Column(String(255), default="")
    
    # 时间戳
    created_at = Column(DateTime, default=utc_now)
    
    # 状态
    is_deleted = Column(Boolean, default=False)


class SmartCreateTask(Base):
    """智能创作任务"""
    __tablename__ = "smart_create_tasks"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False, index=True)
    template_type = Column(String(50), nullable=False)  # novel_storyboard, character_multiview, video_storyboard, scene_multiview, fashion_design, comic_series
    status = Column(String(20), default="pending")  # pending, analyzing, generating, paused, completed, failed
    
    # 输入内容
    input_content = Column(Text, default="")  # 用户输入的文本内容
    style = Column(String(100), default="")  # 画面风格
    
    # 生成配置
    target_count = Column(Integer, default=0)  # 目标生成数量 (0=AI自动分析)
    image_size = Column(String(50), default="1024x768")  # 图片尺寸
    workflow_id = Column(Integer, ForeignKey("workflows.id"), nullable=True)
    config = Column(JSON, default=dict)  # 其他配置项
    
    # AI 分析结果
    analyzed_prompts = Column(JSON, default=list)  # AI 分析生成的提示词列表
    
    # 执行进度
    total_count = Column(Integer, default=0)  # 实际总数
    completed_count = Column(Integer, default=0)
    failed_count = Column(Integer, default=0)
    current_prompt_id = Column(String(100), default="")  # 当前执行的 ComfyUI prompt_id
    
    # 结果
    result_images = Column(JSON, default=list)  # 生成的图片列表
    error_message = Column(Text, default="")
    
    # 时间戳
    created_at = Column(DateTime, default=utc_now)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
