# -*- coding: utf-8 -*-
"""敌人境界、战斗缩放、高阶特殊机制与掉落测试。"""
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
from game.engine import GameEngine
from game.save_manager import SaveManager


class TestEnemyRealmAndScaling(unittest.TestCase):
    """敌人境界字段与战斗缩放测试。"""

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.item_lib = ItemLibrary(config_dir="config")
        self.enemy_lib = EnemyLibrary(config_dir="config")
        self.skill_lib = SkillLibrary(config_dir="config")
        self.npc_lib = NPCLibrary(config_dir="config")
        self.quest_lib = QuestLibrary(config_dir="config")

        self.player = Player(name="测试修士")
        self.world = World(config_dir="config")
        self.event_pool = EventPool(config_dir="config")
        self.engine = GameEngine(
            self.player,
            self.world,
            self.event_pool,
            self.item_lib,
            self.enemy_lib,
            self.skill_lib,
            self.npc_lib,
            self.quest_lib,
            save_manager=SaveManager(save_path="test_enemy_realm.json"),
        )

    def tearDown(self):
        import os
        if os.path.exists("test_enemy_realm.json"):
            os.remove("test_enemy_realm.json")

    def test_enemy_loaded_with_realm_id(self):
        """敌人模板应包含 realm_id 字段。"""
        enemy_data = self.enemy_lib.get("qilin")
        self.assertIsNotNone(enemy_data)
        self.assertIn("realm_id", enemy_data)
        self.assertEqual(enemy_data["realm_id"], "golden_core_peak")

    def test_enemy_instance_has_realm_id(self):
        """从模板创建的 Enemy 实例应携带 realm_id。"""
        enemy = Enemy.from_dict(self.enemy_lib.get("qilin"))
        self.assertEqual(enemy.realm_id, "golden_core_peak")

    def test_realm_scaling_strengthens_higher_enemy(self):
        """玩家境界低于敌人时，敌人属性应被增强。"""
        enemy = Enemy.from_dict(self.enemy_lib.get("qilin"))
        original_hp = enemy.max_hp
        original_atk = enemy.attack
        self.engine.start_combat(enemy)
        self.assertGreater(enemy.max_hp, original_hp)
        self.assertGreater(enemy.attack, original_atk)

    def test_realm_scaling_weakens_lower_enemy(self):
        """玩家境界高于敌人时，敌人属性应被削弱。"""
        self.player.realm_id = "nascent_soul"
        enemy = Enemy.from_dict(self.enemy_lib.get("wolf"))
        original_hp = enemy.max_hp
        original_atk = enemy.attack
        self.engine.start_combat(enemy)
        self.assertLess(enemy.max_hp, original_hp)
        self.assertLess(enemy.attack, original_atk)

    def test_combat_damage_modifier_uses_realm(self):
        """伤害修正应基于敌人 realm_id 而非 level。"""
        self.player.realm_id = "foundation_early"
        enemy = Enemy.from_dict(self.enemy_lib.get("qilin"))
        modifier = self.engine._combat_damage_modifier(enemy)
        # 玩家 order=10，麒麟 order=16，diff=-6，modifier=1-6*0.2=0.5（被限制）
        self.assertLess(modifier, 1.0)


class TestEnemySpecialMechanics(unittest.TestCase):
    """高阶敌人专属技能与召唤机制测试。"""

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.item_lib = ItemLibrary(config_dir="config")
        self.enemy_lib = EnemyLibrary(config_dir="config")
        self.skill_lib = SkillLibrary(config_dir="config")
        self.npc_lib = NPCLibrary(config_dir="config")
        self.quest_lib = QuestLibrary(config_dir="config")

        self.player = Player(name="测试修士")
        self.player.health = 1000
        self.player.max_health = 1000
        self.world = World(config_dir="config")
        self.event_pool = EventPool(config_dir="config")
        self.engine = GameEngine(
            self.player,
            self.world,
            self.event_pool,
            self.item_lib,
            self.enemy_lib,
            self.skill_lib,
            self.npc_lib,
            self.quest_lib,
            save_manager=SaveManager(save_path="test_enemy_special.json"),
        )

    def tearDown(self):
        import os
        if os.path.exists("test_enemy_special.json"):
            os.remove("test_enemy_special.json")

    @patch("game.engine.random.random", return_value=0.0)
    def test_special_skill_trigger(self, mock_random):
        """高阶敌人应能触发专属技能。"""
        enemy = Enemy.from_dict(self.enemy_lib.get("thunder_lord"))
        self.engine.start_combat(enemy)
        initial_health = self.player.health
        logs, _ = self.engine.combat_round(enemy, "attack")
        # random=0 保证 thunder_lord 的 special_skill 触发
        self.assertTrue(
            any("雷霆万钧" in log for log in logs),
            logs
        )
        self.assertLess(self.player.health, initial_health)

    @patch("game.engine.random.random", return_value=0.0)
    def test_summon_trigger(self, mock_random):
        """高阶敌人应能召唤协助单位。"""
        enemy = Enemy.from_dict(self.enemy_lib.get("qilin"))
        self.engine.start_combat(enemy)
        logs, _ = self.engine.combat_round(enemy, "attack")
        self.assertTrue(
            any("圣火分身" in log for log in logs),
            logs
        )
        self.assertEqual(len(self.engine.enemy_summons), 1)

    @patch("game.engine.random.random", return_value=0.0)
    def test_summon_attacks_player(self, mock_random):
        """召唤物应在后续回合攻击玩家。"""
        enemy = Enemy.from_dict(self.enemy_lib.get("qilin"))
        self.engine.start_combat(enemy)
        # 第一回合召唤
        self.engine.combat_round(enemy, "attack")
        self.assertEqual(len(self.engine.enemy_summons), 1)
        initial_health = self.player.health
        # 第二回合召唤物应协同攻击
        self.engine.combat_round(enemy, "attack")
        self.assertLess(self.player.health, initial_health)


class TestEnemyLootScaling(unittest.TestCase):
    """基于境界的掉落调整测试。"""

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.enemy_lib = EnemyLibrary(config_dir="config")

    def test_loot_increases_when_enemy_higher(self):
        """越级挑战时掉落概率应提升。"""
        enemy = Enemy.from_dict(self.enemy_lib.get("qilin"))
        # 多次采样，玩家境界 order=1 时麒麟掉落应更频繁
        results_low = []
        results_high = []
        for _ in range(100):
            results_low.extend(enemy.get_loot(player_realm_order=1))
            results_high.extend(enemy.get_loot(player_realm_order=16))
        self.assertGreater(len(results_low), len(results_high))

    def test_high_level_enemy_extra_loot(self):
        """高阶敌人有概率额外掉落。"""
        enemy = Enemy.from_dict(self.enemy_lib.get("qilin"))
        total = 0
        for _ in range(100):
            total += len(enemy.get_loot(player_realm_order=1))
        # 麒麟有 3 个必掉物品 + 30% 额外掉落，100 次应明显超过 300
        self.assertGreater(total, 300)

    def test_demon_core_quality_by_realm_gap(self):
        """妖核应按境界差映射为下品/中品/上品。"""
        wolf = Enemy.from_dict(self.enemy_lib.get("wolf"))
        # wolf 境界 order=2，玩家 order=1 时差 1 → 中品
        self.assertEqual(
            wolf._resolve_demon_core_quality("demon_core", 1), "demon_core_mid"
        )
        # 玩家 order=5 时差 -3 → 下品
        self.assertEqual(
            wolf._resolve_demon_core_quality("demon_core", -3), "demon_core_low"
        )

        qilin = Enemy.from_dict(self.enemy_lib.get("qilin"))
        # qilin 境界 order=17，玩家 order=1 时差 16 → 上品
        self.assertEqual(
            qilin._resolve_demon_core_quality("demon_core", 16), "demon_core_high"
        )
        # 同阶 → 中品
        self.assertEqual(
            qilin._resolve_demon_core_quality("demon_core", 0), "demon_core_mid"
        )

    @patch("game.enemy.random.random", return_value=0.0)
    def test_get_loot_maps_demon_core_quality(self, mock_random):
        """get_loot 返回的妖核应根据境界差呈现对应品质。"""
        # 构造一个高境界且必掉妖核的测试敌人
        enemy = Enemy.from_dict({
            "id": "test_demon",
            "name": "测试妖兽",
            "alignment": "neutral",
            "hp": 100,
            "attack": 10,
            "defense": 0,
            "exp": 0,
            "level": 8,
            "realm_id": "golden_core_peak",
            "loot": [{"item_id": "demon_core", "chance": 1.0}],
        })
        # 玩家 order=1，敌人 order=17，差 16 → 上品
        loot = enemy.get_loot(player_realm_order=1, enemy_realm_order=17)
        self.assertIn("demon_core_high", loot)
        self.assertNotIn("demon_core", loot)
        self.assertNotIn("demon_core_low", loot)
        self.assertNotIn("demon_core_mid", loot)

        # 同阶 → 中品
        loot_same = enemy.get_loot(player_realm_order=17, enemy_realm_order=17)
        self.assertIn("demon_core_mid", loot_same)

        # 玩家高于敌人 → 下品（固定 random 确保触发掉落）
        loot_low = enemy.get_loot(player_realm_order=18, enemy_realm_order=17)
        self.assertIn("demon_core_low", loot_low)


if __name__ == "__main__":
    unittest.main()
