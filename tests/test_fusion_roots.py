# -*- coding: utf-8 -*-
"""融合灵根系统单元测试。

验证融合灵根（如雷火交加、冰风双生）在配置加载、玩家属性展开、
技能施展、克制计算、心法匹配等方面的正确性。
"""
import os
import unittest
from unittest.mock import patch

from PySide6.QtWidgets import QApplication

from game.player import Player
from game.world import World
from game.events import EventPool
from game.item import ItemLibrary
from game.enemy import Enemy, EnemyLibrary
from game.skill import SkillLibrary
from game.npc import NPCLibrary
from game.quest import QuestLibrary
from game.engine import GameEngine, element_multiplier
from game.save_manager import SaveManager
from game.spiritual_root import SpiritualRootConfig
from game.mind_method import MindMethodConfig
from game.item import ItemLibrary


class TestFusionRootConfig(unittest.TestCase):
    """融合灵根配置加载测试。"""

    def test_loads_fusion_roots(self):
        """配置中应加载融合灵根定义。"""
        config = SpiritualRootConfig(config_dir="config")
        self.assertIn("thunder_fire", config.fusion_roots)
        self.assertIn("ice_wind", config.fusion_roots)
        self.assertIn("metal_thunder", config.fusion_roots)
        self.assertIn("wood_ice", config.fusion_roots)

    def test_expand_fusion_root(self):
        """expand_root 应正确展开融合灵根。"""
        config = SpiritualRootConfig(config_dir="config")
        self.assertEqual(sorted(config.expand_root("thunder_fire")), ["fire", "thunder"])
        self.assertEqual(sorted(config.expand_root("ice_wind")), ["ice", "wind"])
        # 普通元素展开为自身
        self.assertEqual(config.expand_root("fire"), ["fire"])

    def test_expand_roots_deduplicated(self):
        """expand_roots 应去重并保留顺序。"""
        config = SpiritualRootConfig(config_dir="config")
        roots = ["thunder_fire", "fire"]
        expanded = config.expand_roots(roots)
        self.assertEqual(expanded, ["thunder", "fire"])

    def test_fusion_root_name_lookup(self):
        """get_element_name 应返回融合灵根中文名。"""
        config = SpiritualRootConfig(config_dir="config")
        self.assertEqual(config.get_element_name("thunder_fire"), "雷火交加")
        self.assertEqual(config.get_element_name("ice_wind"), "冰风双生")

    def test_format_roots_text_with_fusion(self):
        """format_roots_text 应展示融合灵根名称与组成元素。"""
        config = SpiritualRootConfig(config_dir="config")
        text = config.format_roots_text(["thunder_fire"])
        self.assertIn("雷火交加", text)
        self.assertIn("雷", text)
        self.assertIn("火", text)
        self.assertIn("天灵根", text)


class TestPlayerFusionRoots(unittest.TestCase):
    """玩家融合灵根属性展开测试。"""

    def test_fusion_root_expands_elements(self):
        """设置融合灵根后，玩家应能使用组成元素技能。"""
        player = Player(name="融合修士")
        player.set_spiritual_roots(["thunder_fire"], {"thunder_fire": 1.3})
        self.assertEqual(player.spiritual_roots, ["thunder_fire"])
        self.assertEqual(sorted(player.expanded_elements), ["fire", "thunder"])
        self.assertTrue(player.has_element("thunder"))
        self.assertTrue(player.has_element("fire"))
        self.assertFalse(player.has_element("ice"))

    def test_fusion_root_count_as_one(self):
        """融合灵根按 1 个根计数，修炼倍率与天灵根相同。"""
        player = Player(name="融合修士")
        player.set_spiritual_roots(["thunder_fire"])
        self.assertEqual(player.cultivation_multiplier, 1.0)

    def test_fusion_root_purity_shared(self):
        """融合灵根纯度应共享给所有组成元素。"""
        player = Player(name="融合修士")
        player.set_spiritual_roots(["thunder_fire"], {"thunder_fire": 1.4})
        self.assertEqual(player.get_root_purity("thunder"), 1.4)
        self.assertEqual(player.get_root_purity("fire"), 1.4)

    def test_mixed_fusion_and_normal_roots(self):
        """融合灵根与普通灵根可共存。"""
        player = Player(name="混合修士")
        player.set_spiritual_roots(["thunder_fire", "water"])
        self.assertEqual(player.cultivation_multiplier, 1.5)  # 2 个根
        self.assertTrue(player.has_element("thunder"))
        self.assertTrue(player.has_element("fire"))
        self.assertTrue(player.has_element("water"))

    def test_save_and_load_preserves_fusion(self):
        """存档/读档应保留融合灵根。"""
        player = Player(name="融合修士")
        player.set_spiritual_roots(["ice_wind"], {"ice_wind": 1.3})
        data = player.to_dict()
        item_lib = ItemLibrary(config_dir="config")
        loaded = Player.from_dict(data, item_lib)
        self.assertEqual(loaded.spiritual_roots, ["ice_wind"])
        self.assertTrue(loaded.has_element("ice"))
        self.assertTrue(loaded.has_element("wind"))
        self.assertEqual(loaded.get_root_purity("ice"), 1.3)


class TestFusionElementCounters(unittest.TestCase):
    """融合灵根克制计算测试。"""

    def test_fusion_counters_single_element(self):
        """融合灵根对单一属性触发克制。"""
        # thunder_fire 中的 thunder 克制 metal
        self.assertEqual(element_multiplier("thunder_fire", "metal"), 1.5)
        # thunder_fire 中的 fire 被 water 克制
        self.assertEqual(element_multiplier("water", "thunder_fire"), 1.5)
        self.assertEqual(element_multiplier("thunder_fire", "water"), 0.7)

    def test_fusion_counter_priority(self):
        """同时存在克制与被克制时，优先取克制。"""
        # thunder_fire vs metal_thunder:
        # thunder_fire 的 thunder 克制 metal_thunder 的 metal（克）
        # metal_thunder 的 thunder 克制 thunder_fire 的 metal？没有 metal。
        # metal_thunder 的 metal 被 thunder_fire 的 thunder 克（被克）
        # 所以 thunder_fire 克制 metal_thunder
        self.assertEqual(element_multiplier("thunder_fire", "metal_thunder"), 1.5)

    def test_fusion_neutral(self):
        """无克制关系时系数为 1.0。"""
        # thunder_fire 与 earth 无克制关系
        self.assertEqual(element_multiplier("thunder_fire", "earth"), 1.0)


class TestFusionRootsInCombat(unittest.TestCase):
    """融合灵根在战斗中的集成测试。"""

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.item_lib = ItemLibrary(config_dir="config")
        self.enemy_lib = EnemyLibrary(config_dir="config")
        self.skill_lib = SkillLibrary(config_dir="config")
        self.npc_lib = NPCLibrary(config_dir="config")
        self.quest_lib = QuestLibrary(config_dir="config")

        self.player = Player(name="融合修士")
        self.world = World(config_dir="config")
        self.event_pool = EventPool(config_dir="config")
        self.save_path = "test_fusion_roots_save.json"
        self.engine = GameEngine(
            self.player,
            self.world,
            self.event_pool,
            self.item_lib,
            self.enemy_lib,
            self.skill_lib,
            self.npc_lib,
            self.quest_lib,
            save_manager=SaveManager(save_path=self.save_path),
        )

    def tearDown(self):
        if os.path.exists(self.save_path):
            os.remove(self.save_path)

    def _create_enemy(self, **kwargs):
        data = {
            "id": kwargs.get("enemy_id", "test_enemy"),
            "name": kwargs.get("name", "测试敌人"),
            "alignment": "neutral",
            "hp": kwargs.get("hp", 1000),
            "attack": kwargs.get("attack", 20),
            "defense": kwargs.get("defense", 0),
            "exp": 0,
            "loot": [],
        }
        data.update(kwargs)
        return Enemy.from_dict(data)

    def _setup_combat(self, enemy):
        self.player.health = self.player.max_health
        self.player.qi = 9999
        self.player.base_attack = 10
        self.player.base_defense = 0
        self.player.shield_qi = 0
        self.engine.start_combat(enemy)

    def _learn_and_prepare(self, skill_id):
        skill = self.skill_lib.get(skill_id)
        self.player.learn_skill(skill_id)
        self.player.qi = 9999
        self.player.health = self.player.max_health
        # 拥有融合灵根后，组成元素已包含在 expanded_elements 中
        if skill.path_exclusive:
            self.player.cultivation_path = skill.path_exclusive

    def test_fusion_player_uses_thunder_skill(self):
        """雷火交加灵根玩家可使用雷属性技能。"""
        self.player.set_spiritual_roots(["thunder_fire"])
        enemy = self._create_enemy(hp=1000, element="metal", defense=0)
        self._learn_and_prepare("thunder_chain")
        self._setup_combat(enemy)

        with patch("game.engine.random.random", return_value=0.9):
            logs, result = self.engine.combat_round(enemy, "skill", "thunder_chain")
        self.assertEqual(result, "continue")
        # 雷克金，应触发克制提示
        self.assertTrue(any("雷" in log and "金" in log for log in logs))

    def test_fusion_player_uses_fire_skill(self):
        """雷火交加灵根玩家可使用火属性技能。"""
        self.player.set_spiritual_roots(["thunder_fire"])
        enemy = self._create_enemy(hp=1000, element="metal", defense=0)
        self._learn_and_prepare("fireball")
        self._setup_combat(enemy)

        with patch("game.engine.random.random", return_value=0.9):
            logs, result = self.engine.combat_round(enemy, "skill", "fireball")
        self.assertEqual(result, "continue")
        # 火克金
        self.assertTrue(any("火" in log and "金" in log for log in logs))

    def test_fusion_player_defends_with_first_element(self):
        """敌人攻击融合灵根玩家时，以展开后的首个元素作为防御属性。"""
        self.player.set_spiritual_roots(["ice_wind"])
        # ice_wind 展开为 ["ice", "wind"]，首个 ice 被 fire 克制
        enemy = self._create_enemy(hp=1000, attack=30, element="fire")
        self._setup_combat(enemy)

        with patch("game.engine.random.random", return_value=0.9):
            logs, result = self.engine.combat_round(enemy, "attack")
        self.assertEqual(result, "continue")
        self.assertTrue(any("火" in log and "冰" in log for log in logs))


class TestMindMethodWithFusionRoots(unittest.TestCase):
    """心法与融合灵根兼容性测试。"""

    def test_fusion_root_can_learn_element_mind_method(self):
        """拥有融合灵根的玩家可学习组成元素对应心法。"""
        player = Player(name="融合修士")
        player.set_spiritual_roots(["thunder_fire"])
        player.realm_id = "qi_refining_3"  # 满足大部分心法境界要求
        config = MindMethodConfig(config_dir="config")
        # 查找一个雷属性或火属性心法
        method_id = None
        for mcfg in config.get_all():
            if mcfg.get("element") in ("thunder", "fire"):
                method_id = mcfg["id"]
                break
        if method_id is None:
            self.skipTest("未找到雷/火属性心法，跳过")
        self.assertTrue(config.can_learn(method_id, player))


if __name__ == "__main__":
    unittest.main()
