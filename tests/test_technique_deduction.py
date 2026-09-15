# -*- coding: utf-8 -*-
"""维度③·M19 功法推演单元测试（无头）。

验证：开启推演生成节点序列；逐节点参悟消耗悟性+灵石并累积品质；
forced 确定化（成功/滞涩）；大成落定自创功法并注册为更强 Skill；
未竟不可大成；pending_deduction 存档 round-trip；品质阶乘算 Skill 强度。
"""
import unittest

from game.player import Player
from game.world import World
from game.events import EventPool
from game.item import Item, ItemLibrary
from game.enemy import EnemyLibrary
from game.skill import SkillLibrary
from game.npc import NPCLibrary
from game.quest import QuestLibrary
from game.engine import GameEngine


class TestTechniqueDeduction(unittest.TestCase):
    def _make_engine(self, realm="golden_core_early", stones=200, wisdom=50):
        player = Player(name="功法推演")
        player.realm_id = realm
        player.wisdom = wisdom
        for _ in range(stones):
            player.add_item(Item(
                item_id="spirit_stone", name="灵石", item_type="currency", value=1,
                description="", effects={}, stackable=True, max_stack=99, count=1,
            ))
        engine = GameEngine(
            player, World(config_dir="config"), EventPool(config_dir="config"),
            ItemLibrary(config_dir="config"), EnemyLibrary(config_dir="config"),
            SkillLibrary(config_dir="config"), NPCLibrary(config_dir="config"),
            QuestLibrary(config_dir="config"),
            save_manager=None, config_dir="config",
        )
        return engine

    # -------- 1. 开启推演生成节点序列 --------
    def test_start_deduction_creates_pending(self):
        engine = self._make_engine()
        ok, msg = engine.start_technique_deduction("试剑诀", "剑修", "attack")
        self.assertTrue(ok)
        pd = engine.player.pending_deduction
        self.assertIsNotNone(pd)
        self.assertEqual(pd["name"], "试剑诀")
        self.assertEqual(pd["school"], "剑修")
        self.assertEqual(len(pd["nodes"]), 4)  # max_nodes
        self.assertEqual(pd["idx"], 0)
        self.assertEqual(pd["quality"], 0)

    # -------- 2. 境界不足不可开启 --------
    def test_start_deduction_requires_realm(self):
        engine = self._make_engine(realm="qi_refining_early")  # 低境界
        ok, msg = engine.start_technique_deduction("试剑诀", "剑修", "attack")
        self.assertFalse(ok)
        self.assertIsNone(engine.player.pending_deduction)

    # -------- 3. 逐节点参悟：消耗 + 累积品质（forced 成功） --------
    def test_resolve_node_forced_success_accumulates(self):
        engine = self._make_engine()
        engine.start_technique_deduction("试剑诀", "剑修", "attack")
        w0 = engine.player.wisdom
        s0 = engine.player.count_item("spirit_stone")
        ok, msg, detail = engine.resolve_technique_deduction_node(force_success=True)
        self.assertTrue(ok)
        self.assertEqual(detail["outcome"], "妙悟")
        self.assertEqual(detail["gain"], detail["gain"])  # 成功全额
        # 消耗：每节点 wisdom 3 + stone 5
        self.assertEqual(engine.player.wisdom, w0 - 3)
        self.assertEqual(engine.player.count_item("spirit_stone"), s0 - 5)
        self.assertEqual(engine.player.pending_deduction["idx"], 1)
        self.assertGreater(engine.player.pending_deduction["quality"], 0)

    # -------- 4. 全节点成功 → 高品质阶（仙/道）--------
    def test_all_success_yields_high_tier(self):
        engine = self._make_engine()
        engine.start_technique_deduction("试剑诀", "剑修", "attack")
        for _ in range(4):
            engine.resolve_technique_deduction_node(force_success=True)
        status = engine.hundred_schools_manager.get_deduction_status()
        # 每个节点 quality ∈ {7,8,9}，四成功 ⇒ 28~36，至少『仙』品
        self.assertGreaterEqual(status["quality"], 28)
        self.assertIn(status["tier"], ("仙", "道"))

    # -------- 5. 全节点滞涩 → 低品质阶（凡/灵）--------
    def test_all_failure_yields_low_tier(self):
        engine = self._make_engine()
        engine.start_technique_deduction("试剑诀", "剑修", "attack")
        for _ in range(4):
            engine.resolve_technique_deduction_node(force_success=False)
        status = engine.hundred_schools_manager.get_deduction_status()
        # 滞涩半额：每个节点 floor(quality/2) ∈ {3,4}，四滞涩 ⇒ 12~16
        self.assertLessEqual(status["quality"], 16)
        self.assertIn(status["tier"], ("凡", "灵"))

    # -------- 6. 未竟不可大成；大成落定并注册 Skill --------
    def test_commit_requires_all_nodes_then_registers_skill(self):
        engine = self._make_engine()
        engine.start_technique_deduction("试剑诀", "剑修", "attack")
        # 只参悟 2 个节点就大成 → 应失败
        engine.resolve_technique_deduction_node(force_success=True)
        engine.resolve_technique_deduction_node(force_success=True)
        ok, msg, tech = engine.commit_technique_deduction()
        self.assertFalse(ok)
        self.assertIsNone(tech)

        # 参悟剩余 2 个节点后大成 → 成功并注册
        engine.resolve_technique_deduction_node(force_success=True)
        engine.resolve_technique_deduction_node(force_success=True)
        ok, msg, tech = engine.commit_technique_deduction()
        self.assertTrue(ok)
        self.assertIsNotNone(tech)
        self.assertEqual(tech["name"], "试剑诀")
        self.assertGreater(tech["quality"], 0)
        # Skill 已注册且学会，描述含品阶
        sk = engine.skill_library.get(tech["skill_id"])
        self.assertIsNotNone(sk)
        self.assertIn("品", sk.description)
        self.assertIn(tech["skill_id"], engine.player.skills)
        # pending 已清空
        self.assertIsNone(engine.player.pending_deduction)

    # -------- 7. pending_deduction 存档 round-trip --------
    def test_pending_deduction_save_roundtrip(self):
        engine = self._make_engine()
        engine.start_technique_deduction("试剑诀", "剑修", "attack")
        engine.resolve_technique_deduction_node(force_success=True)
        snap = engine.player.to_dict()

        player2 = Player.from_dict(snap, ItemLibrary(config_dir="config"))
        self.assertIsNotNone(player2.pending_deduction)
        self.assertEqual(player2.pending_deduction["name"], "试剑诀")
        self.assertEqual(player2.pending_deduction["idx"], 1)
        self.assertEqual(player2.pending_deduction["quality"],
                         engine.player.pending_deduction["quality"])

    # -------- 8. 品质阶乘算 Skill 强度（剑修 base_damage 30）--------
    def test_quality_tier_scales_skill_stats(self):
        engine = self._make_engine()
        mgr = engine.hundred_schools_manager
        # 凡品（quality=0）⇒ ×1.0
        base = mgr.build_skill_kwargs(
            {"skill_id": "x1", "school": "剑修", "attribute": "attack", "quality": 0}
        )
        self.assertEqual(base["base_damage"], 30)
        # 道品（quality=34 ⇒ ×2.0）
        high = mgr.build_skill_kwargs(
            {"skill_id": "x2", "school": "剑修", "attribute": "attack", "quality": 34}
        )
        self.assertEqual(high["base_damage"], 60)
        self.assertEqual(high["realm_multiplier"], 1.2)  # 0.6 × 2.0
        self.assertIn("道品", high["description"])
        # 既有旧功法（无 quality 键）不受影响
        legacy = mgr.build_skill_kwargs(
            {"skill_id": "x3", "school": "剑修", "attribute": "attack"}
        )
        self.assertEqual(legacy["base_damage"], 30)


if __name__ == "__main__":
    unittest.main()
