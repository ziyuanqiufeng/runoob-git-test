# -*- coding: utf-8 -*-
"""控制效果与战斗状态机单元测试。

验证新增 effects 字段在 Skill 中的解析、engine 中 `_apply_skill_effects`、
状态推进 `_tick_combat_states`、眩晕/封印/嘲讽/护盾/反弹等逻辑在战斗循环中的实际表现。
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
from game.skill import Skill, SkillLibrary
from game.npc import NPCLibrary
from game.quest import QuestLibrary
from game.engine import GameEngine
from game.save_manager import SaveManager


class TestSkillEffectsParsing(unittest.TestCase):
    """Skill 对象与 effects 字段解析测试。"""

    def test_skill_from_dict_with_effects(self):
        """Skill.from_dict 应正确加载 effects 列表。"""
        data = {
            "id": "test_stun",
            "name": "测试眩晕",
            "description": "",
            "base_damage": 0,
            "effects": [
                {"type": "stun", "target": "enemy", "turns": 2},
                {"type": "dot", "target": "enemy", "damage": 5, "turns": 3},
            ],
        }
        skill = Skill.from_dict(data)
        self.assertEqual(len(skill.effects), 2)
        self.assertEqual(skill.effects[0]["type"], "stun")
        self.assertEqual(skill.effects[1]["damage"], 5)

    def test_skill_create_copies_effects(self):
        """SkillLibrary.create 应复制 effects，避免模板被修改。"""
        lib = SkillLibrary(config_dir="config")
        template = lib.get("metal_prison")
        self.assertTrue(len(template.effects) > 0)
        copy1 = lib.create("metal_prison")
        copy2 = lib.create("metal_prison")
        copy1.effects[0]["turns"] = 99
        self.assertNotEqual(copy1.effects[0]["turns"], copy2.effects[0]["turns"])


class TestCombatStateMachine(unittest.TestCase):
    """engine 中控制效果应用与状态推进测试。"""

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
        self.save_path = "test_control_effects_save.json"
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
        """构造一个可控测试敌人。"""
        data = {
            "id": kwargs.get("enemy_id", "test_enemy"),
            "name": kwargs.get("name", "测试敌人"),
            "alignment": "neutral",
            "hp": kwargs.get("hp", 100),
            "attack": kwargs.get("attack", 10),
            "defense": kwargs.get("defense", 0),
            "exp": 0,
            "loot": [],
        }
        data.update(kwargs)
        return Enemy.from_dict(data)

    def _setup_combat(self, enemy):
        """初始化战斗并确保玩家可活到测试结束。"""
        self.player.health = self.player.max_health
        self.player.qi = 9999  # 战斗中施展技能消耗的是修为/真气，直接给足
        self.engine.start_combat(enemy)

    def _make_skill(self, effects, element="none", qi_cost=0, cooldown=0):
        """手动构造一个仅用于 `_apply_skill_effects` 测试的 Skill。"""
        return Skill(
            skill_id="test_skill",
            name="测试技能",
            description="",
            base_damage=0,
            element=element,
            qi_cost=qi_cost,
            cooldown=cooldown,
            effects=effects,
        )

    def test_apply_stun_sets_state(self):
        """眩晕效果应设置 enemy_stunned 并写入日志。"""
        enemy = self._create_enemy()
        self._setup_combat(enemy)
        skill = self._make_skill([{"type": "stun", "target": "enemy", "turns": 2}])
        logs = []
        self.engine._apply_skill_effects(skill, enemy, logs)
        self.assertEqual(self.engine.enemy_stunned, 2)
        self.assertTrue(any("眩晕" in log for log in logs))

    def test_apply_seal_sets_state(self):
        """封印效果应设置 enemy_skill_sealed。"""
        enemy = self._create_enemy()
        self._setup_combat(enemy)
        skill = self._make_skill([{"type": "seal", "target": "enemy", "turns": 2}])
        logs = []
        self.engine._apply_skill_effects(skill, enemy, logs)
        self.assertEqual(self.engine.enemy_skill_sealed, 2)

    def test_apply_taunt_sets_state(self):
        """嘲讽效果应设置 enemy_taunted。"""
        enemy = self._create_enemy()
        self._setup_combat(enemy)
        skill = self._make_skill([{"type": "taunt", "target": "enemy", "turns": 1}])
        logs = []
        self.engine._apply_skill_effects(skill, enemy, logs)
        self.assertEqual(self.engine.enemy_taunted, 1)

    def test_apply_attack_down_and_defense_down(self):
        """攻击/防御削弱应加入对应列表。"""
        enemy = self._create_enemy()
        self._setup_combat(enemy)
        skill = self._make_skill([
            {"type": "attack_down", "target": "enemy", "ratio": 0.3, "turns": 2},
            {"type": "defense_down", "target": "enemy", "ratio": 0.4, "turns": 2},
        ])
        logs = []
        self.engine._apply_skill_effects(skill, enemy, logs)
        self.assertEqual(len(self.engine.enemy_attack_down), 1)
        self.assertEqual(self.engine.enemy_attack_down[0]["ratio"], 0.3)
        self.assertEqual(self.engine._get_enemy_attack_multiplier(), 0.7)
        self.assertEqual(self.engine._get_enemy_defense_multiplier(), 0.6)

    def test_apply_dot(self):
        """持续伤害效果应加入 combat_dot_effects。"""
        enemy = self._create_enemy()
        self._setup_combat(enemy)
        skill = self._make_skill([{"type": "dot", "target": "enemy", "damage": 8, "turns": 3}])
        logs = []
        self.engine._apply_skill_effects(skill, enemy, logs)
        self.assertEqual(len(self.engine.combat_dot_effects), 1)
        self.assertEqual(self.engine.combat_dot_effects[0]["damage"], 8)

    def test_apply_shield(self):
        """护盾效果应累加 player_shield。"""
        enemy = self._create_enemy()
        self._setup_combat(enemy)
        skill = self._make_skill([{"type": "shield", "target": "player", "amount": 30}])
        logs = []
        self.engine._apply_skill_effects(skill, enemy, logs)
        self.assertEqual(self.engine.player_shield, 30)

    def test_apply_reflect(self):
        """反弹效果应取最大比例并设置 player_reflect_ratio。"""
        enemy = self._create_enemy()
        self._setup_combat(enemy)
        skill = self._make_skill([{"type": "reflect", "target": "player", "ratio": 0.3, "turns": 2}])
        logs = []
        self.engine._apply_skill_effects(skill, enemy, logs)
        self.assertEqual(self.engine.player_reflect_ratio, 0.3)

    def test_apply_evasion_up(self):
        """闪避提升应设置 player_evasion_bonus。"""
        enemy = self._create_enemy()
        self._setup_combat(enemy)
        skill = self._make_skill([{"type": "evasion_up", "target": "player", "ratio": 0.5, "turns": 1}])
        logs = []
        self.engine._apply_skill_effects(skill, enemy, logs)
        self.assertEqual(self.engine.player_evasion_bonus, 0.5)

    def test_apply_attack_up_and_defense_up(self):
        """攻击/防御增益应加入对应列表并提升乘数。"""
        enemy = self._create_enemy()
        self._setup_combat(enemy)
        skill = self._make_skill([
            {"type": "attack_up", "target": "player", "ratio": 0.2, "turns": 2},
            {"type": "defense_up", "target": "player", "ratio": 0.25, "turns": 2},
        ])
        logs = []
        self.engine._apply_skill_effects(skill, enemy, logs)
        self.assertEqual(self.engine._get_player_attack_multiplier(), 1.2)
        self.assertEqual(self.engine._get_player_defense_multiplier(), 1.25)

    def test_apply_heal_over_time(self):
        """持续恢复应加入 player_hot 并在 tick 时治疗。"""
        enemy = self._create_enemy()
        self._setup_combat(enemy)
        self.player.health = self.player.max_health - 20
        skill = self._make_skill([{"type": "heal_over_time", "target": "player", "amount": 10, "turns": 2}])
        logs = []
        self.engine._apply_skill_effects(skill, enemy, logs)
        self.assertEqual(len(self.engine.player_hot), 1)

        before = self.player.health
        self.engine._tick_combat_states(logs)
        self.assertEqual(self.player.health, before + 10)

    def test_apply_cleanse(self):
        """净化效果应设置 player_cleanse。"""
        enemy = self._create_enemy()
        self._setup_combat(enemy)
        skill = self._make_skill([{"type": "cleanse", "target": "player"}])
        logs = []
        self.engine._apply_skill_effects(skill, enemy, logs)
        self.assertTrue(self.engine.player_cleanse)

    def test_tick_combat_states_decrements_durations(self):
        """状态推进应正确递减剩余回合数并在过期时提示。"""
        enemy = self._create_enemy()
        self._setup_combat(enemy)
        self.engine.enemy_stunned = 1
        self.engine.enemy_skill_sealed = 1
        self.engine.enemy_attack_down.append({"ratio": 0.2, "turns": 1})
        self.engine.player_attack_up.append({"ratio": 0.2, "turns": 1})

        logs = []
        self.engine._tick_combat_states(logs)
        self.assertEqual(self.engine.enemy_stunned, 0)
        self.assertEqual(self.engine.enemy_skill_sealed, 0)
        self.assertEqual(len(self.engine.enemy_attack_down), 0)
        self.assertEqual(len(self.engine.player_attack_up), 0)
        self.assertTrue(any("恢复" in log or "消失" in log for log in logs))

    def test_stun_skips_enemy_turn(self):
        """敌人眩晕时应跳过其行动。"""
        enemy = self._create_enemy(hp=1000, attack=50)
        self._setup_combat(enemy)
        self.player.base_attack = 1
        self.player.base_defense = 0
        self.engine.enemy_stunned = 1

        health_before = self.player.health
        logs, result = self.engine.combat_round(enemy, "attack")
        self.assertEqual(result, "continue")
        self.assertEqual(self.player.health, health_before)
        self.assertTrue(any("眩晕" in log for log in logs))
        self.assertEqual(self.engine.enemy_stunned, 0)

    def test_seal_forces_normal_attack(self):
        """敌人被封印时不能使用技能，只能普通攻击。"""
        # 构造一个只会强力技能的高攻敌人
        enemy = self._create_enemy(
            hp=1000,
            attack=10,
            skills=[{
                "name": "狂暴一击",
                "description": "",
                "damage_multiplier": 5.0,
                "cooldown": 0,
                "chance": 1.0,
            }],
        )
        self._setup_combat(enemy)
        self.player.base_attack = 1
        self.player.base_defense = 0
        # 关闭法修真气护盾，避免其吸收全部伤害干扰判定
        self.player.shield_qi = 0
        self.engine.enemy_skill_sealed = 2

        # 同时 patch engine 与 enemy 的随机数，确保敌人按预期使用技能/普攻
        with patch("game.engine.random.random", return_value=0.0), \
             patch("game.enemy.random.random", return_value=0.0):
            logs, result = self.engine.combat_round(enemy, "attack")
        self.assertEqual(result, "continue")
        # 封印提示 + 普通攻击造成的低伤害
        self.assertTrue(any("封印" in log or "镇妖" in log for log in logs))
        # 伤害应接近 attack(10) - defense(0)，而非技能倍率后的 50
        self.assertLessEqual(self.player.max_health - self.player.health, 15)

    def test_shield_absorbs_damage(self):
        """玩家护盾应吸收敌人伤害。"""
        enemy = self._create_enemy(hp=1000, attack=30)
        self._setup_combat(enemy)
        self.player.base_attack = 1
        self.player.base_defense = 0
        # 关闭法修真气护盾，让 player_shield 单独生效
        self.player.shield_qi = 0
        self.engine.player_shield = 25

        with patch("game.engine.random.random", return_value=0.9):
            logs, result = self.engine.combat_round(enemy, "attack")
        self.assertEqual(result, "continue")
        self.assertTrue(any("护盾" in log for log in logs))
        # 护盾吸收 25，玩家实际受到 5 点伤害（30 - 25）
        self.assertEqual(self.player.max_health - self.player.health, 5)
        self.assertEqual(self.engine.player_shield, 0)

    def test_reflect_damages_enemy(self):
        """玩家反弹应把伤害返还给敌人。"""
        enemy = self._create_enemy(hp=100, attack=30)
        self._setup_combat(enemy)
        self.player.base_attack = 1
        self.player.base_defense = 0
        # 关闭法修真气护盾，让伤害能传递到反弹逻辑
        self.player.shield_qi = 0
        self.engine.player_reflect_ratio = 0.5

        enemy_hp_before = enemy.hp
        with patch("game.engine.random.random", return_value=0.9):
            logs, result = self.engine.combat_round(enemy, "attack")
        self.assertEqual(result, "continue")
        self.assertTrue(any("反弹" in log for log in logs))
        # 敌人造成 30 点伤害，反弹 50% 即 15
        self.assertLess(enemy.hp, enemy_hp_before)

    def test_cleanse_resets_each_turn(self):
        """净化标记应在每回合结束时重置。"""
        enemy = self._create_enemy()
        self._setup_combat(enemy)
        self.engine.player_cleanse = True
        logs = []
        self.engine._tick_combat_states(logs)
        self.assertFalse(self.engine.player_cleanse)

    def test_evasion_resets_each_turn(self):
        """闪避加成应在每回合结束时清空。"""
        enemy = self._create_enemy()
        self._setup_combat(enemy)
        self.engine.player_evasion_bonus = 0.5
        logs = []
        self.engine._tick_combat_states(logs)
        self.assertEqual(self.engine.player_evasion_bonus, 0.0)


class TestConfiguredSkillEffects(unittest.TestCase):
    """使用 skills.json 中真实配置验证效果应用。"""

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
        )

    def _setup_player_for_skill(self, skill_id):
        """让玩家满足指定技能施展条件。"""
        skill = self.skill_lib.get(skill_id)
        self.player.learn_skill(skill_id)
        self.player.qi = 9999  # 战斗中施展技能消耗的是修为/真气，直接给足
        self.player.health = self.player.max_health
        # 补充所需灵根（通过 set_spiritual_roots 确保 expanded_elements 同步更新）
        if skill.element != "none" and not self.player.has_element(skill.element):
            self.player.set_spiritual_roots(self.player.spiritual_roots + [skill.element])
        # 补充流派限制
        if skill.path_exclusive:
            self.player.cultivation_path = skill.path_exclusive
        # 剑修需要装备剑
        if skill.path_exclusive == "jian":
            sword = self.item_lib.create("iron_sword")
            self.player.equip(sword)

    def test_metal_prison_stuns_enemy(self):
        """庚金牢笼应眩晕敌人 1 回合。"""
        enemy = Enemy.from_dict({
            "id": "test_target",
            "name": "靶子",
            "alignment": "neutral",
            "hp": 1000,
            "attack": 1,
            "defense": 0,
            "exp": 0,
            "loot": [],
        })
        self._setup_player_for_skill("metal_prison")
        self.engine.start_combat(enemy)
        with patch("game.engine.random.random", return_value=0.9):
            logs, result = self.engine.combat_round(enemy, "skill", "metal_prison")
        self.assertEqual(result, "continue")
        self.assertTrue(any("庚金牢笼" in log and "眩晕" in log for log in logs))
        # 眩晕在敌人行动阶段已消耗，战斗结束后状态归 0
        self.assertEqual(self.engine.enemy_stunned, 0)

    def test_earth_guardian_applies_shield(self):
        """大地守护应给玩家添加护盾。"""
        enemy = Enemy.from_dict({
            "id": "test_target",
            "name": "靶子",
            "alignment": "neutral",
            "hp": 1000,
            "attack": 1,
            "defense": 0,
            "exp": 0,
            "loot": [],
        })
        self._setup_player_for_skill("earth_guardian")
        self.engine.start_combat(enemy)
        # 关闭法修真气护盾，确保大地守护的 player_shield 可被观察到
        self.player.shield_qi = 0
        with patch("game.engine.random.random", return_value=0.9):
            self.engine.combat_round(enemy, "skill", "earth_guardian")
        self.assertGreater(self.engine.player_shield, 0)


if __name__ == "__main__":
    unittest.main()
