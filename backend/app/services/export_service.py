# export_service.py

"""
导出服务
- 批量导出图片
- 打包为 ZIP
- 生成提示词文档
- 可选水印和调整尺寸
"""

import os
import zipfile
import shutil
import json
import logging
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Dict, Any
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class ExportOptions:
    """导出选项"""
    format: str = "zip"  # "zip" | "folder"
    include_prompts: bool = True  # 包含提示词文件
    include_metadata: bool = True  # 包含元数据 JSON
    naming: str = "index"  # "index" | "title" | "both"
    add_watermark: bool = False
    watermark_text: str = ""
    resize: Optional[tuple] = None  # (width, height) 或 None
    quality: int = 95  # JPEG 质量
    convert_format: Optional[str] = None  # None | "png" | "jpg" | "webp"


class ExportService:
    """导出服务"""

    def __init__(self, output_dir: str = "./exports"):
        """
        初始化导出服务

        Args:
            output_dir: 导出文件存放目录
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    async def export_task(
        self,
        task_id: int,
        task_name: str,
        images: List[Dict[str, Any]],
        characters: List[Dict[str, Any]] = None,
        options: ExportOptions = None
    ) -> Dict[str, Any]:
        """
        导出任务结果

        Args:
            task_id: 任务 ID
            task_name: 任务名称
            images: 图片数据列表
            characters: 角色数据列表
            options: 导出选项

        Returns:
            {
                "success": bool,
                "path": str,
                "total_images": int,
                "exported_images": int,
                "file_size": int
            }
        """
        options = options or ExportOptions()

        # 生成导出目录名
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_name = self._sanitize_filename(task_name)[:30]
        export_name = f"{safe_name}_{task_id}_{timestamp}"
        export_path = self.output_dir / export_name
        export_path.mkdir(parents=True, exist_ok=True)

        exported_count = 0
        total_count = len(images)

        try:
            # 导出图片
            for img_data in images:
                if img_data.get("status") != "completed":
                    continue

                src_path = img_data.get("local_path")
                if not src_path or not os.path.exists(src_path):
                    continue

                # 生成文件名
                filename = self._generate_filename(img_data, options, exported_count)
                dst_path = export_path / filename

                # 处理图片
                success = await self._process_image(
                    src_path,
                    str(dst_path),
                    options
                )

                if success:
                    exported_count += 1

            # 导出提示词文件
            if options.include_prompts:
                await self._export_prompts(export_path, images)

            # 导出元数据
            if options.include_metadata:
                await self._export_metadata(
                    export_path,
                    task_id,
                    task_name,
                    images,
                    characters
                )

            # 打包为 ZIP
            final_path = str(export_path)
            file_size = 0

            if options.format == "zip":
                zip_path = self.output_dir / f"{export_name}.zip"
                await self._create_zip(export_path, zip_path)

                # 删除临时文件夹
                shutil.rmtree(export_path)

                final_path = str(zip_path)
                file_size = os.path.getsize(zip_path)
            else:
                # 计算文件夹大小
                file_size = sum(
                    f.stat().st_size
                    for f in export_path.rglob("*")
                    if f.is_file()
                )

            return {
                "success": True,
                "path": final_path,
                "total_images": total_count,
                "exported_images": exported_count,
                "file_size": file_size,
            }

        except Exception as e:
            logger.exception(f"导出失败: {e}")
            # 清理
            if export_path.exists():
                shutil.rmtree(export_path)

            return {
                "success": False,
                "error": str(e),
                "total_images": total_count,
                "exported_images": exported_count,
            }

    def _generate_filename(
        self,
        img_data: Dict,
        options: ExportOptions,
        index: int
    ) -> str:
        """生成文件名"""
        idx = img_data.get("index", index)
        title = img_data.get("title", "")

        # 获取扩展名
        original_path = img_data.get("local_path", "")
        original_ext = Path(original_path).suffix.lower() if original_path else ".png"

        if options.convert_format:
            ext = f".{options.convert_format}"
        else:
            ext = original_ext

        # 根据命名方式生成
        if options.naming == "title" and title:
            safe_title = self._sanitize_filename(title)[:50]
            return f"{idx:03d}_{safe_title}{ext}"
        elif options.naming == "both" and title:
            safe_title = self._sanitize_filename(title)[:30]
            return f"{idx:03d}_{safe_title}{ext}"
        else:
            return f"{idx:03d}{ext}"

    async def _process_image(
        self,
        src_path: str,
        dst_path: str,
        options: ExportOptions
    ) -> bool:
        """处理并保存图片"""
        try:
            from PIL import Image, ImageDraw, ImageFont

            img = Image.open(src_path)

            # 转换为 RGB（如果需要保存为 JPEG）
            if dst_path.lower().endswith(('.jpg', '.jpeg')):
                if img.mode in ('RGBA', 'P'):
                    img = img.convert('RGB')

            # 调整尺寸
            if options.resize:
                img = img.resize(options.resize, Image.LANCZOS)

            # 添加水印
            if options.add_watermark and options.watermark_text:
                img = self._add_watermark(img, options.watermark_text)

            # 保存
            save_kwargs = {}
            if dst_path.lower().endswith(('.jpg', '.jpeg')):
                save_kwargs['quality'] = options.quality
                save_kwargs['optimize'] = True
            elif dst_path.lower().endswith('.webp'):
                save_kwargs['quality'] = options.quality
            elif dst_path.lower().endswith('.png'):
                save_kwargs['optimize'] = True

            img.save(dst_path, **save_kwargs)
            return True

        except Exception as e:
            logger.error(f"处理图片失败 {src_path}: {e}")
            return False

    def _add_watermark(self, img, text: str):
        """添加水印"""
        from PIL import ImageDraw, ImageFont

        # 创建绘图对象
        draw = ImageDraw.Draw(img)

        # 尝试加载字体
        try:
            font_size = max(16, img.width // 40)
            font = ImageFont.truetype("arial.ttf", font_size)
        except:
            font = ImageFont.load_default()

        # 获取文字尺寸
        bbox = draw.textbbox((0, 0), text, font=font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]

        # 计算位置（右下角）
        padding = 10
        x = img.width - text_width - padding
        y = img.height - text_height - padding

        # 绘制半透明背景
        bg_padding = 5
        draw.rectangle(
            [x - bg_padding, y - bg_padding,
             x + text_width + bg_padding, y + text_height + bg_padding],
            fill=(0, 0, 0, 128)
        )

        # 绘制文字
        draw.text((x, y), text, fill=(255, 255, 255, 220), font=font)

        return img

    async def _export_prompts(self, export_path: Path, images: List[Dict]):
        """导出提示词文件"""
        prompts_file = export_path / "prompts.txt"

        with open(prompts_file, 'w', encoding='utf-8') as f:
            f.write("=" * 60 + "\n")
            f.write("AI 绘画提示词导出\n")
            f.write(f"导出时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write("=" * 60 + "\n\n")

            for img_data in images:
                index = img_data.get("index", 0)
                title = img_data.get("title", f"Image {index}")
                status = img_data.get("status", "unknown")

                f.write(f"--- [{index:03d}] {title} ({status}) ---\n\n")

                # 场景描述
                description = img_data.get("description", "")
                if description:
                    f.write(f"描述:\n{description}\n\n")

                # Positive
                positive = img_data.get("positive", "")
                if positive:
                    f.write(f"Positive:\n{positive}\n\n")

                # Negative
                negative = img_data.get("negative", "")
                if negative:
                    f.write(f"Negative:\n{negative}\n\n")

                # 场景信息
                scene = img_data.get("scene", {})
                if scene:
                    f.write("Scene:\n")
                    for key, value in scene.items():
                        f.write(f"  - {key}: {value}\n")
                    f.write("\n")

                f.write("\n")

    async def _export_metadata(
        self,
        export_path: Path,
        task_id: int,
        task_name: str,
        images: List[Dict],
        characters: List[Dict] = None
    ):
        """导出元数据 JSON"""
        metadata = {
            "task_id": task_id,
            "task_name": task_name,
            "export_time": datetime.now().isoformat(),
            "total_images": len(images),
            "completed_images": sum(1 for img in images if img.get("status") == "completed"),
            "characters": characters or [],
            "images": []
        }

        for img_data in images:
            # 移除本地路径（隐私考虑）
            img_export = {k: v for k, v in img_data.items() if k != "local_path"}
            metadata["images"].append(img_export)

        metadata_file = export_path / "metadata.json"
        with open(metadata_file, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, ensure_ascii=False, indent=2)

    async def _create_zip(self, source_dir: Path, zip_path: Path):
        """创建 ZIP 文件"""
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
            for file in source_dir.rglob("*"):
                if file.is_file():
                    arcname = file.relative_to(source_dir)
                    zf.write(file, arcname)

    def _sanitize_filename(self, filename: str) -> str:
        """清理文件名"""
        # 移除或替换不安全的字符
        unsafe_chars = '<>:"/\\|?*'
        for char in unsafe_chars:
            filename = filename.replace(char, '_')

        # 移除控制字符
        filename = ''.join(c for c in filename if c.isprintable())

        # 去除首尾空格和点
        filename = filename.strip().strip('.')

        return filename or "untitled"

    async def cleanup_old_exports(self, max_age_days: int = 7):
        """清理旧的导出文件"""
        import time

        now = time.time()
        max_age_seconds = max_age_days * 24 * 60 * 60

        cleaned = 0
        for item in self.output_dir.iterdir():
            try:
                if item.stat().st_mtime < now - max_age_seconds:
                    if item.is_file():
                        item.unlink()
                    elif item.is_dir():
                        shutil.rmtree(item)
                    cleaned += 1
            except Exception as e:
                logger.warning(f"清理失败 {item}: {e}")

        logger.info(f"清理了 {cleaned} 个过期导出文件")
        return cleaned


# 单例
export_service = ExportService()


# ============ 批量导出辅助函数 ============

async def export_task_results(
    task_id: int,
    task_name: str,
    images: List[Dict],
    characters: List[Dict] = None,
    format: str = "zip",
    include_prompts: bool = True,
    naming: str = "index",
    output_dir: str = "./exports"
) -> Dict[str, Any]:
    """
    便捷函数：导出任务结果

    Args:
        task_id: 任务 ID
        task_name: 任务名称
        images: 图片数据列表
        characters: 角色数据列表
        format: "zip" 或 "folder"
        include_prompts: 是否包含提示词
        naming: 命名方式 "index" | "title" | "both"
        output_dir: 输出目录

    Returns:
        导出结果
    """
    service = ExportService(output_dir)
    options = ExportOptions(
        format=format,
        include_prompts=include_prompts,
        naming=naming,
    )

    return await service.export_task(
        task_id=task_id,
        task_name=task_name,
        images=images,
        characters=characters,
        options=options
    )


async def export_single_image(
    image_path: str,
    output_path: str,
    resize: tuple = None,
    watermark: str = None,
    quality: int = 95
) -> bool:
    """
    便捷函数：导出单张图片
    """
    service = ExportService()
    options = ExportOptions(
        resize=resize,
        add_watermark=bool(watermark),
        watermark_text=watermark or "",
        quality=quality,
    )

    return await service._process_image(image_path, output_path, options)
