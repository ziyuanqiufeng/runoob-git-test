# -*- coding: utf-8 -*-
"""炼丹管理器。

将炼丹/炼器与洞府建筑等级挂钩：
- 炼丹室等级影响炼丹成功率与品质
- 丹修流派提供额外成功率加成
- 批量炼制支持一次消耗多份材料
"""

import json
import os
import random


class AlchemyManager:
    """管理玩家已学丹方、材料检查、成功率计算与炼丹产出。

    参数:
        player: 玩家对象，包含 learned_recipes、inventory、cultivation_path 等。
        item_library: 物品库，用于创建丹药与消耗材料。
        residence_manager: 洞府管理器，提供炼丹室等级加成。
        config_dir: 配置文件目录，默认 "config"。
    """

    # 品质等级与对应效果倍率
    QUALITY_TIERS = {
        "普通": {"multiplier": 1.0, "threshold": 0.0},
        "上品": {"multiplier": 1.3, "threshold": 0.75},
        "极品": {"multiplier": 1.6, "threshold": 0.90},
    }

    def __init__(self, player, item_library, residence_manager, config_dir="config"):
        # 保存依赖对象
        self.player = player
        self.item_library = item_library
        self.residence_manager = residence_manager
        # 加载配方配置
        self.config_dir = config_dir
        self.recipes = self._load_recipes()

    def _load_recipes(self):
        """从 recipes.json 加载所有配方，返回 id -> recipe 字典。"""
        path = os.path.join(self.config_dir, "recipes.json")
        if not os.path.exists(path):
            return {}
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return {recipe["id"]: recipe for recipe in data}

    def get_recipe(self, recipe_id):
        """根据 ID 获取配方配置。"""
        return self.recipes.get(recipe_id)

    def get_learned_recipes(self):
        """返回玩家已习得的炼丹配方列表。"""
        learned = getattr(self.player, "learned_recipes", [])
        return [
            self.recipes[rid]
            for rid in learned
            if rid in self.recipes and self.recipes[rid].get("category") == "alchemy"
        ]

    def get_all_alchemy_recipes(self):
        """返回所有炼丹类配方（用于未习得时展示可学习列表）。"""
        return [
            recipe for recipe in self.recipes.values()
            if recipe.get("category") == "alchemy"
        ]

    def can_craft(self, recipe_id, batch=1):
        """检查是否可以炼制指定配方指定次数。

        返回 (bool, message)。
        """
        # 参数校验
        if batch < 1:
            return False, "炼制次数至少为 1。"
        recipe = self.get_recipe(recipe_id)
        if not recipe:
            return False, "丹方不存在。"
        # 必须已习得
        if recipe_id not in getattr(self.player, "learned_recipes", []):
            return False, "你尚未掌握这条丹方。"
        # 检查材料是否充足
        materials = recipe.get("materials", {})
        for item_id, count in materials.items():
            required = count * batch
            owned = self.player.count_item(item_id)
            if owned < required:
                template = self.item_library.get(item_id)
                name = template.name if template else item_id
                return False, f"材料不足：{name} 需要 {required} 个（拥有 {owned}）。"
        return True, ""

    def _compute_success_rate(self, recipe):
        """计算单次炼丹成功率。"""
        base_rate = recipe.get("success_rate", 0.7)
        bonus = 0.0
        # 丹修流派加成
        if getattr(self.player, "cultivation_path", None) == "dan_xiu":
            bonus += recipe.get("dan_xiu_bonus", 0.0)
        # 悟性小幅加成
        wisdom = getattr(self.player, "wisdom", 5)
        bonus += wisdom * 0.005
        # 炼丹室建筑加成
        bonus += self.residence_manager.get_alchemy_success_bonus()
        # 成功率上限 99%，避免必定成功
        return min(0.99, base_rate + bonus)

    def _compute_quality(self, success_rate, rng=None):
        """根据成功率与随机数决定丹药品质。"""
        rng = rng or random
        # 品质判定：成功率越高，越容易出上品/极品
        roll = rng.random()
        # 将成功率作为品质基准，roll 越小品质越高
        quality_score = success_rate * (1 - roll)
        if quality_score >= self.QUALITY_TIERS["极品"]["threshold"]:
            return "极品"
        if quality_score >= self.QUALITY_TIERS["上品"]["threshold"]:
            return "上品"
        return "普通"

    def _apply_quality(self, item, quality):
        """将品质应用到物品：修改名称、描述与效果倍率。"""
        if not quality or quality == "普通":
            return item
        # 更新名称前缀
        item.quality = quality
        item.name = f"【{quality}】{item.name}"
        # 更新描述
        item.description = f"品质：{quality}。{item.description}"
        # 效果倍率调整
        multiplier = self.QUALITY_TIERS[quality]["multiplier"]
        scaled_effects = {}
        for key, value in item.effects.items():
            if isinstance(value, (int, float)):
                scaled_effects[key] = int(value * multiplier)
            else:
                scaled_effects[key] = value
        item.effects = scaled_effects
        # 价值随品质提升
        item.value = int(item.value * multiplier)
        return item

    def craft(self, recipe_id, batch=1, rng=None):
        """执行炼丹。

        返回 (success, message, items)，其中 items 是成功时产出的 Item 列表。
        """
        rng = rng or random
        ok, msg = self.can_craft(recipe_id, batch)
        if not ok:
            return False, msg, []

        recipe = self.get_recipe(recipe_id)
        materials = recipe.get("materials", {})
        result = recipe.get("result", {})
        product_id = result.get("item_id")
        product_count = result.get("count", 1)

        # 扣除材料
        for item_id, count in materials.items():
            self.player.consume_items(item_id, count * batch)

        # 计算成功率
        success_rate = self._compute_success_rate(recipe)
        # 炼丹室品质加成
        quality_bonus = self.residence_manager.get_alchemy_quality_bonus()

        produced_items = []
        success_count = 0
        fail_count = 0

        for _ in range(batch):
            if rng.random() < success_rate:
                # 成功：决定品质并创建物品
                quality = self._compute_quality(
                    min(0.99, success_rate + quality_bonus), rng
                )
                item = self.item_library.create(product_id)
                if item:
                    self._apply_quality(item, quality)
                    item.count = product_count
                    self.player.add_item(item)
                    produced_items.append(item)
                success_count += 1
            else:
                fail_count += 1

        # 丹修失败时有 50% 概率挽回一半材料（按总失败次数计算一次）
        if fail_count > 0 and self.player.cultivation_path == "dan_xiu":
            if rng.random() < 0.5:
                for item_id, count in materials.items():
                    refund = (count * fail_count) // 2
                    if refund > 0:
                        refunded = self.item_library.create(item_id)
                        if refunded:
                            refunded.stackable = True
                            refunded.count = refund
                            self.player.add_item(refunded)
                return (
                    True,
                    f"炼制完成：成功 {success_count} 次，失败 {fail_count} 次；"
                    f"丹修经验丰富，挽回一半失败材料。",
                    produced_items,
                )

        if success_count == 0:
            return (
                False,
                f"炼丹失败 {fail_count} 次，药材化为灰烬。"
                f"（成功率 {success_rate*100:.1f}%）",
                [],
            )

        return (
            True,
            f"炼丹成功 {success_count} 次，失败 {fail_count} 次，"
            f"获得 {product_id} x{success_count * product_count}。"
            f"（成功率 {success_rate*100:.1f}%）",
            produced_items,
        )

    def preview(self, recipe_id, batch=1):
        """预览炼丹结果：成功率、预计材料消耗。

        返回 (success, message, info_dict) 或失败信息。
        """
        ok, msg = self.can_craft(recipe_id, batch)
        if not ok:
            return False, msg, {}
        recipe = self.get_recipe(recipe_id)
        success_rate = self._compute_success_rate(recipe)
        materials = recipe.get("materials", {})
        material_preview = []
        for item_id, count in materials.items():
            template = self.item_library.get(item_id)
            name = template.name if template else item_id
            owned = self.player.count_item(item_id)
            required = count * batch
            material_preview.append({
                "item_id": item_id,
                "name": name,
                "required": required,
                "owned": owned,
                "enough": owned >= required,
            })
        return True, "", {
            "success_rate": success_rate,
            "materials": material_preview,
            "product_id": recipe.get("result", {}).get("item_id"),
            "product_count": recipe.get("result", {}).get("count", 1) * batch,
        }
