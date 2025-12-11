"""智能创作任务执行服务"""
import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Optional

import httpx
from sqlalchemy import select

from ..database import async_session
from ..models import SmartCreateTask, Workflow, ComfyUIServer
from ..config import get_settings
from .image_storage import image_storage_service

logger = logging.getLogger(__name__)

settings = get_settings()

# 默认超时时间（秒），可通过环境变量配置
DEFAULT_TASK_TIMEOUT = int(getattr(settings, 'SMART_CREATE_TIMEOUT', 1800))  # 默认 30 分钟


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
    """智能创作任务执行器"""
    
    def __init__(self):
        self.running_tasks: dict[int, asyncio.Task] = {}
        self.paused_tasks: set[int] = set()
        self.stopped_tasks: set[int] = set()  # 停止的任务
        self._default_checkpoint: Optional[str] = None
        self._recovery_done = False
    
    async def recover_interrupted_tasks(self):
        """恢复因服务重启而中断的任务 - 继续监控已提交的任务"""
        if self._recovery_done:
            return
        self._recovery_done = True

        try:
            comfyui_url = await get_comfyui_url()

            async with async_session() as db:
                # 查找状态为 generating 的任务（说明是中断的）
                result = await db.execute(
                    select(SmartCreateTask).where(SmartCreateTask.status == "generating")
                )
                interrupted_tasks = result.scalars().all()

                if not interrupted_tasks:
                    logger.info("没有需要恢复的中断任务")
                    return

                logger.info(f"发现 {len(interrupted_tasks)} 个中断的任务，准备恢复...")

                for task in interrupted_tasks:
                    # 检查是否有已提交的 jobs
                    jobs = task.result_images or []

                    if jobs and any(j.get("prompt_id") for j in jobs if isinstance(j, dict)):
                        # 有已提交的任务，检查哪些还没完成
                        pending_jobs = [
                            j for j in jobs
                            if isinstance(j, dict) and j.get("status") not in ["completed", "failed"]
                        ]

                        if pending_jobs:
                            # 有待处理的 jobs，继续监控
                            logger.info(f"任务 {task.id} 有 {len(pending_jobs)} 个未完成的 jobs，继续监控...")
                            asyncio.create_task(self._monitor_jobs(task.id, jobs, comfyui_url))
                        else:
                            # 所有 jobs 都已完成或失败，更新任务状态
                            completed_jobs = [j for j in jobs if isinstance(j, dict) and j.get("status") == "completed"]
                            failed_jobs = [j for j in jobs if isinstance(j, dict) and j.get("status") == "failed"]

                            if len(completed_jobs) > 0:
                                task.status = "completed"
                                logger.info(f"任务 {task.id} 已完成，成功 {len(completed_jobs)} 个，失败 {len(failed_jobs)} 个")
                            else:
                                task.status = "failed"
                                task.error_message = "所有分镜生成失败"
                                logger.info(f"任务 {task.id} 失败，所有分镜生成失败")

                            task.completed_count = len(completed_jobs)
                            task.failed_count = len(failed_jobs)
                            await db.commit()
                    else:
                        # 没有已提交的任务，重新执行
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
        
        return "v1-5-pruned-emaonly.safetensors"  # 回退默认值
    
    async def execute_task(self, task_id: int):
        """执行智能创作任务 - 批量提交+并行监控模式"""
        # 获取默认的 ComfyUI URL
        comfyui_url = await get_comfyui_url()
        logger.info(f"执行任务 {task_id}，使用 ComfyUI: {comfyui_url}")
        
        async with async_session() as db:
            # 获取任务
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
            base_seed = 12345 if use_fixed_seed else None
            
            logger.info(f"任务配置: config={task.config}, images_per_prompt={images_per_prompt}")
            
            # 开始执行
            task.status = "generating"
            task.started_at = datetime.now(timezone.utc)
            task.total_count = len(task.analyzed_prompts) * images_per_prompt
            logger.info(f"任务 {task_id}: 分镜数={len(task.analyzed_prompts)}, 每分镜图片数={images_per_prompt}, 总任务数={task.total_count}")
            await db.commit()
            
            # 第一阶段：批量提交所有分镜到 ComfyUI 队列
            pending_jobs = []  # [{prompt_index, image_index, prompt_id, title}]
            
            try:
                logger.info(f"开始批量提交 {len(task.analyzed_prompts)} 个分镜")
                
                for i, prompt_data in enumerate(task.analyzed_prompts):
                    # 检查是否停止
                    if task_id in self.stopped_tasks:
                        task.status = "failed"
                        task.error_message = "任务已被用户停止"
                        self.stopped_tasks.discard(task_id)
                        await db.commit()
                        logger.info(f"任务 {task_id} 已被用户停止")
                        return

                    # 检查是否暂停 - 暂停时等待恢复
                    while task_id in self.paused_tasks:
                        logger.info(f"任务 {task_id} 已暂停，等待恢复...")
                        await asyncio.sleep(2)
                        # 暂停期间也要检查是否停止
                        if task_id in self.stopped_tasks:
                            task.status = "failed"
                            task.error_message = "任务已被用户停止"
                            self.stopped_tasks.discard(task_id)
                            await db.commit()
                            logger.info(f"任务 {task_id} 在暂停期间被停止")
                            return
                    
                    for j in range(images_per_prompt):
                        # 生成唯一的 seed，避免 ComfyUI 缓存
                        if base_seed:
                            seed = base_seed + i * images_per_prompt + j
                        else:
                            # 使用时间戳 + 索引生成随机 seed
                            import random
                            seed = random.randint(0, 2**32 - 1)
                        
                        try:
                            # 构建 ComfyUI prompt
                            comfy_prompt = await self._build_comfy_prompt(
                                prompt_data,
                                workflow_data,
                                task.image_size,
                                seed,
                                comfyui_url
                            )
                            
                            # 发送到 ComfyUI 队列
                            prompt_id = await self._queue_prompt(comfy_prompt, comfyui_url)
                            
                            if prompt_id:
                                pending_jobs.append({
                                    "prompt_index": i,
                                    "image_index": j,
                                    "prompt_id": prompt_id,
                                    "title": prompt_data.get("title", f"分镜 {i+1}"),
                                    "status": "pending",
                                    "path": None,
                                })
                                logger.info(f"分镜 {i+1}-{j+1} 已提交: {prompt_id}")
                            else:
                                task.failed_count += 1
                                logger.error(f"分镜 {i+1}-{j+1} 提交失败")
                        except Exception as e:
                            task.failed_count += 1
                            logger.error(f"分镜 {i+1}-{j+1} 提交异常: {e}")
                
                # 保存待处理任务列表
                task.result_images = pending_jobs
                await db.commit()
                
                logger.info(f"批量提交完成，共 {len(pending_jobs)} 个任务在队列中")
                
                if len(pending_jobs) == 0:
                    task.status = "failed"
                    task.error_message = "没有成功提交任何分镜"
                    task.completed_at = datetime.now(timezone.utc)
                    await db.commit()
                    return
                
            except Exception as e:
                task.status = "failed"
                task.error_message = str(e)
                logger.error(f"任务 {task_id} 执行异常: {e}")
                await db.commit()
                return
        
        # 第二阶段：在 db session 外监控所有任务完成状态
        # 从任务配置获取超时时间，默认使用全局配置
        task_timeout = task.config.get("timeout", DEFAULT_TASK_TIMEOUT)
        await self._monitor_jobs(task_id, pending_jobs, comfyui_url, timeout=task_timeout)
    
    async def _monitor_jobs(self, task_id: int, jobs: list, comfyui_url: str, timeout: int = DEFAULT_TASK_TIMEOUT):
        """监控所有提交的任务完成状态
        
        Args:
            task_id: 任务 ID
            jobs: 待监控的任务列表
            comfyui_url: ComfyUI 服务地址
            timeout: 超时时间（秒），默认 30 分钟
        """
        logger.info(f"开始监控任务 {task_id}，共 {len(jobs)} 个 jobs，超时 {timeout}s，ComfyUI: {comfyui_url}")
        start_time = asyncio.get_event_loop().time()
        
        # 获取任务的 analyzed_prompts 用于提取提示词
        task_analyzed_prompts = []
        async with async_session() as db:
            result = await db.execute(
                select(SmartCreateTask).where(SmartCreateTask.id == task_id)
            )
            task = result.scalar_one_or_none()
            if task and task.analyzed_prompts:
                task_analyzed_prompts = task.analyzed_prompts

        while asyncio.get_event_loop().time() - start_time < timeout:
            # 检查是否停止
            if task_id in self.stopped_tasks:
                logger.info(f"任务 {task_id} 监控被停止")
                self.stopped_tasks.discard(task_id)
                break

            # 检查是否暂停 - 暂停时跳过检查但继续循环
            if task_id in self.paused_tasks:
                await asyncio.sleep(2)
                continue
            
            # 检查每个 pending 的任务
            all_done = True
            completed_count = 0
            
            # 先获取当前队列状态，判断哪些任务还在执行中
            running_prompts = set()
            pending_prompts = set()
            try:
                async with httpx.AsyncClient(timeout=10.0) as client:
                    queue_response = await client.get(f"{comfyui_url}/queue")
                    if queue_response.status_code == 200:
                        queue_data = queue_response.json()
                        # 正在执行的任务
                        for item in queue_data.get("queue_running", []):
                            if len(item) >= 2:
                                running_prompts.add(item[1])
                        # 等待执行的任务
                        for item in queue_data.get("queue_pending", []):
                            if len(item) >= 2:
                                pending_prompts.add(item[1])
                        logger.debug(f"队列状态: running={len(running_prompts)}, pending={len(pending_prompts)}")
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
                
                # 如果任务还在队列中（执行中或等待中），重置失败计数
                if prompt_id in running_prompts or prompt_id in pending_prompts:
                    job["_not_found_count"] = 0
                    logger.debug(f"分镜 {job['prompt_index']+1} 还在队列中")
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
                                    # 任务完成，获取图片
                                    outputs = prompt_data.get("outputs", {})
                                    logger.info(f"分镜 {job['prompt_index']+1} 完成，outputs 节点: {list(outputs.keys())}")
                                    
                                    if not outputs:
                                        logger.error(f"分镜 {job['prompt_index']+1} 完成但 outputs 为空")
                                        logger.error(f"status: {status}")
                                        logger.error(f"prompt_data keys: {list(prompt_data.keys())}")
                                        # 记录完整的 prompt_data，但限制长度
                                        import json
                                        prompt_str = json.dumps(prompt_data, ensure_ascii=False, indent=2)
                                        logger.error(f"完整 prompt_data (前2000字符): {prompt_str[:2000]}")
                                    
                                    for node_id, output in outputs.items():
                                        logger.debug(f"节点 {node_id} 输出: {output}")
                                        if "images" in output:
                                            images = output["images"]
                                            if images:
                                                filename = images[0].get("filename")
                                                subfolder = images[0].get("subfolder", "")
                                                job["path"] = filename
                                                job["subfolder"] = subfolder
                                                job["status"] = "completed"
                                                logger.info(f"分镜 {job['prompt_index']+1} 完成: {filename}")
                                                
                                                # 保存图片到图库
                                                try:
                                                    # 获取对应的 analyzed_prompt
                                                    prompt_index = job.get("prompt_index", 0)
                                                    analyzed_prompt = {}
                                                    if prompt_index < len(task_analyzed_prompts):
                                                        analyzed_prompt = task_analyzed_prompts[prompt_index]
                                                    
                                                    logger.info(f"准备保存图片到图库: {filename}, prompt_index={prompt_index}")
                                                    await self._save_to_gallery(
                                                        comfyui_url=comfyui_url,
                                                        filename=filename,
                                                        subfolder=subfolder,
                                                        prompt_id=prompt_id,
                                                        prompt_data=analyzed_prompt,
                                                        task_id=task_id,
                                                        job_title=job.get("title", "")
                                                    )
                                                except Exception as e:
                                                    logger.error(f"保存图片到图库失败: {e}", exc_info=True)
                                                
                                                break
                                        # 有些节点用 gifs 而不是 images
                                        elif "gifs" in output:
                                            gifs = output["gifs"]
                                            if gifs:
                                                filename = gifs[0].get("filename")
                                                subfolder = gifs[0].get("subfolder", "")
                                                job["path"] = filename
                                                job["subfolder"] = subfolder
                                                job["status"] = "completed"
                                                logger.info(f"分镜 {job['prompt_index']+1} 完成(gif): {filename}")
                                                
                                                # 保存图片到图库
                                                try:
                                                    # 获取对应的 analyzed_prompt
                                                    prompt_index = job.get("prompt_index", 0)
                                                    analyzed_prompt = {}
                                                    if prompt_index < len(task_analyzed_prompts):
                                                        analyzed_prompt = task_analyzed_prompts[prompt_index]
                                                    
                                                    logger.info(f"准备保存GIF到图库: {filename}, prompt_index={prompt_index}")
                                                    await self._save_to_gallery(
                                                        comfyui_url=comfyui_url,
                                                        filename=filename,
                                                        subfolder=subfolder,
                                                        prompt_id=prompt_id,
                                                        prompt_data=analyzed_prompt,
                                                        task_id=task_id,
                                                        job_title=job.get("title", "")
                                                    )
                                                except Exception as e:
                                                    logger.error(f"保存图片到图库失败: {e}", exc_info=True)
                                                
                                                break
                                    
                                    if job["status"] != "completed":
                                        job["status"] = "failed"
                                        logger.warning(f"分镜 {job['prompt_index']+1} 完成但无图片, outputs={outputs}")
                            else:
                                # history 中没有这个 prompt_id，且不在队列中
                                # 可能是任务被取消或 ComfyUI 重启导致丢失
                                job["_not_found_count"] = job.get("_not_found_count", 0) + 1
                                # 增加容错时间：5分钟后才标记失败
                                if job["_not_found_count"] >= 150:  # 150 * 2秒 = 5分钟
                                    job["status"] = "failed"
                                    job["error"] = "任务在 ComfyUI 中丢失"
                                    logger.warning(f"分镜 {job['prompt_index']+1} 在队列和历史中都未找到，标记失败")
                except Exception as e:
                    logger.warning(f"检查任务 {prompt_id} 状态失败: {e}")
            
            # 更新数据库中的进度
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
                    
                    # 检查是否全部完成
                    if all_done or (len(completed_jobs) + len(failed_jobs) == len(jobs)):
                        if len(completed_jobs) > 0:
                            task.status = "completed"
                            logger.info(f"任务 {task_id} 完成，成功 {len(completed_jobs)} 个，失败 {len(failed_jobs)} 个")
                        else:
                            task.status = "failed"
                            task.error_message = "所有分镜生成失败"
                            logger.error(f"任务 {task_id} 失败，所有分镜生成失败")
                        task.completed_at = datetime.now(timezone.utc)
                    
                    await db.commit()
                    
                    if task.status in ["completed", "failed"]:
                        return
            
            await asyncio.sleep(2)  # 每 2 秒检查一次
        
        # 超时处理
        async with async_session() as db:
            result = await db.execute(
                select(SmartCreateTask).where(SmartCreateTask.id == task_id)
            )
            task = result.scalar_one_or_none()
            if task and task.status == "generating":
                task.status = "failed"
                task.error_message = f"任务超时 ({timeout}s / {timeout // 60} 分钟)"
                task.completed_at = datetime.now(timezone.utc)
                await db.commit()
                logger.error(f"任务 {task_id} 超时")
    
    async def _build_comfy_prompt(
        self,
        prompt_data: dict,
        workflow_data: Optional[dict],
        image_size: str,
        seed: Optional[int],
        comfyui_url: str
    ) -> dict:
        """构建 ComfyUI prompt"""
        # 解析尺寸
        width, height = map(int, image_size.split('x'))
        
        # 如果有工作流，使用工作流并替换参数
        if workflow_data:
            prompt = json.loads(json.dumps(workflow_data))
            
            logger.info(f"开始替换工作流提示词，目标正向: {prompt_data.get('positive', '')[:50]}...")
            
            # 统计 CLIPTextEncode 节点
            clip_nodes = []
            for node_id, node in prompt.items():
                if isinstance(node, dict) and node.get("class_type") == "CLIPTextEncode":
                    clip_nodes.append((node_id, node))
            
            logger.info(f"找到 {len(clip_nodes)} 个 CLIPTextEncode 节点")
            
            # 根据节点内容判断正负向
            positive_set = False
            negative_set = False
            
            for node_id, node in clip_nodes:
                inputs = node.get("inputs", {})
                text = inputs.get("text", "")
                logger.info(f"节点 {node_id} 原始文本: {text[:50]}...")
                
                # 检查是否是负向提示词（通常包含 bad, worst, low quality 等）
                is_negative = any(kw in text.lower() for kw in ["bad", "worst", "low quality", "ugly", "deformed", "nsfw"])
                
                if is_negative and not negative_set:
                    inputs["text"] = prompt_data.get("negative", "")
                    negative_set = True
                    logger.info(f"替换负向提示词节点: {node_id}")
                elif not positive_set:
                    # 替换为正向提示词
                    new_text = prompt_data.get("positive", "")
                    inputs["text"] = new_text
                    positive_set = True
                    logger.info(f"替换正向提示词节点: {node_id}, 新文本: {new_text[:50]}...")
            
            # 如果只有一个节点且没有设置负向，也没关系（有些工作流用 ConditioningZeroOut）
            if not positive_set:
                logger.warning("未找到可替换的正向提示词节点！")
            
            # 替换其他节点
            for node_id, node in prompt.items():
                if isinstance(node, dict):
                    class_type = node.get("class_type", "")
                    inputs = node.get("inputs", {})
                    
                    # 替换尺寸 - 支持多种 LatentImage 类型
                    if class_type in ["EmptyLatentImage", "EmptySD3LatentImage"]:
                        inputs["width"] = width
                        inputs["height"] = height
                        logger.info(f"替换尺寸节点 {node_id}: {width}x{height}")
                    
                    # 替换种子
                    if class_type == "KSampler" and seed is not None:
                        old_seed = inputs.get("seed")
                        inputs["seed"] = seed
                        logger.info(f"替换种子节点 {node_id}: {old_seed} -> {seed}")
            
            logger.info(f"工作流提示词替换完成: positive={positive_set}, negative={negative_set}")
            
            # 验证工作流是否有输出节点
            has_output = False
            for node_id, node in prompt.items():
                if isinstance(node, dict):
                    class_type = node.get("class_type", "")
                    if class_type in ["SaveImage", "PreviewImage", "SaveAnimatedWEBP", "VHS_VideoCombine"]:
                        has_output = True
                        logger.info(f"找到输出节点: {node_id} ({class_type})")
                        break
            
            if not has_output:
                logger.error("警告：工作流中没有找到输出节点（SaveImage/PreviewImage等），任务可能无法获取结果图片！")
            
            return prompt
        
        # 没有工作流，使用默认的简单工作流
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
                    error_text = response.text
                    logger.error(f"ComfyUI 返回错误: {response.status_code} - {error_text}")
                    return None
                data = response.json()
                prompt_id = data.get("prompt_id")
                if prompt_id:
                    logger.info(f"成功提交任务到 ComfyUI: {prompt_id}")
                return prompt_id
        except Exception as e:
            logger.error(f"提交任务到 ComfyUI 失败: {e}")
            return None
    
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
        await self._monitor_jobs(task_id, jobs, comfyui_url)

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
            use_fixed_seed = task.config.get("use_fixed_seed", False)
            base_seed = 12345 if use_fixed_seed else None

            logger.info(f"重试 {len(failed_jobs)} 个失败的分镜")

            # 重新提交失败的分镜
            for job in failed_jobs:
                if task_id in self.stopped_tasks:
                    break

                prompt_index = job.get("prompt_index", 0)
                image_index = job.get("image_index", 0)

                if prompt_index < len(task.analyzed_prompts):
                    prompt_data = task.analyzed_prompts[prompt_index]
                    seed = base_seed + prompt_index * 10 + image_index if base_seed else None

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
                        else:
                            logger.error(f"分镜 {prompt_index+1}-{image_index+1} 重新提交失败")
                    except Exception as e:
                        logger.error(f"分镜 {prompt_index+1}-{image_index+1} 重试异常: {e}")

            task.result_images = jobs
            await db.commit()

        # 继续监控
        await self._monitor_jobs(task_id, jobs, comfyui_url)
    
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
        """将生成的图片保存到图库数据库
        
        Args:
            comfyui_url: ComfyUI 服务地址
            filename: 图片文件名
            subfolder: 子文件夹
            prompt_id: ComfyUI prompt ID
            prompt_data: 提示词数据
            task_id: 任务 ID
            job_title: 任务标题
        """
        try:
            # 从 ComfyUI 获取图片数据
            async with httpx.AsyncClient(timeout=30.0) as client:
                # 构建图片 URL
                params = {
                    "filename": filename,
                    "subfolder": subfolder,
                    "type": "output"
                }
                response = await client.get(f"{comfyui_url}/view", params=params)
                
                if response.status_code != 200:
                    logger.error(f"获取图片失败: {filename}, status={response.status_code}")
                    return
                
                image_data = response.content
                
                # 计算图片内容的 MD5 哈希值
                import hashlib
                from pathlib import Path
                image_hash = hashlib.md5(image_data).hexdigest()
                
                # 优先通过 content_hash 检查是否已存储
                from ..models import StoredImage
                async with async_session() as db:
                    result = await db.execute(
                        select(StoredImage)
                        .where(StoredImage.content_hash == image_hash)
                        .limit(1)
                    )
                    existing_by_hash = result.scalar_one_or_none()
                    if existing_by_hash:
                        logger.info(f"图片已存在（内容相同）: {filename} -> {existing_by_hash.filename} (id={existing_by_hash.id}, hash={image_hash[:8]}...)")
                        return
                    
                    # 检查文件名是否冲突
                    result = await db.execute(
                        select(StoredImage)
                        .where(StoredImage.filename == filename)
                        .limit(1)
                    )
                    existing_by_name = result.scalar_one_or_none()
                    if existing_by_name:
                        # 文件名冲突，生成新的文件名
                        base_name = Path(filename).stem
                        ext = Path(filename).suffix
                        new_filename = f"{base_name}_{image_hash[:8]}{ext}"
                        logger.info(f"文件名冲突，使用新文件名: {new_filename}")
                        filename = new_filename
                
                # 提取提示词信息（确保是字符串）
                positive = ""
                negative = ""
                seed = None
                steps = None
                cfg = None
                sampler = None
                model = None
                
                # prompt_data 是 analyzed_prompts 中的一个元素
                if isinstance(prompt_data, dict):
                    # 提取提示词
                    positive = str(prompt_data.get("prompt", ""))
                    negative = str(prompt_data.get("negative_prompt", ""))
                    
                    # 提取生成参数
                    if "seed" in prompt_data:
                        seed = prompt_data.get("seed")
                    if "steps" in prompt_data:
                        steps = prompt_data.get("steps")
                    if "cfg" in prompt_data:
                        cfg = prompt_data.get("cfg")
                    if "sampler" in prompt_data:
                        sampler = prompt_data.get("sampler")
                    if "model" in prompt_data:
                        model = prompt_data.get("model")
                
                # 保存到图库
                result = await image_storage_service.store_image(
                    image_data=image_data,
                    filename=filename,
                    original_path=f"{subfolder}/{filename}" if subfolder else filename,
                    comfyui_prompt_id=prompt_id,
                    prompt_id=None,  # 智能创作任务没有关联的 SavedPrompt
                    positive=positive or job_title,  # 如果没有提示词，使用任务标题
                    negative=negative,
                    seed=seed,
                    steps=steps,
                    cfg=cfg,
                    sampler=sampler,
                    model=model,
                )
                
                if result:
                    logger.info(f"图片已保存到图库: {filename} (id={result.get('id')})")
                else:
                    logger.warning(f"图片保存到图库失败: {filename}")
                    
        except Exception as e:
            logger.error(f"保存图片到图库异常: {filename}, error={e}", exc_info=True)
    
    def stop_task(self, task_id: int):
        """停止任务"""
        self.stopped_tasks.add(task_id)
        # 如果有正在运行的 asyncio 任务，取消它
        if task_id in self.running_tasks:
            self.running_tasks[task_id].cancel()
            del self.running_tasks[task_id]
        logger.info(f"任务 {task_id} 已标记为停止")

    async def cancel_comfyui_jobs(self, jobs: list, comfyui_url: str):
        """取消 ComfyUI 队列中的任务"""
        if not jobs:
            return

        try:
            # 收集所有待处理的 prompt_id
            prompt_ids = [
                j.get("prompt_id") for j in jobs
                if isinstance(j, dict) and j.get("prompt_id") and j.get("status") == "pending"
            ]

            if not prompt_ids:
                return

            logger.info(f"准备取消 {len(prompt_ids)} 个 ComfyUI 任务")

            async with httpx.AsyncClient(timeout=10.0) as client:
                # 获取当前队列
                response = await client.get(f"{comfyui_url}/queue")
                if response.status_code == 200:
                    queue_data = response.json()
                    # queue_running 和 queue_pending 中的任务
                    running = queue_data.get("queue_running", [])
                    pending = queue_data.get("queue_pending", [])

                    # 找出需要取消的任务
                    to_delete = []
                    for item in running + pending:
                        if len(item) > 1 and item[1] in prompt_ids:
                            to_delete.append(item[1])

                    # 删除队列中的任务
                    if to_delete:
                        await client.post(
                            f"{comfyui_url}/queue",
                            json={"delete": to_delete}
                        )
                        logger.info(f"已从 ComfyUI 队列删除 {len(to_delete)} 个任务")

                # 同时中断当前正在执行的任务
                await client.post(f"{comfyui_url}/interrupt")
                logger.info("已发送中断信号到 ComfyUI")

        except Exception as e:
            logger.warning(f"取消 ComfyUI 任务失败: {e}")

    async def cancel_comfyui_jobs_by_task(self, task_id: int, jobs: list):
        """通过任务 ID 取消 ComfyUI 队列中的任务"""
        comfyui_url = await get_comfyui_url()
        logger.info(f"取消任务 {task_id} 的 ComfyUI 队列任务")
        await self.cancel_comfyui_jobs(jobs, comfyui_url)


# 全局执行器实例
smart_create_executor = SmartCreateExecutor()
