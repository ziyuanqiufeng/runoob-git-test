# -*- coding: utf-8 -*-
import unittest

from game.player import Player
from game.world import World
from game.companion import CompanionManager, CompanionConfig


class MockNPCLibrary:
    """简易 NPC 库，仅用于测试。"""

    def __init__(self):
        self.npcs = {
            "elder_qing": {"id": "elder_qing", "name": "青云长老"},
            "market_keeper": {"id": "market_keeper", "name": "坊市掌柜"},
            "unknown": {"id": "unknown", "name": "神秘人"},
        }

    def get(self, npc_id):
        return self.npcs.get(npc_id)


class TestCompanionManager(unittest.TestCase):
    """道侣系统测试。"""

    def setUp(self):
        self.player = Player(name="测试修士")
        self.player.realm_id = "qi_refining_3"  # 满足 min_realm_order=3
        self.world = World(config_dir="config")
        self.npc_lib = MockNPCLibrary()
        self.manager = CompanionManager(self.player, self.world, npc_library=self.npc_lib)

    def test_form_companion_requires_favor(self):
        """好感度不足时不能结为道侣。"""
        ok, msg = self.manager.form_companion("elder_qing")
        self.assertFalse(ok)
        self.assertIn("好感度", msg)

    def test_form_companion_success(self):
        """满足条件时成功结为道侣。"""
        self.player.npc_relationships["elder_qing"] = 10
        ok, msg = self.manager.form_companion("elder_qing")
        self.assertTrue(ok)
        self.assertIn("青云长老", msg)
        self.assertEqual(len(self.player.companions), 1)

    def test_cannot_form_duplicate_companion(self):
        """不能重复结为道侣。"""
        self.player.npc_relationships["elder_qing"] = 10
        self.manager.form_companion("elder_qing")
        ok, msg = self.manager.form_companion("elder_qing")
        self.assertFalse(ok)
        self.assertIn("已是", msg)

    def test_max_companion_limit(self):
        """道侣数量达到上限后不能再结。"""
        self.player.npc_relationships["elder_qing"] = 10
        self.player.npc_relationships["market_keeper"] = 10
        self.player.npc_relationships["unknown"] = 10
        self.manager.form_companion("elder_qing")
        self.manager.form_companion("market_keeper")
        self.manager.form_companion("unknown")
        self.player.npc_relationships["extra"] = 10
        self.npc_lib.npcs["extra"] = {"id": "extra", "name": "额外"}
        ok, msg = self.manager.form_companion("extra")
        self.assertFalse(ok)
        self.assertIn("上限", msg)

    def test_dual_cultivation(self):
        """双修应增加修为、亲密度并进入冷却。"""
        self.player.npc_relationships["elder_qing"] = 10
        self.manager.form_companion("elder_qing")
        qi_before = self.player.qi
        ok, msg = self.manager.dual_cultivate("elder_qing")
        self.assertTrue(ok)
        self.assertGreater(self.player.qi, qi_before)
        self.assertEqual(self.player.companions[0]["intimacy"], 5)

    def test_dual_cultivation_cooldown(self):
        """双修冷却期内不能再次双修。"""
        self.player.npc_relationships["elder_qing"] = 10
        self.manager.form_companion("elder_qing")
        self.manager.dual_cultivate("elder_qing")
        ok, msg = self.manager.dual_cultivate("elder_qing")
        self.assertFalse(ok)
        self.assertIn("冷却", msg)

    def test_cannot_dual_with_dead_companion(self):
        """不能和已逝道侣双修。"""
        self.player.npc_relationships["elder_qing"] = 10
        self.manager.form_companion("elder_qing")
        self.manager.on_companion_death("elder_qing")
        ok, msg = self.manager.dual_cultivate("elder_qing")
        self.assertFalse(ok)
        self.assertIn("已逝", msg)

    def test_battle_bonus(self):
        """道侣亲密度应转化为战斗加成。"""
        self.player.npc_relationships["elder_qing"] = 10
        self.manager.form_companion("elder_qing")
        self.manager.increase_intimacy("elder_qing", 50)
        atk, defense = self.manager.get_battle_bonus()
        self.assertGreater(atk, 0)
        self.assertGreater(defense, 0)

    def test_companion_death_penalty(self):
        """道侣死亡应扣除道心、增加心魔。"""
        self.player.npc_relationships["elder_qing"] = 10
        self.manager.form_companion("elder_qing")
        self.player.mental_state = 50
        self.player.heart_demon = 0
        result = self.manager.on_companion_death("elder_qing")
        self.assertIsNotNone(result)
        self.assertLess(self.player.mental_state, 50)
        self.assertGreater(self.player.heart_demon, 0)
        self.assertFalse(self.player.companions[0]["is_alive"])

    def test_get_alive_companions(self):
        """应正确筛选在世的道侣。"""
        self.player.npc_relationships["elder_qing"] = 10
        self.player.npc_relationships["market_keeper"] = 10
        self.manager.form_companion("elder_qing")
        self.manager.form_companion("market_keeper")
        self.manager.on_companion_death("elder_qing")
        alive = self.manager.get_alive_companions()
        self.assertEqual(len(alive), 1)
        self.assertEqual(alive[0]["npc_id"], "market_keeper")


if __name__ == "__main__":
    unittest.main()
