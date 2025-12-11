"""导入推荐 LoRA 列表"""
import asyncio
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app.database import async_session, init_db
from app.models import SavedPrompt


async def main():
    """导入 LoRA 推荐列表"""
    await init_db()
    
    lora_file = Path(__file__).parent.parent.parent.parent / "prompt" / "good_lora.txt"
    
    if not lora_file.exists():
        print("good_lora.txt not found")
        return
    
    content = lora_file.read_text(encoding='utf-8')
    loras = [line.strip() for line in content.split('\n') if line.strip()]
    
    print(f"Found {len(loras)} LoRA names")
    
    # 创建一个包含所有推荐 LoRA 的 prompt 记录
    lora_list = '\n'.join([f"- {lora}" for lora in loras])
    
    async with async_session() as session:
        prompt = SavedPrompt(
            name="推荐 LoRA 列表",
            positive=lora_list,
            negative="",
            category="LoRA参考",
            source="imported",
            tags=["lora", "reference"],
        )
        session.add(prompt)
        await session.commit()
    
    print(f"[OK] Imported {len(loras)} LoRA names as reference")


if __name__ == "__main__":
    asyncio.run(main())
