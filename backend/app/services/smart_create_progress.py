"""智能创作进度 WebSocket 推送服务"""
import asyncio
import json
import logging
from typing import Optional
from dataclasses import dataclass
from fastapi import WebSocket
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


@dataclass
class TaskProgress:
    """任务进度数据"""
    task_id: int
    status: str
    total_count: int
    completed_count: int
    failed_count: int
    current_job: Optional[dict] = None
    message: str = ""
    timestamp: str = ""

    def to_dict(self) -> dict:
        return {
            "type": "smart_create_progress",
            "task_id": self.task_id,
            "status": self.status,
            "total_count": self.total_count,
            "completed_count": self.completed_count,
            "failed_count": self.failed_count,
            "current_job": self.current_job,
            "message": self.message,
            "timestamp": self.timestamp or datetime.now(timezone.utc).isoformat(),
        }


class SmartCreateProgressManager:
    """智能创作进度管理器 - 支持 WebSocket 广播"""

    def __init__(self):
        # task_id -> set of WebSocket connections
        self._subscribers: dict[int, set[WebSocket]] = {}
        # 全局订阅者（接收所有任务更新）
        self._global_subscribers: set[WebSocket] = set()
        self._lock = asyncio.Lock()

    async def subscribe(self, websocket: WebSocket, task_id: Optional[int] = None):
        """订阅任务进度更新"""
        async with self._lock:
            if task_id is not None:
                if task_id not in self._subscribers:
                    self._subscribers[task_id] = set()
                self._subscribers[task_id].add(websocket)
                logger.info(f"WebSocket 订阅任务 {task_id}")
            else:
                self._global_subscribers.add(websocket)
                logger.info("WebSocket 订阅全局任务更新")

    async def unsubscribe(self, websocket: WebSocket, task_id: Optional[int] = None):
        """取消订阅"""
        async with self._lock:
            if task_id is not None:
                if task_id in self._subscribers:
                    self._subscribers[task_id].discard(websocket)
                    if not self._subscribers[task_id]:
                        del self._subscribers[task_id]
            else:
                self._global_subscribers.discard(websocket)
            # 清理所有订阅
            for tid in list(self._subscribers.keys()):
                self._subscribers[tid].discard(websocket)
                if not self._subscribers[tid]:
                    del self._subscribers[tid]

    async def broadcast_progress(self, progress: TaskProgress):
        """广播进度更新"""
        message = progress.to_dict()
        task_id = progress.task_id

        # 发送给特定任务的订阅者
        subscribers = self._subscribers.get(task_id, set()).copy()
        # 发送给全局订阅者
        all_subscribers = subscribers | self._global_subscribers.copy()

        disconnected = []
        for ws in all_subscribers:
            try:
                await ws.send_json(message)
            except Exception:
                disconnected.append(ws)

        # 清理断开的连接
        for ws in disconnected:
            await self.unsubscribe(ws)

    async def broadcast_job_update(
        self,
        task_id: int,
        job_index: int,
        job_status: str,
        job_title: str = "",
        job_path: str = "",
        error: str = ""
    ):
        """广播单个分镜更新"""
        message = {
            "type": "smart_create_job_update",
            "task_id": task_id,
            "job_index": job_index,
            "job_status": job_status,
            "job_title": job_title,
            "job_path": job_path,
            "error": error,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        subscribers = self._subscribers.get(task_id, set()).copy()
        all_subscribers = subscribers | self._global_subscribers.copy()

        disconnected = []
        for ws in all_subscribers:
            try:
                await ws.send_json(message)
            except Exception:
                disconnected.append(ws)

        for ws in disconnected:
            await self.unsubscribe(ws)

    async def broadcast_task_status(
        self,
        task_id: int,
        status: str,
        message: str = ""
    ):
        """广播任务状态变更"""
        msg = {
            "type": "smart_create_status",
            "task_id": task_id,
            "status": status,
            "message": message,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        subscribers = self._subscribers.get(task_id, set()).copy()
        all_subscribers = subscribers | self._global_subscribers.copy()

        disconnected = []
        for ws in all_subscribers:
            try:
                await ws.send_json(msg)
            except Exception:
                disconnected.append(ws)

        for ws in disconnected:
            await self.unsubscribe(ws)


# 全局单例
smart_create_progress_manager = SmartCreateProgressManager()
