"""种子管理器 - 用于生成可控的随机种子"""
import hashlib
import random
from typing import Optional


class SeedManager:
    """种子管理器"""

    def __init__(self, base_seed: Optional[int] = None):
        """
        初始化种子管理器

        Args:
            base_seed: 基础种子，如果为 None 则随机生成
        """
        if base_seed is None:
            base_seed = random.randint(1, 2**31 - 1)

        self.base_seed = base_seed
        self._used_seeds: set[int] = set()

    def get_seed_for_prompt(self, prompt_index: int, variation: int = 0) -> int:
        """
        获取特定分镜的种子

        同一个分镜的多个变体使用不同种子，但有关联性

        Args:
            prompt_index: 分镜索引
            variation: 变体索引

        Returns:
            计算得到的种子值
        """
        # 基于内容哈希（相同输入 = 相同种子）
        seed_input = f"{self.base_seed}_{prompt_index}_{variation}"
        hash_value = int(hashlib.md5(seed_input.encode()).hexdigest()[:8], 16)
        seed = hash_value % (2**31 - 1)

        # 确保种子唯一
        while seed in self._used_seeds:
            seed = (seed + 1) % (2**31 - 1)

        self._used_seeds.add(seed)
        return seed

    def get_consistent_seed_for_character(self, character_id: str) -> int:
        """
        获取角色专用种子 - 用于生成角色设定图

        同一角色始终使用相同种子，有助于保持一致性

        Args:
            character_id: 角色 ID

        Returns:
            角色专用种子
        """
        seed_input = f"{self.base_seed}_char_{character_id}"
        hash_value = int(hashlib.md5(seed_input.encode()).hexdigest()[:8], 16)
        return hash_value % (2**31 - 1)

    def get_random_seed(self) -> int:
        """获取随机种子"""
        seed = random.randint(1, 2**31 - 1)
        while seed in self._used_seeds:
            seed = random.randint(1, 2**31 - 1)
        self._used_seeds.add(seed)
        return seed

    def reset(self):
        """重置已使用的种子记录"""
        self._used_seeds.clear()


# 工厂函数
def create_seed_manager(
    task_id: Optional[int] = None,
    use_fixed_seed: bool = False,
    custom_base_seed: Optional[int] = None
) -> SeedManager:
    """
    创建种子管理器的工厂函数

    Args:
        task_id: 任务 ID，用于生成可复现的种子
        use_fixed_seed: 是否使用固定种子模式
        custom_base_seed: 自定义基础种子

    Returns:
        SeedManager 实例
    """
    if custom_base_seed is not None:
        return SeedManager(base_seed=custom_base_seed)

    if use_fixed_seed and task_id is not None:
        # 使用任务 ID 作为基础种子，确保同一任务的结果可复现
        return SeedManager(base_seed=task_id * 1000)

    # 随机种子
    return SeedManager()
