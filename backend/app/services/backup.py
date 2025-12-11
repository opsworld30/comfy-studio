"""数据库备份服务"""
import os
import shutil
import logging
import asyncio
from pathlib import Path
from datetime import datetime, timedelta
import gzip

logger = logging.getLogger(__name__)


class BackupService:
    """自动备份数据库的服务"""
    
    def __init__(
        self,
        db_path: str = "./data/workflows.db",
        backup_dir: str = "./data/backups",
        max_backups: int = 10,
        compress: bool = True,
    ):
        self.db_path = Path(db_path)
        self.backup_dir = Path(backup_dir)
        self.max_backups = max_backups
        self.compress = compress
        
        # 确保备份目录存在
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        
        self._running = False
        self._task: asyncio.Task | None = None
    
    async def start(self, interval_hours: int = 6):
        """启动定期备份任务"""
        if self._running:
            return
        
        self._running = True
        self._task = asyncio.create_task(self._backup_loop(interval_hours))
        logger.info(f"备份服务已启动，间隔 {interval_hours} 小时")
    
    async def stop(self):
        """停止备份任务"""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("备份服务已停止")
    
    async def _backup_loop(self, interval_hours: int):
        """备份循环"""
        while self._running:
            try:
                await self.create_backup()
            except Exception as e:
                logger.error(f"备份任务出错: {e}")
            
            await asyncio.sleep(interval_hours * 3600)
    
    async def create_backup(self, description: str = "auto") -> dict | None:
        """创建数据库备份"""
        if not self.db_path.exists():
            logger.warning(f"数据库文件不存在: {self.db_path}")
            return None
        
        # 生成备份文件名
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_name = f"backup_{timestamp}_{description}"
        
        if self.compress:
            backup_path = self.backup_dir / f"{backup_name}.db.gz"
        else:
            backup_path = self.backup_dir / f"{backup_name}.db"
        
        try:
            if self.compress:
                # 压缩备份
                with open(self.db_path, 'rb') as f_in:
                    with gzip.open(backup_path, 'wb') as f_out:
                        shutil.copyfileobj(f_in, f_out)
            else:
                # 直接复制
                shutil.copy2(self.db_path, backup_path)
            
            # 获取备份信息
            backup_size = backup_path.stat().st_size
            original_size = self.db_path.stat().st_size
            
            logger.info(
                f"备份创建成功: {backup_path.name} "
                f"({backup_size / 1024:.1f} KB, "
                f"压缩率: {backup_size / original_size * 100:.1f}%)"
            )
            
            # 清理旧备份
            await self._cleanup_old_backups()
            
            return {
                "path": str(backup_path),
                "name": backup_path.name,
                "size": backup_size,
                "original_size": original_size,
                "created_at": datetime.now().isoformat(),
            }
            
        except Exception as e:
            logger.error(f"创建备份失败: {e}")
            raise
    
    async def _cleanup_old_backups(self):
        """清理旧备份，保留最新的 max_backups 个"""
        backups = self.list_backups()
        
        if len(backups) <= self.max_backups:
            return
        
        # 按创建时间排序，删除最旧的
        backups.sort(key=lambda x: x["created_at"], reverse=True)
        
        for backup in backups[self.max_backups:]:
            try:
                Path(backup["path"]).unlink()
                logger.info(f"删除旧备份: {backup['name']}")
            except Exception as e:
                logger.warning(f"删除备份失败 {backup['name']}: {e}")
    
    def list_backups(self) -> list[dict]:
        """列出所有备份"""
        backups = []
        
        for file_path in self.backup_dir.glob("backup_*"):
            if file_path.is_file():
                try:
                    stat = file_path.stat()
                    backups.append({
                        "path": str(file_path),
                        "name": file_path.name,
                        "size": stat.st_size,
                        "created_at": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                    })
                except Exception:
                    pass
        
        return sorted(backups, key=lambda x: x["created_at"], reverse=True)
    
    async def restore_backup(self, backup_name: str) -> bool:
        """从备份恢复数据库"""
        backup_path = self.backup_dir / backup_name
        
        if not backup_path.exists():
            logger.error(f"备份文件不存在: {backup_name}")
            return False
        
        try:
            # 先备份当前数据库
            await self.create_backup(description="pre_restore")
            
            if backup_name.endswith('.gz'):
                # 解压恢复
                with gzip.open(backup_path, 'rb') as f_in:
                    with open(self.db_path, 'wb') as f_out:
                        shutil.copyfileobj(f_in, f_out)
            else:
                # 直接复制
                shutil.copy2(backup_path, self.db_path)
            
            logger.info(f"数据库已从备份恢复: {backup_name}")
            return True
            
        except Exception as e:
            logger.error(f"恢复备份失败: {e}")
            return False
    
    def delete_backup(self, backup_name: str) -> bool:
        """删除指定备份"""
        backup_path = self.backup_dir / backup_name
        
        if not backup_path.exists():
            return False
        
        try:
            backup_path.unlink()
            logger.info(f"备份已删除: {backup_name}")
            return True
        except Exception as e:
            logger.error(f"删除备份失败: {e}")
            return False


# 全局实例
backup_service = BackupService()
