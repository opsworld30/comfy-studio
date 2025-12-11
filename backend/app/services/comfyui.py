"""ComfyUI 服务"""
import httpx
import logging
import time
from typing import Any

from ..config import get_settings
from .cache import cache_service

settings = get_settings()
logger = logging.getLogger(__name__)

# 默认 ComfyUI URL
DEFAULT_COMFYUI_URL = "http://127.0.0.1:8188"


class CacheEntry:
    """缓存条目"""
    def __init__(self, data: Any, ttl: int = 60):
        self.data = data
        self.expires_at = time.time() + ttl
    
    def is_expired(self) -> bool:
        return time.time() > self.expires_at


class ComfyUIService:
    """ComfyUI API 服务"""
    
    # 图片缓存配置
    MAX_CACHE_SIZE_MB = 100  # 最大缓存大小 100MB
    MAX_CACHE_COUNT = 100    # 最大缓存数量
    
    def __init__(self):
        self._base_url: str | None = None  # 从数据库动态获取
        self._base_url_cache_time: float = 0
        self._base_url_cache_ttl = 60  # URL 缓存 60 秒
        self.client = httpx.AsyncClient(timeout=30.0)
        self._cache: dict[str, CacheEntry] = {}
        self._image_cache: dict[str, tuple[bytes, float]] = {}  # filename -> (data, timestamp)
        self._image_cache_ttl = 300  # 图片缓存 5 分钟
        self._cache_size_bytes = 0  # 当前缓存总大小（字节）
    
    @property
    def base_url(self) -> str:
        """获取 ComfyUI URL（优先从缓存获取）"""
        # 如果缓存有效，直接返回
        if self._base_url and time.time() - self._base_url_cache_time < self._base_url_cache_ttl:
            return self._base_url
        return self._base_url or DEFAULT_COMFYUI_URL
    
    async def get_base_url(self) -> str:
        """异步获取 ComfyUI URL（从数据库）"""
        if self._base_url and time.time() - self._base_url_cache_time < self._base_url_cache_ttl:
            return self._base_url
        
        try:
            from ..database import async_session
            from ..models import ComfyUIServer
            from sqlalchemy import select
            
            async with async_session() as db:
                result = await db.execute(
                    select(ComfyUIServer)
                    .where(ComfyUIServer.is_default == True)
                    .where(ComfyUIServer.is_active == True)
                )
                server = result.scalar_one_or_none()
                
                if server:
                    self._base_url = server.url
                else:
                    result = await db.execute(
                        select(ComfyUIServer)
                        .where(ComfyUIServer.is_active == True)
                        .order_by(ComfyUIServer.created_at)
                        .limit(1)
                    )
                    server = result.scalar_one_or_none()
                    if server:
                        self._base_url = server.url
                    else:
                        self._base_url = DEFAULT_COMFYUI_URL
                
                self._base_url_cache_time = time.time()
        except Exception as e:
            logger.warning("获取 ComfyUI URL 配置失败，使用默认值: %s", e)
            self._base_url = DEFAULT_COMFYUI_URL
        
        return self._base_url
    
    def _get_cache(self, key: str) -> Any | None:
        """获取缓存"""
        entry = self._cache.get(key)
        if entry and not entry.is_expired():
            return entry.data
        return None
    
    def _set_cache(self, key: str, data: Any, ttl: int = 60):
        """设置缓存"""
        self._cache[key] = CacheEntry(data, ttl)
    
    async def check_connection(self) -> bool:
        """检查 ComfyUI 连接状态"""
        try:
            base_url = await self.get_base_url()
            response = await self.client.get(f"{base_url}/system_stats")
            return response.status_code == 200
        except Exception:
            return False
    
    async def get_system_stats(self, use_cache: bool = True) -> dict[str, Any]:
        """获取系统状态（带缓存，10秒TTL）"""
        base_url = await self.get_base_url()
        cache_key = f"system_stats:{base_url}"

        if use_cache:
            cached = cache_service.get(cache_key)
            if cached is not None:
                return cached

        try:
            response = await self.client.get(f"{base_url}/system_stats")
            if response.status_code == 200:
                data = response.json()
                cache_service.set(cache_key, data, ttl=10)  # 缓存10秒
                return data
        except Exception:
            pass
        return {}
    
    async def get_queue(self, use_cache: bool = True) -> dict[str, Any]:
        """获取队列状态（带缓存，5秒TTL）"""
        base_url = await self.get_base_url()
        cache_key = f"queue:{base_url}"

        if use_cache:
            cached = cache_service.get(cache_key)
            if cached is not None:
                return cached

        try:
            response = await self.client.get(f"{base_url}/queue")
            if response.status_code == 200:
                data = response.json()
                cache_service.set(cache_key, data, ttl=5)  # 缓存5秒
                return data
        except Exception:
            pass
        return {"queue_running": [], "queue_pending": []}
    
    async def queue_prompt(self, workflow_data: dict[str, Any], client_id: str = "") -> dict[str, Any]:
        """提交工作流到队列"""
        payload = {
            "prompt": workflow_data,
        }
        if client_id:
            payload["client_id"] = client_id
        
        try:
            base_url = await self.get_base_url()
            response = await self.client.post(
                f"{base_url}/prompt",
                json=payload,
            )
            if response.status_code == 200:
                return response.json()
            else:
                return {"error": response.text}
        except Exception as e:
            return {"error": str(e)}
    
    async def get_history(self, prompt_id: str = "") -> dict[str, Any]:
        """获取执行历史"""
        try:
            base_url = await self.get_base_url()
            url = f"{base_url}/history"
            if prompt_id:
                url = f"{url}/{prompt_id}"
            response = await self.client.get(url)
            if response.status_code == 200:
                return response.json()
        except Exception:
            pass
        return {}
    
    async def get_object_info(self) -> dict[str, Any]:
        """获取节点信息（带缓存，10分钟）"""
        cache_key = "object_info"
        cached = self._get_cache(cache_key)
        if cached:
            logger.debug("Using cached object_info")
            return cached
        
        try:
            base_url = await self.get_base_url()
            response = await self.client.get(f"{base_url}/object_info")
            if response.status_code == 200:
                data = response.json()
                self._set_cache(cache_key, data, ttl=600)  # 缓存 10 分钟
                return data
        except Exception as e:
            logger.error("Failed to get object_info: %s", e)
        return {}
    
    async def interrupt(self) -> bool:
        """中断当前执行"""
        try:
            base_url = await self.get_base_url()
            response = await self.client.post(f"{base_url}/interrupt")
            return response.status_code == 200
        except Exception:
            return False
    
    async def clear_queue(self) -> bool:
        """清空队列"""
        try:
            base_url = await self.get_base_url()
            response = await self.client.post(
                f"{base_url}/queue",
                json={"clear": True}
            )
            return response.status_code == 200
        except Exception:
            return False
    
    def _add_to_image_cache(self, key: str, data: bytes):
        """添加图片到缓存（带内存限制）"""
        data_size = len(data)
        max_size_bytes = self.MAX_CACHE_SIZE_MB * 1024 * 1024
        
        # 如果单个图片超过最大缓存大小的一半，不缓存
        if data_size > max_size_bytes // 2:
            logger.debug("Image too large to cache: %d bytes", data_size)
            return
        
        # 清理直到有足够空间
        while (self._cache_size_bytes + data_size > max_size_bytes or 
               len(self._image_cache) >= self.MAX_CACHE_COUNT):
            if not self._image_cache:
                break
            # 清理最旧的缓存
            oldest_key = min(self._image_cache, key=lambda k: self._image_cache[k][1])
            old_data, _ = self._image_cache[oldest_key]
            self._cache_size_bytes -= len(old_data)
            del self._image_cache[oldest_key]
        
        self._image_cache[key] = (data, time.time())
        self._cache_size_bytes += data_size
        logger.debug("Image cached: %s, cache size: %.2f MB", key, self._cache_size_bytes / 1024 / 1024)
    
    async def get_image(self, filename: str, subfolder: str = "", folder_type: str = "output") -> bytes | None:
        """获取生成的图片（带缓存，限制内存使用）"""
        # 生成缓存键
        cache_key = f"{folder_type}:{subfolder}:{filename}"
        
        # 检查缓存
        if cache_key in self._image_cache:
            data, timestamp = self._image_cache[cache_key]
            if time.time() - timestamp < self._image_cache_ttl:
                logger.debug("Using cached image: %s", filename)
                return data
            else:
                # 缓存过期，清理
                self._cache_size_bytes -= len(data)
                del self._image_cache[cache_key]
        
        try:
            base_url = await self.get_base_url()
            params = {
                "filename": filename,
                "subfolder": subfolder,
                "type": folder_type,
            }
            response = await self.client.get(f"{base_url}/view", params=params)
            if response.status_code == 200:
                data = response.content
                # 缓存图片（带内存限制）
                self._add_to_image_cache(cache_key, data)
                return data
        except Exception as e:
            logger.error("Failed to get image %s: %s", filename, e)
        return None
    
    async def upload_image(self, file_content: bytes, filename: str, subfolder: str = "", overwrite: bool = False) -> dict[str, Any]:
        """上传图片到 ComfyUI"""
        try:
            base_url = await self.get_base_url()
            files = {"image": (filename, file_content)}
            data = {
                "subfolder": subfolder,
                "overwrite": str(overwrite).lower(),
            }
            response = await self.client.post(
                f"{base_url}/upload/image",
                files=files,
                data=data,
            )
            if response.status_code == 200:
                return response.json()
        except Exception as e:
            return {"error": str(e)}
        return {}
    
    async def get_models(self) -> list[str]:
        """获取可用的模型列表"""
        cache_key = "models"
        cached = self._get_cache(cache_key)
        if cached:
            return cached
        
        object_info = await self.get_object_info()
        models = []
        
        if "CheckpointLoaderSimple" in object_info:
            ckpt_info = object_info["CheckpointLoaderSimple"]
            if "input" in ckpt_info and "required" in ckpt_info["input"]:
                ckpt_name = ckpt_info["input"]["required"].get("ckpt_name", [])
                if isinstance(ckpt_name, list) and len(ckpt_name) > 0 and isinstance(ckpt_name[0], list):
                    models = ckpt_name[0]
        
        self._set_cache(cache_key, models, ttl=300)
        return models
    
    async def get_unets(self) -> list[str]:
        """获取可用的 UNET 模型列表"""
        cache_key = "unets"
        cached = self._get_cache(cache_key)
        if cached:
            return cached
        
        object_info = await self.get_object_info()
        unets = []
        
        if "UNETLoader" in object_info:
            unet_info = object_info["UNETLoader"]
            if "input" in unet_info and "required" in unet_info["input"]:
                unet_name = unet_info["input"]["required"].get("unet_name", [])
                if isinstance(unet_name, list) and len(unet_name) > 0 and isinstance(unet_name[0], list):
                    unets = unet_name[0]
        
        self._set_cache(cache_key, unets, ttl=300)
        return unets
    
    async def get_vaes(self) -> list[str]:
        """获取可用的 VAE 列表"""
        cache_key = "vaes"
        cached = self._get_cache(cache_key)
        if cached:
            return cached
        
        object_info = await self.get_object_info()
        vaes = []
        
        if "VAELoader" in object_info:
            vae_info = object_info["VAELoader"]
            if "input" in vae_info and "required" in vae_info["input"]:
                vae_name = vae_info["input"]["required"].get("vae_name", [])
                if isinstance(vae_name, list) and len(vae_name) > 0 and isinstance(vae_name[0], list):
                    vaes = vae_name[0]
        
        self._set_cache(cache_key, vaes, ttl=300)
        return vaes
    
    async def get_loras(self) -> list[str]:
        """获取可用的 LoRA 列表"""
        cache_key = "loras"
        cached = self._get_cache(cache_key)
        if cached:
            return cached
        
        object_info = await self.get_object_info()
        loras = []
        
        if "LoraLoader" in object_info:
            lora_info = object_info["LoraLoader"]
            if "input" in lora_info and "required" in lora_info["input"]:
                lora_name = lora_info["input"]["required"].get("lora_name", [])
                if isinstance(lora_name, list) and len(lora_name) > 0 and isinstance(lora_name[0], list):
                    loras = lora_name[0]
        
        self._set_cache(cache_key, loras, ttl=300)
        return loras
    
    async def get_samplers(self) -> list[str]:
        """获取可用的采样器列表"""
        cache_key = "samplers"
        cached = self._get_cache(cache_key)
        if cached:
            return cached
        
        object_info = await self.get_object_info()
        samplers = []
        
        if "KSampler" in object_info:
            sampler_info = object_info["KSampler"]
            if "input" in sampler_info and "required" in sampler_info["input"]:
                sampler_name = sampler_info["input"]["required"].get("sampler_name", [])
                if isinstance(sampler_name, list) and len(sampler_name) > 0 and isinstance(sampler_name[0], list):
                    samplers = sampler_name[0]
        
        self._set_cache(cache_key, samplers, ttl=300)
        return samplers
    
    async def get_schedulers(self) -> list[str]:
        """获取可用的调度器列表"""
        cache_key = "schedulers"
        cached = self._get_cache(cache_key)
        if cached:
            return cached
        
        object_info = await self.get_object_info()
        schedulers = []
        
        if "KSampler" in object_info:
            sampler_info = object_info["KSampler"]
            if "input" in sampler_info and "required" in sampler_info["input"]:
                scheduler = sampler_info["input"]["required"].get("scheduler", [])
                if isinstance(scheduler, list) and len(scheduler) > 0 and isinstance(scheduler[0], list):
                    schedulers = scheduler[0]
        
        self._set_cache(cache_key, schedulers, ttl=300)
        return schedulers
    
    async def get_last_prompt(self) -> dict[str, Any]:
        """获取最后一次执行的工作流"""
        history = await self.get_history()
        if not history:
            return {}
        
        sorted_history = sorted(
            history.items(),
            key=lambda x: x[1].get("status", {}).get("status_str", ""),
            reverse=True
        )
        
        if sorted_history:
            prompt_id, data = sorted_history[0]
            prompt_info = data.get("prompt", [])
            if isinstance(prompt_info, list) and len(prompt_info) >= 3:
                return {
                    "prompt_id": prompt_id,
                    "workflow": prompt_info[2],
                }
        
        return {}
    
    async def get_recent_images_with_prompt(self, limit: int = 100) -> list[dict[str, Any]]:
        """获取最近生成的图片列表（从历史记录中提取）
        
        Args:
            limit: 最大返回数量
            
        Returns:
            图片信息列表，每项包含 filename, subfolder, type, prompt_id, positive, negative 等
        """
        from .prompt_extractor import prompt_extractor
        
        history = await self.get_history()
        if not history:
            return []
        
        images = []
        
        for prompt_id, data in history.items():
            outputs = data.get("outputs", {})
            prompt_info = data.get("prompt", [])
            
            # 提取 prompt 数据
            positive = ""
            negative = ""
            model = ""
            sampler = ""
            steps = 0
            cfg = 0.0
            seed = 0
            
            if isinstance(prompt_info, list) and len(prompt_info) >= 3:
                workflow = prompt_info[2]
                if isinstance(workflow, dict):
                    extracted = prompt_extractor.extract_from_workflow(workflow)
                    if extracted:
                        p = extracted[0]
                        positive = p.positive
                        negative = p.negative
                        model = p.model
                        sampler = p.sampler
                        steps = p.steps
                        cfg = p.cfg
                        seed = p.seed
            
            # 遍历所有节点的输出
            for node_id, node_output in outputs.items():
                if "images" in node_output:
                    for img in node_output["images"]:
                        img_info = {
                            "filename": img.get("filename", ""),
                            "subfolder": img.get("subfolder", ""),
                            "type": img.get("type", "output"),
                            "prompt_id": prompt_id,
                            "node_id": node_id,
                            "positive": positive,
                            "negative": negative,
                            "model": model,
                            "sampler": sampler,
                            "steps": steps,
                            "cfg": cfg,
                            "seed": seed,
                        }
                        images.append(img_info)
            
            if len(images) >= limit:
                break
        
        return images[:limit]


# 单例
comfyui_service = ComfyUIService()
