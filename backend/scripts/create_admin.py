"""创建默认管理员用户"""
import asyncio
import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import select
from app.database import async_session
from app.models import User
from app.utils.auth import get_password_hash


async def create_admin_user():
    """创建默认管理员用户"""
    async with async_session() as db:
        # 检查是否已存在管理员
        result = await db.execute(select(User).where(User.username == "admin"))
        existing_admin = result.scalar_one_or_none()
        
        if existing_admin:
            print("❌ 管理员用户已存在")
            return
        
        # 创建管理员用户
        admin = User(
            username="admin",
            email="admin@example.com",
            full_name="系统管理员",
            hashed_password=get_password_hash("admin123"),
            is_active=True,
            is_superuser=True
        )
        
        db.add(admin)
        await db.commit()
        
        print("✅ 管理员用户创建成功")
        print("   用户名: admin")
        print("   密码: admin123")
        print("   ⚠️  请及时修改默认密码！")


if __name__ == "__main__":
    asyncio.run(create_admin_user())
