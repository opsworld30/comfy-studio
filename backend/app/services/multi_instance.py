"""多 ComfyUI 实例管理服务"""
import logging
import asyncio
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
import httpx

logger = logging.getLogger(__name__)


@dataclass
class ComfyUIInstance:
    """ComfyUI 实例信息"""
    id: str
    name: str
    url: str
    enabled: bool = True
    priority: int = 0  # 优先级，数字越小优先级越高
    max_queue: int = 5  # 最大队列长度
    
    # 运行时状态
    is_online: bool = False
    current_queue: int = 0
    last_check: datetime | None = None
    last_error: str | None = None
    
    # 统计信息
    total_jobs: int = 0
    successful_jobs: int = 0
    failed_jobs: int = 0


class MultiInstanceService:
    """管理多个 ComfyUI 实例"""
    
    def __init__(self):
        self.instances: dict[str, ComfyUIInstance] = {}
        self._running = False
        self._task: asyncio.Task | None = None
        self._client = httpx.AsyncClient(timeout=10.0)
    
    def add_instance(
        self,
        id: str,
        name: str,
        url: str,
        priority: int = 0,
        max_queue: int = 5,
    ) -> ComfyUIInstance:
        """添加 ComfyUI 实例"""
        instance = ComfyUIInstance(
            id=id,
            name=name,
            url=url.rstrip('/'),
            priority=priority,
            max_queue=max_queue,
        )
        self.instances[id] = instance
        logger.info(f"添加 ComfyUI 实例: {name} ({url})")
        return instance
    
    def remove_instance(self, id: str) -> bool:
        """移除实例"""
        if id in self.instances:
            del self.instances[id]
            logger.info(f"移除 ComfyUI 实例: {id}")
            return True
        return False
    
    def get_instance(self, id: str) -> ComfyUIInstance | None:
        """获取实例"""
        return self.instances.get(id)
    
    def list_instances(self) -> list[ComfyUIInstance]:
        """列出所有实例"""
        return list(self.instances.values())
    
    async def start(self, check_interval: int = 30):
        """启动健康检查任务"""
        if self._running:
            return
        
        self._running = True
        self._task = asyncio.create_task(self._health_check_loop(check_interval))
        logger.info("多实例管理服务已启动")
    
    async def stop(self):
        """停止服务"""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        await self._client.aclose()
        logger.info("多实例管理服务已停止")
    
    async def _health_check_loop(self, interval: int):
        """健康检查循环"""
        while self._running:
            await self.check_all_instances()
            await asyncio.sleep(interval)
    
    async def check_all_instances(self):
        """检查所有实例状态"""
        tasks = [self.check_instance(id) for id in self.instances]
        await asyncio.gather(*tasks, return_exceptions=True)
    
    async def check_instance(self, id: str) -> bool:
        """检查单个实例状态"""
        instance = self.instances.get(id)
        if not instance:
            return False
        
        try:
            # 获取系统状态
            response = await self._client.get(f"{instance.url}/system_stats")
            response.raise_for_status()
            
            # 获取队列状态
            queue_response = await self._client.get(f"{instance.url}/queue")
            queue_data = queue_response.json()
            
            instance.is_online = True
            instance.current_queue = len(queue_data.get("queue_running", [])) + len(queue_data.get("queue_pending", []))
            instance.last_check = datetime.now()
            instance.last_error = None
            
            return True
            
        except Exception as e:
            instance.is_online = False
            instance.last_check = datetime.now()
            instance.last_error = str(e)
            logger.warning(f"实例 {instance.name} 检查失败: {e}")
            return False
    
    def get_best_instance(self) -> ComfyUIInstance | None:
        """获取最佳可用实例（负载均衡）"""
        available = [
            inst for inst in self.instances.values()
            if inst.enabled and inst.is_online and inst.current_queue < inst.max_queue
        ]
        
        if not available:
            return None
        
        # 按优先级和当前队列长度排序
        available.sort(key=lambda x: (x.priority, x.current_queue))
        return available[0]
    
    async def queue_prompt(
        self,
        prompt: dict,
        instance_id: str | None = None
    ) -> tuple[ComfyUIInstance | None, dict]:
        """向实例提交任务"""
        # 选择实例
        if instance_id:
            instance = self.instances.get(instance_id)
            if not instance or not instance.is_online:
                return None, {"error": f"实例 {instance_id} 不可用"}
        else:
            instance = self.get_best_instance()
            if not instance:
                return None, {"error": "没有可用的 ComfyUI 实例"}
        
        try:
            response = await self._client.post(
                f"{instance.url}/prompt",
                json={"prompt": prompt}
            )
            response.raise_for_status()
            result = response.json()
            
            instance.total_jobs += 1
            instance.current_queue += 1
            
            return instance, result
            
        except Exception as e:
            instance.failed_jobs += 1
            logger.error(f"向实例 {instance.name} 提交任务失败: {e}")
            return instance, {"error": str(e)}
    
    async def get_history(
        self,
        prompt_id: str,
        instance_id: str | None = None
    ) -> dict:
        """获取执行历史"""
        # 如果指定了实例
        if instance_id:
            instance = self.instances.get(instance_id)
            if instance:
                try:
                    response = await self._client.get(
                        f"{instance.url}/history/{prompt_id}"
                    )
                    return response.json()
                except Exception:
                    pass
            return {}
        
        # 否则查询所有在线实例
        for instance in self.instances.values():
            if not instance.is_online:
                continue
            
            try:
                response = await self._client.get(
                    f"{instance.url}/history/{prompt_id}"
                )
                data = response.json()
                if data:
                    return data
            except Exception:
                continue
        
        return {}
    
    def get_stats(self) -> dict:
        """获取统计信息"""
        online_count = sum(1 for inst in self.instances.values() if inst.is_online)
        total_queue = sum(inst.current_queue for inst in self.instances.values() if inst.is_online)
        
        return {
            "total_instances": len(self.instances),
            "online_instances": online_count,
            "total_queue": total_queue,
            "instances": [
                {
                    "id": inst.id,
                    "name": inst.name,
                    "url": inst.url,
                    "is_online": inst.is_online,
                    "current_queue": inst.current_queue,
                    "total_jobs": inst.total_jobs,
                    "successful_jobs": inst.successful_jobs,
                    "failed_jobs": inst.failed_jobs,
                    "last_check": inst.last_check.isoformat() if inst.last_check else None,
                    "last_error": inst.last_error,
                }
                for inst in self.instances.values()
            ]
        }


# 全局实例
multi_instance_service = MultiInstanceService()
