"""
完整的 content_hash 迁移流程
1. 添加 content_hash 字段
2. 为已存在的图片计算并更新 MD5
"""
import asyncio
import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from add_content_hash_column import add_content_hash_column
from update_content_hash import update_content_hash


async def main():
    """执行完整的迁移流程"""
    
    print("=" * 60)
    print("Content Hash 迁移工具")
    print("=" * 60)
    print()
    
    # 步骤 1: 添加字段
    print("步骤 1/2: 添加数据库字段")
    print("-" * 60)
    await add_content_hash_column()
    print()
    
    # 步骤 2: 更新已存在的图片
    print("步骤 2/2: 更新已存在图片的 MD5")
    print("-" * 60)
    await update_content_hash()
    print()
    
    print("=" * 60)
    print("迁移完成！")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
