"""
块存储服务 - 高效的文件存储系统
模仿 Facebook 的 Haystack 存储方式，将多个文件存储在大块文件中
"""
import logging
from pathlib import Path
from typing import Optional, BinaryIO, Tuple

logger = logging.getLogger(__name__)

# 存储配置
STORAGE_DIR = Path("data/images")
STORAGE_DIR.mkdir(parents=True, exist_ok=True)

# 每个块文件最大 500MB
BLOCK_MAX_SIZE = 500 * 1024 * 1024

# XOR 加密密钥
XOR_KEY = b"ComfyUIHelper2024ImageStorage"


def xor_encrypt(data: bytes) -> bytes:
    """简单 XOR 加密/解密"""
    return bytes(b ^ XOR_KEY[i % len(XOR_KEY)] for i, b in enumerate(data))


class StorageBlock:
    """存储块类"""
    
    def __init__(self, block_id: int):
        import threading
        self.block_id = block_id
        self.filepath = STORAGE_DIR / f"block_{block_id}.dat"
        self.size = 0
        self.file: Optional[BinaryIO] = None
        self._lock = threading.Lock()
        self._initialize()
    
    def _initialize(self):
        """初始化存储块"""
        try:
            if self.filepath.exists():
                self.size = self.filepath.stat().st_size
            self.file = open(self.filepath, "ab+")
        except IOError as e:
            logger.error(f"初始化存储块 {self.block_id} 失败: {e}")
            raise
    
    def close(self):
        """关闭文件"""
        if self.file:
            self.file.close()
            self.file = None
    
    def __del__(self):
        """析构函数，关闭文件"""
        self.close()
    
    def write(self, data: bytes) -> Tuple[int, int]:
        """
        写入数据到存储块
        
        Returns:
            Tuple[offset, size]
        """
        try:
            # 加密数据
            encrypted_data = xor_encrypt(data)
            
            offset = self.size
            self.file.seek(offset)
            self.file.write(encrypted_data)
            self.file.flush()
            size = len(encrypted_data)
            self.size += size
            return offset, size
        except IOError as e:
            logger.error(f"写入存储块 {self.block_id} 失败: {e}")
            raise
    
    def read(self, offset: int, size: int) -> bytes:
        """从存储块读取数据"""
        import threading
        if not hasattr(self, '_lock'):
            self._lock = threading.Lock()
        
        try:
            with self._lock:
                self.file.seek(offset)
                encrypted_data = self.file.read(size)
            # 解密数据
            return xor_encrypt(encrypted_data)
        except IOError as e:
            logger.error(f"读取存储块 {self.block_id} 失败: {e}")
            raise


class StorageService:
    """存储服务类（单例）"""
    
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        self._current_block_id = self._find_current_block_id()
        self._current_block = StorageBlock(self._current_block_id)
        self._block_cache: dict[int, StorageBlock] = {}
        self._initialized = True
        logger.info(f"存储服务初始化完成，当前块 ID: {self._current_block_id}")
    
    def _find_current_block_id(self) -> int:
        """查找当前最大的块 ID"""
        max_block_id = 0
        if STORAGE_DIR.exists():
            for filepath in STORAGE_DIR.glob("block_*.dat"):
                try:
                    block_id = int(filepath.stem.split("_")[1])
                    if block_id > max_block_id:
                        max_block_id = block_id
                except (ValueError, IndexError):
                    continue
        return max_block_id
    
    def write_file(self, data: bytes) -> Tuple[int, int, int]:
        """
        写入文件数据
        
        Returns:
            Tuple[block_id, offset, size]
        """
        # 检查是否需要创建新块
        if self._current_block.size + len(data) > BLOCK_MAX_SIZE:
            self._current_block.close()
            self._current_block_id += 1
            self._current_block = StorageBlock(self._current_block_id)
            logger.info(f"创建新存储块: {self._current_block_id}")
        
        offset, size = self._current_block.write(data)
        return self._current_block_id, offset, size
    
    def read_file(self, block_id: int, offset: int, size: int) -> bytes:
        """
        读取文件数据
        
        Args:
            block_id: 存储块 ID
            offset: 偏移量
            size: 数据大小
            
        Returns:
            文件数据
        
        Raises:
            FileNotFoundError: 块文件不存在
            IOError: 读取失败
        """
        # 检查块文件是否存在
        block_path = STORAGE_DIR / f"block_{block_id}.dat"
        if not block_path.exists():
            raise FileNotFoundError(f"存储块 {block_id} 不存在")
        
        # 如果是当前块，直接读取
        if block_id == self._current_block_id:
            return self._current_block.read(offset, size)
        
        # 使用缓存的块
        if block_id not in self._block_cache:
            self._block_cache[block_id] = StorageBlock(block_id)
        
        return self._block_cache[block_id].read(offset, size)
    
    def close_all(self):
        """关闭所有打开的块文件"""
        if self._current_block:
            self._current_block.close()
        for block in self._block_cache.values():
            block.close()
        self._block_cache.clear()
        logger.info("存储服务已关闭所有块文件")
    
    def get_stats(self) -> dict:
        """获取存储统计信息"""
        total_size = 0
        block_count = 0
        
        for filepath in STORAGE_DIR.glob("block_*.dat"):
            total_size += filepath.stat().st_size
            block_count += 1
        
        return {
            "block_count": block_count,
            "total_size": total_size,
            "total_size_mb": round(total_size / (1024 * 1024), 2),
            "current_block_id": self._current_block_id,
            "current_block_size": self._current_block.size,
        }


# 全局存储服务实例（延迟初始化）
_storage_service: StorageService | None = None

def get_storage_service() -> StorageService:
    """获取存储服务实例"""
    global _storage_service
    if _storage_service is None:
        _storage_service = StorageService()
    return _storage_service

# 兼容旧代码
class StorageServiceProxy:
    """代理类，延迟初始化"""
    def __getattr__(self, name):
        return getattr(get_storage_service(), name)

storage_service = StorageServiceProxy()
