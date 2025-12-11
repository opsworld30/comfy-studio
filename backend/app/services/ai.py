"""AI Prompt 优化服务"""
import httpx
import logging
from typing import Any

logger = logging.getLogger(__name__)

# 系统提示词
SYSTEM_PROMPTS = {
    "optimize": """你是一个专业的 Stable Diffusion 提示词优化专家。
用户会给你一个提示词，请优化它使其更加详细、专业，能生成更高质量的图片。
规则：
1. 保持原意，但增加细节描述
2. 添加质量相关的标签（如 masterpiece, best quality, highly detailed 等）
3. 优化词语顺序，重要的放前面
4. 只输出优化后的英文提示词，不要解释""",

    "translate": """你是一个专业的翻译专家，专门将中文翻译成 Stable Diffusion 提示词格式的英文。
规则：
1. 将中文翻译成适合 AI 绘画的英文提示词
2. 使用逗号分隔不同的描述
3. 只输出翻译后的英文提示词，不要解释""",

    "expand": """你是一个专业的 Stable Diffusion 提示词扩展专家。
用户会给你一个简短的提示词，请大幅扩展它，添加更多细节。
规则：
1. 保持原意，但大幅增加细节
2. 添加光影、构图、氛围、材质等描述
3. 添加质量标签
4. 只输出扩展后的英文提示词，不要解释""",

    "negative": """你是一个专业的 Stable Diffusion 负面提示词生成专家。
用户会给你一个正向提示词，请根据它生成合适的负面提示词。
规则：
1. 根据正向提示词的内容，生成能避免常见问题的负面词
2. 包含基础质量负面词（如 low quality, blurry, bad anatomy 等）
3. 根据内容添加特定负面词（如人物需要 bad hands, extra fingers 等）
4. 只输出负面提示词，不要解释""",

    "style": """你是一个专业的 Stable Diffusion 提示词风格转换专家。
用户会给你一个提示词和目标风格，请将提示词转换为该风格。
规则：
1. 保持原始内容，但转换为目标风格
2. 添加该风格特有的描述词
3. 只输出转换后的英文提示词，不要解释

目标风格：{style}""",

    "generate": """你是一个专业的 Stable Diffusion 提示词生成专家。
用户会用中文描述想要的图片，请生成专业的英文提示词。

请严格按以下 JSON 格式输出，不要有任何其他内容：
{
  "name": "简短的中文名称，2-6个字，描述图片主题",
  "category": "分类，从以下选择：人物、风景、动漫、写实、插画、概念艺术、其他",
  "positive": "正向提示词，描述想要的内容，包含质量标签",
  "negative": "负向提示词，描述不想要的内容"
}

规则：
1. name 是简短的中文名称，如"樱花少女"、"山水画"、"机甲战士"
2. category 必须从给定选项中选择
3. positive 必须是英文，包含详细描述和质量标签（masterpiece, best quality, highly detailed 等）
4. negative 必须是英文，包含常见负面词（low quality, blurry, bad anatomy, extra fingers 等）
5. 根据描述内容添加合适的风格、光影、构图描述
6. 只输出 JSON，不要有任何解释""",
}


class AIService:
    """AI 服务"""
    
    def __init__(self):
        self.client = httpx.AsyncClient(timeout=60.0)
    
    async def optimize_prompt(
        self,
        prompt: str,
        action: str,
        api_key: str,
        api_url: str,
        model: str,
        style: str | None = None,
    ) -> str:
        """优化提示词"""
        if not api_key:
            raise ValueError("未配置 API Key")
        
        # 获取系统提示词
        system_prompt = SYSTEM_PROMPTS.get(action)
        if not system_prompt:
            raise ValueError(f"不支持的操作: {action}")
        
        # 风格转换需要替换风格
        if action == "style" and style:
            system_prompt = system_prompt.format(style=style)
        
        # 构建请求
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.7,
            "max_tokens": 1000,
        }
        
        try:
            # 确保 URL 正确
            url = api_url.rstrip("/")
            if not url.endswith("/chat/completions"):
                url = f"{url}/chat/completions"
            
            logger.info(f"AI request: url={url}, model={model}, action={action}")
            logger.info(f"AI prompt: {prompt[:100]}...")
            
            response = await self.client.post(
                url,
                headers=headers,
                json=payload,
            )
            
            logger.info(f"AI response status: {response.status_code}")
            
            if response.status_code != 200:
                error_text = response.text
                logger.error(f"AI API error: {response.status_code} - {error_text}")
                raise ValueError(f"AI API 错误: {response.status_code} - {error_text}")
            
            data = response.json()
            logger.info(f"AI response data: {str(data)[:500]}")
            
            result = data["choices"][0]["message"]["content"].strip()
            
            # 清理结果（移除可能的引号和多余空白）
            result = result.strip('"\'')
            
            logger.info(f"AI result: {result[:100]}...")
            return result
            
        except httpx.TimeoutException:
            logger.error("AI API timeout")
            raise ValueError("AI API 请求超时")
        except Exception as e:
            logger.error(f"AI optimize error: {type(e).__name__}: {e}")
            raise ValueError(f"AI 优化失败: {str(e)}")


    async def generate_prompt(
        self,
        description: str,
        api_key: str,
        api_url: str,
        model: str,
        style: str | None = None,
    ) -> dict:
        """根据描述生成提示词"""
        import json
        
        if not api_key:
            raise ValueError("未配置 API Key")
        
        system_prompt = SYSTEM_PROMPTS["generate"]
        
        # 如果有风格要求，添加到描述中
        user_content = description
        if style:
            user_content = f"{description}\n\n风格要求：{style}"
        
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content},
            ],
            "temperature": 0.7,
            "max_tokens": 1000,
        }
        
        try:
            url = api_url.rstrip("/")
            if not url.endswith("/chat/completions"):
                url = f"{url}/chat/completions"
            
            logger.info(f"AI generate request: url={url}, model={model}")
            logger.info(f"AI description: {description[:100]}...")
            
            response = await self.client.post(
                url,
                headers=headers,
                json=payload,
            )
            
            if response.status_code != 200:
                error_text = response.text
                logger.error(f"AI API error: {response.status_code} - {error_text}")
                raise ValueError(f"AI API 错误: {response.status_code}")
            
            data = response.json()
            result_text = data["choices"][0]["message"]["content"].strip()
            
            logger.info(f"AI generate result: {result_text[:200]}...")
            
            # 尝试解析 JSON
            try:
                # 清理可能的 markdown 代码块
                if result_text.startswith("```"):
                    result_text = result_text.split("```")[1]
                    if result_text.startswith("json"):
                        result_text = result_text[4:]
                result_text = result_text.strip()
                
                result = json.loads(result_text)
                return {
                    "name": result.get("name", "未命名"),
                    "category": result.get("category", "其他"),
                    "positive": result.get("positive", ""),
                    "negative": result.get("negative", ""),
                }
            except json.JSONDecodeError:
                # 如果不是 JSON，尝试作为纯文本处理
                logger.warning(f"Failed to parse JSON, using as plain text: {result_text[:100]}")
                return {
                    "name": "AI生成",
                    "category": "其他",
                    "positive": result_text,
                    "negative": "low quality, blurry, bad anatomy, extra fingers, poorly drawn hands, poorly drawn face",
                }
                
        except httpx.TimeoutException:
            logger.error("AI API timeout")
            raise ValueError("AI API 请求超时")
        except Exception as e:
            logger.error(f"AI generate error: {type(e).__name__}: {e}")
            raise ValueError(f"AI 生成失败: {str(e)}")


# 单例
ai_service = AIService()
