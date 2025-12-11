"""数据库配置"""
import logging
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.pool import StaticPool
from sqlalchemy import text, inspect
from pathlib import Path

from .config import get_settings

logger = logging.getLogger(__name__)

settings = get_settings()

# 确保数据目录存在
Path("./data").mkdir(exist_ok=True)
Path(settings.BACKUP_DIR).mkdir(parents=True, exist_ok=True)

# 数据库引擎配置
# SQLite 使用 StaticPool 以支持多线程
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=False,
    # SQLite 特定配置
    connect_args={"check_same_thread": False} if "sqlite" in settings.DATABASE_URL else {},
    poolclass=StaticPool if "sqlite" in settings.DATABASE_URL else None,
)

async_session = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


class Base(DeclarativeBase):
    pass


async def get_db():
    """获取数据库会话"""
    async with async_session() as session:
        try:
            yield session
        finally:
            await session.close()


async def init_db():
    """初始化数据库"""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    # 执行数据库迁移
    await run_migrations()


def _check_column_exists(connection, table: str, column: str) -> bool:
    """检查列是否存在（兼容多种数据库）"""
    inspector = inspect(connection)
    try:
        columns = [c['name'] for c in inspector.get_columns(table)]
        return column in columns
    except Exception:
        return False


async def run_migrations():
    """执行数据库迁移 - 添加缺失的列（兼容 SQLite/PostgreSQL/MySQL）"""
    migrations = [
        # StoredImage 新增字段
        ("stored_images", "comfyui_prompt_id", "VARCHAR(100) DEFAULT ''"),
        ("stored_images", "prompt_id", "INTEGER"),
        # SavedPrompt 新增字段
        ("saved_prompts", "model", "VARCHAR(255) DEFAULT ''"),
        ("saved_prompts", "sampler", "VARCHAR(100) DEFAULT ''"),
        ("saved_prompts", "steps", "INTEGER DEFAULT 0"),
        ("saved_prompts", "cfg", "FLOAT DEFAULT 0"),
        ("saved_prompts", "seed", "INTEGER DEFAULT 0"),
        ("saved_prompts", "width", "INTEGER DEFAULT 0"),
        ("saved_prompts", "height", "INTEGER DEFAULT 0"),
    ]
    
    async with engine.begin() as conn:
        for table, column, column_type in migrations:
            try:
                # 使用 SQLAlchemy inspect 检查列是否存在（兼容多种数据库）
                exists = await conn.run_sync(_check_column_exists, table, column)
                
                if not exists:
                    await conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {column_type}"))
                    logger.info(f"数据库迁移: 添加列 {table}.{column}")
            except Exception as e:
                logger.warning(f"迁移 {table}.{column} 失败: {e}")
