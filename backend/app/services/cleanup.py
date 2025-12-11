"""文件清理服务"""
import os
import time
import logging
import asyncio
from pathlib import Path
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class CleanupService:
    """定期清理过期文件和缓存的服务"""
    
    def __init__(
        self,
        cache_dir: str = "./data/cache",
        temp_dir: str = "./data/temp",
        max_cache_age_hours: int = 24,
        max_temp_age_hours: int = 1,
        max_cache_size_mb: int = 500,
    ):
        self.cache_dir = Path(cache_dir)
        self.temp_dir = Path(temp_dir)
        self.max_cache_age_hours = max_cache_age_hours
        self.max_temp_age_hours = max_temp_age_hours
        self.max_cache_size_mb = max_cache_size_mb
        
        # 确保目录存在
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.temp_dir.mkdir(parents=True, exist_ok=True)
        
        self._running = False
        self._task: asyncio.Task | None = None
    
    async def start(self, interval_minutes: int = 30):
        """启动定期清理任务"""
        if self._running:
            return
        
        self._running = True
        self._task = asyncio.create_task(self._cleanup_loop(interval_minutes))
        logger.info(f"清理服务已启动，间隔 {interval_minutes} 分钟")
    
    async def stop(self):
        """停止清理任务"""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("清理服务已停止")
    
    async def _cleanup_loop(self, interval_minutes: int):
        """清理循环"""
        while self._running:
            try:
                await self.cleanup()
            except Exception as e:
                logger.error(f"清理任务出错: {e}")
            
            await asyncio.sleep(interval_minutes * 60)
    
    async def cleanup(self) -> dict:
        """执行清理"""
        result = {
            "temp_files_deleted": 0,
            "cache_files_deleted": 0,
            "bytes_freed": 0,
        }
        
        # 清理临时文件
        temp_result = await self._cleanup_directory(
            self.temp_dir,
            max_age_hours=self.max_temp_age_hours
        )
        result["temp_files_deleted"] = temp_result["files_deleted"]
        result["bytes_freed"] += temp_result["bytes_freed"]
        
        # 清理缓存文件（按时间）
        cache_result = await self._cleanup_directory(
            self.cache_dir,
            max_age_hours=self.max_cache_age_hours
        )
        result["cache_files_deleted"] = cache_result["files_deleted"]
        result["bytes_freed"] += cache_result["bytes_freed"]
        
        # 如果缓存仍然超过大小限制，删除最旧的文件
        size_result = await self._cleanup_by_size(
            self.cache_dir,
            max_size_mb=self.max_cache_size_mb
        )
        result["cache_files_deleted"] += size_result["files_deleted"]
        result["bytes_freed"] += size_result["bytes_freed"]
        
        if result["bytes_freed"] > 0:
            logger.info(
                f"清理完成: 删除 {result['temp_files_deleted']} 个临时文件, "
                f"{result['cache_files_deleted']} 个缓存文件, "
                f"释放 {result['bytes_freed'] / 1024 / 1024:.2f} MB"
            )
        
        return result
    
    async def _cleanup_directory(
        self,
        directory: Path,
        max_age_hours: int
    ) -> dict:
        """清理目录中的过期文件"""
        result = {"files_deleted": 0, "bytes_freed": 0}
        
        if not directory.exists():
            return result
        
        cutoff_time = time.time() - (max_age_hours * 3600)
        
        for file_path in directory.rglob("*"):
            if not file_path.is_file():
                continue
            
            try:
                stat = file_path.stat()
                if stat.st_mtime < cutoff_time:
                    size = stat.st_size
                    file_path.unlink()
                    result["files_deleted"] += 1
                    result["bytes_freed"] += size
            except Exception as e:
                logger.warning(f"删除文件失败 {file_path}: {e}")
        
        # 清理空目录
        for dir_path in sorted(directory.rglob("*"), reverse=True):
            if dir_path.is_dir():
                try:
                    dir_path.rmdir()  # 只能删除空目录
                except OSError:
                    pass  # 目录不为空，跳过
        
        return result
    
    async def _cleanup_by_size(
        self,
        directory: Path,
        max_size_mb: int
    ) -> dict:
        """按大小限制清理目录"""
        result = {"files_deleted": 0, "bytes_freed": 0}
        
        if not directory.exists():
            return result
        
        max_size_bytes = max_size_mb * 1024 * 1024
        
        # 获取所有文件及其信息
        files = []
        total_size = 0
        
        for file_path in directory.rglob("*"):
            if file_path.is_file():
                try:
                    stat = file_path.stat()
                    files.append((file_path, stat.st_mtime, stat.st_size))
                    total_size += stat.st_size
                except Exception:
                    pass
        
        # 如果未超过限制，直接返回
        if total_size <= max_size_bytes:
            return result
        
        # 按修改时间排序（最旧的在前）
        files.sort(key=lambda x: x[1])
        
        # 删除最旧的文件直到满足大小限制
        for file_path, _, size in files:
            if total_size <= max_size_bytes:
                break
            
            try:
                file_path.unlink()
                result["files_deleted"] += 1
                result["bytes_freed"] += size
                total_size -= size
            except Exception as e:
                logger.warning(f"删除文件失败 {file_path}: {e}")
        
        return result
    
    def get_stats(self) -> dict:
        """获取存储统计信息"""
        stats = {
            "cache": self._get_dir_stats(self.cache_dir),
            "temp": self._get_dir_stats(self.temp_dir),
        }
        return stats
    
    def _get_dir_stats(self, directory: Path) -> dict:
        """获取目录统计信息"""
        if not directory.exists():
            return {"files": 0, "size_mb": 0}
        
        files = 0
        total_size = 0
        
        for file_path in directory.rglob("*"):
            if file_path.is_file():
                try:
                    total_size += file_path.stat().st_size
                    files += 1
                except Exception:
                    pass
        
        return {
            "files": files,
            "size_mb": round(total_size / 1024 / 1024, 2),
        }


# 全局实例
cleanup_service = CleanupService()
