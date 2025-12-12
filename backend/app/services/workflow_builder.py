# workflow_builder.py

"""
ComfyUI 工作流构建器
- 动态构建工作流
- 支持 IP-Adapter
- 支持 ControlNet
- 种子管理
"""

import json
import copy
import hashlib
import logging
from typing import Optional, Dict, Any
from pathlib import Path

logger = logging.getLogger(__name__)


class SeedManager:
    """种子管理器"""

    def __init__(self, base_seed: Optional[int] = None):
        """
        初始化种子管理器

        Args:
            base_seed: 基础种子，如果为 None 则随机生成
        """
        if base_seed is None:
            import random
            base_seed = random.randint(1, 2**31 - 1)

        self.base_seed = base_seed

    def get_seed_for_prompt(self, prompt_index: int, variation: int = 0) -> int:
        """
        获取特定分镜的种子

        同一个分镜的多个变体使用不同种子，但有关联性
        """
        seed_input = f"{self.base_seed}_{prompt_index}_{variation}"
        hash_value = int(hashlib.md5(seed_input.encode()).hexdigest()[:8], 16)
        return hash_value % (2**31 - 1)

    def get_consistent_seed_for_character(self, character_id: str) -> int:
        """
        获取角色专用种子

        用于生成角色设定图，同一角色始终使用相同种子
        """
        seed_input = f"{self.base_seed}_char_{character_id}"
        hash_value = int(hashlib.md5(seed_input.encode()).hexdigest()[:8], 16)
        return hash_value % (2**31 - 1)


class WorkflowBuilder:
    """ComfyUI 工作流构建器"""

    # 节点类型常量
    NODE_KSAMPLER = "KSampler"
    NODE_CLIP_TEXT = "CLIPTextEncode"
    NODE_EMPTY_LATENT = "EmptyLatentImage"
    NODE_LOAD_IMAGE = "LoadImage"
    NODE_IP_ADAPTER = "IPAdapterApply"
    NODE_CONTROLNET = "ControlNetApply"
    NODE_SAVE_IMAGE = "SaveImage"

    def __init__(self, base_workflow: Optional[Dict] = None):
        """
        初始化构建器

        Args:
            base_workflow: 基础工作流模板，如果为 None 则使用默认模板
        """
        if base_workflow:
            self.workflow = copy.deepcopy(base_workflow)
        else:
            self.workflow = self._get_default_workflow()

        self._node_id_counter = self._get_max_node_id() + 1

    def _get_max_node_id(self) -> int:
        """获取当前工作流中最大的节点 ID"""
        max_id = 0
        for node_id in self.workflow.keys():
            try:
                num_id = int(node_id)
                max_id = max(max_id, num_id)
            except ValueError:
                pass
        return max_id

    def _get_next_node_id(self) -> str:
        """获取下一个可用的节点 ID"""
        node_id = str(self._node_id_counter)
        self._node_id_counter += 1
        return node_id

    def _find_node_by_type(self, class_type: str, title_hint: str = None) -> Optional[str]:
        """根据类型查找节点 ID"""
        for node_id, node in self.workflow.items():
            if node.get("class_type") == class_type:
                if title_hint:
                    meta = node.get("_meta", {})
                    title = meta.get("title", "").lower()
                    if title_hint.lower() in title:
                        return node_id
                else:
                    return node_id
        return None

    def set_prompt(self, positive: str, negative: str) -> 'WorkflowBuilder':
        """设置提示词"""
        for node_id, node in self.workflow.items():
            if node.get("class_type") == self.NODE_CLIP_TEXT:
                inputs = node.get("inputs", {})
                meta = node.get("_meta", {})
                title = meta.get("title", "").lower()

                # 根据标题或其他线索判断是 positive 还是 negative
                if "positive" in title or "pos" in node_id.lower():
                    inputs["text"] = positive
                elif "negative" in title or "neg" in node_id.lower():
                    inputs["text"] = negative

        return self

    def set_positive_prompt(self, positive: str) -> 'WorkflowBuilder':
        """单独设置正向提示词"""
        positive_node = self._find_node_by_type(self.NODE_CLIP_TEXT, "positive")
        if positive_node:
            self.workflow[positive_node]["inputs"]["text"] = positive
        return self

    def set_negative_prompt(self, negative: str) -> 'WorkflowBuilder':
        """单独设置负向提示词"""
        negative_node = self._find_node_by_type(self.NODE_CLIP_TEXT, "negative")
        if negative_node:
            self.workflow[negative_node]["inputs"]["text"] = negative
        return self

    def set_seed(self, seed: int) -> 'WorkflowBuilder':
        """设置种子"""
        for node_id, node in self.workflow.items():
            if node.get("class_type") == self.NODE_KSAMPLER:
                node["inputs"]["seed"] = seed
        return self

    def set_size(self, width: int, height: int) -> 'WorkflowBuilder':
        """设置图片尺寸"""
        for node_id, node in self.workflow.items():
            if node.get("class_type") == self.NODE_EMPTY_LATENT:
                node["inputs"]["width"] = width
                node["inputs"]["height"] = height
        return self

    def set_steps(self, steps: int) -> 'WorkflowBuilder':
        """设置采样步数"""
        for node_id, node in self.workflow.items():
            if node.get("class_type") == self.NODE_KSAMPLER:
                node["inputs"]["steps"] = steps
        return self

    def set_cfg(self, cfg: float) -> 'WorkflowBuilder':
        """设置 CFG Scale"""
        for node_id, node in self.workflow.items():
            if node.get("class_type") == self.NODE_KSAMPLER:
                node["inputs"]["cfg"] = cfg
        return self

    def set_sampler(self, sampler_name: str, scheduler: str = "normal") -> 'WorkflowBuilder':
        """设置采样器"""
        for node_id, node in self.workflow.items():
            if node.get("class_type") == self.NODE_KSAMPLER:
                node["inputs"]["sampler_name"] = sampler_name
                node["inputs"]["scheduler"] = scheduler
        return self

    def add_ip_adapter(
        self,
        reference_image_path: str,
        weight: float = 0.7,
        noise: float = 0.1,
        weight_type: str = "style transfer",
        start_at: float = 0.0,
        end_at: float = 1.0
    ) -> 'WorkflowBuilder':
        """
        添加 IP-Adapter 节点

        用于保持角色一致性，需要先有参考图

        Args:
            reference_image_path: 参考图路径
            weight: IP-Adapter 权重 (0.5-0.8 推荐)
            noise: 噪声量
            weight_type: 权重类型 ("style transfer", "composition", "original")
            start_at: 开始应用的步数比例
            end_at: 结束应用的步数比例
        """
        # 添加加载参考图节点
        load_image_id = self._get_next_node_id()
        self.workflow[load_image_id] = {
            "class_type": "LoadImage",
            "inputs": {
                "image": reference_image_path
            },
            "_meta": {
                "title": "Load Reference Image (IP-Adapter)"
            }
        }

        # 查找模型加载节点
        model_loader_id = self._find_node_by_type("CheckpointLoaderSimple")
        if not model_loader_id:
            model_loader_id = self._find_node_by_type("CheckpointLoader")

        # 查找 IP-Adapter 模型加载节点（如果已存在）
        ipadapter_loader_id = self._find_node_by_type("IPAdapterModelLoader")

        # 如果没有 IP-Adapter 模型加载节点，添加一个
        if not ipadapter_loader_id:
            ipadapter_loader_id = self._get_next_node_id()
            self.workflow[ipadapter_loader_id] = {
                "class_type": "IPAdapterModelLoader",
                "inputs": {
                    "ipadapter_file": "ip-adapter_sd15.bin"  # 根据实际模型调整
                },
                "_meta": {
                    "title": "Load IP-Adapter Model"
                }
            }

        # 添加 IP-Adapter 应用节点
        ip_adapter_id = self._get_next_node_id()
        self.workflow[ip_adapter_id] = {
            "class_type": "IPAdapterApply",
            "inputs": {
                "weight": weight,
                "noise": noise,
                "weight_type": weight_type,
                "start_at": start_at,
                "end_at": end_at,
                "model": [model_loader_id, 0] if model_loader_id else None,
                "ipadapter": [ipadapter_loader_id, 0],
                "image": [load_image_id, 0],
            },
            "_meta": {
                "title": "Apply IP-Adapter"
            }
        }

        # 更新 KSampler 的模型输入
        for node_id, node in self.workflow.items():
            if node.get("class_type") == self.NODE_KSAMPLER:
                node["inputs"]["model"] = [ip_adapter_id, 0]

        logger.info(f"Added IP-Adapter with weight={weight}, ref_image={reference_image_path}")
        return self

    def add_controlnet(
        self,
        control_image_path: str,
        controlnet_type: str = "openpose",
        strength: float = 0.8,
        start_percent: float = 0.0,
        end_percent: float = 1.0
    ) -> 'WorkflowBuilder':
        """
        添加 ControlNet 节点

        Args:
            control_image_path: 控制图路径
            controlnet_type: ControlNet 类型 (openpose, depth, canny, lineart 等)
            strength: 控制强度
            start_percent: 开始百分比
            end_percent: 结束百分比
        """
        # ControlNet 模型映射
        controlnet_models = {
            "openpose": "control_v11p_sd15_openpose.pth",
            "depth": "control_v11f1p_sd15_depth.pth",
            "canny": "control_v11p_sd15_canny.pth",
            "lineart": "control_v11p_sd15_lineart.pth",
            "softedge": "control_v11p_sd15_softedge.pth",
            "scribble": "control_v11p_sd15_scribble.pth",
        }

        controlnet_file = controlnet_models.get(controlnet_type, controlnet_type)

        # 添加加载控制图节点
        load_image_id = self._get_next_node_id()
        self.workflow[load_image_id] = {
            "class_type": "LoadImage",
            "inputs": {
                "image": control_image_path
            },
            "_meta": {
                "title": f"Load Control Image ({controlnet_type})"
            }
        }

        # 添加 ControlNet 加载节点
        controlnet_loader_id = self._get_next_node_id()
        self.workflow[controlnet_loader_id] = {
            "class_type": "ControlNetLoader",
            "inputs": {
                "control_net_name": controlnet_file
            },
            "_meta": {
                "title": f"Load ControlNet ({controlnet_type})"
            }
        }

        # 查找 positive conditioning 节点
        positive_node_id = self._find_node_by_type(self.NODE_CLIP_TEXT, "positive")

        # 添加 ControlNet 应用节点
        controlnet_apply_id = self._get_next_node_id()
        self.workflow[controlnet_apply_id] = {
            "class_type": "ControlNetApply",
            "inputs": {
                "strength": strength,
                "conditioning": [positive_node_id, 0] if positive_node_id else None,
                "control_net": [controlnet_loader_id, 0],
                "image": [load_image_id, 0],
            },
            "_meta": {
                "title": f"Apply ControlNet ({controlnet_type})"
            }
        }

        # 更新 KSampler 的 conditioning 输入
        for node_id, node in self.workflow.items():
            if node.get("class_type") == self.NODE_KSAMPLER:
                node["inputs"]["positive"] = [controlnet_apply_id, 0]

        logger.info(f"Added ControlNet ({controlnet_type}) with strength={strength}")
        return self

    def set_output_filename(self, filename_prefix: str) -> 'WorkflowBuilder':
        """设置输出文件名前缀"""
        for node_id, node in self.workflow.items():
            if node.get("class_type") == self.NODE_SAVE_IMAGE:
                node["inputs"]["filename_prefix"] = filename_prefix
        return self

    def build(self) -> Dict:
        """构建最终工作流"""
        return copy.deepcopy(self.workflow)

    def to_json(self, indent: int = 2) -> str:
        """导出为 JSON 字符串"""
        return json.dumps(self.workflow, indent=indent)

    def save_to_file(self, filepath: str):
        """保存工作流到文件"""
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(self.workflow, f, indent=2)

    @classmethod
    def from_file(cls, filepath: str) -> 'WorkflowBuilder':
        """从文件加载工作流"""
        with open(filepath, 'r', encoding='utf-8') as f:
            workflow = json.load(f)
        return cls(workflow)

    def _get_default_workflow(self) -> Dict:
        """获取默认工作流模板"""
        return {
            "3": {
                "class_type": "KSampler",
                "inputs": {
                    "seed": 0,
                    "steps": 20,
                    "cfg": 7,
                    "sampler_name": "euler_ancestral",
                    "scheduler": "normal",
                    "denoise": 1,
                    "model": ["4", 0],
                    "positive": ["6", 0],
                    "negative": ["7", 0],
                    "latent_image": ["5", 0]
                },
                "_meta": {
                    "title": "KSampler"
                }
            },
            "4": {
                "class_type": "CheckpointLoaderSimple",
                "inputs": {
                    "ckpt_name": "v1-5-pruned-emaonly.safetensors"
                },
                "_meta": {
                    "title": "Load Checkpoint"
                }
            },
            "5": {
                "class_type": "EmptyLatentImage",
                "inputs": {
                    "width": 512,
                    "height": 512,
                    "batch_size": 1
                },
                "_meta": {
                    "title": "Empty Latent Image"
                }
            },
            "6": {
                "class_type": "CLIPTextEncode",
                "inputs": {
                    "text": "",
                    "clip": ["4", 1]
                },
                "_meta": {
                    "title": "CLIP Text Encode (Positive)"
                }
            },
            "7": {
                "class_type": "CLIPTextEncode",
                "inputs": {
                    "text": "",
                    "clip": ["4", 1]
                },
                "_meta": {
                    "title": "CLIP Text Encode (Negative)"
                }
            },
            "8": {
                "class_type": "VAEDecode",
                "inputs": {
                    "samples": ["3", 0],
                    "vae": ["4", 2]
                },
                "_meta": {
                    "title": "VAE Decode"
                }
            },
            "9": {
                "class_type": "SaveImage",
                "inputs": {
                    "filename_prefix": "ComfyUI",
                    "images": ["8", 0]
                },
                "_meta": {
                    "title": "Save Image"
                }
            }
        }


def parse_image_size(size_str: str) -> tuple[int, int]:
    """解析图片尺寸字符串"""
    try:
        parts = size_str.lower().replace('x', '*').replace('×', '*').split('*')
        width = int(parts[0].strip())
        height = int(parts[1].strip()) if len(parts) > 1 else width
        return width, height
    except:
        return 1024, 768  # 默认尺寸


def build_workflow_for_prompt(
    base_workflow: Dict,
    prompt_data: dict,
    task_config: dict,
    prompt_index: int,
    variation_index: int = 0,
    character_references: Optional[Dict[str, str]] = None
) -> Dict:
    """
    为单个分镜构建完整工作流

    Args:
        base_workflow: 基础工作流
        prompt_data: 分镜数据
        task_config: 任务配置
        prompt_index: 分镜索引
        variation_index: 变体索引（同一分镜生成多张时）
        character_references: 角色参考图 {"char_01": "path/to/image.png"}

    Returns:
        构建好的工作流
    """
    builder = WorkflowBuilder(base_workflow)

    # 设置提示词
    builder.set_prompt(
        positive=prompt_data.get("positive", ""),
        negative=prompt_data.get("negative", "")
    )

    # 设置尺寸
    size_str = task_config.get("image_size", "1024x768")
    width, height = parse_image_size(size_str)
    builder.set_size(width, height)

    # 设置种子
    if task_config.get("use_fixed_seed"):
        base_seed = task_config.get("base_seed", 12345)
        seed_manager = SeedManager(base_seed)
        seed = seed_manager.get_seed_for_prompt(prompt_index, variation_index)
        builder.set_seed(seed)

    # IP-Adapter（如果有角色参考图）
    if character_references and task_config.get("use_ip_adapter"):
        char_ids = prompt_data.get("characters_present", [])
        if char_ids:
            # 使用第一个出场角色的参考图
            first_char_id = char_ids[0]
            ref_image = character_references.get(first_char_id)
            if ref_image:
                weight = task_config.get("ip_adapter_weight", 0.7)
                builder.add_ip_adapter(
                    reference_image_path=ref_image,
                    weight=weight
                )

    # ControlNet（如果有）
    control_image = task_config.get("control_image")
    if control_image:
        controlnet_type = task_config.get("controlnet_type", "openpose")
        controlnet_strength = task_config.get("controlnet_strength", 0.8)
        builder.add_controlnet(
            control_image_path=control_image,
            controlnet_type=controlnet_type,
            strength=controlnet_strength
        )

    # 设置输出文件名
    filename_prefix = f"task_{task_config.get('task_id', 0)}/{prompt_index:03d}_{variation_index}"
    builder.set_output_filename(filename_prefix)

    return builder.build()
