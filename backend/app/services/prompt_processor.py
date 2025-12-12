"""提示词处理器 - 确保一致性和质量"""
import json
import re
import logging
from typing import Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class ProcessedPrompt:
    """处理后的提示词"""
    index: int
    title: str
    description: str
    positive: str
    negative: str
    characters: list[str]
    scene_info: dict


class PromptProcessor:
    """提示词处理器 - 确保一致性"""

    # 通用负面词（兜底）
    UNIVERSAL_NEGATIVE = (
        "lowres, bad anatomy, bad hands, text, error, missing fingers, "
        "extra digit, fewer digits, cropped, worst quality, low quality, "
        "normal quality, jpeg artifacts, signature, watermark, username, "
        "blurry, deformed, ugly, duplicate, morbid, mutilated, "
        "out of frame, extra limbs, cloned face, disfigured, "
        "gross proportions, malformed limbs, missing arms, missing legs, "
        "extra arms, extra legs, fused fingers, too many fingers, long neck, "
        "mutated hands, poorly drawn hands, poorly drawn face, mutation, "
        "extra fingers, missing limbs, floating limbs, disconnected limbs, "
        "bad proportions, cropped head, out of shot"
    )

    def __init__(self):
        self.character_cache: dict[str, str] = {}  # 缓存角色标签

    def process_ai_response(self, raw_content: str) -> dict:
        """处理 AI 返回的原始内容"""
        # 解析 JSON
        data = self._parse_json(raw_content)

        # 提取并缓存角色信息
        characters = data.get("characters", [])
        for char in characters:
            char_id = char.get("id", char.get("name", ""))
            self.character_cache[char_id] = char.get("full_tags", "")

        # 获取全局风格
        global_style = data.get("global_style", {})
        quality_tags = global_style.get("quality", "masterpiece, best quality")
        art_style = global_style.get("art_style", "")
        global_negative = global_style.get("negative", self.UNIVERSAL_NEGATIVE)

        # 处理每个分镜
        processed_prompts = []
        for prompt in data.get("prompts", []):
            processed = self._process_single_prompt(
                prompt,
                quality_tags,
                art_style,
                global_negative
            )
            processed_prompts.append(processed)

        return {
            "characters": characters,
            "global_style": global_style,
            "prompts": processed_prompts,
        }

    def _process_single_prompt(
        self,
        prompt: dict,
        quality_tags: str,
        art_style: str,
        global_negative: str
    ) -> dict:
        """处理单个分镜，确保格式正确"""

        # 验证并补全 positive
        positive = prompt.get("positive", "")
        if not positive or len(positive) < 50:
            # AI 没生成好，我们重新组装
            positive = self._assemble_positive(prompt, quality_tags, art_style)
        else:
            # 确保开头有质量词
            quality_start = quality_tags.split(",")[0].strip()
            if not positive.lower().startswith(quality_start.lower()):
                positive = f"{quality_tags}, {positive}"

        # 处理 negative
        negative = prompt.get("negative", "")
        if not negative:
            negative = global_negative
        elif "lowres" not in negative.lower():
            # 补充必要的负面词
            negative = f"{negative}, {self.UNIVERSAL_NEGATIVE}"

        # 清理提示词
        positive = self._clean_prompt(positive)
        negative = self._clean_prompt(negative)

        return {
            "index": prompt.get("index", 0),
            "title": prompt.get("title", f"分镜 {prompt.get('index', 0)}"),
            "description": prompt.get("description", ""),
            "positive": positive,
            "negative": negative,
            "story_position": prompt.get("story_position", ""),
            "characters_present": prompt.get("characters_present", []),
            "scene": prompt.get("scene", {}),
            "camera": prompt.get("camera", {}),
        }

    def _assemble_positive(
        self,
        prompt: dict,
        quality_tags: str,
        art_style: str
    ) -> str:
        """手动组装 positive 提示词"""
        parts = []

        # 1. 质量词
        parts.append(quality_tags)

        # 2. 风格词
        if art_style:
            parts.append(art_style)

        # 3. 人数和角色标签
        char_ids = prompt.get("characters_present", [])
        if char_ids:
            # 人数
            count = len(char_ids)
            if count == 1:
                parts.append("solo")
            elif count == 2:
                parts.append("2people")
            else:
                parts.append(f"{count}people")

            # 角色标签
            for cid in char_ids:
                if cid in self.character_cache:
                    parts.append(self.character_cache[cid])

        # 4. 动作
        action = prompt.get("action", "")
        if action:
            parts.append(action)

        # 5. 表情
        emotion = prompt.get("emotion", "")
        if emotion:
            parts.append(emotion)

        # 6. 场景
        scene = prompt.get("scene", {})
        if scene.get("location"):
            parts.append(scene["location"])
        if scene.get("time_of_day"):
            parts.append(scene["time_of_day"])
        if scene.get("weather_lighting"):
            parts.append(scene["weather_lighting"])

        # 7. 镜头
        camera = prompt.get("camera", {})
        if camera.get("shot"):
            parts.append(camera["shot"])
        if camera.get("angle"):
            parts.append(camera["angle"])

        return ", ".join([p for p in parts if p])

    def _clean_prompt(self, prompt: str) -> str:
        """清理提示词"""
        # 移除多余空格和逗号
        prompt = re.sub(r'\s+', ' ', prompt)
        prompt = re.sub(r',\s*,', ',', prompt)
        prompt = re.sub(r'^[\s,]+|[\s,]+$', '', prompt)
        return prompt

    def _parse_json(self, content: str) -> dict:
        """解析 JSON，处理各种格式问题"""
        # 移除 markdown 代码块
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0]
        elif "```" in content:
            parts = content.split("```")
            if len(parts) >= 2:
                content = parts[1]
                # 如果第一行是语言标识符，跳过它
                lines = content.split('\n')
                if lines and lines[0].strip() in ['json', 'JSON', '']:
                    content = '\n'.join(lines[1:])

        content = content.strip()

        try:
            return json.loads(content)
        except json.JSONDecodeError:
            # 尝试修复常见问题
            # 1. 移除控制字符
            content = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', content)

            try:
                return json.loads(content)
            except json.JSONDecodeError:
                # 2. 尝试提取 JSON 对象
                match = re.search(r'\{[\s\S]*\}', content)
                if match:
                    return json.loads(match.group())
                raise


class PromptEnhancer:
    """提示词增强器"""

    def __init__(self):
        # 质量增强词
        self.quality_boost = [
            "masterpiece", "best quality", "highly detailed",
            "sharp focus", "professional"
        ]

        # 通用负面词
        self.universal_negative = PromptProcessor.UNIVERSAL_NEGATIVE

    def process_ai_response(self, ai_response: dict) -> dict:
        """处理 AI 返回的结构化数据"""
        characters = ai_response.get("characters", [])
        style_anchor = ai_response.get("style_anchor", ai_response.get("global_style", {}))
        prompts = ai_response.get("prompts", [])

        # 构建角色查找表
        char_map = {c.get("id", c.get("name", "")): c for c in characters}

        # 增强每个分镜的提示词
        enhanced_prompts = []
        for prompt in prompts:
            enhanced = self._enhance_single_prompt(prompt, char_map, style_anchor)
            enhanced_prompts.append(enhanced)

        return {
            "characters": characters,
            "style_anchor": style_anchor,
            "prompts": enhanced_prompts
        }

    def _enhance_single_prompt(
        self,
        prompt: dict,
        char_map: dict,
        style_anchor: dict
    ) -> dict:
        """增强单个分镜提示词"""

        # 组装角色标签
        char_tags = []
        char_ids = prompt.get("characters_in_scene", prompt.get("characters_present", []))
        for cid in char_ids:
            if cid in char_map:
                char_tags.append(char_map[cid].get("full_tags", char_map[cid].get("fixed_tags", "")))

        # 人数标签
        gender_count = {"male": 0, "female": 0}
        for cid in char_ids:
            if cid in char_map:
                gender = char_map[cid].get("gender", "")
                if gender in gender_count:
                    gender_count[gender] += 1

        people_tag = self._generate_people_tag(gender_count)

        # 组装完整提示词
        parts = [
            # 1. 质量
            style_anchor.get("quality_tags", style_anchor.get("quality", "masterpiece, best quality")),
            # 2. 风格
            style_anchor.get("art_style", ""),
            style_anchor.get("color_tone", ""),
            # 3. 人数
            people_tag,
            # 4. 角色外貌（固定）
            ", ".join(char_tags),
            # 5. 动作表情
            prompt.get("action", ""),
            prompt.get("emotion", ""),
            # 6. 场景
            prompt.get("scene", {}).get("location", ""),
            prompt.get("scene", {}).get("time", prompt.get("scene", {}).get("time_of_day", "")),
            prompt.get("scene", {}).get("weather", prompt.get("scene", {}).get("weather_lighting", "")),
            # 7. 构图
            prompt.get("composition", prompt.get("camera", {})).get("shot_type", prompt.get("camera", {}).get("shot", "")),
            prompt.get("composition", prompt.get("camera", {})).get("angle", ""),
            # 8. 氛围
            style_anchor.get("atmosphere", ""),
        ]

        # 清理并合并
        positive = ", ".join([p.strip() for p in parts if p and p.strip()])

        # 如果原本有 positive，优先使用（但确保质量词在前）
        original_positive = prompt.get("positive", "")
        if original_positive and len(original_positive) > 50:
            quality_start = style_anchor.get("quality_tags", style_anchor.get("quality", "masterpiece"))
            if not original_positive.lower().startswith("masterpiece"):
                positive = f"{quality_start}, {original_positive}"
            else:
                positive = original_positive

        # 增强负面提示词
        original_negative = prompt.get("negative", "")
        negative = self._merge_negative(original_negative)

        return {
            **prompt,
            "positive": positive,
            "negative": negative,
            "character_tags": char_tags,  # 保存用于调试
        }

    def _generate_people_tag(self, gender_count: dict) -> str:
        """生成人数标签"""
        tags = []
        if gender_count["female"] == 1:
            tags.append("1girl")
        elif gender_count["female"] > 1:
            tags.append(f"{gender_count['female']}girls")

        if gender_count["male"] == 1:
            tags.append("1boy")
        elif gender_count["male"] > 1:
            tags.append(f"{gender_count['male']}boys")

        return " ".join(tags) if tags else ""

    def _merge_negative(self, original: str) -> str:
        """合并负面提示词"""
        if not original:
            return self.universal_negative
        # 避免重复
        if "lowres" in original.lower() and "bad anatomy" in original.lower():
            return original
        return f"{original}, {self.universal_negative}"


# 单例
prompt_processor = PromptProcessor()
prompt_enhancer = PromptEnhancer()
