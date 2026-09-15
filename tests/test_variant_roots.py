# -*- coding: utf-8 -*-
"""变异/特殊灵根系统单元测试。

验证新增雷、冰、风三种变异灵根在配置、克制计算、战斗、技能释放中的正确性。
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
from game.engine import GameEngine, element_multiplier, ELEMENT_NAMES, ELEMENT_COUNTERS
from game.save_manager import SaveManager
from game.spiritual_root import SpiritualRootConfig


class TestVariantRootConfig(unittest.TestCase):
    """ SpiritualRootConfig 对变异灵根的加载测试。 """

    def test_loads_variant_elements(self):
        """配置应包含雷、冰、风三种变异属性。"""
        config = SpiritualRootConfig(config_dir="config")
        for elem in ("thunder", "ice", "wind"):
            self.assertIn(elem, config.elements)
            self.assertIn(elem, config.variant_elements)
            self.assertTrue(config.get_element_name(elem))

    def test_variant_element_names_and_colors(self):
        """变异属性应有中文名与颜色配置。"""
        config = SpiritualRootConfig(config_dir="config")
        self.assertEqual(config.get_element_name("thunder"), "雷")
        self.assertEqual(config.get_element_name("ice"), "冰")
        self.assertEqual(config.get_element_name("wind"), "风")
        self.assertTrue(config.get_element_color("thunder").startswith("#"))

    def test_random_roots_can_include_variants(self):
        """随机生成灵根时可能包含变异属性。"""
        config = SpiritualRootConfig(config_dir="config")
        found_variant = False
        for _ in range(200):
            roots = config.random_roots()
            if any(r in config.variant_elements for r in roots):
                found_variant = True
                break
        self.assertTrue(found_variant, "200 次随机应至少生成一次含变异属性的灵根")


class TestElementCounterWithVariants(unittest.TestCase):
    """ 变异灵根克制关系测试。 """

    def test_thunder_counters_metal(self):
        """雷克金：雷攻金受 1.5 倍，金攻雷受 0.7 倍。"""
        self.assertEqual(element_multiplier("thunder", "metal"), 1.5)
        self.assertEqual(element_multiplier("metal", "thunder"), 0.7)

    def test_ice_counters_fire(self):
        """冰克火：冰攻火受 1.5 倍，火攻冰受 0.7 倍。"""
        self.assertEqual(element_multiplier("ice", "fire"), 1.5)
        self.assertEqual(element_multiplier("fire", "ice"), 0.7)

    def test_wind_counters_wood(self):
        """风克木：风攻木受 1.5 倍，木攻风受 0.7 倍。"""
        self.assertEqual(element_multiplier("wind", "wood"), 1.5)
        self.assertEqual(element_multiplier("wood", "wind"), 0.7)

    def test_variant_vs_variant_neutral(self):
        """变异属性之间无克制时系数为 1.0。"""
        self.assertEqual(element_multiplier("thunder", "ice"), 1.0)
        self.assertEqual(element_multiplier("wind", "thunder"), 1.0)

    def test_element_names_include_variants(self):
        """ELEMENT_NAMES 应包含变异属性中文名。"""
        self.assertEqual(ELEMENT_NAMES["thunder"], "雷")
        self.assertEqual(ELEMENT_NAMES["ice"], "冰")
        self.assertEqual(ELEMENT_NAMES["wind"], "风")

    def test_element_counters_include_variants(self):
        """ELEMENT_COUNTERS 应定义变异属性克制。"""
        self.assertEqual(ELEMENT_COUNTERS["thunder"], "metal")
        self.assertEqual(ELEMENT_COUNTERS["ice"], "fire")
        self.assertEqual(ELEMENT_COUNTERS["wind"], "wood")


class TestVariantRootInCombat(unittest.TestCase):
    """ 变异灵根在战斗流程中的集成测试。 """

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
        self.save_path = "test_variant_roots_save.json"
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
        """构造测试敌人。"""
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
        """初始化战斗。"""
        self.player.health = self.player.max_health
        self.player.qi = 9999
        self.player.base_attack = 10
        self.player.base_defense = 0
        self.player.shield_qi = 0
        self.engine.start_combat(enemy)

    def _learn_and_prepare(self, skill_id):
        """学习技能并满足施展条件。"""
        skill = self.skill_lib.get(skill_id)
        self.player.learn_skill(skill_id)
        self.player.qi = 9999
        self.player.health = self.player.max_health
        if skill.element != "none" and not self.player.has_element(skill.element):
            self.player.set_spiritual_roots(self.player.spiritual_roots + [skill.element])
        if skill.path_exclusive:
            self.player.cultivation_path = skill.path_exclusive

    def test_thunder_skill_uses_variant_element(self):
        """雷属性技能可被雷灵根玩家使用并触发克制。"""
        enemy = self._create_enemy(hp=1000, element="metal", defense=0)
        self._learn_and_prepare("thunder_chain")
        self._setup_combat(enemy)

        with patch("game.engine.random.random", return_value=0.9):
            logs, result = self.engine.combat_round(enemy, "skill", "thunder_chain")
        self.assertEqual(result, "continue")
        # 雷克金，日志应出现克制提示
        self.assertTrue(any("雷" in log and "金" in log for log in logs))
        # 眩晕效果在敌人行动阶段已消耗，通过日志确认曾生效
        self.assertTrue(any("麻痹" in log or "眩晕" in log for log in logs))

    def test_ice_skill_seals_enemy(self):
        """冰属性技能可封印敌人技能。"""
        enemy = self._create_enemy(hp=1000, element="fire", defense=0)
        self._learn_and_prepare("ice_seal")
        self._setup_combat(enemy)

        with patch("game.engine.random.random", return_value=0.9):
            logs, result = self.engine.combat_round(enemy, "skill", "ice_seal")
        self.assertEqual(result, "continue")
        # 冰克火
        self.assertTrue(any("冰" in log and "火" in log for log in logs))
        # 封印效果在敌人行动阶段被触发，通过日志确认
        self.assertTrue(any("封印" in log for log in logs))

    def test_wind_skill_gives_evasion(self):
        """风属性技能可提供闪避加成。"""
        enemy = self._create_enemy(hp=1000, element="wood", defense=0)
        self._learn_and_prepare("gale_step")
        self._setup_combat(enemy)

        with patch("game.engine.random.random", return_value=0.9):
            logs, result = self.engine.combat_round(enemy, "skill", "gale_step")
        self.assertEqual(result, "continue")
        # 闪避加成在回合结束时被清空，通过日志确认效果曾生效
        self.assertTrue(any("闪避" in log for log in logs))

    def test_variant_enemy_attacks_player(self):
        """变异属性敌人可正常参与战斗并触发克制。"""
        enemy = self._create_enemy(
            hp=1000,
            attack=30,
            element="thunder",
            enemy_id="test_thunder_enemy",
        )
        # 玩家主灵根为金，被雷克制
        self.player.set_spiritual_roots(["metal"], {"metal": 1.0})
        self._setup_combat(enemy)

        with patch("game.engine.random.random", return_value=0.9):
            logs, result = self.engine.combat_round(enemy, "attack")
        self.assertEqual(result, "continue")
        # 雷克金，敌人攻击玩家时应出现克制提示
        self.assertTrue(any("雷" in log and "金" in log for log in logs))


class TestVariantSkillLibrary(unittest.TestCase):
    """ 技能库加载变异技能测试。 """

    def test_variant_skills_loaded(self):
        """技能库应加载新增的变异属性技能。"""
        lib = SkillLibrary(config_dir="config")
        for sid in ("thunder_chain", "heavens_thunder", "ice_spike", "ice_seal", "wind_blade", "gale_step"):
            skill = lib.get(sid)
            self.assertIsNotNone(skill, f"技能 {sid} 应存在")
            self.assertIn(skill.element, ("thunder", "ice", "wind"))


class TestVariantEnemyLibrary(unittest.TestCase):
    """ 敌人库加载变异敌人测试。 """

    def test_variant_enemies_loaded(self):
        """敌人库应加载新增的变异属性敌人。"""
        lib = EnemyLibrary(config_dir="config")
        for eid in ("thunder_wolf", "ice_spirit", "wind_roc"):
            enemy = lib.get(eid)
            self.assertIsNotNone(enemy, f"敌人 {eid} 应存在")
            # EnemyLibrary.get 返回原始字典，需通过键访问
            element = enemy.get("element") if isinstance(enemy, dict) else enemy.element
            self.assertIn(element, ("thunder", "ice", "wind"))


if __name__ == "__main__":
    unittest.main()
