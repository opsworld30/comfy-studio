"""
自动迁移服务 - 监听 ComfyUI 生成完成后自动迁移图片
"""
import asyncio
import logging
import os
from pathlib import Path
from typing import Optional

from sqlalchemy import select

from ..config import get_settings
from ..database import async_session
from datetime import datetime, timezone
from ..models import UserSettings, ExecutionHistory, ComfyUIServer
from .image_storage import image_storage_service
from .comfyui import comfyui_service
from .prompt_extractor import prompt_extractor

settings = get_settings()
logger = logging.getLogger(__name__)

DEFAULT_COMFYUI_SETTINGS = {
    "url": "http://127.0.0.1:8188",
    "output_dir": "",
    "auto_migrate": True,
    "delete_original": True,
}


class AutoMigrateService:
    """自动迁移服务"""
    
    def __init__(self):
        self._task: Optional[asyncio.Task] = None
        self._running = False
        self._processed_prompts: set[str] = set()  # 已处理的 prompt_id
        self._max_processed = 1000  # 最多记录 1000 个已处理的 ID
    
    async def _get_settings(self) -> dict:
        """从数据库获取 ComfyUI 设置"""
        try:
            async with async_session() as db:
                result = await db.execute(
                    select(UserSettings).where(UserSettings.key == "comfyui_settings")
                )
                settings = result.scalar_one_or_none()
                if settings:
                    return {**DEFAULT_COMFYUI_SETTINGS, **settings.value}
        except Exception as e:
            logger.warning("获取设置失败: %s", e)
        return DEFAULT_COMFYUI_SETTINGS
    
    async def start(self):
        """启动自动迁移服务"""
        if self._running:
            logger.info("自动迁移服务已在运行中")
            return
        
        self._running = True
        self._task = asyncio.create_task(self._watch_loop())
        logger.info("🚀 自动迁移服务已启动 - 监听 ComfyUI WebSocket")
    
    async def stop(self):
        """停止服务"""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("自动迁移服务已停止")
    
    async def _get_comfyui_url(self) -> str:
        """从数据库获取当前活动的 ComfyUI URL"""
        try:
            async with async_session() as db:
                # 优先获取默认服务器
                result = await db.execute(
                    select(ComfyUIServer)
                    .where(ComfyUIServer.is_default == True)
                    .where(ComfyUIServer.is_active == True)
                )
                server = result.scalar_one_or_none()
                
                if not server:
                    # 没有默认服务器，获取第一个活动的
                    result = await db.execute(
                        select(ComfyUIServer)
                        .where(ComfyUIServer.is_active == True)
                        .order_by(ComfyUIServer.created_at)
                        .limit(1)
                    )
                    server = result.scalar_one_or_none()
                
                if server:
                    return server.url
        except Exception as e:
            logger.warning("获取 ComfyUI URL 失败: %s", e)
        
        return DEFAULT_COMFYUI_SETTINGS["url"]
    
    async def _watch_loop(self):
        """监听 ComfyUI 执行完成 - 使用轮询方式"""
        logger.info("🚀 自动迁移服务启动 - 使用轮询模式监控执行完成")
        
        while self._running:
            try:
                # 获取历史记录，检查新完成的任务
                history = await comfyui_service.get_history()
                
                if history:
                    for prompt_id, data in history.items():
                        if prompt_id in self._processed_prompts:
                            continue
                        
                        # 检查是否有输出（表示已完成）
                        outputs = data.get("outputs", {})
                        if not outputs:
                            continue
                        
                        # 检查是否启用自动迁移
                        comfyui_settings = await self._get_settings()
                        if not comfyui_settings.get("auto_migrate", True):
                            self._processed_prompts.add(prompt_id)
                            continue
                        
                        logger.info("发现新完成的任务: %s", prompt_id)
                        
                        # 记录执行开始（如果还没记录）
                        await self._record_execution_start(prompt_id)
                        
                        # 迁移图片
                        migrated_count = await self._migrate_prompt_images(prompt_id, comfyui_settings)
                        
                        # 记录执行完成
                        await self._record_execution_complete(prompt_id, migrated_count)
                        
                        # 标记为已处理
                        self._processed_prompts.add(prompt_id)
                        
                        # 清理过多的记录
                        if len(self._processed_prompts) > self._max_processed:
                            to_remove = list(self._processed_prompts)[:self._max_processed // 2]
                            for pid in to_remove:
                                self._processed_prompts.discard(pid)
                
            except Exception as e:
                logger.debug("轮询检查失败: %s", e)
            
            # 每 5 秒检查一次
            if self._running:
                await asyncio.sleep(5)
    
    async def _handle_message(self, data: dict):
        """处理 WebSocket 消息"""
        msg_type = data.get("type", "")
        
        # 监听执行开始
        if msg_type == "execution_start":
            prompt_id = data.get("data", {}).get("prompt_id", "")
            if prompt_id:
                await self._record_execution_start(prompt_id)
        
        # 监听执行完成消息
        if msg_type == "executed":
            prompt_id = data.get("data", {}).get("prompt_id", "")
            if prompt_id and prompt_id not in self._processed_prompts:
                # 检查是否启用自动迁移
                comfyui_settings = await self._get_settings()
                if not comfyui_settings.get("auto_migrate", True):
                    return
                
                # 延迟一点确保图片已保存
                await asyncio.sleep(1)
                migrated_count = await self._migrate_prompt_images(prompt_id, comfyui_settings)
                
                # 记录执行完成
                await self._record_execution_complete(prompt_id, migrated_count)
                
                # 记录已处理
                self._processed_prompts.add(prompt_id)
                
                # 清理过多的记录
                if len(self._processed_prompts) > self._max_processed:
                    # 移除一半旧记录
                    to_remove = list(self._processed_prompts)[:self._max_processed // 2]
                    for pid in to_remove:
                        self._processed_prompts.discard(pid)
    
    async def _record_execution_start(self, prompt_id: str):
        """记录执行开始"""
        try:
            async with async_session() as db:
                # 检查是否已存在
                result = await db.execute(
                    select(ExecutionHistory).where(ExecutionHistory.prompt_id == prompt_id)
                )
                if result.scalar_one_or_none():
                    return
                
                history = ExecutionHistory(
                    prompt_id=prompt_id,
                    status="running",
                    started_at=datetime.now(timezone.utc)
                )
                db.add(history)
                await db.commit()
                logger.debug("记录执行开始: %s", prompt_id)
        except Exception as e:
            logger.error("记录执行开始失败: %s", e)
    
    async def _record_execution_complete(self, prompt_id: str, image_count: int = 0):
        """记录执行完成"""
        try:
            async with async_session() as db:
                result = await db.execute(
                    select(ExecutionHistory).where(ExecutionHistory.prompt_id == prompt_id)
                )
                history = result.scalar_one_or_none()
                
                if history:
                    history.status = "completed"
                    history.completed_at = datetime.now(timezone.utc)
                    history.result = {"image_count": image_count}
                else:
                    # 如果没有开始记录，创建一个完成记录
                    history = ExecutionHistory(
                        prompt_id=prompt_id,
                        status="completed",
                        started_at=datetime.now(timezone.utc),
                        completed_at=datetime.now(timezone.utc),
                        result={"image_count": image_count}
                    )
                    db.add(history)
                
                await db.commit()
                logger.debug("记录执行完成: %s, 图片数: %d", prompt_id, image_count)
        except Exception as e:
            logger.error("记录执行完成失败: %s", e)
    
    async def _migrate_prompt_images(self, prompt_id: str, comfyui_settings: dict) -> int:
        """迁移指定 prompt_id 的图片，返回迁移的图片数量"""
        try:
            # 获取该 prompt 的历史记录
            history = await comfyui_service.get_history(prompt_id)
            
            if not history or prompt_id not in history:
                return 0
            
            prompt_data = history[prompt_id]
            outputs = prompt_data.get("outputs", {})
            prompt_info = prompt_data.get("prompt", [])
            
            # 提取 prompt 信息
            positive = ""
            negative = ""
            model = ""
            sampler = ""
            steps = 0
            cfg = 0.0
            seed = 0
            
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
            
            migrated_count = 0
            
            # 遍历输出图片
            for _node_id, node_output in outputs.items():
                if "images" not in node_output:
                    continue
                
                for img in node_output["images"]:
                    filename = img.get("filename", "")
                    subfolder = img.get("subfolder", "")
                    folder_type = img.get("type", "output")
                    
                    # 存储图片
                    stored = await image_storage_service.store_new_image_from_comfyui(
                        filename=filename,
                        subfolder=subfolder,
                        folder_type=folder_type,
                        prompt_info={
                            "positive": positive,
                            "negative": negative,
                            "seed": seed,
                            "steps": steps,
                            "cfg": cfg,
                            "sampler": sampler,
                            "model": model,
                        },
                        comfyui_prompt_id=prompt_id,
                    )
                    
                    if stored:
                        migrated_count += 1
                        
                        # 尝试匹配并关联 Prompt
                        await image_storage_service.match_and_link_prompt(stored["id"], positive, filename)
                        
                        # 删除 ComfyUI 原图
                        output_dir = comfyui_settings.get("output_dir", "")
                        delete_original = comfyui_settings.get("delete_original", True)
                        
                        logger.info("删除配置: output_dir=%s, delete_original=%s", output_dir, delete_original)
                        
                        if output_dir and delete_original:
                            try:
                                original_path = Path(output_dir)
                                if subfolder:
                                    original_path = original_path / subfolder
                                original_path = original_path / filename
                                
                                logger.info("尝试删除: %s, 存在=%s", original_path, original_path.exists())
                                
                                if original_path.exists():
                                    os.remove(original_path)
                                    logger.info("已删除原图: %s", original_path)
                                else:
                                    logger.warning("原图不存在: %s", original_path)
                            except Exception as e:
                                logger.warning("删除原图失败 %s: %s", filename, e)
            
            if migrated_count > 0:
                logger.info("自动迁移完成: prompt_id=%s, 迁移 %d 张图片", prompt_id, migrated_count)
            
            return migrated_count
                
        except Exception as e:
            logger.error("自动迁移失败 prompt_id=%s: %s", prompt_id, e)
            return 0


# 全局实例
auto_migrate_service = AutoMigrateService()
