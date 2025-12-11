"""异步任务队列服务

基于 asyncio 的轻量级任务队列，支持：
- 优先级队列
- 任务重试
- 并发控制
- 任务状态追踪
- 死信队列
"""
import asyncio
import logging
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Coroutine, TypeVar
from collections import defaultdict

logger = logging.getLogger(__name__)

T = TypeVar('T')


class TaskStatus(str, Enum):
    """任务状态"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    RETRYING = "retrying"


class TaskPriority(int, Enum):
    """任务优先级（数值越小优先级越高）"""
    CRITICAL = 0
    HIGH = 1
    NORMAL = 2
    LOW = 3
    BACKGROUND = 4


@dataclass(order=True)
class Task:
    """任务定义"""
    priority: int
    created_at: float = field(compare=True)
    task_id: str = field(default_factory=lambda: str(uuid.uuid4()), compare=False)
    name: str = field(default="", compare=False)
    func: Callable[..., Coroutine] = field(default=None, compare=False)
    args: tuple = field(default_factory=tuple, compare=False)
    kwargs: dict = field(default_factory=dict, compare=False)
    max_retries: int = field(default=3, compare=False)
    retry_count: int = field(default=0, compare=False)
    retry_delay: float = field(default=1.0, compare=False)  # 重试延迟（秒）
    timeout: float = field(default=300.0, compare=False)  # 超时时间（秒）
    status: TaskStatus = field(default=TaskStatus.PENDING, compare=False)
    result: Any = field(default=None, compare=False)
    error: str = field(default="", compare=False)
    started_at: float = field(default=0, compare=False)
    completed_at: float = field(default=0, compare=False)
    callback: Callable[[Any], None] = field(default=None, compare=False)
    error_callback: Callable[[Exception], None] = field(default=None, compare=False)


@dataclass
class QueueStats:
    """队列统计信息"""
    pending: int = 0
    running: int = 0
    completed: int = 0
    failed: int = 0
    cancelled: int = 0
    total_processed: int = 0
    avg_wait_time: float = 0.0
    avg_execution_time: float = 0.0


class TaskQueue:
    """异步任务队列
    
    支持优先级、重试、并发控制等特性
    """
    
    def __init__(
        self,
        name: str = "default",
        max_workers: int = 4,
        max_queue_size: int = 1000,
    ):
        self.name = name
        self.max_workers = max_workers
        self.max_queue_size = max_queue_size
        
        self._queue: asyncio.PriorityQueue[Task] = asyncio.PriorityQueue(maxsize=max_queue_size)
        self._workers: list[asyncio.Task] = []
        self._running_tasks: dict[str, Task] = {}
        self._completed_tasks: dict[str, Task] = {}
        self._dead_letter_queue: list[Task] = []
        
        self._running = False
        self._shutdown_event = asyncio.Event()
        
        # 统计信息
        self._stats = QueueStats()
        self._wait_times: list[float] = []
        self._execution_times: list[float] = []
        
        # 任务回调
        self._global_callbacks: dict[str, list[Callable]] = defaultdict(list)
    
    async def start(self):
        """启动任务队列"""
        if self._running:
            return
        
        self._running = True
        self._shutdown_event.clear()
        
        # 启动工作协程
        for i in range(self.max_workers):
            worker = asyncio.create_task(self._worker(i))
            self._workers.append(worker)
        
        logger.info(f"TaskQueue '{self.name}' started with {self.max_workers} workers")
    
    async def stop(self, wait: bool = True, timeout: float = 30.0):
        """停止任务队列
        
        Args:
            wait: 是否等待当前任务完成
            timeout: 等待超时时间
        """
        if not self._running:
            return
        
        self._running = False
        self._shutdown_event.set()
        
        if wait and self._running_tasks:
            logger.info(f"Waiting for {len(self._running_tasks)} running tasks to complete...")
            try:
                await asyncio.wait_for(
                    asyncio.gather(*[asyncio.sleep(0.1) for _ in range(int(timeout * 10))]),
                    timeout=timeout
                )
            except asyncio.TimeoutError:
                logger.warning("Timeout waiting for tasks, cancelling workers")
        
        # 取消所有工作协程
        for worker in self._workers:
            worker.cancel()
        
        await asyncio.gather(*self._workers, return_exceptions=True)
        self._workers.clear()
        
        logger.info(f"TaskQueue '{self.name}' stopped")
    
    async def submit(
        self,
        func: Callable[..., Coroutine],
        *args,
        name: str = "",
        priority: TaskPriority = TaskPriority.NORMAL,
        max_retries: int = 3,
        retry_delay: float = 1.0,
        timeout: float = 300.0,
        callback: Callable[[Any], None] = None,
        error_callback: Callable[[Exception], None] = None,
        **kwargs
    ) -> str:
        """提交任务
        
        Args:
            func: 异步函数
            *args: 位置参数
            name: 任务名称
            priority: 优先级
            max_retries: 最大重试次数
            retry_delay: 重试延迟
            timeout: 超时时间
            callback: 成功回调
            error_callback: 失败回调
            **kwargs: 关键字参数
            
        Returns:
            任务 ID
        """
        if not self._running:
            raise RuntimeError("TaskQueue is not running")
        
        task = Task(
            priority=priority.value,
            created_at=time.time(),
            name=name or func.__name__,
            func=func,
            args=args,
            kwargs=kwargs,
            max_retries=max_retries,
            retry_delay=retry_delay,
            timeout=timeout,
            callback=callback,
            error_callback=error_callback,
        )
        
        try:
            self._queue.put_nowait(task)
            self._stats.pending += 1
            logger.debug(f"Task '{task.name}' ({task.task_id}) submitted with priority {priority.name}")
            return task.task_id
        except asyncio.QueueFull:
            raise RuntimeError(f"Queue is full (max_size={self.max_queue_size})")
    
    async def submit_batch(
        self,
        tasks: list[tuple[Callable, tuple, dict]],
        priority: TaskPriority = TaskPriority.NORMAL,
    ) -> list[str]:
        """批量提交任务
        
        Args:
            tasks: [(func, args, kwargs), ...]
            priority: 优先级
            
        Returns:
            任务 ID 列表
        """
        task_ids = []
        for func, args, kwargs in tasks:
            task_id = await self.submit(func, *args, priority=priority, **kwargs)
            task_ids.append(task_id)
        return task_ids
    
    def get_task(self, task_id: str) -> Task | None:
        """获取任务信息"""
        if task_id in self._running_tasks:
            return self._running_tasks[task_id]
        if task_id in self._completed_tasks:
            return self._completed_tasks[task_id]
        return None
    
    async def cancel_task(self, task_id: str) -> bool:
        """取消任务（仅支持取消未开始的任务）"""
        # 注意：asyncio.PriorityQueue 不支持直接删除元素
        # 这里只能标记任务为取消状态，在执行时跳过
        task = self.get_task(task_id)
        if task and task.status == TaskStatus.PENDING:
            task.status = TaskStatus.CANCELLED
            self._stats.cancelled += 1
            return True
        return False
    
    def get_stats(self) -> dict:
        """获取队列统计信息"""
        # 计算平均等待时间和执行时间
        avg_wait = sum(self._wait_times[-100:]) / len(self._wait_times[-100:]) if self._wait_times else 0
        avg_exec = sum(self._execution_times[-100:]) / len(self._execution_times[-100:]) if self._execution_times else 0
        
        return {
            "name": self.name,
            "max_workers": self.max_workers,
            "active_workers": len([w for w in self._workers if not w.done()]),
            "pending": self._queue.qsize(),
            "running": len(self._running_tasks),
            "completed": self._stats.completed,
            "failed": self._stats.failed,
            "cancelled": self._stats.cancelled,
            "total_processed": self._stats.total_processed,
            "avg_wait_time_ms": round(avg_wait * 1000, 2),
            "avg_execution_time_ms": round(avg_exec * 1000, 2),
            "dead_letter_count": len(self._dead_letter_queue),
        }
    
    def get_dead_letter_tasks(self) -> list[dict]:
        """获取死信队列中的任务"""
        return [
            {
                "task_id": t.task_id,
                "name": t.name,
                "error": t.error,
                "retry_count": t.retry_count,
                "created_at": datetime.fromtimestamp(t.created_at, tz=timezone.utc).isoformat(),
            }
            for t in self._dead_letter_queue
        ]
    
    async def retry_dead_letter(self, task_id: str) -> bool:
        """重试死信队列中的任务"""
        for i, task in enumerate(self._dead_letter_queue):
            if task.task_id == task_id:
                task.retry_count = 0
                task.status = TaskStatus.PENDING
                task.error = ""
                self._dead_letter_queue.pop(i)
                await self._queue.put(task)
                return True
        return False
    
    def on(self, event: str, callback: Callable):
        """注册全局事件回调
        
        支持的事件：
        - task_started: 任务开始
        - task_completed: 任务完成
        - task_failed: 任务失败
        - task_retrying: 任务重试
        """
        self._global_callbacks[event].append(callback)
    
    async def _emit(self, event: str, task: Task, **kwargs):
        """触发事件"""
        for callback in self._global_callbacks[event]:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(task, **kwargs)
                else:
                    callback(task, **kwargs)
            except Exception as e:
                logger.error(f"Error in event callback: {e}")
    
    async def _worker(self, worker_id: int):
        """工作协程"""
        logger.debug(f"Worker {worker_id} started")
        
        while self._running or not self._queue.empty():
            try:
                # 使用超时获取任务，以便检查关闭事件
                try:
                    task = await asyncio.wait_for(self._queue.get(), timeout=1.0)
                except asyncio.TimeoutError:
                    continue
                
                # 检查任务是否已取消
                if task.status == TaskStatus.CANCELLED:
                    self._queue.task_done()
                    continue
                
                # 记录等待时间
                wait_time = time.time() - task.created_at
                self._wait_times.append(wait_time)
                
                # 执行任务
                await self._execute_task(task)
                
                self._queue.task_done()
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Worker {worker_id} error: {e}")
        
        logger.debug(f"Worker {worker_id} stopped")
    
    async def _execute_task(self, task: Task):
        """执行单个任务"""
        task.status = TaskStatus.RUNNING
        task.started_at = time.time()
        self._running_tasks[task.task_id] = task
        self._stats.pending -= 1
        self._stats.running = len(self._running_tasks)
        
        await self._emit("task_started", task)
        
        try:
            # 带超时执行
            result = await asyncio.wait_for(
                task.func(*task.args, **task.kwargs),
                timeout=task.timeout
            )
            
            task.status = TaskStatus.COMPLETED
            task.result = result
            task.completed_at = time.time()
            
            # 记录执行时间
            exec_time = task.completed_at - task.started_at
            self._execution_times.append(exec_time)
            
            self._stats.completed += 1
            self._stats.total_processed += 1
            
            # 调用成功回调
            if task.callback:
                try:
                    if asyncio.iscoroutinefunction(task.callback):
                        await task.callback(result)
                    else:
                        task.callback(result)
                except Exception as e:
                    logger.error(f"Task callback error: {e}")
            
            await self._emit("task_completed", task, result=result)
            
            logger.debug(f"Task '{task.name}' completed in {exec_time:.2f}s")
            
        except asyncio.TimeoutError:
            task.error = f"Task timed out after {task.timeout}s"
            await self._handle_task_failure(task, TimeoutError(task.error))
            
        except Exception as e:
            task.error = str(e)
            await self._handle_task_failure(task, e)
        
        finally:
            self._running_tasks.pop(task.task_id, None)
            self._completed_tasks[task.task_id] = task
            self._stats.running = len(self._running_tasks)
            
            # 限制已完成任务的缓存大小
            if len(self._completed_tasks) > 1000:
                oldest_key = next(iter(self._completed_tasks))
                del self._completed_tasks[oldest_key]
    
    async def _handle_task_failure(self, task: Task, error: Exception):
        """处理任务失败"""
        task.retry_count += 1
        
        if task.retry_count <= task.max_retries:
            # 重试
            task.status = TaskStatus.RETRYING
            await self._emit("task_retrying", task, error=error, retry_count=task.retry_count)
            
            logger.warning(
                f"Task '{task.name}' failed, retrying ({task.retry_count}/{task.max_retries}): {error}"
            )
            
            # 延迟后重新入队
            await asyncio.sleep(task.retry_delay * task.retry_count)  # 指数退避
            task.status = TaskStatus.PENDING
            await self._queue.put(task)
            self._stats.pending += 1
        else:
            # 移入死信队列
            task.status = TaskStatus.FAILED
            task.completed_at = time.time()
            self._dead_letter_queue.append(task)
            self._stats.failed += 1
            self._stats.total_processed += 1
            
            # 调用失败回调
            if task.error_callback:
                try:
                    if asyncio.iscoroutinefunction(task.error_callback):
                        await task.error_callback(error)
                    else:
                        task.error_callback(error)
                except Exception as e:
                    logger.error(f"Task error callback error: {e}")
            
            await self._emit("task_failed", task, error=error)
            
            logger.error(f"Task '{task.name}' failed after {task.max_retries} retries: {error}")


# ========== 全局任务队列实例 ==========

# 默认队列（通用任务）
default_queue = TaskQueue(name="default", max_workers=4)

# 高优先级队列（紧急任务）
priority_queue = TaskQueue(name="priority", max_workers=2)

# 后台队列（低优先级任务）
background_queue = TaskQueue(name="background", max_workers=2)


async def start_all_queues():
    """启动所有任务队列"""
    await default_queue.start()
    await priority_queue.start()
    await background_queue.start()
    logger.info("All task queues started")


async def stop_all_queues():
    """停止所有任务队列"""
    await default_queue.stop()
    await priority_queue.stop()
    await background_queue.stop()
    logger.info("All task queues stopped")


def get_all_queue_stats() -> dict:
    """获取所有队列的统计信息"""
    return {
        "default": default_queue.get_stats(),
        "priority": priority_queue.get_stats(),
        "background": background_queue.get_stats(),
    }
