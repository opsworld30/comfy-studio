"""智能创作任务执行服务 - 滑动窗口+流水线架构"""
import asyncio
import json
import logging
from asyncio import Semaphore, Queue
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Optional

import httpx
from sqlalchemy import select

from ..database import async_session
from ..models import SmartCreateTask, Workflow, ComfyUIServer
from ..config import get_settings
from .image_storage import image_storage_service
from .seed_manager import create_seed_manager
from .smart_create_progress import smart_create_progress_manager, TaskProgress

logger = logging.getLogger(__name__)

settings = get_settings()

# 默认超时时间（秒），可通过环境变量配置
DEFAULT_TASK_TIMEOUT = int(getattr(settings, 'SMART_CREATE_TIMEOUT', 1800))  # 默认 30 分钟


class JobStatus(Enum):
    """任务状态"""
    PENDING = "pending"
    SUBMITTED = "submitted"
    GENERATING = "generating"
    DOWNLOADING = "downloading"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class GenerationJob:
    """单个生成任务"""
    index: int
    prompt_index: int
    image_index: int
    prompt_data: dict
    title: str = ""
    prompt_id: Optional[str] = None
    status: JobStatus = JobStatus.PENDING
    result_url: Optional[str] = None
    local_path: Optional[str] = None
    subfolder: str = ""
    error: Optional[str] = None
    retry_count: int = 0
    _not_found_count: int = 0

    def to_dict(self) -> dict:
        """转换为可序列化的字典"""
        return {
            "prompt_index": self.prompt_index,
            "image_index": self.image_index,
            "prompt_id": self.prompt_id,
            "title": self.title,
            "status": self.status.value,
            "path": self.local_path,
            "subfolder": self.subfolder,
            "error": self.error,
            "_not_found_count": self._not_found_count,
        }


async def get_comfyui_url() -> str:
    """从数据库获取默认的 ComfyUI URL"""
    try:
        async with async_session() as db:
            result = await db.execute(
                select(ComfyUIServer).where(ComfyUIServer.is_default.is_(True))
            )
            server = result.scalar_one_or_none()
            if server:
                logger.info(f"使用 ComfyUI 服务器: {server.name} ({server.url})")
                return server.url
    except Exception as e:
        logger.warning(f"获取默认 ComfyUI 服务器失败: {e}")

    return settings.COMFYUI_URL


class SmartCreateExecutor:
    """智能创作任务执行器 - 滑动窗口+流水线架构"""

    def __init__(self):
        # 并发控制
        self.max_concurrent_generate = 2  # ComfyUI 同时生成数
        self.max_concurrent_download = 4  # 同时下载数
        self.max_retries = 3

        # 任务控制
        self.running_tasks: dict[int, asyncio.Task] = {}
        self.paused_tasks: set[int] = set()
        self.stopped_tasks: set[int] = set()
        self._default_checkpoint: Optional[str] = None
        self._recovery_done = False

    async def recover_interrupted_tasks(self):
        """恢复因服务重启而中断的任务"""
        if self._recovery_done:
            return
        self._recovery_done = True

        try:
            comfyui_url = await get_comfyui_url()

            async with async_session() as db:
                result = await db.execute(
                    select(SmartCreateTask).where(SmartCreateTask.status == "generating")
                )
                interrupted_tasks = result.scalars().all()

                if not interrupted_tasks:
                    logger.info("没有需要恢复的中断任务")
                    return

                logger.info(f"发现 {len(interrupted_tasks)} 个中断的任务，准备恢复...")

                for task in interrupted_tasks:
                    jobs = task.result_images or []

                    if jobs and any(j.get("prompt_id") for j in jobs if isinstance(j, dict)):
                        pending_jobs = [
                            j for j in jobs
                            if isinstance(j, dict) and j.get("status") not in ["completed", "failed"]
                        ]

                        if pending_jobs:
                            logger.info(f"任务 {task.id} 有 {len(pending_jobs)} 个未完成的 jobs，继续监控...")
                            asyncio.create_task(self._legacy_monitor_jobs(task.id, jobs, comfyui_url))
                        else:
                            completed_jobs = [j for j in jobs if isinstance(j, dict) and j.get("status") == "completed"]
                            failed_jobs = [j for j in jobs if isinstance(j, dict) and j.get("status") == "failed"]

                            if len(completed_jobs) > 0:
                                task.status = "completed"
                            else:
                                task.status = "failed"
                                task.error_message = "所有分镜生成失败"

                            task.completed_count = len(completed_jobs)
                            task.failed_count = len(failed_jobs)
                            await db.commit()
                    else:
                        logger.info(f"任务 {task.id} 没有已提交的 jobs，重新执行...")
                        task.completed_count = 0
                        task.failed_count = 0
                        task.result_images = []
                        await db.commit()
                        asyncio.create_task(self.execute_task(task.id))

        except Exception as e:
            logger.error(f"恢复中断任务失败: {e}")

    async def _get_default_checkpoint(self, comfyui_url: str) -> str:
        """获取默认的 checkpoint 模型"""
        if self._default_checkpoint:
            return self._default_checkpoint

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(f"{comfyui_url}/object_info/CheckpointLoaderSimple")
                if response.status_code == 200:
                    data = response.json()
                    checkpoints = data.get("CheckpointLoaderSimple", {}).get("input", {}).get("required", {}).get("ckpt_name", [[]])[0]
                    if checkpoints:
                        self._default_checkpoint = checkpoints[0]
                        logger.info(f"使用默认 checkpoint: {self._default_checkpoint}")
                        return self._default_checkpoint
        except Exception as e:
            logger.warning(f"获取 checkpoint 列表失败: {e}")

        return "v1-5-pruned-emaonly.safetensors"

    async def execute_task(self, task_id: int):
        """主执行入口 - 流水线架构"""
        comfyui_url = await get_comfyui_url()
        logger.info(f"执行任务 {task_id}，使用 ComfyUI: {comfyui_url}")

        async with async_session() as db:
            result = await db.execute(
                select(SmartCreateTask).where(SmartCreateTask.id == task_id)
            )
            task = result.scalar_one_or_none()

            if not task:
                return

            if not task.analyzed_prompts:
                task.status = "failed"
                task.error_message = "没有可执行的提示词"
                await db.commit()
                return

            # 获取工作流
            workflow_data = None
            if task.workflow_id:
                wf_result = await db.execute(
                    select(Workflow).where(Workflow.id == task.workflow_id)
                )
                workflow = wf_result.scalar_one_or_none()
                if workflow:
                    workflow_data = workflow.workflow_data

            # 执行配置
            images_per_prompt = task.config.get("images_per_prompt", 1)
            use_fixed_seed = task.config.get("use_fixed_seed", False)
            task_timeout = task.config.get("timeout", DEFAULT_TASK_TIMEOUT)

            logger.info(f"任务配置: images_per_prompt={images_per_prompt}, use_fixed_seed={use_fixed_seed}")

            # 创建种子管理器
            seed_manager = create_seed_manager(
                task_id=task_id,
                use_fixed_seed=use_fixed_seed
            )

            # 创建任务队列
            jobs = self._create_jobs(task, images_per_prompt)

            # 更新任务状态
            task.status = "generating"
            task.started_at = datetime.now(timezone.utc)
            task.total_count = len(jobs)
            task.result_images = [j.to_dict() for j in jobs]
            await db.commit()

            logger.info(f"任务 {task_id}: 分镜数={len(task.analyzed_prompts)}, 每分镜图片数={images_per_prompt}, 总任务数={len(jobs)}")

        # 创建流水线队列
        submit_queue: Queue[GenerationJob] = Queue()
        download_queue: Queue[GenerationJob] = Queue()

        # 放入待提交队列
        for job in jobs:
            await submit_queue.put(job)

        # 创建完成信号
        submit_done = asyncio.Event()
        download_done = asyncio.Event()

        try:
            # 启动流水线
            await asyncio.gather(
                self._submit_pipeline(
                    task_id, submit_queue, download_queue, submit_done,
                    workflow_data, task.image_size, seed_manager, comfyui_url
                ),
                self._monitor_pipeline(
                    task_id, jobs, download_queue, submit_done, comfyui_url, task_timeout
                ),
                self._download_pipeline(
                    task_id, download_queue, download_done, comfyui_url
                ),
                self._progress_reporter(task_id, jobs, download_done),
            )
        except Exception as e:
            logger.exception(f"任务 {task_id} 执行异常: {e}")

        # 最终状态更新
        await self._finalize_task(task_id, jobs)

    def _create_jobs(self, task: SmartCreateTask, images_per_prompt: int) -> list[GenerationJob]:
        """从任务创建 Job 列表"""
        jobs = []
        for i, prompt_data in enumerate(task.analyzed_prompts):
            for j in range(images_per_prompt):
                jobs.append(GenerationJob(
                    index=len(jobs),
                    prompt_index=i,
                    image_index=j,
                    prompt_data=prompt_data,
                    title=prompt_data.get("title", f"分镜 {i+1}"),
                ))
        return jobs

    async def _submit_pipeline(
        self,
        task_id: int,
        submit_queue: Queue[GenerationJob],
        download_queue: Queue[GenerationJob],
        submit_done: asyncio.Event,
        workflow_data: Optional[dict],
        image_size: str,
        seed_manager,
        comfyui_url: str
    ):
        """提交流水线 - 滑动窗口控制并发"""
        semaphore = Semaphore(self.max_concurrent_generate)
        submitted_count = 0
        total_jobs = submit_queue.qsize()

        try:
            while not submit_queue.empty():
                # 检查暂停/停止
                if task_id in self.stopped_tasks:
                    logger.info(f"任务 {task_id} 提交流水线被停止")
                    break
                while task_id in self.paused_tasks:
                    await asyncio.sleep(1)
                    if task_id in self.stopped_tasks:
                        break

                try:
                    job = submit_queue.get_nowait()
                except asyncio.QueueEmpty:
                    break

                # 使用信号量控制并发
                async with semaphore:
                    seed = seed_manager.get_seed_for_prompt(job.prompt_index, job.image_index)

                    try:
                        comfy_prompt = await self._build_comfy_prompt(
                            job.prompt_data,
                            workflow_data,
                            image_size,
                            seed,
                            comfyui_url
                        )

                        prompt_id = await self._queue_prompt(comfy_prompt, comfyui_url)

                        if prompt_id:
                            job.prompt_id = prompt_id
                            job.status = JobStatus.SUBMITTED
                            submitted_count += 1
                            logger.info(f"分镜 {job.prompt_index+1}-{job.image_index+1} 已提交: {prompt_id} ({submitted_count}/{total_jobs})")
                        else:
                            job.status = JobStatus.FAILED
                            job.error = "提交失败"
                            await download_queue.put(job)

                    except Exception as e:
                        job.error = str(e)
                        job.retry_count += 1
                        if job.retry_count < self.max_retries:
                            await submit_queue.put(job)  # 重试
                            logger.warning(f"分镜 {job.prompt_index+1} 提交失败，重试 {job.retry_count}/{self.max_retries}")
                        else:
                            job.status = JobStatus.FAILED
                            await download_queue.put(job)
                            logger.error(f"分镜 {job.prompt_index+1} 提交失败，已达最大重试次数")

        finally:
            submit_done.set()
            logger.info(f"任务 {task_id} 提交流水线完成，共提交 {submitted_count} 个任务")

    async def _monitor_pipeline(
        self,
        task_id: int,
        jobs: list[GenerationJob],
        download_queue: Queue[GenerationJob],
        submit_done: asyncio.Event,
        comfyui_url: str,
        timeout: int
    ):
        """监控流水线 - 监控提交的任务完成状态"""
        start_time = asyncio.get_event_loop().time()
        logger.info(f"任务 {task_id} 监控流水线启动，超时 {timeout}s")

        # 获取任务的 analyzed_prompts
        task_analyzed_prompts = []
        async with async_session() as db:
            result = await db.execute(
                select(SmartCreateTask).where(SmartCreateTask.id == task_id)
            )
            task = result.scalar_one_or_none()
            if task and task.analyzed_prompts:
                task_analyzed_prompts = task.analyzed_prompts

        while asyncio.get_event_loop().time() - start_time < timeout:
            if task_id in self.stopped_tasks:
                logger.info(f"任务 {task_id} 监控流水线被停止")
                break

            if task_id in self.paused_tasks:
                await asyncio.sleep(2)
                continue

            # 获取队列状态
            running_prompts = set()
            pending_prompts = set()
            try:
                async with httpx.AsyncClient(timeout=10.0) as client:
                    queue_response = await client.get(f"{comfyui_url}/queue")
                    if queue_response.status_code == 200:
                        queue_data = queue_response.json()
                        for item in queue_data.get("queue_running", []):
                            if len(item) >= 2:
                                running_prompts.add(item[1])
                        for item in queue_data.get("queue_pending", []):
                            if len(item) >= 2:
                                pending_prompts.add(item[1])
            except Exception as e:
                logger.warning(f"获取队列状态失败: {e}")

            # 检查每个已提交的任务
            all_processed = True
            for job in jobs:
                if job.status in [JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.DOWNLOADING]:
                    continue

                if job.status == JobStatus.PENDING:
                    all_processed = False
                    continue

                if not job.prompt_id:
                    continue

                all_processed = False
                job.status = JobStatus.GENERATING

                # 检查是否还在队列中
                if job.prompt_id in running_prompts or job.prompt_id in pending_prompts:
                    job._not_found_count = 0
                    continue

                # 查询历史记录
                try:
                    async with httpx.AsyncClient(timeout=10.0) as client:
                        response = await client.get(f"{comfyui_url}/history/{job.prompt_id}")
                        if response.status_code == 200:
                            data = response.json()
                            if job.prompt_id in data:
                                prompt_data = data[job.prompt_id]
                                status = prompt_data.get("status", {})

                                if status.get("completed", False):
                                    outputs = prompt_data.get("outputs", {})
                                    image_found = False

                                    for node_id, output in outputs.items():
                                        if "images" in output and output["images"]:
                                            img = output["images"][0]
                                            job.local_path = img.get("filename")
                                            job.subfolder = img.get("subfolder", "")
                                            job.status = JobStatus.DOWNLOADING
                                            image_found = True

                                            # 保存到图库
                                            analyzed_prompt = {}
                                            if job.prompt_index < len(task_analyzed_prompts):
                                                analyzed_prompt = task_analyzed_prompts[job.prompt_index]

                                            await self._save_to_gallery(
                                                comfyui_url=comfyui_url,
                                                filename=job.local_path,
                                                subfolder=job.subfolder,
                                                prompt_id=job.prompt_id,
                                                prompt_data=analyzed_prompt,
                                                task_id=task_id,
                                                job_title=job.title
                                            )

                                            await download_queue.put(job)
                                            logger.info(f"分镜 {job.prompt_index+1}-{job.image_index+1} 完成: {job.local_path}")
                                            break

                                        elif "gifs" in output and output["gifs"]:
                                            gif = output["gifs"][0]
                                            job.local_path = gif.get("filename")
                                            job.subfolder = gif.get("subfolder", "")
                                            job.status = JobStatus.DOWNLOADING

                                            analyzed_prompt = {}
                                            if job.prompt_index < len(task_analyzed_prompts):
                                                analyzed_prompt = task_analyzed_prompts[job.prompt_index]

                                            await self._save_to_gallery(
                                                comfyui_url=comfyui_url,
                                                filename=job.local_path,
                                                subfolder=job.subfolder,
                                                prompt_id=job.prompt_id,
                                                prompt_data=analyzed_prompt,
                                                task_id=task_id,
                                                job_title=job.title
                                            )

                                            await download_queue.put(job)
                                            image_found = True
                                            break

                                    if not image_found:
                                        job.status = JobStatus.FAILED
                                        job.error = "完成但无图片输出"
                                        await download_queue.put(job)
                            else:
                                # 不在历史中，增加计数
                                job._not_found_count += 1
                                if job._not_found_count >= 150:  # 5分钟
                                    job.status = JobStatus.FAILED
                                    job.error = "任务在 ComfyUI 中丢失"
                                    await download_queue.put(job)

                except Exception as e:
                    logger.warning(f"检查任务 {job.prompt_id} 状态失败: {e}")

            # 检查是否全部处理完成
            if submit_done.is_set() and all_processed:
                break

            await asyncio.sleep(2)

        logger.info(f"任务 {task_id} 监控流水线结束")

    async def _download_pipeline(
        self,
        task_id: int,
        download_queue: Queue[GenerationJob],
        download_done: asyncio.Event,
        comfyui_url: str
    ):
        """下载流水线 - 已在监控流水线中完成保存，这里主要是标记状态"""
        semaphore = Semaphore(self.max_concurrent_download)

        while True:
            if task_id in self.stopped_tasks:
                break

            try:
                job = await asyncio.wait_for(download_queue.get(), timeout=5.0)
            except asyncio.TimeoutError:
                # 检查是否所有任务都完成了
                if download_done.is_set():
                    break
                continue

            if job.status == JobStatus.FAILED:
                continue

            # 标记为完成
            job.status = JobStatus.COMPLETED

        download_done.set()
        logger.info(f"任务 {task_id} 下载流水线结束")

    async def _progress_reporter(
        self,
        task_id: int,
        jobs: list[GenerationJob],
        download_done: asyncio.Event
    ):
        """实时进度上报 - 支持 WebSocket 广播"""
        while not download_done.is_set():
            if task_id in self.stopped_tasks:
                break

            # 统计各状态数量
            status_counts = {}
            for job in jobs:
                status_counts[job.status] = status_counts.get(job.status, 0) + 1

            completed = status_counts.get(JobStatus.COMPLETED, 0)
            downloading = status_counts.get(JobStatus.DOWNLOADING, 0)
            failed = status_counts.get(JobStatus.FAILED, 0)
            generating = status_counts.get(JobStatus.GENERATING, 0)
            submitted = status_counts.get(JobStatus.SUBMITTED, 0)
            total = len(jobs)

            # 找到当前正在生成的任务
            current_job = None
            for job in jobs:
                if job.status in [JobStatus.GENERATING, JobStatus.SUBMITTED]:
                    current_job = {
                        "index": job.index,
                        "title": job.title,
                        "prompt_index": job.prompt_index,
                        "status": job.status.value
                    }
                    break

            # 更新数据库
            async with async_session() as db:
                result = await db.execute(
                    select(SmartCreateTask).where(SmartCreateTask.id == task_id)
                )
                task = result.scalar_one_or_none()
                if task:
                    task.completed_count = completed + downloading
                    task.failed_count = failed
                    task.result_images = [j.to_dict() for j in jobs]
                    await db.commit()

            # 通过 WebSocket 广播进度
            progress = TaskProgress(
                task_id=task_id,
                status="generating",
                total_count=total,
                completed_count=completed + downloading,
                failed_count=failed,
                current_job=current_job,
                message=f"正在生成: {completed + downloading}/{total}"
            )
            await smart_create_progress_manager.broadcast_progress(progress)

            logger.debug(f"任务 {task_id} 进度: 完成={completed}, 下载中={downloading}, 生成中={generating}, 提交={submitted}, 失败={failed}, 总计={total}")

            # 检查是否全部完成
            if completed + downloading + failed >= total:
                download_done.set()
                break

            await asyncio.sleep(3)

    async def _finalize_task(self, task_id: int, jobs: list[GenerationJob]):
        """最终状态更新"""
        final_status = "completed"
        message = ""

        async with async_session() as db:
            result = await db.execute(
                select(SmartCreateTask).where(SmartCreateTask.id == task_id)
            )
            task = result.scalar_one_or_none()
            if task:
                completed_jobs = [j for j in jobs if j.status in [JobStatus.COMPLETED, JobStatus.DOWNLOADING]]
                failed_jobs = [j for j in jobs if j.status == JobStatus.FAILED]

                task.completed_count = len(completed_jobs)
                task.failed_count = len(failed_jobs)
                task.result_images = [j.to_dict() for j in jobs]

                if task_id in self.stopped_tasks:
                    task.status = "failed"
                    task.error_message = "任务已被用户停止"
                    final_status = "stopped"
                    message = "任务已被用户停止"
                    self.stopped_tasks.discard(task_id)
                elif len(completed_jobs) > 0:
                    task.status = "completed"
                    final_status = "completed"
                    message = f"完成 {len(completed_jobs)} 个，失败 {len(failed_jobs)} 个"
                    logger.info(f"任务 {task_id} 完成，成功 {len(completed_jobs)} 个，失败 {len(failed_jobs)} 个")
                else:
                    task.status = "failed"
                    task.error_message = "所有分镜生成失败"
                    final_status = "failed"
                    message = "所有分镜生成失败"
                    logger.error(f"任务 {task_id} 失败，所有分镜生成失败")

                task.completed_at = datetime.now(timezone.utc)
                await db.commit()

        # 广播任务完成状态
        await smart_create_progress_manager.broadcast_task_status(
            task_id=task_id,
            status=final_status,
            message=message
        )

    # ========== 兼容旧的监控方法 ==========

    async def _legacy_monitor_jobs(self, task_id: int, jobs: list, comfyui_url: str, timeout: int = DEFAULT_TASK_TIMEOUT):
        """兼容旧版的监控方法"""
        logger.info(f"使用旧版监控方法: 任务 {task_id}")
        start_time = asyncio.get_event_loop().time()

        task_analyzed_prompts = []
        async with async_session() as db:
            result = await db.execute(
                select(SmartCreateTask).where(SmartCreateTask.id == task_id)
            )
            task = result.scalar_one_or_none()
            if task and task.analyzed_prompts:
                task_analyzed_prompts = task.analyzed_prompts

        while asyncio.get_event_loop().time() - start_time < timeout:
            if task_id in self.stopped_tasks:
                self.stopped_tasks.discard(task_id)
                break

            if task_id in self.paused_tasks:
                await asyncio.sleep(2)
                continue

            all_done = True
            completed_count = 0

            running_prompts = set()
            pending_prompts = set()
            try:
                async with httpx.AsyncClient(timeout=10.0) as client:
                    queue_response = await client.get(f"{comfyui_url}/queue")
                    if queue_response.status_code == 200:
                        queue_data = queue_response.json()
                        for item in queue_data.get("queue_running", []):
                            if len(item) >= 2:
                                running_prompts.add(item[1])
                        for item in queue_data.get("queue_pending", []):
                            if len(item) >= 2:
                                pending_prompts.add(item[1])
            except Exception as e:
                logger.warning(f"获取队列状态失败: {e}")

            for job in jobs:
                if job["status"] == "completed":
                    completed_count += 1
                    continue
                if job["status"] == "failed":
                    continue

                all_done = False
                prompt_id = job["prompt_id"]

                if prompt_id in running_prompts or prompt_id in pending_prompts:
                    job["_not_found_count"] = 0
                    continue

                try:
                    async with httpx.AsyncClient(timeout=10.0) as client:
                        response = await client.get(f"{comfyui_url}/history/{prompt_id}")
                        if response.status_code == 200:
                            data = response.json()
                            if prompt_id in data:
                                prompt_data = data[prompt_id]
                                status = prompt_data.get("status", {})

                                if status.get("completed", False):
                                    outputs = prompt_data.get("outputs", {})
                                    for node_id, output in outputs.items():
                                        if "images" in output:
                                            images = output["images"]
                                            if images:
                                                filename = images[0].get("filename")
                                                subfolder = images[0].get("subfolder", "")
                                                job["path"] = filename
                                                job["subfolder"] = subfolder
                                                job["status"] = "completed"

                                                prompt_index = job.get("prompt_index", 0)
                                                analyzed_prompt = {}
                                                if prompt_index < len(task_analyzed_prompts):
                                                    analyzed_prompt = task_analyzed_prompts[prompt_index]

                                                await self._save_to_gallery(
                                                    comfyui_url=comfyui_url,
                                                    filename=filename,
                                                    subfolder=subfolder,
                                                    prompt_id=prompt_id,
                                                    prompt_data=analyzed_prompt,
                                                    task_id=task_id,
                                                    job_title=job.get("title", "")
                                                )
                                                break

                                    if job["status"] != "completed":
                                        job["status"] = "failed"
                            else:
                                job["_not_found_count"] = job.get("_not_found_count", 0) + 1
                                if job["_not_found_count"] >= 150:
                                    job["status"] = "failed"
                                    job["error"] = "任务在 ComfyUI 中丢失"
                except Exception as e:
                    logger.warning(f"检查任务 {prompt_id} 状态失败: {e}")

            async with async_session() as db:
                result = await db.execute(
                    select(SmartCreateTask).where(SmartCreateTask.id == task_id)
                )
                task = result.scalar_one_or_none()
                if task:
                    completed_jobs = [j for j in jobs if j["status"] == "completed"]
                    failed_jobs = [j for j in jobs if j["status"] == "failed"]

                    task.completed_count = len(completed_jobs)
                    task.failed_count = len(failed_jobs)
                    task.result_images = jobs

                    if all_done or (len(completed_jobs) + len(failed_jobs) == len(jobs)):
                        if len(completed_jobs) > 0:
                            task.status = "completed"
                        else:
                            task.status = "failed"
                            task.error_message = "所有分镜生成失败"
                        task.completed_at = datetime.now(timezone.utc)

                    await db.commit()

                    if task.status in ["completed", "failed"]:
                        return

            await asyncio.sleep(2)

        async with async_session() as db:
            result = await db.execute(
                select(SmartCreateTask).where(SmartCreateTask.id == task_id)
            )
            task = result.scalar_one_or_none()
            if task and task.status == "generating":
                task.status = "failed"
                task.error_message = f"任务超时 ({timeout}s)"
                task.completed_at = datetime.now(timezone.utc)
                await db.commit()

    # ========== 工作流构建方法 ==========

    async def _build_comfy_prompt(
        self,
        prompt_data: dict,
        workflow_data: Optional[dict],
        image_size: str,
        seed: Optional[int],
        comfyui_url: str
    ) -> dict:
        """构建 ComfyUI prompt"""
        width, height = map(int, image_size.split('x'))

        if workflow_data:
            prompt = json.loads(json.dumps(workflow_data))

            clip_nodes = []
            for node_id, node in prompt.items():
                if isinstance(node, dict) and node.get("class_type") == "CLIPTextEncode":
                    clip_nodes.append((node_id, node))

            positive_set = False
            negative_set = False

            for node_id, node in clip_nodes:
                inputs = node.get("inputs", {})
                text = inputs.get("text", "")

                is_negative = any(kw in text.lower() for kw in ["bad", "worst", "low quality", "ugly", "deformed", "nsfw"])

                if is_negative and not negative_set:
                    inputs["text"] = prompt_data.get("negative", "")
                    negative_set = True
                elif not positive_set:
                    inputs["text"] = prompt_data.get("positive", "")
                    positive_set = True

            for node_id, node in prompt.items():
                if isinstance(node, dict):
                    class_type = node.get("class_type", "")
                    inputs = node.get("inputs", {})

                    if class_type in ["EmptyLatentImage", "EmptySD3LatentImage"]:
                        inputs["width"] = width
                        inputs["height"] = height

                    if class_type == "KSampler" and seed is not None:
                        inputs["seed"] = seed

            return prompt

        return await self._build_default_prompt(prompt_data, width, height, seed, comfyui_url)

    async def _build_default_prompt(
        self,
        prompt_data: dict,
        width: int,
        height: int,
        seed: Optional[int],
        comfyui_url: str
    ) -> dict:
        """构建默认的简单工作流"""
        checkpoint = await self._get_default_checkpoint(comfyui_url)
        return {
            "3": {
                "class_type": "KSampler",
                "inputs": {
                    "cfg": 7,
                    "denoise": 1,
                    "latent_image": ["5", 0],
                    "model": ["4", 0],
                    "negative": ["7", 0],
                    "positive": ["6", 0],
                    "sampler_name": "euler",
                    "scheduler": "normal",
                    "seed": seed or 12345,
                    "steps": 20
                }
            },
            "4": {
                "class_type": "CheckpointLoaderSimple",
                "inputs": {
                    "ckpt_name": checkpoint
                }
            },
            "5": {
                "class_type": "EmptyLatentImage",
                "inputs": {
                    "batch_size": 1,
                    "height": height,
                    "width": width
                }
            },
            "6": {
                "class_type": "CLIPTextEncode",
                "inputs": {
                    "clip": ["4", 1],
                    "text": prompt_data.get("positive", "")
                }
            },
            "7": {
                "class_type": "CLIPTextEncode",
                "inputs": {
                    "clip": ["4", 1],
                    "text": prompt_data.get("negative", "")
                }
            },
            "8": {
                "class_type": "VAEDecode",
                "inputs": {
                    "samples": ["3", 0],
                    "vae": ["4", 2]
                }
            },
            "9": {
                "class_type": "SaveImage",
                "inputs": {
                    "filename_prefix": "SmartCreate",
                    "images": ["8", 0]
                }
            }
        }

    async def _queue_prompt(self, prompt: dict, comfyui_url: str) -> Optional[str]:
        """发送 prompt 到 ComfyUI 队列"""
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{comfyui_url}/prompt",
                    json={"prompt": prompt}
                )
                if response.status_code != 200:
                    logger.error(f"ComfyUI 返回错误: {response.status_code} - {response.text}")
                    return None
                data = response.json()
                return data.get("prompt_id")
        except Exception as e:
            logger.error(f"提交任务到 ComfyUI 失败: {e}")
            return None

    async def _save_to_gallery(
        self,
        comfyui_url: str,
        filename: str,
        subfolder: str,
        prompt_id: str,
        prompt_data: dict,
        task_id: int,
        job_title: str
    ):
        """保存图片到图库"""
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                params = {
                    "filename": filename,
                    "subfolder": subfolder,
                    "type": "output"
                }
                response = await client.get(f"{comfyui_url}/view", params=params)

                if response.status_code != 200:
                    logger.error(f"获取图片失败: {filename}")
                    return

                image_data = response.content

                import hashlib
                from pathlib import Path
                image_hash = hashlib.md5(image_data).hexdigest()

                from ..models import StoredImage
                async with async_session() as db:
                    result = await db.execute(
                        select(StoredImage)
                        .where(StoredImage.content_hash == image_hash)
                        .limit(1)
                    )
                    if result.scalar_one_or_none():
                        logger.info(f"图片已存在（内容相同）: {filename}")
                        return

                    result = await db.execute(
                        select(StoredImage)
                        .where(StoredImage.filename == filename)
                        .limit(1)
                    )
                    if result.scalar_one_or_none():
                        base_name = Path(filename).stem
                        ext = Path(filename).suffix
                        filename = f"{base_name}_{image_hash[:8]}{ext}"

                positive = ""
                negative = ""
                if isinstance(prompt_data, dict):
                    positive = str(prompt_data.get("positive", prompt_data.get("prompt", "")))
                    negative = str(prompt_data.get("negative", prompt_data.get("negative_prompt", "")))

                result = await image_storage_service.store_image(
                    image_data=image_data,
                    filename=filename,
                    original_path=f"{subfolder}/{filename}" if subfolder else filename,
                    comfyui_prompt_id=prompt_id,
                    prompt_id=None,
                    positive=positive or job_title,
                    negative=negative,
                )

                if result:
                    logger.info(f"图片已保存到图库: {filename}")

        except Exception as e:
            logger.error(f"保存图片到图库异常: {filename}, error={e}")

    # ========== 任务控制方法 ==========

    def pause_task(self, task_id: int):
        """暂停任务"""
        self.paused_tasks.add(task_id)

    def resume_task(self, task_id: int):
        """恢复任务"""
        self.paused_tasks.discard(task_id)

    async def resume_monitoring(self, task_id: int, jobs: list):
        """恢复监控已提交的任务"""
        comfyui_url = await get_comfyui_url()
        logger.info(f"恢复监控任务 {task_id}，共 {len(jobs)} 个 jobs")
        await self._legacy_monitor_jobs(task_id, jobs, comfyui_url)

    async def retry_failed_jobs(self, task_id: int):
        """重试失败的分镜"""
        comfyui_url = await get_comfyui_url()
        logger.info(f"开始重试任务 {task_id} 的失败分镜")

        async with async_session() as db:
            result = await db.execute(
                select(SmartCreateTask).where(SmartCreateTask.id == task_id)
            )
            task = result.scalar_one_or_none()

            if not task:
                return

            jobs = task.result_images or []
            failed_jobs = [j for j in jobs if isinstance(j, dict) and j.get("status") == "failed"]

            if not failed_jobs:
                task.status = "completed"
                await db.commit()
                return

            workflow_data = None
            if task.workflow_id:
                wf_result = await db.execute(
                    select(Workflow).where(Workflow.id == task.workflow_id)
                )
                workflow = wf_result.scalar_one_or_none()
                if workflow:
                    workflow_data = workflow.workflow_data

            use_fixed_seed = task.config.get("use_fixed_seed", False)
            seed_manager = create_seed_manager(task_id=task_id, use_fixed_seed=use_fixed_seed)

            logger.info(f"重试 {len(failed_jobs)} 个失败的分镜")

            for job in failed_jobs:
                if task_id in self.stopped_tasks:
                    break

                prompt_index = job.get("prompt_index", 0)
                image_index = job.get("image_index", 0)

                if prompt_index < len(task.analyzed_prompts):
                    prompt_data = task.analyzed_prompts[prompt_index]
                    seed = seed_manager.get_seed_for_prompt(prompt_index, image_index)

                    try:
                        comfy_prompt = await self._build_comfy_prompt(
                            prompt_data,
                            workflow_data,
                            task.image_size,
                            seed,
                            comfyui_url
                        )

                        prompt_id = await self._queue_prompt(comfy_prompt, comfyui_url)

                        if prompt_id:
                            job["prompt_id"] = prompt_id
                            job["status"] = "pending"
                            job["_not_found_count"] = 0
                            logger.info(f"分镜 {prompt_index+1}-{image_index+1} 重新提交: {prompt_id}")
                    except Exception as e:
                        logger.error(f"分镜 {prompt_index+1} 重试异常: {e}")

            task.result_images = jobs
            await db.commit()

        await self._legacy_monitor_jobs(task_id, jobs, comfyui_url)

    def stop_task(self, task_id: int):
        """停止任务"""
        self.stopped_tasks.add(task_id)
        if task_id in self.running_tasks:
            self.running_tasks[task_id].cancel()
            del self.running_tasks[task_id]
        logger.info(f"任务 {task_id} 已标记为停止")

    async def cancel_comfyui_jobs(self, jobs: list, comfyui_url: str):
        """取消 ComfyUI 队列中的任务"""
        if not jobs:
            return

        try:
            prompt_ids = [
                j.get("prompt_id") for j in jobs
                if isinstance(j, dict) and j.get("prompt_id") and j.get("status") == "pending"
            ]

            if not prompt_ids:
                return

            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(f"{comfyui_url}/queue")
                if response.status_code == 200:
                    queue_data = response.json()
                    running = queue_data.get("queue_running", [])
                    pending = queue_data.get("queue_pending", [])

                    to_delete = []
                    for item in running + pending:
                        if len(item) > 1 and item[1] in prompt_ids:
                            to_delete.append(item[1])

                    if to_delete:
                        await client.post(
                            f"{comfyui_url}/queue",
                            json={"delete": to_delete}
                        )
                        logger.info(f"已从 ComfyUI 队列删除 {len(to_delete)} 个任务")

                await client.post(f"{comfyui_url}/interrupt")

        except Exception as e:
            logger.warning(f"取消 ComfyUI 任务失败: {e}")

    async def cancel_comfyui_jobs_by_task(self, task_id: int, jobs: list):
        """通过任务 ID 取消 ComfyUI 队列中的任务"""
        comfyui_url = await get_comfyui_url()
        await self.cancel_comfyui_jobs(jobs, comfyui_url)


# 全局执行器实例
smart_create_executor = SmartCreateExecutor()
