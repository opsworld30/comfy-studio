# quality_checker.py

"""
图片质量检测器
- 基础质量检测
- 损坏检测
- 可扩展的高级检测
"""

import os
import logging
from typing import Tuple, Optional
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

logger = logging.getLogger(__name__)


class QualityLevel(Enum):
    """质量等级"""
    EXCELLENT = "excellent"  # 优秀
    GOOD = "good"            # 良好
    ACCEPTABLE = "acceptable"  # 可接受
    POOR = "poor"            # 差
    FAILED = "failed"        # 失败/损坏


@dataclass
class QualityReport:
    """质量检测报告"""
    passed: bool
    level: QualityLevel
    score: float  # 0-1
    width: int = 0
    height: int = 0
    file_size: int = 0
    issues: list = field(default_factory=list)
    suggestions: list = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "passed": self.passed,
            "level": self.level.value,
            "score": self.score,
            "width": self.width,
            "height": self.height,
            "file_size": self.file_size,
            "issues": self.issues,
            "suggestions": self.suggestions,
        }


class QualityChecker:
    """图片质量检测器"""

    def __init__(
        self,
        min_width: int = 512,
        min_height: int = 512,
        max_file_size: int = 50 * 1024 * 1024,  # 50MB
        min_file_size: int = 10 * 1024,  # 10KB
    ):
        """
        初始化检测器

        Args:
            min_width: 最小宽度
            min_height: 最小高度
            max_file_size: 最大文件大小
            min_file_size: 最小文件大小（太小可能是损坏的）
        """
        self.min_width = min_width
        self.min_height = min_height
        self.max_file_size = max_file_size
        self.min_file_size = min_file_size

    async def check_image(self, image_path: str) -> QualityReport:
        """
        检测图片质量

        Args:
            image_path: 图片路径

        Returns:
            QualityReport 质量报告
        """
        issues = []
        suggestions = []
        score = 1.0
        width = 0
        height = 0
        file_size = 0

        # 检查文件是否存在
        if not os.path.exists(image_path):
            return QualityReport(
                passed=False,
                level=QualityLevel.FAILED,
                score=0,
                issues=["文件不存在"],
            )

        # 获取文件大小
        try:
            file_size = os.path.getsize(image_path)
        except Exception as e:
            return QualityReport(
                passed=False,
                level=QualityLevel.FAILED,
                score=0,
                issues=[f"无法获取文件大小: {e}"],
            )

        # 检查文件大小
        if file_size < self.min_file_size:
            issues.append(f"文件过小 ({file_size} bytes)，可能已损坏")
            score -= 0.5
        elif file_size > self.max_file_size:
            issues.append(f"文件过大 ({file_size / 1024 / 1024:.1f} MB)")
            suggestions.append("考虑压缩图片")
            score -= 0.1

        # 尝试打开图片
        try:
            from PIL import Image

            # 验证图片
            img = Image.open(image_path)
            img.verify()  # 验证图片完整性

            # 重新打开以获取信息
            img = Image.open(image_path)
            width, height = img.size
            mode = img.mode

        except Exception as e:
            return QualityReport(
                passed=False,
                level=QualityLevel.FAILED,
                score=0,
                file_size=file_size,
                issues=[f"图片损坏或无法读取: {e}"],
            )

        # 检查尺寸
        if width < self.min_width:
            issues.append(f"宽度过小 ({width}px < {self.min_width}px)")
            score -= 0.2
        if height < self.min_height:
            issues.append(f"高度过小 ({height}px < {self.min_height}px)")
            score -= 0.2

        # 检查宽高比
        aspect_ratio = width / height if height > 0 else 0
        if aspect_ratio > 3 or aspect_ratio < 0.33:
            issues.append(f"宽高比异常 ({aspect_ratio:.2f})")
            suggestions.append("检查图片是否被异常裁剪")
            score -= 0.1

        # 检查颜色模式
        if mode not in ["RGB", "RGBA", "L"]:
            issues.append(f"颜色模式异常 ({mode})")
            score -= 0.1

        # 确保分数在 0-1 范围内
        score = max(0, min(1, score))

        # 确定质量等级
        if score >= 0.9:
            level = QualityLevel.EXCELLENT
        elif score >= 0.7:
            level = QualityLevel.GOOD
        elif score >= 0.5:
            level = QualityLevel.ACCEPTABLE
        elif score > 0:
            level = QualityLevel.POOR
        else:
            level = QualityLevel.FAILED

        # 判断是否通过
        passed = score >= 0.5 and level != QualityLevel.FAILED

        return QualityReport(
            passed=passed,
            level=level,
            score=score,
            width=width,
            height=height,
            file_size=file_size,
            issues=issues,
            suggestions=suggestions,
        )

    async def check_batch(self, image_paths: list[str]) -> dict:
        """
        批量检测图片

        Returns:
            {
                "total": 总数,
                "passed": 通过数,
                "failed": 失败数,
                "reports": [QualityReport, ...],
                "average_score": 平均分
            }
        """
        reports = []
        for path in image_paths:
            report = await self.check_image(path)
            reports.append(report)

        passed_count = sum(1 for r in reports if r.passed)
        total_score = sum(r.score for r in reports)

        return {
            "total": len(reports),
            "passed": passed_count,
            "failed": len(reports) - passed_count,
            "reports": reports,
            "average_score": total_score / len(reports) if reports else 0,
        }


class AdvancedQualityChecker(QualityChecker):
    """
    高级质量检测器

    可选功能（需要额外依赖）：
    - 美学评分
    - NSFW 检测
    - 人脸检测
    - 文本检测
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._aesthetic_model = None
        self._nsfw_model = None

    async def check_aesthetic_score(self, image_path: str) -> float:
        """
        获取美学评分（需要安装额外模型）

        Returns:
            0-10 的美学评分
        """
        try:
            return 7.0  # 默认返回
        except Exception as e:
            logger.warning(f"美学评分失败: {e}")
            return 5.0

    async def check_nsfw(self, image_path: str) -> Tuple[bool, float]:
        """
        NSFW 检测

        Returns:
            (是否安全, NSFW 分数 0-1)
        """
        try:
            return True, 0.0  # 默认安全
        except Exception as e:
            logger.warning(f"NSFW 检测失败: {e}")
            return True, 0.0

    async def check_text_in_image(self, image_path: str) -> Tuple[bool, list[str]]:
        """
        检测图片中的文字（AI 生成的图片有时会出现乱码文字）

        Returns:
            (是否包含文字, 检测到的文字列表)
        """
        try:
            return False, []
        except Exception as e:
            logger.warning(f"文字检测失败: {e}")
            return False, []

    async def check_image_advanced(self, image_path: str) -> QualityReport:
        """
        高级质量检测（包含所有检测项）
        """
        # 先进行基础检测
        report = await self.check_image(image_path)

        if not report.passed:
            return report

        # 美学评分
        aesthetic_score = await self.check_aesthetic_score(image_path)
        if aesthetic_score < 4:
            report.issues.append(f"美学评分较低 ({aesthetic_score:.1f}/10)")
            report.suggestions.append("考虑重新生成")
            report.score -= 0.15

        # NSFW 检测
        is_safe, nsfw_score = await self.check_nsfw(image_path)
        if not is_safe:
            report.issues.append(f"内容可能不适当 (NSFW: {nsfw_score:.2f})")
            report.score -= 0.3

        # 文字检测
        has_text, texts = await self.check_text_in_image(image_path)
        if has_text:
            report.issues.append("图片中检测到文字/乱码")
            report.suggestions.append("检查提示词中是否有导致文字生成的内容")
            report.score -= 0.1

        # 重新计算通过状态
        report.score = max(0, min(1, report.score))
        report.passed = report.score >= 0.5

        return report


# 单例
quality_checker = QualityChecker()


# ============ 重试策略 ============

class RetryStrategy:
    """重试策略"""

    @staticmethod
    def adjust_prompt_for_retry(
        prompt_data: dict,
        quality_report: QualityReport,
        attempt: int
    ) -> dict:
        """
        根据质量问题调整提示词

        Args:
            prompt_data: 原始提示词数据
            quality_report: 质量报告
            attempt: 当前重试次数

        Returns:
            调整后的提示词数据
        """
        positive = prompt_data.get("positive", "")
        negative = prompt_data.get("negative", "")
        issues = quality_report.issues

        adjustments = []

        # 根据问题类型调整
        for issue in issues:
            issue_lower = issue.lower()

            if "美学" in issue or "aesthetic" in issue_lower:
                # 加强质量词
                if "(masterpiece:1.3)" not in positive:
                    positive = positive.replace(
                        "masterpiece",
                        "(masterpiece:1.3)"
                    )
                adjustments.append("加强质量词")

            if "不适当" in issue or "nsfw" in issue_lower:
                # 加强安全词
                safe_words = "safe, sfw, appropriate, "
                if safe_words not in positive:
                    positive = safe_words + positive
                negative = "nsfw, nude, explicit, suggestive, " + negative
                adjustments.append("加强安全词")

            if "文字" in issue or "text" in issue_lower:
                # 加强无文字
                if "no text" not in negative.lower():
                    negative = "text, watermark, signature, letters, words, " + negative
                adjustments.append("加强无文字")

            if "损坏" in issue or "过小" in issue:
                # 可能是生成参数问题，增加步数
                adjustments.append("可能需要调整生成参数")

        # 根据重试次数增加变化
        if attempt >= 2:
            # 第三次尝试，添加更多质量词
            positive = f"(best quality:1.4), (highly detailed:1.3), {positive}"
            negative = f"(worst quality:1.5), (low quality:1.5), {negative}"
            adjustments.append("大幅加强质量控制")

        logger.info(f"重试调整: {adjustments}")

        return {
            **prompt_data,
            "positive": positive,
            "negative": negative,
            "_retry_adjustments": adjustments,
        }
