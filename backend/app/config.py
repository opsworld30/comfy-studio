"""应用配置"""
from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    """应用设置"""
    # 数据库
    DATABASE_URL: str = "sqlite+aiosqlite:///./data/workflows.db"
    
    # ComfyUI 配置
    COMFYUI_URL: str = "http://127.0.0.1:8188"
    COMFYUI_PATH: str = "/Users/mac/code/python/comfyui-helper/ComfyUI"
    
    # 备份目录
    BACKUP_DIR: str = "./data/backups"
    
    # CORS
    CORS_ORIGINS: list[str] = [
        "http://localhost:5173", 
        "http://127.0.0.1:5173",
        "http://localhost:5174",
        "http://127.0.0.1:5174",
        "http://localhost:5175",
        "http://127.0.0.1:5175",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ]
    
    class Config:
        env_file = ".env"


@lru_cache
def get_settings() -> Settings:
    return Settings()


# 全局 settings 实例
settings = get_settings()
