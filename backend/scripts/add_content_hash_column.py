"""
添加 content_hash 字段到 stored_images 表
"""
import asyncio
import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import text
from app.database import engine


async def add_content_hash_column():
    """添加 content_hash 字段"""
    
    print("开始添加 content_hash 字段...")
    
    async with engine.begin() as conn:
        try:
            # 检查字段是否已存在
            result = await conn.execute(text(
                "SELECT COUNT(*) as count FROM pragma_table_info('stored_images') "
                "WHERE name='content_hash'"
            ))
            row = result.fetchone()
            
            if row and row[0] > 0:
                print("✓ content_hash 字段已存在")
                return
            
            # 添加字段
            print("添加 content_hash 字段...")
            await conn.execute(text(
                "ALTER TABLE stored_images ADD COLUMN content_hash VARCHAR(32)"
            ))
            
            # 创建索引
            print("创建索引...")
            await conn.execute(text(
                "CREATE INDEX IF NOT EXISTS ix_stored_images_content_hash "
                "ON stored_images(content_hash)"
            ))
            
            print("✓ 字段添加成功！")
            
        except Exception as e:
            print(f"✗ 添加字段失败: {e}")
            raise


if __name__ == "__main__":
    asyncio.run(add_content_hash_column())
