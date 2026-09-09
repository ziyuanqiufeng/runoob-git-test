# -*- coding: utf-8 -*-
"""
炼器附魔与装备词缀管理器。

负责：
- 装备强化：提升强化等级，附加基础属性
- 装备附魔：附加随机词缀
- 词缀重铸：替换已有词缀
- 计算装备总效果（基础效果 + 强化加成 + 词缀效果）
"""
import json
import os
import random


class EquipmentConfig:
    """加载炼器附魔配置。"""

    def __init__(self, config_dir="config"):
        path = os.path.join(config_dir, "equipment_affixes.json")
        with open(path, "r", encoding="utf-8") as f:
            self.data = json.load(f)

    def get_enhancement_rules(self):
        """获取强化规则。"""
        return self.data.get("enhancement_rules", {})

    def get_affix_rules(self):
        """获取附魔规则。"""
        return self.data.get("affix_rules", {})

    def get_affix_pool(self):
        """获取完整词缀池。"""
        return self.data.get("affix_pool", [])

    def get_affix(self, affix_id):
        """根据 ID 获取词缀模板。"""
        for affix in self.get_affix_pool():
            if affix.get("id") == affix_id:
                return affix
        return None


class EquipmentManager:
    """管理装备强化、附魔、重铸与总属性计算。"""

    def __init__(self, player, item_library, config=None):
        self.player = player
        self.item_library = item_library
        self.config = config or EquipmentConfig()

    def _get_enhancement_cost(self, level):
        """计算强化到下一级所需的灵石。"""
        rules = self.config.get_enhancement_rules()
        base = rules.get("cost_per_level", {}).get("spirit_stone", 50)
        increment = rules.get("cost_per_level", {}).get("increment", 30)
        return base + level * increment

    def _get_enhancement_success_rate(self, level):
        """计算强化成功率。"""
        rules = self.config.get_enhancement_rules()
        base = rules.get("base_success_rate", 0.95)
        decay = rules.get("success_rate_decay_per_level", 0.08)
        return max(0.05, base - level * decay)

    def _get_failure_penalty(self, level):
        """根据强化等级确定失败惩罚类型。"""
        rules = self.config.get_enhancement_rules()
        penalty = rules.get("failure_penalty", {})
        if level <= 3:
            return penalty.get("level_1_3", "none")
        if level <= 6:
            return penalty.get("level_4_6", "level_down")
        return penalty.get("level_7_9", "level_down_or_destroy")

    def _consume_spirit_stones(self, amount):
        """消耗玩家背包中的灵石，返回是否成功。"""
        # 查找灵石数量
        total = 0
        for item in self.player.inventory:
            if item.id == "spirit_stone":
                total += item.count
        if total < amount:
            return False
        # 消耗灵石
        remaining = amount
        for item in self.player.inventory:
            if item.id == "spirit_stone":
                consume = min(item.count, remaining)
                item.count -= consume
                remaining -= consume
        # 清理数量为 0 的堆叠
        self.player.inventory = [
            item for item in self.player.inventory if item.count > 0
        ]
        return True

    def _consume_material(self, material_id, count):
        """消耗指定材料，返回是否成功。"""
        total = 0
        for item in self.player.inventory:
            if item.id == material_id:
                total += item.count
        if total < count:
            return False
        remaining = count
        for item in self.player.inventory:
            if item.id == material_id:
                consume = min(item.count, remaining)
                item.count -= consume
                remaining -= consume
        self.player.inventory = [
            item for item in self.player.inventory if item.count > 0
        ]
        return True

    def can_enhance(self, item):
        """
        检查装备是否可以强化。

        返回 (success, message)。
        """
        if item.type not in ["weapon", "helmet", "armor", "accessory"]:
            return False, "只有装备才可以强化。"
        rules = self.config.get_enhancement_rules()
        max_level = rules.get("max_level", 10)
        if item.enhancement_level >= max_level:
            return False, "该装备已达到最高强化等级。"
        cost = self._get_enhancement_cost(item.enhancement_level)
        if not self._has_spirit_stones(cost):
            return False, f"强化需要 {cost} 灵石，数量不足。"
        return True, ""

    def _has_spirit_stones(self, amount):
        """检查玩家是否有足够灵石。"""
        total = sum(
            item.count for item in self.player.inventory
            if item.id == "spirit_stone"
        )
        return total >= amount

    def enhance(self, item):
        """
        强化装备。

        返回 (success, message, destroyed)。
        destroyed 为 True 表示装备已损毁。
        """
        ok, msg = self.can_enhance(item)
        if not ok:
            return False, msg, False

        cost = self._get_enhancement_cost(item.enhancement_level)
        if not self._consume_spirit_stones(cost):
            return False, "灵石不足。", False

        rate = self._get_enhancement_success_rate(item.enhancement_level)
        if random.random() < rate:
            item.enhancement_level += 1
            return (
                True,
                f"强化成功！{item.name} 提升至 +{item.enhancement_level}。",
                False,
            )

        # 失败处理
        penalty = self._get_failure_penalty(item.enhancement_level)
        if penalty == "none":
            return False, "强化失败，装备未受损。", False
        if penalty == "level_down":
            item.enhancement_level = max(0, item.enhancement_level - 1)
            return False, f"强化失败，等级回落至 +{item.enhancement_level}。", False
        # level_down_or_destroy：按配置概率损毁，否则降级
        destroy_chance = self.config.get_enhancement_rules().get("destroy_chance", 0.3)
        if random.random() < destroy_chance:
            return False, "强化失败，装备损毁。", True
        if item.enhancement_level > 0:
            item.enhancement_level = max(0, item.enhancement_level - 1)
            return (
                False,
                f"强化失败，等级回落至 +{item.enhancement_level}。",
                False,
            )
        return False, "强化失败，装备损毁。", True

    def can_enchant(self, item):
        """
        检查装备是否可以附魔。

        返回 (success, message)。
        """
        if item.type not in self.config.get_affix_rules().get(
            "allowed_types", []
        ):
            return False, "该物品无法附魔。"
        max_affixes = self.config.get_affix_rules().get("max_affixes", 4)
        if len(item.affixes) >= max_affixes:
            return False, "该装备词缀已满。"
        cost = self.config.get_affix_rules().get("enchant_cost", {})
        spirit_stone = cost.get("spirit_stone", 200)
        material_id = cost.get("material_id")
        material_count = cost.get("material_count", 1)
        if not self._has_spirit_stones(spirit_stone):
            return False, f"附魔需要 {spirit_stone} 灵石，数量不足。"
        if material_id and not self._has_material(material_id, material_count):
            return False, f"附魔需要 {material_count} 个 {material_id}，数量不足。"
        return True, ""

    def _has_material(self, material_id, count):
        """检查是否有足够材料。"""
        total = sum(
            item.count for item in self.player.inventory
            if item.id == material_id
        )
        return total >= count

    def enchant(self, item):
        """
        为装备附加一条随机词缀。

        返回 (success, message, affix)。
        """
        ok, msg = self.can_enchant(item)
        if not ok:
            return False, msg, None

        cost = self.config.get_affix_rules().get("enchant_cost", {})
        spirit_stone = cost.get("spirit_stone", 200)
        material_id = cost.get("material_id")
        material_count = cost.get("material_count", 1)

        if not self._consume_spirit_stones(spirit_stone):
            return False, "灵石不足。", None
        if material_id and not self._consume_material(material_id, material_count):
            return False, "材料不足。", None

        affix = self._roll_affix(item.type)
        if not affix:
            return False, "没有适合该装备的词缀。", None

        item.affixes.append(affix)
        return True, f"附魔成功！获得词缀【{affix['name']}】。", affix

    def _roll_affix(self, item_type):
        """根据装备类型抽取一条词缀。"""
        pool = [
            a for a in self.config.get_affix_pool()
            if item_type in a.get("slots", [])
        ]
        if not pool:
            return None
        weights = [a.get("weight", 1) for a in pool]
        template = random.choices(pool, weights=weights, k=1)[0]
        value_range = template.get("value_range", [1, 1])
        value = random.randint(value_range[0], value_range[1])
        return {
            "id": template["id"],
            "name": template["name"],
            "description": template["description"].format(value=value),
            "value": value,
            "effects": self._compute_affix_effects(template, value),
        }

    def _compute_affix_effects(self, template, value):
        """根据词缀模板和随机值计算实际效果。"""
        effects = {}
        for key, base in template.get("effect", {}).items():
            # 对于百分比效果，value 是百分数，基础值按 value 缩放
            if isinstance(base, float):
                effects[key] = round(base * value, 3)
            else:
                effects[key] = int(base * value / max(template.get("value_range", [1, 1])[1], 1))
        return effects

    def can_reforge(self, item, affix_index):
        """
        检查指定词缀是否可以重铸。

        返回 (success, message)。
        """
        if item.type not in self.config.get_affix_rules().get(
            "allowed_types", []
        ):
            return False, "该物品无法重铸。"
        if affix_index < 0 or affix_index >= len(item.affixes):
            return False, "词缀索引无效。"
        cost = self.config.get_affix_rules().get("reforge_cost", {})
        spirit_stone = cost.get("spirit_stone", 100)
        material_id = cost.get("material_id")
        material_count = cost.get("material_count", 2)
        if not self._has_spirit_stones(spirit_stone):
            return False, f"重铸需要 {spirit_stone} 灵石，数量不足。"
        if material_id and not self._has_material(material_id, material_count):
            return False, f"重铸需要 {material_count} 个 {material_id}，数量不足。"
        return True, ""

    def reforge(self, item, affix_index):
        """
        重铸装备上的指定词缀。

        返回 (success, message, affix)。
        """
        ok, msg = self.can_reforge(item, affix_index)
        if not ok:
            return False, msg, None

        cost = self.config.get_affix_rules().get("reforge_cost", {})
        spirit_stone = cost.get("spirit_stone", 100)
        material_id = cost.get("material_id")
        material_count = cost.get("material_count", 2)

        if not self._consume_spirit_stones(spirit_stone):
            return False, "灵石不足。", None
        if material_id and not self._consume_material(material_id, material_count):
            return False, "材料不足。", None

        affix = self._roll_affix(item.type)
        if not affix:
            return False, "没有适合该装备的词缀。", None

        item.affixes[affix_index] = affix
        return True, f"重铸成功！新词缀【{affix['name']}】。", affix

    def get_enhanced_effects(self, item):
        """
        获取装备强化后的额外效果。

        返回效果字典，供 Player 属性计算使用。
        """
        rules = self.config.get_enhancement_rules()
        bonuses = rules.get("attribute_bonus_per_level", {})
        result = {}
        for attr, per_level in bonuses.items():
            result[attr] = item.enhancement_level * per_level
        return result

    def get_affix_effects(self, item):
        """
        获取装备所有词缀的合计效果。

        返回效果字典。
        """
        result = {}
        for affix in item.affixes:
            for key, value in affix.get("effects", {}).items():
                result[key] = result.get(key, 0) + value
        return result

    def get_total_effects(self, item):
        """
        获取装备总效果：基础效果 + 强化加成 + 词缀效果。

        返回效果字典。
        """
        total = dict(item.effects)
        for key, value in self.get_enhanced_effects(item).items():
            total[key] = total.get(key, 0) + value
        for key, value in self.get_affix_effects(item).items():
            total[key] = total.get(key, 0) + value
        return total
