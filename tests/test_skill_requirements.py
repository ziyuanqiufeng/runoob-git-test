# -*- coding: utf-8 -*-
"""技能使用条件与界面提示测试。

覆盖：灵气不足、境界不足、灵根不匹配、流派不匹配、武器缺失等不可用原因，
以及 get_skill_usability 返回的提示信息。
"""
import os
import unittest

from PySide6.QtWidgets import QApplication

from game.player import Player
from game.world import World
from game.events import EventPool
from game.item import ItemLibrary
from game.enemy import EnemyLibrary
from game.skill import SkillLibrary
from game.npc import NPCLibrary
from game.quest import QuestLibrary
from game.engine import GameEngine
from game.save_manager import SaveManager


class TestSkillRequirements(unittest.TestCase):
    """技能使用条件测试。"""

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
        self.save_path = "test_skill_requirements_save.json"
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

    def _create_enemy(self):
        from game.enemy import Enemy
        return Enemy.from_dict({
            "id": "test_enemy",
            "name": "测试敌人",
            "alignment": "neutral",
            "hp": 1000,
            "attack": 10,
            "defense": 0,
            "exp": 0,
            "loot": [],
        })

    def test_skill_realm_id_loaded(self):
        """技能配置中的 realm_id 应被正确加载。"""
        skill = self.skill_lib.get("five_elements_formation")
        self.assertEqual(skill.realm_id, "golden_core_peak")

    def test_usability_warns_low_realm(self):
        """境界不足时 get_skill_usability 仍允许尝试，并提示成功率。"""
        self.player.set_spiritual_roots(["metal", "wood", "water", "fire", "earth"])
        self.player.learn_skill("five_elements_formation")
        self.player.realm_id = "qi_refining_1"
        self.player.qi = 1000
        can_use, reasons = self.engine.get_skill_usability("five_elements_formation")
        self.assertTrue(can_use)
        self.assertTrue(any("境界不足" in r and "成功率" in r for r in reasons), reasons)

    def test_usability_allows_high_realm(self):
        """满足境界要求时应可用且无警告。"""
        self.player.set_spiritual_roots(["metal", "wood", "water", "fire", "earth"])
        self.player.learn_skill("five_elements_formation")
        self.player.realm_id = "golden_core_peak"
        self.player.qi = 1000
        can_use, reasons = self.engine.get_skill_usability("five_elements_formation")
        self.assertTrue(can_use)
        self.assertEqual(reasons, [])

    def test_combat_round_low_realm_can_backlash(self):
        """战斗中跨境界强行施展高阶技能可能失败并受到反噬。"""
        from unittest.mock import patch
        self.player.set_spiritual_roots(["metal", "wood", "water", "fire", "earth"])
        self.player.learn_skill("five_elements_formation")
        self.player.realm_id = "qi_refining_1"
        self.player.qi = 1000
        self.player.health = 1000
        enemy = self._create_enemy()
        self.engine.start_combat(enemy)
        # 固定 random 让强行施展失败
        with patch("random.random", return_value=1.0):
            logs, _ = self.engine.combat_round(enemy, "skill", "five_elements_formation")
        self.assertTrue(any("强行施展" in log and "反噬" in log for log in logs), logs)
        # 反噬应消耗真气并损失生命
        self.assertLess(self.player.qi, 1000)
        self.assertLess(self.player.health, 1000)

    def test_usability_blocks_low_qi(self):
        """真气不足时应返回对应原因。"""
        self.player.set_spiritual_roots(["fire"])
        self.player.learn_skill("fireball")
        self.player.realm_id = "qi_refining_1"
        self.player.qi = 0
        can_use, reasons = self.engine.get_skill_usability("fireball")
        self.assertFalse(can_use)
        self.assertTrue(any("真气不足" in r for r in reasons), reasons)

    def test_usability_blocks_wrong_element(self):
        """灵根不匹配时应返回对应原因。"""
        self.player.set_spiritual_roots(["water"])
        self.player.learn_skill("fireball")
        self.player.qi = 100
        can_use, reasons = self.engine.get_skill_usability("fireball")
        self.assertFalse(can_use)
        self.assertTrue(any("需要火" in r for r in reasons), reasons)

    def test_usability_blocks_wrong_path(self):
        """流派不匹配时应返回对应原因。"""
        self.player.set_spiritual_roots(["metal"])
        self.player.cultivation_path = "fa"
        self.player.learn_skill("sword_qi")
        self.player.qi = 100
        can_use, reasons = self.engine.get_skill_usability("sword_qi")
        self.assertFalse(can_use)
        self.assertTrue(any("剑修专属" in r for r in reasons), reasons)

    def test_proficiency_initializes_on_learn(self):
        """学习技能时熟练度应初始化为 1 级。"""
        self.player.set_spiritual_roots(["fire"])
        self.player.learn_skill("fireball")
        self.assertEqual(self.player.get_skill_proficiency("fireball"), 1)
        self.assertIn("fireball", self.player.skill_proficiency)

    def test_proficiency_reduces_qi_cost(self):
        """熟练度越高，技能实际真气消耗越低。"""
        self.player.set_spiritual_roots(["fire"])
        self.player.learn_skill("fireball")
        base_cost = self.skill_lib.get("fireball").qi_cost
        low_cost = self.engine._get_effective_qi_cost("fireball")
        self.assertEqual(low_cost, base_cost)

        # 将熟练度提升到 5 级（1+2+3+4 级共需 3+6+9+12=30 经验）
        for _ in range(30):
            self.player.gain_skill_exp("fireball")
        self.assertEqual(self.player.get_skill_proficiency("fireball"), 5)
        high_cost = self.engine._get_effective_qi_cost("fireball")
        self.assertLess(high_cost, base_cost)

    def test_proficiency_increases_damage(self):
        """熟练度越高，技能伤害越高。"""
        self.player.set_spiritual_roots(["fire"])
        self.player.learn_skill("fireball")
        self.player.realm_id = "foundation_peak"
        base_damage = self.engine._calculate_skill_damage(self.skill_lib.get("fireball"))

        # 将熟练度提升到 10 级（共需 3+6+...+27=135 经验）
        for _ in range(135):
            self.player.gain_skill_exp("fireball")
        self.assertEqual(self.player.get_skill_proficiency("fireball"), 10)
        high_damage = self.engine._calculate_skill_damage(self.skill_lib.get("fireball"))
        self.assertGreater(high_damage, base_damage)

    def test_proficiency_saved_and_loaded(self):
        """存档应正确保存和恢复技能熟练度。"""
        self.player.set_spiritual_roots(["fire"])
        self.player.learn_skill("fireball")
        for _ in range(20):
            self.player.gain_skill_exp("fireball")
        level = self.player.get_skill_proficiency("fireball")
        self.assertGreater(level, 1)

        data = self.player.to_dict()
        restored = Player.from_dict(data, self.item_lib)
        self.assertEqual(restored.get_skill_proficiency("fireball"), level)
        self.assertEqual(restored.skill_proficiency["fireball"]["exp"], self.player.skill_proficiency["fireball"]["exp"])

    def test_proficiency_increases_heal(self):
        """治疗技能熟练度越高，治疗量越高。"""
        self.player.set_spiritual_roots(["wood"])
        self.player.learn_skill("healing_breath")
        base_heal = self.engine._calculate_skill_heal(self.skill_lib.get("healing_breath"))
        # 升到 10 级
        for _ in range(135):
            self.player.gain_skill_exp("healing_breath")
        high_heal = self.engine._calculate_skill_heal(self.skill_lib.get("healing_breath"))
        self.assertGreater(high_heal, base_heal)

    def test_proficiency_increases_control_bonus(self):
        """控制技能熟练度越高，控制成功率加成越高。"""
        self.player.set_spiritual_roots(["earth"])
        self.player.learn_skill("bagua_formation")
        self.player.cultivation_path = "zhen"
        base_bonus = self.player.get_skill_control_bonus("bagua_formation")
        self.assertEqual(base_bonus, 0.0)
        # 升到 10 级
        for _ in range(135):
            self.player.gain_skill_exp("bagua_formation")
        high_bonus = self.player.get_skill_control_bonus("bagua_formation")
        self.assertGreater(high_bonus, base_bonus)

    def test_max_level_no_cooldown_effect(self):
        """满级技能有概率不进入冷却。"""
        from unittest.mock import patch
        self.player.set_spiritual_roots(["fire"])
        self.player.learn_skill("fireball")
        for _ in range(135):
            self.player.gain_skill_exp("fireball")
        self.player.qi = 1000
        enemy = self._create_enemy()
        self.engine.start_combat(enemy)
        # 固定 random 让免冷却特效触发（需小于 0.2）
        with patch("random.random", return_value=0.1):
            self.engine.combat_round(enemy, "skill", "fireball")
        self.assertEqual(self.player.get_skill_cooldown("fireball"), 0)

    def test_max_level_damage_debuff_effect(self):
        """满级伤害技能有概率附加异常。"""
        from unittest.mock import patch
        self.player.set_spiritual_roots(["fire"])
        self.player.learn_skill("fireball")
        for _ in range(135):
            self.player.gain_skill_exp("fireball")
        enemy = self._create_enemy()
        self.engine.start_combat(enemy)
        logs = []
        # 第一次 random 大于免冷却概率，第二次 random 小于附加异常概率
        with patch("random.random", side_effect=[0.3, 0.1]):
            self.engine._apply_mastery_max_level_bonus("fireball", self.skill_lib.get("fireball"), enemy, logs)
        self.assertTrue(any("化境" in log or "满级" in log for log in logs), logs)
        # 异常应作用到敌人身上（眩晕、封印、中毒、削弱等任意一种）
        self.assertTrue(
            self.engine.enemy_stunned > 0
            or self.engine.enemy_skill_sealed > 0
            or len(self.engine.combat_dot_effects) > 0
            or len(self.engine.enemy_attack_down) > 0
            or len(self.engine.enemy_defense_down) > 0,
            "满级伤害技能应附加异常状态",
        )

    def test_max_level_control_extra_turn(self):
        """满级控制技能持续回合 +1。"""
        self.player.set_spiritual_roots(["earth"])
        self.player.learn_skill("bagua_formation")
        self.player.cultivation_path = "zhen"
        for _ in range(135):
            self.player.gain_skill_exp("bagua_formation")
        enemy = self._create_enemy()
        self.engine.start_combat(enemy)
        # 构造一个 2 回合眩晕的控制技能，测试满级后变为 3 回合
        class DummyControlSkill:
            id = "bagua_formation"
            name = "测试控制"
            effects = [{"type": "stun", "target": "enemy", "turns": 2}]

        self.engine._apply_skill_effects(DummyControlSkill(), enemy, [])
        self.assertEqual(self.engine.enemy_stunned, 3)


if __name__ == "__main__":
    unittest.main()
