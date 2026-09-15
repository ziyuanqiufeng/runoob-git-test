# -*- coding: utf-8 -*-
"""FamilyManager 单元测试（F-01 家族核心）。"""
import random
import unittest

from game.player import Player
from game.family import (
    FamilyManager, FAMILY_MIN_REALM_ORDER, CREATE_COST_STONE, CREATE_COST_REPUTATION
)
from game.item import ItemLibrary


def _make_player(realm="golden_core_early", stones=10000, rep=300):
    p = Player(name="家主")
    p.realm_id = realm
    lib = ItemLibrary(config_dir="config")
    for _ in range(stones):
        p.add_item(lib.create("spirit_stone"))
    p.reputation = {"righteous": rep}
    return p


def _make_manager(player=None, feature=True):
    p = player or _make_player()
    mgr = FamilyManager(
        p, config_dir="config",
        is_feature_enabled=(lambda f: feature),
        get_month_callback=lambda: 0,
    )
    return mgr, p


class TestFamilyManager(unittest.TestCase):
    def test_can_create_gates(self):
        # 低境界不可创建
        mgr, p = _make_manager(_make_player(realm="qi_refining_1"))
        ok, msg = mgr.can_create()
        self.assertFalse(ok)
        # 灵石不足
        mgr2, p2 = _make_manager(_make_player(stones=10))
        ok2, _ = mgr2.can_create()
        self.assertFalse(ok2)
        # 声望不足
        mgr3, p3 = _make_manager(_make_player(rep=10))
        ok3, _ = mgr3.can_create()
        self.assertFalse(ok3)
        # 功能关闭
        mgr4, _ = _make_manager(feature=False)
        self.assertFalse(mgr4.can_create()[0])

    def test_create_and_persist(self):
        mgr, p = _make_manager()
        ok, msg = mgr.create("苏氏", "问道泽苍生", "righteous")
        self.assertTrue(ok, msg)
        self.assertIsNotNone(p.family)
        self.assertEqual(p.family["name"], "苏氏")
        # 家主作为首位成员
        self.assertEqual(len(p.family["members"]), 1)
        # 灵石被消耗
        self.assertLess(p.count_item("spirit_stone"), 10000)

    def test_recruit_and_assign(self):
        mgr, p = _make_manager()
        mgr.create("苏氏", "x", "righteous")
        mem = mgr.recruit_member(quality="normal")
        self.assertIsNotNone(mem)
        self.assertIn(mem["id"], [m["id"] for m in p.family["members"]])
        self.assertTrue(mgr.assign_task(mem["id"], "manage"))
        self.assertEqual(mgr.get_member(mem["id"])["task"], "manage")

    def test_monthly_settle_produces(self):
        mgr, p = _make_manager()
        mgr.create("苏氏", "x", "righteous")
        mem = mgr.recruit_member(quality="normal")
        mgr.assign_task(mem["id"], "manage")
        before_treasury = p.family["treasury"]
        mgr.monthly_settle()
        # 经营成员应产出灵石
        self.assertGreaterEqual(p.family["treasury"], before_treasury)

    def test_build_or_upgrade(self):
        mgr, p = _make_manager()
        mgr.create("苏氏", "x", "righteous")
        p.family["treasury"] = 100000
        ok, msg = mgr.build_or_upgrade("shop")
        self.assertTrue(ok, msg)
        self.assertEqual(p.family["buildings"]["shop"], 1)

    def test_disband(self):
        mgr, p = _make_manager()
        mgr.create("苏氏", "x", "righteous")
        ok, msg = mgr.disband()
        self.assertTrue(ok)
        self.assertIsNone(p.family)

    def test_tick_monthly_noop_without_family(self):
        mgr, p = _make_manager()
        # 未建家族，tick 不应报错
        mgr.tick_monthly()
        self.assertIsNone(p.family)

    def test_feature_flag_off_noop(self):
        mgr, _ = _make_manager(feature=False)
        self.assertFalse(mgr.is_enabled())
        self.assertFalse(mgr.can_create()[0])

    def test_inherit_as_heir(self):
        mgr, p = _make_manager()
        mgr.create("苏氏", "x", "righteous")
        mgr.recruit_member(quality="normal")
        mgr.recruit_member(quality="normal")
        self.assertTrue(mgr.can_inherit_as_heir())
        self.assertTrue(mgr.inherit_as_heir())
        # 原家主（首位）已被移除
        self.assertEqual(len(p.family["members"]), 2)


if __name__ == "__main__":
    unittest.main()
