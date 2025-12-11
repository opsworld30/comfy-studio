"""
图片存储服务 - 管理图片的存储、迁移和获取
"""
import asyncio
import hashlib
import logging
import os
from io import BytesIO
from pathlib import Path
from typing import Optional

from PIL import Image
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import StoredImage, SavedPrompt
from ..database import async_session
from .storage import storage_service
from .comfyui import comfyui_service

logger = logging.getLogger(__name__)


class ImageStorageService:
    """图片存储服务"""
    
    def __init__(self):
        self._migration_running = False
        self._watch_task: Optional[asyncio.Task] = None
    
    async def store_image(
        self,
        image_data: bytes,
        filename: str,
        original_path: str = "",
        comfyui_prompt_id: str = "",
        prompt_id: int = None,
        positive: str = "",
        negative: str = "",
        seed: int = None,
        steps: int = None,
        cfg: float = None,
        sampler: str = "",
        model: str = "",
    ) -> Optional[dict]:
        """
        存储图片到块存储
        
        Returns:
            包含 id, filename, positive 的字典
        """
        # 获取图片尺寸
        width, height = None, None
        try:
            with Image.open(BytesIO(image_data)) as img:
                width, height = img.size
        except Exception as e:
            logger.warning(f"无法获取图片尺寸: {e}")
        
        # 确定 MIME 类型
        ext = Path(filename).suffix.lower()
        mimetype_map = {
            ".png": "image/png",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".webp": "image/webp",
            ".gif": "image/gif",
        }
        mimetype = mimetype_map.get(ext, "image/png")
        
        # 计算内容哈希值
        content_hash = hashlib.md5(image_data).hexdigest()
        
        # 写入块存储
        block_id, offset, size = storage_service.write_file(image_data)
        
        # 创建数据库记录
        async with async_session() as db:
            stored_image = StoredImage(
                filename=filename,
                original_path=original_path,
                comfyui_prompt_id=comfyui_prompt_id,
                prompt_id=prompt_id,
                block_id=block_id,
                offset=offset,
                size=size,
                width=width,
                height=height,
                mimetype=mimetype,
                content_hash=content_hash,
                positive=positive,
                negative=negative,
                seed=seed,
                steps=steps,
                cfg=cfg,
                sampler=sampler,
                model=model,
            )
            db.add(stored_image)
            await db.commit()
            
            # 获取 ID 后再返回，避免 session 关闭后无法访问
            image_id = stored_image.id
            
            logger.info(f"图片已存储: {filename} (id={image_id}) -> block_{block_id}, offset={offset}, size={size}")
            
            # 返回一个简单的数据结构，而不是 ORM 对象
            return {
                "id": image_id,
                "filename": filename,
                "positive": positive,
            }
    
    async def get_image(self, image_id: int) -> Optional[tuple[bytes, str]]:
        """
        获取图片数据
        
        Returns:
            Tuple[image_data, mimetype] 或 None
        """
        async with async_session() as db:
            result = await db.execute(
                select(StoredImage).where(
                    StoredImage.id == image_id,
                    StoredImage.is_deleted.is_(False)
                )
            )
            image = result.scalar_one_or_none()
            
            if not image:
                return None
            
            data = storage_service.read_file(image.block_id, image.offset, image.size)
            return data, image.mimetype
    
    async def get_image_by_filename(self, filename: str) -> Optional[tuple[bytes, str]]:
        """
        根据文件名获取图片
        
        Returns:
            Tuple[image_data, mimetype] 或 None
        """
        async with async_session() as db:
            result = await db.execute(
                select(StoredImage).where(
                    StoredImage.filename == filename,
                    StoredImage.is_deleted.is_(False)
                ).order_by(desc(StoredImage.created_at))
            )
            image = result.scalar_one_or_none()
            
            if not image:
                return None
            
            data = storage_service.read_file(image.block_id, image.offset, image.size)
            return data, image.mimetype
    
    async def list_images(
        self,
        limit: int = 100,
        offset: int = 0,
        db: AsyncSession = None,
    ) -> list[StoredImage]:
        """获取图片列表"""
        if db is None:
            async with async_session() as db:
                result = await db.execute(
                    select(StoredImage)
                    .where(StoredImage.is_deleted.is_(False))
                    .order_by(desc(StoredImage.created_at))
                    .offset(offset)
                    .limit(limit)
                )
                return list(result.scalars().all())
        else:
            result = await db.execute(
                select(StoredImage)
                .where(StoredImage.is_deleted.is_(False))
                .order_by(desc(StoredImage.created_at))
                .offset(offset)
                .limit(limit)
            )
            return list(result.scalars().all())
    
    async def migrate_from_comfyui(self, delete_original: bool = True) -> dict:
        """
        从 ComfyUI 迁移现有图片
        
        Args:
            delete_original: 是否删除原始文件
            
        Returns:
            迁移统计信息
        """
        if self._migration_running:
            return {"error": "迁移正在进行中"}
        
        self._migration_running = True
        stats = {
            "total": 0,
            "migrated": 0,
            "skipped": 0,
            "failed": 0,
            "deleted": 0,
        }
        
        try:
            # 获取 ComfyUI 输出目录
            comfyui_url = comfyui_service.base_url
            # 从 system_stats 获取输出目录路径不太可靠，直接获取历史图片
            
            # 获取所有历史图片
            images = await comfyui_service.get_recent_images_with_prompt(limit=1000)
            stats["total"] = len(images)
            
            logger.info(f"开始迁移 {len(images)} 张图片...")
            
            for img_info in images:
                try:
                    filename = img_info.get("filename", "")
                    subfolder = img_info.get("subfolder", "")
                    folder_type = img_info.get("type", "output")
                    
                    # 检查是否已迁移
                    async with async_session() as db:
                        result = await db.execute(
                            select(StoredImage)
                            .where(StoredImage.filename == filename)
                            .limit(1)
                        )
                        if result.scalar_one_or_none():
                            stats["skipped"] += 1
                            continue
                    
                    # 获取图片数据
                    image_data = await comfyui_service.get_image(filename, subfolder, folder_type)
                    if not image_data:
                        stats["failed"] += 1
                        continue
                    
                    # 尝试匹配 Prompt
                    matched_prompt_id = None
                    positive = img_info.get("positive", "")
                    if positive and len(positive) >= 20:
                        async with async_session() as db:
                            search_text = positive[:50]
                            result = await db.execute(
                                select(SavedPrompt)
                                .where(SavedPrompt.positive.contains(search_text))
                                .limit(1)
                            )
                            matched_prompt = result.scalar_one_or_none()
                            if matched_prompt:
                                matched_prompt_id = matched_prompt.id
                    
                    # 存储图片
                    await self.store_image(
                        image_data=image_data,
                        filename=filename,
                        original_path=f"{subfolder}/{filename}" if subfolder else filename,
                        comfyui_prompt_id=img_info.get("prompt_id", ""),
                        prompt_id=matched_prompt_id,
                        positive=positive,
                        negative=img_info.get("negative", ""),
                        seed=img_info.get("seed"),
                        steps=img_info.get("steps"),
                        cfg=img_info.get("cfg"),
                        sampler=img_info.get("sampler", ""),
                        model=img_info.get("model", ""),
                    )
                    stats["migrated"] += 1
                    if matched_prompt_id:
                        stats["linked"] = stats.get("linked", 0) + 1
                    
                    # 删除原始文件
                    if delete_original:
                        try:
                            # 从数据库获取 ComfyUI 输出目录配置
                            async with async_session() as db:
                                from ..models import UserSettings
                                result = await db.execute(
                                    select(UserSettings).where(UserSettings.key == "comfyui_settings")
                                )
                                settings = result.scalar_one_or_none()
                                output_dir = ""
                                if settings and settings.value:
                                    output_dir = settings.value.get("output_dir", "")
                                
                                if output_dir:
                                    original_path = Path(output_dir)
                                    if subfolder:
                                        original_path = original_path / subfolder
                                    original_path = original_path / filename
                                    
                                    if original_path.exists():
                                        os.remove(original_path)
                                        stats["deleted"] = stats.get("deleted", 0) + 1
                                        logger.info(f"已删除原图: {original_path}")
                        except Exception as del_e:
                            logger.warning(f"删除原图失败 {filename}: {del_e}")
                    
                except Exception as e:
                    logger.error(f"迁移图片 {img_info.get('filename', 'unknown')} 失败: {e}")
                    stats["failed"] += 1
            
            logger.info(f"迁移完成: {stats}")
            return stats
            
        finally:
            self._migration_running = False
    
    async def store_new_image_from_comfyui(
        self,
        filename: str,
        subfolder: str = "",
        folder_type: str = "output",
        prompt_info: dict = None,
        comfyui_prompt_id: str = "",
    ) -> Optional[dict]:
        """
        从 ComfyUI 获取新生成的图片并存储
        
        Args:
            filename: 文件名
            subfolder: 子文件夹
            folder_type: 文件夹类型
            prompt_info: Prompt 信息
            comfyui_prompt_id: ComfyUI 执行的 prompt_id
            
        Returns:
            StoredImage 或 None
        """
        try:
            # 获取图片数据
            image_data = await comfyui_service.get_image(filename, subfolder, folder_type)
            if not image_data:
                logger.warning(f"无法获取图片: {filename}")
                return None
            
            # 计算图片内容的 MD5 哈希值
            image_hash = hashlib.md5(image_data).hexdigest()
            
            # 优先通过 content_hash 检查是否已存储（最准确的去重方式）
            async with async_session() as db:
                result = await db.execute(
                    select(StoredImage)
                    .where(StoredImage.content_hash == image_hash)
                    .limit(1)
                )
                existing_by_hash = result.scalar_one_or_none()
                if existing_by_hash:
                    logger.debug(f"图片已存在（内容相同）: {filename} -> {existing_by_hash.filename} (id={existing_by_hash.id}, hash={image_hash[:8]}...)")
                    return None
                
                # 检查文件名是否冲突
                result = await db.execute(
                    select(StoredImage)
                    .where(StoredImage.filename == filename)
                    .limit(1)
                )
                existing_by_name = result.scalar_one_or_none()
                if existing_by_name:
                    # 文件名冲突，生成新的文件名
                    base_name = Path(filename).stem
                    ext = Path(filename).suffix
                    filename = f"{base_name}_{image_hash[:8]}{ext}"
                    logger.info(f"文件名冲突，使用新文件名: {filename}")
            
            # 提取 prompt 信息
            positive = ""
            negative = ""
            seed = None
            steps = None
            cfg = None
            sampler = ""
            model = ""
            
            if prompt_info:
                positive = prompt_info.get("positive", "")
                negative = prompt_info.get("negative", "")
                seed = prompt_info.get("seed")
                steps = prompt_info.get("steps")
                cfg = prompt_info.get("cfg")
                sampler = prompt_info.get("sampler", "")
                model = prompt_info.get("model", "")
            
            # 存储图片
            stored = await self.store_image(
                image_data=image_data,
                filename=filename,
                original_path=f"{subfolder}/{filename}" if subfolder else filename,
                comfyui_prompt_id=comfyui_prompt_id,
                positive=positive,
                negative=negative,
                seed=seed,
                steps=steps,
                cfg=cfg,
                sampler=sampler,
                model=model,
            )
            
            return stored
            
        except Exception as e:
            logger.error(f"存储新图片失败 {filename}: {e}")
            return None
    
    async def get_images_by_prompt_id(self, prompt_id: int, limit: int = 50) -> list[StoredImage]:
        """
        获取指定 Prompt 关联的图片
        
        Args:
            prompt_id: SavedPrompt ID
            limit: 最大返回数量
            
        Returns:
            图片列表
        """
        async with async_session() as db:
            result = await db.execute(
                select(StoredImage)
                .where(
                    StoredImage.prompt_id == prompt_id,
                    StoredImage.is_deleted.is_(False)
                )
                .order_by(desc(StoredImage.created_at))
                .limit(limit)
            )
            return list(result.scalars().all())
    
    async def get_images_by_positive(self, positive: str, limit: int = 50) -> list[StoredImage]:
        """
        根据正向提示词匹配图片（模糊匹配）
        
        Args:
            positive: 正向提示词
            limit: 最大返回数量
            
        Returns:
            图片列表
        """
        if not positive or len(positive) < 20:
            return []
        
        # 取前 50 个字符进行匹配
        search_text = positive[:50]
        
        async with async_session() as db:
            result = await db.execute(
                select(StoredImage)
                .where(
                    StoredImage.positive.contains(search_text),
                    StoredImage.is_deleted.is_(False)
                )
                .order_by(desc(StoredImage.created_at))
                .limit(limit)
            )
            return list(result.scalars().all())
    
    async def match_and_link_prompt(self, image_id: int, positive: str, filename: str = "") -> Optional[int]:
        """
        根据图片的 positive 匹配 SavedPrompt 并建立关联
        
        Args:
            image_id: StoredImage ID
            positive: 正向提示词
            filename: 文件名（用于日志）
            
        Returns:
            匹配到的 prompt_id 或 None
        """
        if not positive or len(positive) < 20:
            return None
        
        search_text = positive[:50]
        
        async with async_session() as db:
            # 查找匹配的 Prompt
            result = await db.execute(
                select(SavedPrompt)
                .where(SavedPrompt.positive.contains(search_text))
                .limit(1)
            )
            prompt = result.scalar_one_or_none()
            
            if prompt:
                # 更新图片的 prompt_id
                image_result = await db.execute(
                    select(StoredImage).where(StoredImage.id == image_id)
                )
                db_image = image_result.scalar_one_or_none()
                if db_image:
                    db_image.prompt_id = prompt.id
                    await db.commit()
                    logger.info(f"图片 {filename} 已关联到 Prompt: {prompt.name}")
                    return prompt.id
        
        return None
    
    async def auto_migrate_new_images(self, delete_original: bool = True) -> dict:
        """
        自动迁移 ComfyUI 中的新图片
        
        Args:
            delete_original: 是否删除原始文件
            
        Returns:
            迁移统计
        """
        from .prompt_extractor import prompt_extractor
        
        stats = {
            "checked": 0,
            "migrated": 0,
            "linked": 0,
            "deleted": 0,
        }
        
        # 获取 ComfyUI 输出目录配置
        output_dir = ""
        if delete_original:
            try:
                async with async_session() as db:
                    from ..models import UserSettings
                    result = await db.execute(
                        select(UserSettings).where(UserSettings.key == "comfyui_settings")
                    )
                    settings = result.scalar_one_or_none()
                    if settings and settings.value:
                        output_dir = settings.value.get("output_dir", "")
            except Exception as e:
                logger.warning(f"获取 ComfyUI 设置失败: {e}")
        
        try:
            # 获取 ComfyUI 历史记录
            history = await comfyui_service.get_history()
            
            for comfyui_prompt_id, prompt_data in history.items():
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
                
                # 遍历输出图片
                for node_id, node_output in outputs.items():
                    if "images" not in node_output:
                        continue
                    
                    for img in node_output["images"]:
                        filename = img.get("filename", "")
                        subfolder = img.get("subfolder", "")
                        folder_type = img.get("type", "output")
                        
                        stats["checked"] += 1
                        
                        # 检查是否已存储
                        async with async_session() as db:
                            result = await db.execute(
                                select(StoredImage)
                                .where(StoredImage.filename == filename)
                                .limit(1)
                            )
                            if result.scalar_one_or_none():
                                continue
                        
                        # 获取图片数据
                        image_data = await comfyui_service.get_image(filename, subfolder, folder_type)
                        if not image_data:
                            continue
                        
                        # 尝试匹配 Prompt
                        matched_prompt_id = None
                        if positive:
                            async with async_session() as db:
                                search_text = positive[:50] if len(positive) >= 50 else positive
                                result = await db.execute(
                                    select(SavedPrompt)
                                    .where(SavedPrompt.positive.contains(search_text))
                                    .limit(1)
                                )
                                matched_prompt = result.scalar_one_or_none()
                                if matched_prompt:
                                    matched_prompt_id = matched_prompt.id
                                    stats["linked"] += 1
                        
                        # 存储图片
                        stored = await self.store_image(
                            image_data=image_data,
                            filename=filename,
                            original_path=f"{subfolder}/{filename}" if subfolder else filename,
                            comfyui_prompt_id=comfyui_prompt_id,
                            prompt_id=matched_prompt_id,
                            positive=positive,
                            negative=negative,
                            seed=seed,
                            steps=steps,
                            cfg=cfg,
                            sampler=sampler,
                            model=model,
                        )
                        
                        if stored:
                            stats["migrated"] += 1
                            logger.info(f"已迁移图片: {filename}")
                            
                            # 删除原始文件
                            if delete_original and output_dir:
                                try:
                                    original_path = Path(output_dir)
                                    if subfolder:
                                        original_path = original_path / subfolder
                                    original_path = original_path / filename
                                    
                                    if original_path.exists():
                                        os.remove(original_path)
                                        stats["deleted"] += 1
                                        logger.info(f"已删除原图: {original_path}")
                                except Exception as del_e:
                                    logger.warning(f"删除原图失败 {filename}: {del_e}")
            
            return stats
            
        except Exception as e:
            logger.error(f"自动迁移失败: {e}")
            return {"error": str(e), **stats}


# 全局实例
image_storage_service = ImageStorageService()
