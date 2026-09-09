# -*- coding: utf-8 -*-
"""炼器台管理器。

在基础装备强化/附魔/重铸之上，加入洞府炼器台等级加成：
- 炼器台等级提升强化成功率
- 器修流派提供额外成功率与降低失败惩罚的加成
"""

import random

from game.equipment_manager import EquipmentManager, EquipmentConfig


class SmithyManager:
    """管理洞府炼器台的强化、附魔、重铸操作。

    参数:
        player: 玩家对象。
        item_library: 物品库。
        residence_manager: 洞府管理器，提供炼器台等级加成。
        config_dir: 炼器配置文件目录，默认 "config"。
    """

    def __init__(self, player, item_library, residence_manager, config_dir="config"):
        # 保存依赖
        self.player = player
        self.item_library = item_library
        self.residence_manager = residence_manager
        # 底层装备管理器负责具体强化/附魔/重铸逻辑
        self.equipment_manager = EquipmentManager(
            player, item_library, config=EquipmentConfig(config_dir)
        )

    def _get_smithy_bonus(self):
        """获取炼器台等级带来的成功率加成。"""
        return self.residence_manager.get_smith_success_bonus()

    def _get_path_bonus(self):
        """获取器修流派的成功率加成。"""
        if getattr(self.player, "cultivation_path", None) == "qi":
            return 0.10
        return 0.0

    def _get_adjusted_success_rate(self, base_rate):
        """根据炼器台等级与流派计算调整后的成功率。"""
        bonus = self._get_smithy_bonus() + self._get_path_bonus()
        return min(0.99, base_rate + bonus)

    def can_enhance(self, item):
        """检查装备是否可在炼器台强化。"""
        # 复用底层管理器的前置检查（装备类型、等级上限、灵石）
        return self.equipment_manager.can_enhance(item)

    def enhance(self, item, rng=None):
        """强化装备，炼器台与器修流派可提高成功率。

        返回 (success, message, destroyed)。
        """
        rng = rng or random
        ok, msg = self.can_enhance(item)
        if not ok:
            return False, msg, False

        # 扣除灵石与材料
        cost = self.equipment_manager._get_enhancement_cost(
            item.enhancement_level
        )
        if not self.equipment_manager._consume_spirit_stones(cost):
            return False, "灵石不足。", False

        # 计算调整后成功率
        base_rate = self.equipment_manager._get_enhancement_success_rate(
            item.enhancement_level
        )
        success_rate = self._get_adjusted_success_rate(base_rate)

        if rng.random() < success_rate:
            item.enhancement_level += 1
            return (
                True,
                f"强化成功！{item.name} 提升至 +{item.enhancement_level}。"
                f"（成功率 {success_rate*100:.1f}%）",
                False,
            )

        # 失败处理：器修有 50% 概率将降级惩罚减轻为「无惩罚」
        penalty = self.equipment_manager._get_failure_penalty(
            item.enhancement_level
        )
        if (
            getattr(self.player, "cultivation_path", None) == "qi"
            and rng.random() < 0.5
        ):
            return (
                False,
                f"强化失败，但器修技艺稳住了装备。"
                f"（成功率 {success_rate*100:.1f}%）",
                False,
            )

        if penalty == "none":
            return (
                False,
                f"强化失败，装备未受损。"
                f"（成功率 {success_rate*100:.1f}%）",
                False,
            )
        if penalty == "level_down":
            item.enhancement_level = max(0, item.enhancement_level - 1)
            return (
                False,
                f"强化失败，等级回落至 +{item.enhancement_level}。"
                f"（成功率 {success_rate*100:.1f}%）",
                False,
            )
        # level_down_or_destroy
        destroy_chance = (
            self.equipment_manager.config.get_enhancement_rules()
            .get("destroy_chance", 0.3)
        )
        if rng.random() < destroy_chance:
            return (
                False,
                f"强化失败，装备损毁。"
                f"（成功率 {success_rate*100:.1f}%）",
                True,
            )
        if item.enhancement_level > 0:
            item.enhancement_level = max(0, item.enhancement_level - 1)
            return (
                False,
                f"强化失败，等级回落至 +{item.enhancement_level}。"
                f"（成功率 {success_rate*100:.1f}%）",
                False,
            )
        return (
            False,
            f"强化失败，装备损毁。"
            f"（成功率 {success_rate*100:.1f}%）",
            True,
        )

    def preview_enhance(self, item):
        """预览强化信息：成功率、消耗、下一级效果。"""
        ok, msg = self.can_enhance(item)
        if not ok:
            return False, msg, {}
        base_rate = self.equipment_manager._get_enhancement_success_rate(
            item.enhancement_level
        )
        success_rate = self._get_adjusted_success_rate(base_rate)
        cost = self.equipment_manager._get_enhancement_cost(
            item.enhancement_level
        )
        rules = self.equipment_manager.config.get_enhancement_rules()
        bonuses = rules.get("attribute_bonus_per_level", {})
        return True, "", {
            "current_level": item.enhancement_level,
            "next_level": item.enhancement_level + 1,
            "success_rate": success_rate,
            "cost": cost,
            "bonus_preview": dict(bonuses),
        }

    def can_enchant(self, item):
        """检查装备是否可附魔。"""
        return self.equipment_manager.can_enchant(item)

    def enchant(self, item, rng=None):
        """为装备附加一条随机词缀，炼器台等级不影响附魔结果。"""
        rng = rng or random
        return self.equipment_manager.enchant(item)

    def can_reforge(self, item, affix_index):
        """检查指定词缀是否可重铸。"""
        return self.equipment_manager.can_reforge(item, affix_index)

    def reforge(self, item, affix_index, rng=None):
        """重铸指定词缀，炼器台等级不影响重铸结果。"""
        rng = rng or random
        return self.equipment_manager.reforge(item, affix_index)

    def list_enhanceable_items(self):
        """返回玩家背包中可强化的装备列表。"""
        allowed = {"weapon", "helmet", "armor", "accessory"}
        return [
            item for item in self.player.inventory
            if getattr(item, "type", None) in allowed
        ]
