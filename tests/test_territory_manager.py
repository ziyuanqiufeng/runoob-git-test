# -*- coding: utf-8 -*-
"""TerritoryManager 单元测试（F-02 领地建设与扩张）。"""
import unittest

from game.player import Player
from game.territory_manager import (
    TerritoryManager,
    TERRITORY_MIN_REALM_ORDER,
)
from game.item import ItemLibrary


def _make_player(realm="nascent_soul", stones=40000):
    p = Player(name="领主")
    p.realm_id = realm
    p.reputation = {}
    lib = ItemLibrary(config_dir="config")
    for _ in range(stones):
        p.add_item(lib.create("spirit_stone"))
    p.item_library = lib
    return p


def _make_manager(player=None, feature=True):
    p = player or _make_player()
    mgr = TerritoryManager(
        p,
        config_dir="config",
        is_feature_enabled=(lambda f: feature),
        get_month_callback=lambda: 0,
        item_library=getattr(p, "item_library", None),
    )
    return mgr, p


class _DeterministicRng:
    """随机永远命中（random()=0），choice 取首项，uniform 取下界。"""

    def random(self):
        return 0.0

    def choice(self, seq):
        return seq[0]

    def uniform(self, a, b):
        return a


class TestTerritoryClaim(unittest.TestCase):
    def test_can_claim_gates(self):
        # 功能关闭
        mgr, _ = _make_manager(feature=False)
        self.assertFalse(mgr.can_claim("qingyun_lingmai")[0])
        # 境界不足
        mgr2, _ = _make_manager(_make_player(realm="golden_core_early"))
        self.assertFalse(mgr2.can_claim("qingyun_lingmai")[0])
        # 灵石不足
        mgr3, _ = _make_manager(_make_player(stones=10))
        self.assertFalse(mgr3.can_claim("qingyun_lingmai")[0])
        # 不存在的地图
        mgr4, _ = _make_manager()
        self.assertFalse(mgr4.can_claim("no_such_map")[0])
        # 一切正常
        mgr5, _ = _make_manager()
        self.assertTrue(mgr5.can_claim("qingyun_lingmai")[0])

    def test_claim_creates_territory(self):
        mgr, p = _make_manager()
        ok, msg = mgr.claim("qingyun_lingmai")
        self.assertTrue(ok, msg)
        ter = p.territory
        self.assertIsNotNone(ter)
        self.assertEqual(ter["territory_id"], "qingyun_lingmai")
        self.assertEqual(ter["tier"], "spirit_vein")
        self.assertEqual(ter["grid"]["rows"], 4)
        self.assertEqual(ter["grid"]["cols"], 4)
        self.assertEqual(ter["max_energy"], 60)
        self.assertEqual(ter["energy"], 60)
        # 灵石已被消耗（claim_cost 8000）
        self.assertEqual(p.count_item("spirit_stone"), 40000 - 8000)
        # 已占据则无法重复占领
        self.assertFalse(mgr.can_claim("bingyuan_lingmai")[0])

    def test_claim_respects_min_realm_order(self):
        # 元婴期恰好为解锁线
        mgr, _ = _make_manager(_make_player(realm="nascent_soul"))
        self.assertGreaterEqual(
            Player.REALM_ORDER.get("nascent_soul", 0), TERRITORY_MIN_REALM_ORDER
        )


class TestTerritoryBuilding(unittest.TestCase):
    def setUp(self):
        self.mgr, self.p = _make_manager()
        self.mgr.claim("qingyun_lingmai")

    def _ter(self):
        return self.p.territory

    def test_place_and_count(self):
        ok, msg = self.mgr.build_mgr.place(self._ter(), 0, 0, "spirit_gathering_tower")
        self.assertTrue(ok, msg)
        placed = self.mgr.build_mgr.placed(self._ter())
        self.assertEqual(len(placed), 1)
        self.assertEqual(placed[0][2], "spirit_gathering_tower")

    def test_place_out_of_bounds(self):
        ok, msg = self.mgr.build_mgr.place(self._ter(), 9, 9, "spirit_gathering_tower")
        self.assertFalse(ok)
        self.assertIn("超出", msg)

    def test_place_occupied(self):
        self.mgr.build_mgr.place(self._ter(), 0, 0, "spirit_gathering_tower")
        ok, msg = self.mgr.build_mgr.place(self._ter(), 0, 0, "guard_tower")
        self.assertFalse(ok)
        self.assertIn("已有", msg)

    def test_upgrade_and_max_level(self):
        self.mgr.build_mgr.place(self._ter(), 0, 0, "spirit_gathering_tower")
        ok, msg = self.mgr.build_mgr.upgrade(self._ter(), 0, 0)
        self.assertTrue(ok, msg)
        self.assertEqual(self._ter()["grid"]["cells"][0][0]["level"], 2)
        # 升到最高级后不可再升
        for _ in range(5):
            self.mgr.build_mgr.upgrade(self._ter(), 0, 0)
        ok_max, _ = self.mgr.build_mgr.can_upgrade(self._ter(), 0, 0)
        self.assertFalse(ok_max)

    def test_remove_and_refund(self):
        before = self.p.count_item("spirit_stone")
        self.mgr.build_mgr.place(self._ter(), 1, 1, "spirit_gathering_tower")
        self.mgr.build_mgr.upgrade(self._ter(), 1, 1)  # 升到2级花费
        ok, msg = self.mgr.build_mgr.remove(self._ter(), 1, 1)
        self.assertTrue(ok, msg)
        self.assertIsNone(self._ter()["grid"]["cells"][1][1])
        # 拆除返还了部分灵石
        self.assertGreater(self.p.count_item("spirit_stone"), before - 1000)

    def test_effect_aggregation(self):
        self.mgr.build_mgr.place(self._ter(), 0, 0, "spirit_gathering_tower")
        self.mgr.build_mgr.upgrade(self._ter(), 0, 0)  # 2 级
        val = self.mgr.build_mgr.get_effect(self._ter(), "spirit_stone")
        # 每级 25，2 级 = 50
        self.assertEqual(val, 50.0)


class TestTerritoryDefense(unittest.TestCase):
    def setUp(self):
        self.mgr, self.p = _make_manager()
        self.mgr.claim("qingyun_lingmai")

    def _ter(self):
        return self.p.territory

    def test_formation_synergy(self):
        self.mgr.build_mgr.place(self._ter(), 0, 0, "formation_eye_fire")
        self.mgr.build_mgr.place(self._ter(), 0, 1, "formation_eye_water")
        self.assertEqual(len(self.mgr.defense_mgr.formation_elements(self._ter())), 2)
        self.assertGreater(self.mgr.defense_mgr.synergy_bonus(self._ter()), 0)

    def test_defense_rate_clamped(self):
        self.mgr.build_mgr.place(self._ter(), 0, 0, "guard_tower")
        self.mgr.build_mgr.place(self._ter(), 0, 1, "formation_eye_fire")
        self.mgr.build_mgr.place(self._ter(), 0, 2, "formation_eye_water")
        rate = self.mgr.defense_mgr.defense_rate(self._ter())
        self.assertGreaterEqual(rate, 0.0)
        self.assertLessEqual(rate, 0.95)

    def test_raid_trigger_and_resolve(self):
        # 用确定命中随机器触发袭扰
        rng = _DeterministicRng()
        raid = self.mgr.defense_mgr.maybe_trigger_raid(self._ter(), rng=rng)
        self.assertIsNotNone(raid)
        self.assertEqual(self._ter()["pending_raid"]["enemy_id"], "beast_tiger")
        # 胜利结算：守卫成功，记录 defended
        ok, msg = self.mgr.defense_mgr.resolve_raid(self._ter(), win=True)
        self.assertTrue(ok)
        self.assertEqual(self._ter()["defended_count"], 1)
        self.assertIsNone(self._ter()["pending_raid"])
        # 再次触发并失败：损毁一座建筑（这里没有建筑，损耗能量）
        raid2 = self.mgr.defense_mgr.maybe_trigger_raid(self._ter(), rng=rng)
        self.assertIsNotNone(raid2)
        ok2, msg2 = self.mgr.defense_mgr.resolve_raid(self._ter(), win=False)
        self.assertFalse(ok2)
        self.assertEqual(self._ter()["raided_count"], 1)


class TestTerritoryProduction(unittest.TestCase):
    def setUp(self):
        self.mgr, self.p = _make_manager()
        self.mgr.claim("qingyun_lingmai")
        self.mgr.build_mgr.place(self.p.territory, 0, 0, "spirit_gathering_tower")

    def test_monthly_settle_treasury(self):
        # 产出进入金库；维护费优先从金库扣、金库不足则从玩家私库补足
        stones_before = self.p.count_item("spirit_stone")
        logs = self.mgr.prod_mgr.settle_monthly(self.p.territory, rng=_DeterministicRng())
        # 聚灵塔 1 级：产出 25 入金库；维护 8 从私库扣除（金库初始为 0）
        self.assertEqual(self.p.territory["treasury"], 25)
        self.assertEqual(self.p.count_item("spirit_stone"), stones_before - 8)
        self.assertTrue(any("灵石" in line for line in logs))


class TestTerritoryTierUpgrade(unittest.TestCase):
    def test_upgrade_tier_expands_grid(self):
        mgr, p = _make_manager()
        mgr.claim("qingyun_lingmai")
        # 先放一座建筑，验证升级后保留
        mgr.build_mgr.place(p.territory, 0, 0, "guard_tower")
        ok, msg = mgr.upgrade_tier()
        self.assertTrue(ok, msg)
        self.assertEqual(p.territory["tier"], "blessed_land")
        self.assertEqual(p.territory["grid"]["rows"], 6)
        self.assertEqual(p.territory["grid"]["cols"], 6)
        # 旧建筑坐标仍有效
        self.assertIsNotNone(p.territory["grid"]["cells"][0][0])
        # 已升至最高则不可再升
        mgr.upgrade_tier()
        self.assertFalse(mgr.can_upgrade_tier()[0])


class TestTerritoryTick(unittest.TestCase):
    def test_tick_noop_when_unclaimed(self):
        mgr, p = _make_manager()
        # 未占据领地，月度结算应为纯 no-op，不报错
        mgr.tick_monthly()
        self.assertIsNone(p.territory)

    def test_tick_settles_when_claimed(self):
        mgr, p = _make_manager()
        mgr.claim("qingyun_lingmai")
        mgr.build_mgr.place(p.territory, 0, 0, "spirit_gathering_tower")
        before = p.territory["treasury"]
        mgr.tick_monthly()
        self.assertNotEqual(p.territory["treasury"], before)


class TestTerritorySaveRoundtrip(unittest.TestCase):
    def test_territory_survives_save(self):
        mgr, p = _make_manager()
        mgr.claim("qingyun_lingmai")
        mgr.build_mgr.place(p.territory, 0, 0, "guard_tower")
        # 模拟存档保存与读取
        saved = p.to_dict()
        restored = Player.from_dict(saved, p.item_library)
        self.assertIsNotNone(restored.territory)
        self.assertEqual(restored.territory["territory_id"], "qingyun_lingmai")
        self.assertIsNotNone(restored.territory["grid"]["cells"][0][0])
        # 旧存档无 territory 字段时为 None（向后兼容）
        legacy = p.to_dict()
        del legacy["territory"]
        restored_legacy = Player.from_dict(legacy, p.item_library)
        self.assertIsNone(restored_legacy.territory)


if __name__ == "__main__":
    unittest.main()
