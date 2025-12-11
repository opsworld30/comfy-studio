"""
提示词爬取服务 - 从热门提示词网站获取提示词
支持的网站:
- Civitai (https://civitai.com) - 最大的 AI 图片社区
- OpenArt (https://openart.ai) - AI 艺术平台
- PromptHero (https://prompthero.com) - 提示词搜索引擎
- Arthub (https://arthub.ai) - AI 艺术社区
"""
import logging
import random
import httpx

logger = logging.getLogger(__name__)

# 请求头，模拟浏览器
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json",
    "Accept-Language": "en-US,en;q=0.9",
}

# 支持的网站列表
SUPPORTED_SOURCES = [
    {
        "id": "civitai",
        "name": "Civitai",
        "url": "https://civitai.com",
        "description": "最大的 AI 图片社区，支持搜索、热门、分页",
        "features": ["search", "trending", "pagination"],
        "available": True,
    },
    {
        "id": "openart",
        "name": "OpenArt",
        "url": "https://openart.ai",
        "description": "AI 艺术平台，高质量提示词",
        "features": ["search"],
        "available": True,
    },
    {
        "id": "liblib",
        "name": "LibLib",
        "url": "https://www.liblib.art",
        "description": "国内 AI 绘画社区 (API 暂不可用)",
        "features": ["search", "trending"],
        "available": False,
    },
]


class PromptCrawlerService:
    """提示词爬取服务"""
    
    def __init__(self):
        self.client = httpx.AsyncClient(timeout=30.0, headers=HEADERS)
    
    async def search_civitai(
        self, 
        query: str = "", 
        limit: int = 20,
        nsfw: bool = False,
        sort: str = "Most Reactions",
        cursor: str = "",
    ) -> dict:
        """
        从 Civitai 搜索图片和提示词
        
        Args:
            query: 搜索关键词
            limit: 返回数量
            nsfw: 是否包含 NSFW 内容
            sort: 排序方式 (Most Reactions, Most Comments, Newest)
            cursor: 分页游标
        
        Returns:
            包含 items 和 nextCursor 的字典
        """
        try:
            # 请求更多数据以确保过滤后有足够的结果
            fetch_limit = min(limit * 3, 200)
            params = {
                "limit": fetch_limit,
                "sort": sort,
                "period": "AllTime",
            }
            if query:
                params["query"] = query
            if not nsfw:
                params["nsfw"] = "None"
            if cursor:
                params["cursor"] = cursor
            
            response = await self.client.get(
                "https://civitai.com/api/v1/images",
                params=params,
            )
            
            if response.status_code != 200:
                logger.warning("Civitai API 请求失败: %s", response.status_code)
                return {"items": [], "nextCursor": ""}
            
            data = response.json()
            items = data.get("items", [])
            metadata = data.get("metadata", {})
            next_cursor = metadata.get("nextCursor", "")
            
            results = []
            for item in items:
                meta = item.get("meta") or {}
                if not meta.get("prompt"):
                    continue
                
                results.append({
                    "source": "civitai",
                    "id": str(item.get("id", "")),
                    "positive": meta.get("prompt", ""),
                    "negative": meta.get("negativePrompt", ""),
                    "model": meta.get("Model", "") or meta.get("model", ""),
                    "sampler": meta.get("sampler", ""),
                    "steps": meta.get("steps", 0),
                    "cfg": meta.get("cfgScale", 0),
                    "seed": meta.get("seed", 0),
                    "width": item.get("width", 0),
                    "height": item.get("height", 0),
                    "image_url": item.get("url", ""),
                    "page_url": f"https://civitai.com/images/{item.get('id', '')}",
                })
                
                # 达到目标数量后停止
                if len(results) >= limit:
                    break
            
            return {
                "items": results,
                "nextCursor": next_cursor,
            }
            
        except Exception as e:
            logger.error("Civitai 搜索失败: %s", e)
            return {"items": [], "nextCursor": ""}
    
    async def search_liblib(
        self,
        query: str = "",
        limit: int = 20,
    ) -> dict:
        """
        从 LibLib.art 搜索提示词（国内 AI 绘画社区）
        """
        try:
            # LibLib 使用 POST 请求
            response = await self.client.post(
                "https://www.liblib.art/api/www/search/image",
                json={
                    "keyword": query or "风景",
                    "pageSize": min(limit * 2, 50),
                    "pageNo": 1,
                    "sortType": 1,  # 1=最新, 2=最热
                },
                headers={
                    **HEADERS,
                    "Content-Type": "application/json",
                    "Referer": "https://www.liblib.art/",
                },
            )
            
            if response.status_code != 200:
                logger.warning("LibLib API 请求失败: %s", response.status_code)
                return {"items": [], "nextCursor": ""}
            
            data = response.json()
            items = data.get("data", {}).get("list", [])
            
            results = []
            for item in items:
                # 提取提示词
                prompt_info = item.get("promptInfo", {}) or {}
                positive = prompt_info.get("prompt", "") or item.get("prompt", "")
                if not positive:
                    continue
                
                results.append({
                    "source": "liblib",
                    "id": str(item.get("id", "")),
                    "positive": positive,
                    "negative": prompt_info.get("negativePrompt", ""),
                    "model": prompt_info.get("modelName", "") or item.get("modelName", ""),
                    "sampler": prompt_info.get("sampler", ""),
                    "steps": prompt_info.get("steps", 0),
                    "cfg": prompt_info.get("cfgScale", 0),
                    "seed": prompt_info.get("seed", 0),
                    "width": item.get("width", 0),
                    "height": item.get("height", 0),
                    "image_url": item.get("imageUrl", "") or item.get("coverUrl", ""),
                    "page_url": f"https://www.liblib.art/modelinfo/{item.get('modelId', '')}",
                })
                
                if len(results) >= limit:
                    break
            
            return {"items": results, "nextCursor": ""}
            
        except Exception as e:
            logger.error("LibLib 搜索失败: %s", e)
            return {"items": [], "nextCursor": ""}
    
    async def search_openart(
        self,
        query: str,
        limit: int = 20,
    ) -> dict:
        """
        从 OpenArt.ai 搜索提示词
        使用其公开的搜索 API
        """
        if not query:
            query = "beautiful"

        try:
            response = await self.client.get(
                "https://openart.ai/api/search",
                params={
                    "searchQuery": query,
                    "pageSize": limit,
                },
            )

            if response.status_code != 200:
                logger.warning("OpenArt API 请求失败: %s", response.status_code)
                return {"items": [], "nextCursor": ""}

            data = response.json()
            items = data.get("items", [])

            results = []
            for item in items:
                prompt = item.get("prompt", "")
                if not prompt:
                    continue

                # 解析 configs 中的参数
                configs = item.get("configs", {}) or {}

                results.append({
                    "source": "openart",
                    "id": item.get("id", ""),
                    "positive": prompt,
                    "negative": configs.get("negative_prompt", ""),
                    "model": item.get("ai_model", ""),
                    "sampler": item.get("sampler", "") or configs.get("sampler", ""),
                    "steps": configs.get("steps", 0) or 0,
                    "cfg": configs.get("cfg_scale", 0) or configs.get("guidance_scale", 0) or 0,
                    "seed": item.get("image_seed", 0) or 0,
                    "width": item.get("image_width", 0) or 0,
                    "height": item.get("image_height", 0) or 0,
                    "image_url": item.get("image_url", "") or item.get("thumbnail_url", ""),
                    "page_url": f"https://openart.ai/discovery/{item.get('id', '')}",
                })

                if len(results) >= limit:
                    break

            return {"items": results, "nextCursor": ""}

        except Exception as e:
            logger.error("OpenArt 搜索失败: %s", e)
            return {"items": [], "nextCursor": ""}
    
    async def search_prompthero(
        self,
        query: str,
        limit: int = 20,
    ) -> list[dict]:
        """
        从 PromptHero 搜索提示词
        """
        if not query:
            query = "masterpiece"
        
        try:
            # PromptHero 使用 Algolia 搜索
            response = await self.client.post(
                "https://y6ygixwkf6-dsn.algolia.net/1/indexes/*/queries",
                headers={
                    "x-algolia-api-key": "a5c7c62b346c61e0c5ad0aaae9e0235e",
                    "x-algolia-application-id": "Y6YGIXWKF6",
                },
                json={
                    "requests": [{
                        "indexName": "prod_images",
                        "params": f"query={query}&hitsPerPage={limit}"
                    }]
                },
            )
            
            if response.status_code != 200:
                logger.warning("PromptHero API 请求失败: %s", response.status_code)
                return []
            
            data = response.json()
            hits = data.get("results", [{}])[0].get("hits", [])
            
            results = []
            for item in hits:
                prompt = item.get("prompt", "")
                if not prompt:
                    continue
                    
                results.append({
                    "source": "prompthero",
                    "id": str(item.get("objectID", "")),
                    "positive": prompt,
                    "negative": item.get("negativePrompt", ""),
                    "model": item.get("model", ""),
                    "sampler": item.get("sampler", ""),
                    "steps": item.get("steps", 0),
                    "cfg": item.get("cfg", 0),
                    "seed": item.get("seed", 0),
                    "width": item.get("width", 0),
                    "height": item.get("height", 0),
                    "image_url": item.get("imageUrl", ""),
                    "page_url": f"https://prompthero.com/prompt/{item.get('objectID', '')}",
                })
            
            return results
            
        except Exception as e:
            logger.error("PromptHero 搜索失败: %s", e)
            return []
    
    async def search_arthub(
        self,
        query: str,
        limit: int = 20,
    ) -> list[dict]:
        """
        从 Arthub.ai 搜索提示词
        """
        if not query:
            query = "art"
        
        try:
            response = await self.client.get(
                "https://arthub.ai/api/search",
                params={
                    "q": query,
                    "limit": limit,
                },
            )
            
            if response.status_code != 200:
                logger.warning("Arthub API 请求失败: %s", response.status_code)
                return []
            
            data = response.json()
            items = data.get("data", [])
            
            results = []
            for item in items:
                prompt = item.get("prompt", "")
                if not prompt:
                    continue
                    
                results.append({
                    "source": "arthub",
                    "id": str(item.get("id", "")),
                    "positive": prompt,
                    "negative": item.get("negativePrompt", ""),
                    "model": item.get("model", ""),
                    "sampler": "",
                    "steps": 0,
                    "cfg": 0,
                    "seed": 0,
                    "width": item.get("width", 0),
                    "height": item.get("height", 0),
                    "image_url": item.get("imageUrl", ""),
                    "page_url": f"https://arthub.ai/art/{item.get('id', '')}",
                })
            
            return results
            
        except Exception as e:
            logger.error("Arthub 搜索失败: %s", e)
            return []
    
    async def search(
        self,
        query: str,
        source: str = "civitai",
        limit: int = 20,
        cursor: str = "",
    ) -> dict:
        """
        统一搜索接口
        """
        if source == "liblib":
            # LibLib API 暂不可用
            return {"items": [], "nextCursor": "", "error": "LibLib API 暂不可用"}
        elif source == "openart":
            return await self.search_openart(query, limit)
        else:
            # 默认 Civitai
            return await self.search_civitai(query, limit, cursor=cursor)
    
    def get_sources(self) -> list[dict]:
        """获取支持的网站列表"""
        return SUPPORTED_SOURCES
    
    async def get_random_prompts(
        self,
        source: str = "civitai",
        category: str = "",
        limit: int = 10,
    ) -> list[dict]:
        """
        获取随机提示词
        """
        if source == "liblib":
            # LibLib API 暂不可用
            return []

        # 热门搜索词
        popular_keywords = [
            "portrait", "landscape", "anime", "fantasy", "sci-fi",
            "cyberpunk", "nature", "architecture", "character", "concept art",
            "digital art", "illustration", "photorealistic", "cinematic",
        ]

        if not category:
            category = random.choice(popular_keywords)

        result = await self.search(category, source, limit)
        return result.get("items", [])
    
    async def get_trending(self, limit: int = 20, cursor: str = "") -> dict:
        """获取热门提示词（从 Civitai）"""
        return await self.search_civitai(
            query="",
            limit=limit,
            sort="Most Reactions",
            cursor=cursor,
        )


# 单例
prompt_crawler = PromptCrawlerService()
