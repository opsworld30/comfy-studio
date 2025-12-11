"""
为已存在的图片补全 content_hash（MD5）
"""
import asyncio
import hashlib
import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import select
from app.database import async_session
from app.models import StoredImage
from app.services.storage import storage_service


async def update_content_hash():
    """为所有没有 content_hash 的图片计算并更新 MD5"""
    
    print("开始更新图片 MD5 哈希值...")
    
    async with async_session() as db:
        # 查询所有没有 content_hash 的图片
        result = await db.execute(
            select(StoredImage).where(
                (StoredImage.content_hash.is_(None)) | (StoredImage.content_hash == "")
            )
        )
        images = result.scalars().all()
        
        total = len(images)
        print(f"找到 {total} 张需要更新的图片")
        
        if total == 0:
            print("所有图片都已有 MD5 哈希值")
            return
        
        updated = 0
        failed = 0
        
        for i, img in enumerate(images, 1):
            try:
                # 从块存储读取图片数据
                image_data = storage_service.read_file(img.block_id, img.offset, img.size)
                
                if not image_data:
                    print(f"[{i}/{total}] 失败: {img.filename} - 无法读取数据")
                    failed += 1
                    continue
                
                # 计算 MD5
                content_hash = hashlib.md5(image_data).hexdigest()
                
                # 更新数据库
                img.content_hash = content_hash
                await db.commit()
                
                updated += 1
                
                # 每 100 张打印一次进度
                if i % 100 == 0 or i == total:
                    print(f"[{i}/{total}] 已更新 {updated} 张，失败 {failed} 张")
                
            except Exception as e:
                print(f"[{i}/{total}] 错误: {img.filename} - {e}")
                failed += 1
                await db.rollback()
        
        print(f"\n更新完成！")
        print(f"  成功: {updated} 张")
        print(f"  失败: {failed} 张")
        print(f"  总计: {total} 张")


if __name__ == "__main__":
    asyncio.run(update_content_hash())
