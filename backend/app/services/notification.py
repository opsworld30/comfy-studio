"""通知服务"""
import logging
from typing import Any, Callable, Awaitable
from enum import Enum

logger = logging.getLogger(__name__)


class NotificationType(str, Enum):
    EXECUTION_START = "execution_start"
    EXECUTION_COMPLETE = "execution_complete"
    EXECUTION_ERROR = "execution_error"
    QUEUE_UPDATE = "queue_update"
    SYSTEM_ALERT = "system_alert"


class NotificationService:
    """通知服务 - 管理事件订阅和推送"""
    
    def __init__(self):
        self._subscribers: dict[NotificationType, list[Callable[[dict], Awaitable[None]]]] = {}
        self._history: list[dict] = []
        self._max_history = 100
    
    def subscribe(
        self, 
        event_type: NotificationType, 
        callback: Callable[[dict], Awaitable[None]]
    ):
        """订阅事件"""
        if event_type not in self._subscribers:
            self._subscribers[event_type] = []
        self._subscribers[event_type].append(callback)
        logger.info(f"New subscriber for {event_type}")
    
    def unsubscribe(
        self, 
        event_type: NotificationType, 
        callback: Callable[[dict], Awaitable[None]]
    ):
        """取消订阅"""
        if event_type in self._subscribers:
            self._subscribers[event_type] = [
                cb for cb in self._subscribers[event_type] if cb != callback
            ]
    
    async def notify(
        self, 
        event_type: NotificationType, 
        data: dict[str, Any],
        save_history: bool = True
    ):
        """发送通知"""
        notification = {
            "type": event_type.value,
            "data": data,
        }
        
        # 保存历史
        if save_history:
            self._history.append(notification)
            if len(self._history) > self._max_history:
                self._history = self._history[-self._max_history:]
        
        # 通知所有订阅者
        if event_type in self._subscribers:
            for callback in self._subscribers[event_type]:
                try:
                    await callback(notification)
                except Exception as e:
                    logger.error(f"Notification callback error: {e}")
        
        logger.debug(f"Notification sent: {event_type} - {data}")
    
    async def notify_execution_start(self, prompt_id: str, workflow_name: str | None = None):
        """通知执行开始"""
        await self.notify(
            NotificationType.EXECUTION_START,
            {
                "prompt_id": prompt_id,
                "workflow_name": workflow_name,
                "message": f"工作流 {workflow_name or prompt_id} 开始执行",
            }
        )
    
    async def notify_execution_complete(
        self, 
        prompt_id: str, 
        workflow_name: str | None = None,
        images: list[str] | None = None
    ):
        """通知执行完成"""
        await self.notify(
            NotificationType.EXECUTION_COMPLETE,
            {
                "prompt_id": prompt_id,
                "workflow_name": workflow_name,
                "images": images or [],
                "message": f"工作流 {workflow_name or prompt_id} 执行完成",
            }
        )
    
    async def notify_execution_error(
        self, 
        prompt_id: str, 
        error: str,
        workflow_name: str | None = None
    ):
        """通知执行错误"""
        await self.notify(
            NotificationType.EXECUTION_ERROR,
            {
                "prompt_id": prompt_id,
                "workflow_name": workflow_name,
                "error": error,
                "message": f"工作流 {workflow_name or prompt_id} 执行失败: {error}",
            }
        )
    
    def get_history(self, limit: int = 50) -> list[dict]:
        """获取通知历史"""
        return self._history[-limit:]


# 单例
notification_service = NotificationService()
