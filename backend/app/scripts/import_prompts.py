"""从文本文件导入 Prompt 到数据库"""
import re
import asyncio
from pathlib import Path
from typing import Generator

# 添加项目路径
import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app.database import async_session, init_db
from app.models import SavedPrompt


def parse_a1111_prompts(content: str) -> Generator[dict, None, None]:
    """解析 A1111 格式的 prompt 文件"""
    # 分割不同的 prompt 块（用分隔线分开）
    separators = [
        r'-{10,}',  # 多个连字符
        r'\*{5,}',  # 多个星号
        r'={10,}',  # 多个等号
    ]
    pattern = '|'.join(separators)
    blocks = re.split(pattern, content)
    
    for block in blocks:
        block = block.strip()
        if not block or len(block) < 50:
            continue
        
        # 解析正向和负向提示词
        positive = ""
        negative = ""
        
        # 查找 Negative prompt: 分隔符
        neg_match = re.search(r'\n\s*Negative prompt:\s*', block, re.IGNORECASE)
        
        if neg_match:
            positive = block[:neg_match.start()].strip()
            rest = block[neg_match.end():]
            
            # 负向提示词在 "Negative prompt:" 之后，参数行之前
            # 参数行通常以 "Steps:" 开头
            steps_match = re.search(r'\n\s*Steps:\s*\d+', rest)
            if steps_match:
                negative = rest[:steps_match.start()].strip()
            else:
                negative = rest.strip()
        else:
            # 没有负向提示词，检查是否有参数行
            steps_match = re.search(r'\n\s*Steps:\s*\d+', block)
            if steps_match:
                positive = block[:steps_match.start()].strip()
            else:
                positive = block.strip()
        
        # 清理提示词
        positive = clean_prompt(positive)
        negative = clean_prompt(negative)
        
        if not positive or len(positive) < 20:
            continue
        
        # 生成名称
        name = generate_name(positive)
        
        # 自动分类
        category = categorize_prompt(positive, negative)
        
        yield {
            "name": name,
            "positive": positive,
            "negative": negative,
            "category": category,
        }


def clean_prompt(text: str) -> str:
    """清理提示词文本"""
    if not text:
        return ""
    
    # 移除多余的空白行
    lines = [line.strip() for line in text.split('\n') if line.strip()]
    text = '\n'.join(lines)
    
    # 合并为单行（保留逗号分隔）
    text = re.sub(r'\n+', ', ', text)
    
    # 移除多余的逗号和空格
    text = re.sub(r',\s*,', ',', text)
    text = re.sub(r'\s+', ' ', text)
    text = text.strip(' ,')
    
    return text


def generate_name(positive: str) -> str:
    """从正向提示词生成名称"""
    # 提取关键词
    skip_words = {
        'masterpiece', 'best quality', 'high quality', 'detailed', '8k', 'uhd', 'hd',
        'raw photo', 'photorealistic', 'realistic', 'ultra', 'film', 'grain', 'overlay',
        'intricate', 'details', 'fujicolor', 'fujifilm', 'lora', '1girl', 'solo',
    }
    
    # 移除 LoRA 标签
    text = re.sub(r'<lora:[^>]+>', '', positive.lower())
    
    # 提取单词
    words = re.findall(r'\b[a-zA-Z\u4e00-\u9fff]{3,}\b', text)
    
    keywords = []
    for word in words:
        if word.lower() not in skip_words:
            keywords.append(word)
            if len(keywords) >= 4:
                break
    
    if keywords:
        return ' '.join(keywords).title()[:50]
    
    # 如果没有提取到关键词，使用前30个字符
    clean_text = re.sub(r'<[^>]+>', '', positive)[:40]
    return clean_text.strip() + "..."


def categorize_prompt(positive: str, negative: str) -> str:
    """自动分类提示词"""
    text = (positive + " " + negative).lower()
    
    categories = {
        "写实人像": ["photorealistic", "raw photo", "realistic", "film", "portrait", "photography"],
        "动漫风格": ["anime", "manga", "cartoon", "illustration", "pixiv"],
        "JK制服": ["jk", "school uniform", "serafuku", "sailor", "学生", "制服"],
        "街拍时尚": ["street", "fashion", "ins style", "urban", "city"],
        "赛博朋克": ["cyberpunk", "neon", "futuristic", "sci-fi"],
        "王家卫风格": ["wong kar", "王家卫", "twilight", "film texture", "high saturation"],
        "泳装比基尼": ["bikini", "swimsuit", "pool", "beach", "泳装"],
        "居家私房": ["bedroom", "bed", "indoor", "home", "pajamas", "lingerie"],
        "黑丝美腿": ["pantyhose", "stockings", "thighhighs", "黑丝", "丝袜"],
        "性感诱惑": ["sexy", "cleavage", "seductive", "erotic"],
    }
    
    for category, keywords in categories.items():
        if any(kw in text for kw in keywords):
            return category
    
    return "其他"


async def import_prompts_from_file(file_path: Path, source_name: str) -> int:
    """从文件导入 prompt"""
    if not file_path.exists():
        print(f"文件不存在: {file_path}")
        return 0
    
    content = file_path.read_text(encoding='utf-8', errors='ignore')
    prompts = list(parse_a1111_prompts(content))
    
    print(f"从 {file_path.name} 解析到 {len(prompts)} 个 prompt")
    
    # 去重
    seen = set()
    unique_prompts = []
    for p in prompts:
        key = (p["positive"][:200].lower(), p["negative"][:100].lower())
        if key not in seen:
            seen.add(key)
            unique_prompts.append(p)
    
    print(f"去重后剩余 {len(unique_prompts)} 个")
    
    # 保存到数据库
    saved_count = 0
    async with async_session() as session:
        for p in unique_prompts:
            prompt = SavedPrompt(
                name=p["name"],
                positive=p["positive"],
                negative=p["negative"],
                category=p["category"],
                source="imported",
                tags=[source_name],
            )
            session.add(prompt)
            saved_count += 1
        
        await session.commit()
    
    return saved_count


async def main():
    """主函数"""
    # 初始化数据库
    await init_db()
    
    # 定义要导入的文件
    prompt_dir = Path(__file__).parent.parent.parent.parent / "prompt"
    
    files = [
        ("sd.txt", "sd"),
        ("sd2.txt", "sd2"),
        ("sd3.txt", "sd3"),
        ("sd4.txt", "sd4"),
        ("sd5.txt", "sd5"),
        ("sdr.txt", "sdr"),
        ("flux-r.txt", "flux-r"),
        ("flux-safe.txt", "flux-safe"),
        ("xl-comic.txt", "xl-comic"),
        ("xl.txt", "xl"),
    ]
    
    total = 0
    for filename, source in files:
        file_path = prompt_dir / filename
        if file_path.exists():
            count = await import_prompts_from_file(file_path, source)
            total += count
            print(f"[OK] {filename}: imported {count} prompts")
        else:
            print(f"[SKIP] {filename}: file not found")
    
    print(f"\nTotal imported: {total} prompts")


if __name__ == "__main__":
    asyncio.run(main())
