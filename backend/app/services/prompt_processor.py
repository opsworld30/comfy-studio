"""提示词处理器 - 确保一致性和质量，支持知名IP角色"""
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
    """提示词处理器 - 支持知名IP角色和权重控制"""

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

    # 质量提升词
    QUALITY_BOOST = "masterpiece, best quality, highly detailed"

    def __init__(self):
        self.character_cache: dict[str, dict] = {}  # 缓存完整角色信息

    def clear_cache(self):
        """清空角色缓存"""
        self.character_cache.clear()

    def process_ai_response(self, raw_content: str) -> dict:
        """处理 AI 返回的原始内容"""
        # 解析 JSON
        data = self._parse_json(raw_content)

        # 处理角色信息
        characters = data.get("characters", [])
        processed_characters = []
        for char in characters:
            processed_char = self._process_character(char)
            processed_characters.append(processed_char)
            # 缓存角色信息
            char_id = char.get("id", char.get("name", ""))
            self.character_cache[char_id] = processed_char

        # 获取全局风格
        global_style = data.get("global_style", {})
        global_style = self._process_global_style(global_style)

        # 处理每个分镜
        processed_prompts = []
        for prompt in data.get("prompts", []):
            processed = self._process_single_prompt(prompt, global_style)
            processed_prompts.append(processed)

        return {
            "characters": processed_characters,
            "global_style": global_style,
            "prompts": processed_prompts,
        }

    def _process_character(self, char: dict) -> dict:
        """处理角色信息 - 支持知名IP识别"""
        is_known_ip = char.get("is_known_ip", False)
        character_tag = char.get("character_tag", "").strip()

        # 知名角色验证：如果标记为知名IP但没有character_tag，尝试补充
        if is_known_ip and not character_tag:
            name = char.get("name", "")
            ip_source = char.get("ip_source", "")
            if name and ip_source and ip_source != "original":
                character_tag = f"{name}, {ip_source}"
                char["character_tag"] = character_tag
                logger.warning(f"知名角色 {name} 缺少character_tag，已自动补充: {character_tag}")

        # 确保 full_tags 存在
        if not char.get("full_tags"):
            parts = [
                character_tag,
                char.get("iconic_features", char.get("fixed_appearance", "")),
                char.get("default_outfit", ""),
            ]
            char["full_tags"] = ", ".join([p for p in parts if p])

        # 清理 full_tags
        char["full_tags"] = self._clean_prompt(char["full_tags"])

        return char

    def _process_global_style(self, style: dict) -> dict:
        """处理全局风格"""
        # 确保有质量词
        if not style.get("quality"):
            style["quality"] = self.QUALITY_BOOST

        # 确保有负面词
        if not style.get("negative"):
            style["negative"] = self.UNIVERSAL_NEGATIVE

        return style

    def _process_single_prompt(self, prompt: dict, global_style: dict) -> dict:
        """处理单个分镜，确保格式正确"""
        quality_tags = global_style.get("quality", self.QUALITY_BOOST)
        art_style = global_style.get("art_style", "")
        global_negative = global_style.get("negative", self.UNIVERSAL_NEGATIVE)

        # 获取出场角色信息
        char_ids = prompt.get("characters_present", [])
        has_known_ip = any(
            self.character_cache.get(cid, {}).get("is_known_ip", False)
            for cid in char_ids
        )

        # 验证并补全 positive
        positive = prompt.get("positive", "")
        if not positive or len(positive) < 50:
            # AI 没生成好，重新组装
            positive = self._assemble_positive(prompt, quality_tags, art_style, has_known_ip)
        else:
            # 确保开头有质量词
            if not positive.lower().startswith("masterpiece"):
                positive = f"{quality_tags}, {positive}"

            # 如果有知名IP角色，添加权重增强
            if has_known_ip:
                positive = self._enhance_with_weights(positive, char_ids)

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
            "characters_present": char_ids,
            "scene": prompt.get("scene", {}),
            "camera": prompt.get("camera", {}),
            "has_known_ip": has_known_ip,
        }

    def _assemble_positive(
        self,
        prompt: dict,
        quality_tags: str,
        art_style: str,
        has_known_ip: bool = False
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

            # 角色标签（知名IP角色需要加权重）
            for cid in char_ids:
                char = self.character_cache.get(cid, {})
                full_tags = char.get("full_tags", "")
                if full_tags:
                    if char.get("is_known_ip") and char.get("character_tag"):
                        # 知名角色：对角色名加权
                        weighted_tags = self._add_weight_to_character_tag(full_tags, char)
                        parts.append(weighted_tags)
                    else:
                        parts.append(full_tags)

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
        if isinstance(scene, dict):
            if scene.get("location"):
                parts.append(scene["location"])
            if scene.get("time_of_day"):
                parts.append(scene["time_of_day"])
            if scene.get("weather_lighting"):
                parts.append(scene["weather_lighting"])

        # 7. 镜头
        camera = prompt.get("camera", {})
        if isinstance(camera, dict):
            if camera.get("shot"):
                parts.append(camera["shot"])
            if camera.get("angle"):
                parts.append(camera["angle"])

        return ", ".join([p for p in parts if p])

    def _add_weight_to_character_tag(self, full_tags: str, char: dict) -> str:
        """为知名角色标签添加权重"""
        character_tag = char.get("character_tag", "")
        if not character_tag:
            return full_tags

        # 提取角色名（第一个逗号前的部分）
        main_name = character_tag.split(",")[0].strip()

        # 给角色名加权重 1.3
        if main_name and main_name in full_tags:
            # 避免重复加权
            if f"({main_name}:" not in full_tags:
                full_tags = full_tags.replace(main_name, f"({main_name}:1.3)", 1)

        return full_tags

    def _enhance_with_weights(self, positive: str, char_ids: list[str]) -> str:
        """为已有的提示词添加权重增强"""
        for cid in char_ids:
            char = self.character_cache.get(cid, {})
            if not char.get("is_known_ip"):
                continue

            character_tag = char.get("character_tag", "")
            if not character_tag:
                continue

            # 提取角色名
            main_name = character_tag.split(",")[0].strip()
            if main_name and main_name in positive:
                # 避免重复加权
                if f"({main_name}:" not in positive:
                    positive = positive.replace(main_name, f"({main_name}:1.3)", 1)

            # 提取标志性特征并加权
            iconic = char.get("iconic_features", "")
            if iconic:
                key_features = self._extract_key_features(iconic)
                for feature in key_features[:3]:  # 最多3个关键特征
                    if feature in positive.lower() and f"({feature}:" not in positive.lower():
                        # 找到原始大小写的特征
                        pattern = re.compile(re.escape(feature), re.IGNORECASE)
                        match = pattern.search(positive)
                        if match:
                            original = match.group()
                            positive = positive.replace(original, f"({original}:1.2)", 1)

        return positive

    def _extract_key_features(self, text: str) -> list[str]:
        """提取关键特征词"""
        # 匹配颜色+名词组合
        patterns = [
            r'((?:red|blue|green|black|white|gold|silver|pink|purple|orange|yellow|brown|blonde|platinum)\s+\w+)',
            r'(\w+\s+(?:hair|eyes|skin|suit|armor|cape|mask|dress|uniform))',
        ]

        features = []
        text_lower = text.lower()
        for pattern in patterns:
            matches = re.findall(pattern, text_lower)
            features.extend(matches)

        return list(set(features))[:5]

    def _clean_prompt(self, prompt: str) -> str:
        """清理提示词"""
        if not prompt:
            return ""
        # 移除多余空格和逗号
        prompt = re.sub(r'\s+', ' ', prompt)
        prompt = re.sub(r',\s*,', ',', prompt)
        prompt = re.sub(r'^[\s,]+|[\s,]+$', '', prompt)
        return prompt.strip()

    def _parse_json(self, content: str) -> dict:
        """解析 JSON，处理各种格式问题"""
        original = content

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
        except json.JSONDecodeError as e:
            logger.error(f"JSON解析失败: {e}")
            logger.error(f"内容预览: {content[:500]}")

            # 尝试修复常见问题
            try:
                # 移除控制字符
                cleaned = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', content)
                return json.loads(cleaned)
            except json.JSONDecodeError:
                pass

            # 尝试提取 JSON 对象
            try:
                match = re.search(r'\{[\s\S]*\}', content)
                if match:
                    return json.loads(match.group())
            except json.JSONDecodeError:
                pass

            raise ValueError(f"无法解析AI响应为JSON: {e}")


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
        has_known_ip = False
        char_ids = prompt.get("characters_in_scene", prompt.get("characters_present", []))

        for cid in char_ids:
            if cid in char_map:
                char = char_map[cid]
                full_tags = char.get("full_tags", char.get("fixed_tags", ""))
                char_tags.append(full_tags)
                if char.get("is_known_ip"):
                    has_known_ip = True

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
            "character_tags": char_tags,
            "has_known_ip": has_known_ip,
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
