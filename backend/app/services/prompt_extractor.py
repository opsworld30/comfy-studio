"""Prompt 提取服务 - 从工作流、历史记录、图片中提取 prompt"""
import re
import logging
from typing import Any
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class ExtractedPrompt:
    """提取的 Prompt"""
    positive: str
    negative: str
    source_node: str = ""
    model: str = ""
    sampler: str = ""
    steps: int = 0
    cfg: float = 0
    seed: int = 0
    width: int = 0
    height: int = 0


class PromptExtractor:
    """从各种来源提取 Prompt"""
    
    # 常见的正向提示词节点类型
    POSITIVE_NODE_TYPES = [
        "CLIPTextEncode",
        "CLIPTextEncodeSDXL",
        "CLIPTextEncodeSDXLRefiner",
        "ConditioningCombine",
        "BNK_CLIPTextEncodeAdvanced",
        "easy positive",
        "CR Prompt Text",
    ]
    
    # 常见的负向提示词节点类型或输入名称
    NEGATIVE_INDICATORS = ["negative", "neg", "uncond", "反向", "负向"]
    
    # 常见的采样器节点类型
    SAMPLER_NODE_TYPES = [
        "KSampler",
        "KSamplerAdvanced",
        "SamplerCustom",
        "easy kSampler",
    ]
    
    def extract_from_workflow(self, workflow_data: dict[str, Any]) -> list[ExtractedPrompt]:
        """从工作流数据中提取所有 prompt"""
        prompts = []
        
        if not workflow_data or not isinstance(workflow_data, dict):
            return prompts
        
        # 收集所有文本编码节点
        text_nodes = {}
        sampler_info = {}
        latent_info = {}
        
        for node_id, node_data in workflow_data.items():
            if not isinstance(node_data, dict):
                continue
            
            class_type = node_data.get("class_type", "")
            inputs = node_data.get("inputs", {})
            
            # 收集文本编码节点
            if any(t in class_type for t in self.POSITIVE_NODE_TYPES):
                text = inputs.get("text", "")
                if isinstance(text, str) and text.strip():
                    text_nodes[node_id] = {
                        "text": text.strip(),
                        "class_type": class_type,
                        "inputs": inputs,
                    }
            
            # 收集采样器信息
            if any(t in class_type for t in self.SAMPLER_NODE_TYPES):
                sampler_info[node_id] = {
                    "sampler_name": inputs.get("sampler_name", ""),
                    "scheduler": inputs.get("scheduler", ""),
                    "steps": inputs.get("steps", 0),
                    "cfg": inputs.get("cfg", 0),
                    "seed": inputs.get("seed", 0),
                    "positive_ref": inputs.get("positive"),
                    "negative_ref": inputs.get("negative"),
                }
            
            # 收集潜空间信息（分辨率）
            if "EmptyLatentImage" in class_type or "LatentImage" in class_type:
                latent_info[node_id] = {
                    "width": inputs.get("width", 512),
                    "height": inputs.get("height", 512),
                }
        
        # 根据采样器的连接关系，配对正负提示词
        for sampler_id, sampler in sampler_info.items():
            positive_text = ""
            negative_text = ""
            
            # 获取正向提示词
            pos_ref = sampler.get("positive_ref")
            if isinstance(pos_ref, list) and len(pos_ref) >= 1:
                pos_node_id = str(pos_ref[0])
                if pos_node_id in text_nodes:
                    positive_text = text_nodes[pos_node_id]["text"]
            
            # 获取负向提示词
            neg_ref = sampler.get("negative_ref")
            if isinstance(neg_ref, list) and len(neg_ref) >= 1:
                neg_node_id = str(neg_ref[0])
                if neg_node_id in text_nodes:
                    negative_text = text_nodes[neg_node_id]["text"]
            
            if positive_text:
                # 获取分辨率
                width, height = 512, 512
                latent_ref = workflow_data.get(sampler_id, {}).get("inputs", {}).get("latent_image")
                if isinstance(latent_ref, list) and len(latent_ref) >= 1:
                    latent_node_id = str(latent_ref[0])
                    if latent_node_id in latent_info:
                        width = latent_info[latent_node_id]["width"]
                        height = latent_info[latent_node_id]["height"]
                
                prompts.append(ExtractedPrompt(
                    positive=positive_text,
                    negative=negative_text,
                    source_node=sampler_id,
                    sampler=sampler.get("sampler_name", ""),
                    steps=sampler.get("steps", 0),
                    cfg=sampler.get("cfg", 0),
                    seed=sampler.get("seed", 0),
                    width=width,
                    height=height,
                ))
        
        # 如果没有通过采样器找到，直接返回所有文本节点
        if not prompts and text_nodes:
            for node_id, node_info in text_nodes.items():
                # 判断是否是负向提示词
                is_negative = any(
                    ind in node_id.lower() or ind in node_info["text"].lower()[:50]
                    for ind in self.NEGATIVE_INDICATORS
                )
                
                if is_negative:
                    continue
                
                prompts.append(ExtractedPrompt(
                    positive=node_info["text"],
                    negative="",
                    source_node=node_id,
                ))
        
        return prompts
    
    def extract_from_history(self, history_data: dict[str, Any]) -> list[ExtractedPrompt]:
        """从 ComfyUI 历史记录中提取 prompt"""
        prompts = []
        
        for prompt_id, data in history_data.items():
            if not isinstance(data, dict):
                continue
            
            # 历史记录中包含 prompt 数据
            prompt_data = data.get("prompt", [])
            if isinstance(prompt_data, list) and len(prompt_data) >= 3:
                workflow_data = prompt_data[2]  # 第三个元素是工作流数据
                if isinstance(workflow_data, dict):
                    extracted = self.extract_from_workflow(workflow_data)
                    prompts.extend(extracted)
        
        return prompts
    
    def extract_from_png_info(self, png_info: str) -> ExtractedPrompt | None:
        """从 PNG 图片的元数据中提取 prompt (ComfyUI 格式)"""
        if not png_info:
            return None
        
        try:
            import json
            # ComfyUI 将工作流信息存储在 PNG 的 prompt 或 workflow 字段
            data = json.loads(png_info)
            if isinstance(data, dict):
                extracted = self.extract_from_workflow(data)
                if extracted:
                    return extracted[0]
        except (json.JSONDecodeError, Exception):
            pass
        
        # 尝试解析 A1111 格式
        return self._parse_a1111_format(png_info)
    
    def _parse_a1111_format(self, text: str) -> ExtractedPrompt | None:
        """解析 Automatic1111 格式的 prompt"""
        if not text:
            return None
        
        # A1111 格式: positive\nNegative prompt: negative\nSteps: 20, ...
        parts = text.split("Negative prompt:")
        
        positive = parts[0].strip() if parts else ""
        negative = ""
        
        if len(parts) > 1:
            # 负向提示词在 "Negative prompt:" 之后，参数之前
            neg_parts = parts[1].split("\n")
            negative_lines = []
            for line in neg_parts:
                if line.strip().startswith(("Steps:", "Sampler:", "CFG", "Seed:", "Size:")):
                    break
                negative_lines.append(line)
            negative = "\n".join(negative_lines).strip()
        
        if positive:
            # 提取参数
            steps = 0
            cfg = 0
            seed = 0
            width, height = 512, 512
            sampler = ""
            
            # 解析参数行
            param_match = re.search(r"Steps:\s*(\d+)", text)
            if param_match:
                steps = int(param_match.group(1))
            
            cfg_match = re.search(r"CFG scale:\s*([\d.]+)", text)
            if cfg_match:
                cfg = float(cfg_match.group(1))
            
            seed_match = re.search(r"Seed:\s*(\d+)", text)
            if seed_match:
                seed = int(seed_match.group(1))
            
            size_match = re.search(r"Size:\s*(\d+)x(\d+)", text)
            if size_match:
                width = int(size_match.group(1))
                height = int(size_match.group(2))
            
            sampler_match = re.search(r"Sampler:\s*([^,\n]+)", text)
            if sampler_match:
                sampler = sampler_match.group(1).strip()
            
            return ExtractedPrompt(
                positive=positive,
                negative=negative,
                sampler=sampler,
                steps=steps,
                cfg=cfg,
                seed=seed,
                width=width,
                height=height,
            )
        
        return None
    
    def deduplicate_prompts(self, prompts: list[ExtractedPrompt]) -> list[ExtractedPrompt]:
        """去重 prompt 列表"""
        seen = set()
        unique = []
        
        for p in prompts:
            key = (p.positive.strip().lower(), p.negative.strip().lower())
            if key not in seen:
                seen.add(key)
                unique.append(p)
        
        return unique
    
    def generate_name(self, prompt: ExtractedPrompt) -> str:
        """为 prompt 生成一个简短的名称"""
        text = prompt.positive[:100]
        
        # 提取关键词
        keywords = []
        
        # 常见的质量词，跳过
        skip_words = {"masterpiece", "best quality", "high quality", "detailed", "8k", "uhd", "hd"}
        
        words = re.findall(r'\b[a-zA-Z\u4e00-\u9fff]+\b', text.lower())
        for word in words:
            if word not in skip_words and len(word) > 2:
                keywords.append(word)
                if len(keywords) >= 3:
                    break
        
        if keywords:
            return " ".join(keywords).title()
        
        # 如果没有提取到关键词，使用前30个字符
        return text[:30].strip() + "..." if len(text) > 30 else text
    
    def categorize_prompt(self, prompt: ExtractedPrompt) -> str:
        """自动分类 prompt"""
        text = (prompt.positive + " " + prompt.negative).lower()
        
        categories = {
            "人物": ["girl", "boy", "woman", "man", "person", "portrait", "face", "1girl", "1boy", "人物", "少女", "女孩"],
            "动漫": ["anime", "manga", "cartoon", "illustration", "pixiv", "动漫", "二次元"],
            "风景": ["landscape", "scenery", "nature", "mountain", "sky", "forest", "ocean", "风景", "自然"],
            "建筑": ["architecture", "building", "interior", "room", "house", "建筑", "室内"],
            "科幻": ["sci-fi", "cyberpunk", "futuristic", "robot", "mech", "科幻", "赛博"],
            "奇幻": ["fantasy", "magic", "dragon", "elf", "fairy", "奇幻", "魔法"],
            "写实": ["realistic", "photorealistic", "photo", "raw", "写实", "真实"],
            "艺术": ["painting", "watercolor", "oil", "artistic", "art style", "艺术", "绘画"],
            "产品": ["product", "commercial", "studio", "产品", "商业"],
            "恐怖": ["horror", "dark", "creepy", "nightmare", "恐怖", "黑暗"],
        }
        
        for category, keywords in categories.items():
            if any(kw in text for kw in keywords):
                return category
        
        return "其他"


# 全局实例
prompt_extractor = PromptExtractor()
