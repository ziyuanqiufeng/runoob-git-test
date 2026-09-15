# -*- coding: utf-8 -*-
"""炼器附魔与装备词缀系统单元测试。"""

import os
import unittest
from unittest.mock import patch

from game.player import Player
from game.item import Item, ItemLibrary
from game.equipment_manager import EquipmentManager, EquipmentConfig


class TestEquipmentManager(unittest.TestCase):
    """EquipmentManager 核心逻辑测试。"""

    def setUp(self):
        """初始化玩家与装备管理器。"""
        self.player = Player(name="测试炼器师")
        self.item_library = ItemLibrary(config_dir="config")
        self.manager = EquipmentManager(self.player, self.item_library)
        # 将管理器注入玩家，用于属性计算测试
        self.player.equipment_manager = self.manager

        # 创建测试装备
        self.sword = self.item_library.create("iron_sword")
        self.armor = self.item_library.create("leather_armor")
        self.accessory = self.item_library.create("jade_pendant")

        # 给足灵石（后续测试会消耗，多准备一些）
        for _ in range(1000):
            stone = self.item_library.create("spirit_stone")
            if stone:
                self.player.add_item(stone)
        # 给足附魔/重铸材料
        for _ in range(100):
            self.player.add_item(self.item_library.create("demon_core_mid"))
            self.player.add_item(self.item_library.create("demon_core_low"))

    def _add_item(self, item):
        """辅助方法：将物品加入玩家背包。"""
        self.player.add_item(item)

    def test_config_loads(self):
        """配置应正确加载强化规则与词缀池。"""
        rules = self.manager.config.get_enhancement_rules()
        self.assertIn("max_level", rules)
        self.assertIn("base_success_rate", rules)
        self.assertIn("failure_penalty", rules)

        pool = self.manager.config.get_affix_pool()
        self.assertTrue(len(pool) > 0)
        self.assertIn("id", pool[0])
        self.assertIn("slots", pool[0])

    def test_enhancement_cost_and_rate(self):
        """强化消耗与成功率应随等级递增/递减。"""
        cost_0 = self.manager._get_enhancement_cost(0)
        cost_5 = self.manager._get_enhancement_cost(5)
        self.assertGreater(cost_5, cost_0)

        rate_0 = self.manager._get_enhancement_success_rate(0)
        rate_5 = self.manager._get_enhancement_success_rate(5)
        self.assertGreater(rate_0, rate_5)
        # 最低成功率不低于 5%
        self.assertGreaterEqual(self.manager._get_enhancement_success_rate(20), 0.05)

    def test_can_enhance_checks(self):
        """can_enhance 应正确检查装备类型、等级上限与灵石。"""
        # 非装备不可强化
        pill = self.item_library.create("health_pill")
        ok, msg = self.manager.can_enhance(pill)
        self.assertFalse(ok)
        self.assertIn("装备", msg)

        # 普通装备可强化
        self._add_item(self.sword)
        ok, msg = self.manager.can_enhance(self.sword)
        self.assertTrue(ok)
        self.assertEqual(msg, "")

        # 达到最高等级后不可强化
        self.sword.enhancement_level = 10
        ok, msg = self.manager.can_enhance(self.sword)
        self.assertFalse(ok)
        self.assertIn("最高", msg)

        # 灵石不足时不可强化
        self.sword.enhancement_level = 0
        self.player.inventory.clear()
        ok, msg = self.manager.can_enhance(self.sword)
        self.assertFalse(ok)
        self.assertIn("灵石", msg)

    def test_enhance_success(self):
        """模拟成功强化应提升等级并消耗灵石。"""
        self._add_item(self.sword)
        before_stones = self.player.count_item("spirit_stone")

        # 强制随机数小于成功率，模拟成功
        with patch("game.equipment_manager.random.random", return_value=0.0):
            success, msg, destroyed = self.manager.enhance(self.sword)

        self.assertTrue(success)
        self.assertFalse(destroyed)
        self.assertEqual(self.sword.enhancement_level, 1)
        self.assertLess(self.player.count_item("spirit_stone"), before_stones)

    def test_enhance_failure_no_penalty_low_level(self):
        """1-3级强化失败应无惩罚。"""
        self.sword.enhancement_level = 2
        self._add_item(self.sword)

        with patch("game.equipment_manager.random.random", return_value=1.0):
            success, msg, destroyed = self.manager.enhance(self.sword)

        self.assertFalse(success)
        self.assertFalse(destroyed)
        self.assertEqual(self.sword.enhancement_level, 2)
        self.assertIn("未受损", msg)

    def test_enhance_failure_level_down_mid_level(self):
        """4-6级强化失败应降级。"""
        self.sword.enhancement_level = 5
        self._add_item(self.sword)

        with patch("game.equipment_manager.random.random", return_value=1.0):
            success, msg, destroyed = self.manager.enhance(self.sword)

        self.assertFalse(success)
        self.assertFalse(destroyed)
        self.assertEqual(self.sword.enhancement_level, 4)
        self.assertIn("回落", msg)

    def test_enhance_failure_high_level_down(self):
        """7级以上强化失败，未触发损毁时应降级。"""
        self.sword.enhancement_level = 7
        self._add_item(self.sword)

        # 第一次 random 判定失败，第二次判定不损毁（1.0 >= 0.3）
        with patch("game.equipment_manager.random.random", side_effect=[1.0, 1.0]):
            success, msg, destroyed = self.manager.enhance(self.sword)

        self.assertFalse(success)
        self.assertFalse(destroyed)
        self.assertEqual(self.sword.enhancement_level, 6)

    def test_enhance_failure_destroy_high_level(self):
        """7级以上强化失败触发损毁概率时应返回损毁。"""
        self.sword.enhancement_level = 7
        self._add_item(self.sword)

        # 第一次 random 判定失败，第二次判定损毁（0.0 < 0.3）
        with patch("game.equipment_manager.random.random", side_effect=[1.0, 0.0]):
            success, msg, destroyed = self.manager.enhance(self.sword)

        self.assertFalse(success)
        self.assertTrue(destroyed)
        self.assertIn("损毁", msg)

    def test_enhanced_effects(self):
        """强化加成应正确计入总效果。"""
        self.sword.enhancement_level = 3
        effects = self.manager.get_enhanced_effects(self.sword)
        self.assertEqual(effects.get("attack"), 6)  # 每级 +2

        total = self.manager.get_total_effects(self.sword)
        self.assertEqual(total.get("attack"), 8 + 6)  # 基础 8 + 强化 6

    def test_can_enchant_checks(self):
        """can_enchant 应检查装备类型、词缀上限与材料。"""
        # 非装备不可附魔
        pill = self.item_library.create("health_pill")
        ok, msg = self.manager.can_enchant(pill)
        self.assertFalse(ok)

        # 装备可附魔
        self._add_item(self.sword)
        ok, msg = self.manager.can_enchant(self.sword)
        self.assertTrue(ok)

        # 词缀满后不可附魔
        self.sword.affixes = [{}, {}, {}, {}]
        ok, msg = self.manager.can_enchant(self.sword)
        self.assertFalse(ok)
        self.assertIn("满", msg)

    def test_enchant_adds_affix(self):
        """附魔应添加一条词缀并消耗材料。"""
        self._add_item(self.sword)
        before_stones = self.player.count_item("spirit_stone")
        before_mats = self.player.count_item("demon_core_mid")

        # 固定随机值以稳定测试
        with patch("game.equipment_manager.random.choices") as mock_choices, \
             patch("game.equipment_manager.random.randint", return_value=5):
            # 选择第一个武器词缀（锋利）
            pool = [
                a for a in self.manager.config.get_affix_pool()
                if "weapon" in a.get("slots", [])
            ]
            mock_choices.return_value = [pool[0]]
            success, msg, affix = self.manager.enchant(self.sword)

        self.assertTrue(success)
        self.assertEqual(len(self.sword.affixes), 1)
        self.assertIn("锋利", msg)
        self.assertLess(self.player.count_item("spirit_stone"), before_stones)
        self.assertLess(self.player.count_item("demon_core_mid"), before_mats)

    def test_affix_effects(self):
        """词缀效果应正确合计。"""
        self.sword.affixes = [
            {"effects": {"attack": 5}},
            {"effects": {"attack": 3, "health": 10}},
        ]
        effects = self.manager.get_affix_effects(self.sword)
        self.assertEqual(effects.get("attack"), 8)
        self.assertEqual(effects.get("health"), 10)

    def test_total_effects(self):
        """总效果应为基础 + 强化 + 词缀。"""
        self.sword.enhancement_level = 2
        self.sword.affixes = [{"effects": {"attack": 4}}]
        total = self.manager.get_total_effects(self.sword)
        self.assertEqual(total.get("attack"), 8 + 4 + 4)  # 基础 8 + 强化 4 + 词缀 4

    def test_can_reforge_checks(self):
        """can_reforge 应检查索引有效性与材料。"""
        self._add_item(self.sword)
        # 无词缀时索引无效
        ok, msg = self.manager.can_reforge(self.sword, 0)
        self.assertFalse(ok)

        self.sword.affixes = [{"name": "锋利"}]
        ok, msg = self.manager.can_reforge(self.sword, 0)
        self.assertTrue(ok)

        # 灵石不足
        self.player.inventory.clear()
        ok, msg = self.manager.can_reforge(self.sword, 0)
        self.assertFalse(ok)
        self.assertIn("灵石", msg)

    def test_reforge_replaces_affix(self):
        """重铸应替换指定词缀。"""
        self._add_item(self.sword)
        self.sword.affixes = [{"id": "old", "name": "旧词缀"}]

        with patch("game.equipment_manager.random.choices") as mock_choices, \
             patch("game.equipment_manager.random.randint", return_value=5):
            pool = [
                a for a in self.manager.config.get_affix_pool()
                if "weapon" in a.get("slots", [])
            ]
            mock_choices.return_value = [pool[0]]
            success, msg, affix = self.manager.reforge(self.sword, 0)

        self.assertTrue(success)
        self.assertEqual(len(self.sword.affixes), 1)
        self.assertIn("锋利", msg)
        self.assertEqual(self.sword.affixes[0].get("id"), "sharp")

    def test_player_attack_includes_enhancement_and_affix(self):
        """玩家攻击力应包含强化与词缀加成。"""
        self.player.base_attack = 10
        self.sword.enhancement_level = 2  # +4 攻击
        self.sword.affixes = [{"effects": {"attack": 3}}]
        self.player.equipment["weapon"] = self.sword

        # 默认流派修正为 1.0
        self.assertEqual(self.player.attack, 10 + 8 + 4 + 3)

    def test_player_defense_includes_enhancement_and_affix(self):
        """玩家防御力应包含强化与词缀加成。"""
        self.player.base_defense = 2
        self.armor.enhancement_level = 3  # +3 防御
        self.armor.affixes = [{"effects": {"defense": 2}}]
        self.player.equipment["armor"] = self.armor

        self.assertEqual(self.player.defense, 2 + 5 + 3 + 2)

    def test_player_max_health_includes_affix(self):
        """玩家生命上限应包含词缀提供的生命加成。"""
        self.armor.affixes = [{"effects": {"health": 15}}]
        self.player.equipment["armor"] = self.armor

        # max_health 在装备时会重新计算，这里手动验证 equipped 加成
        self.assertEqual(self.player.max_health_equipped, 20 + 15)


class TestEquipmentConfig(unittest.TestCase):
    """EquipmentConfig 配置加载测试。"""

    def test_load(self):
        """配置路径存在并可加载。"""
        config = EquipmentConfig(config_dir="config")
        self.assertIsNotNone(config.get_affix("sharp"))
        self.assertIsNone(config.get_affix("not_exist"))


if __name__ == "__main__":
    unittest.main()
