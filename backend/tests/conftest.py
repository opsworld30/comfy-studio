"""
测试配置文件
"""
import pytest
import asyncio
from typing import AsyncGenerator

from app.database import async_session, engine
from app.models import Base


@pytest.fixture(scope="session")
def event_loop():
    """创建事件循环"""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
async def setup_database():
    """设置测试数据库"""
    # 创建所有表
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    yield
    
    # 清理：删除所有表
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.fixture
async def db_session() -> AsyncGenerator:
    """创建测试数据库会话"""
    async with async_session() as session:
        yield session
        await session.rollback()


# 测试标记
pytest_plugins = []

# 标记定义
markers = [
    "slow: marks tests as slow (deselect with '-m \"not slow\"')",
    "integration: marks tests as integration tests",
    "unit: marks tests as unit tests",
    "api: marks tests as API tests",
    "service: marks tests as service tests",
]
