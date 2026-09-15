# -*- coding: utf-8 -*-
"""城池政策与城主竞选系统单元测试。"""
import unittest
from unittest.mock import MagicMock

from game.player import Player
from game.city_policy_manager import CityPolicyManager, CityPolicyConfig


class FakeWorld:
    """用于测试的简易世界对象。"""

    def __init__(self, year=1, month=1):
        self.year = year
        self.month = month


class TestCityPolicyManager(unittest.TestCase):
    """测试城主竞选、政策颁布与每月推进逻辑。"""

    def setUp(self):
        self.player = Player(name="测试城主")
        self.player.world = FakeWorld(year=1, month=1)
        self.city_id = "fufeng_city"
        self.player.city_reputation[self.city_id] = 500
        # 给玩家足够灵石
        from game.item import ItemLibrary
        self.item_lib = ItemLibrary(config_dir="config")
        for _ in range(10000):
            self.player.add_item(self.item_lib.create("spirit_stone"))
        self.manager = CityPolicyManager(self.player, self.city_id)

    def test_not_mayor_by_default(self):
        """初始状态不应是城主。"""
        self.assertFalse(self.manager.is_mayor())

    def test_can_campaign_meets_requirements(self):
        """满足声望与灵石要求时应可竞选。"""
        ok, msg = self.manager.can_campaign()
        self.assertTrue(ok, msg)

    def test_campaign_success_sets_mayor(self):
        """强制竞选成功后应标记为城主。"""
        import random
        random.seed(1)
        ok, msg = self.manager.campaign()
        self.assertTrue(ok, msg)
        self.assertTrue(self.manager.is_mayor())
        self.assertGreater(self.manager.get_mayor_until_month(), 0)

    def test_only_mayor_can_enact_policy(self):
        """非城主不能颁布政策。"""
        ok, msg = self.manager.enact_policy("encourage_cultivation")
        self.assertFalse(ok)
        self.assertIn("城主", msg)

    def test_enact_policy_as_mayor(self):
        """城主满足条件时可颁布政策。"""
        self._make_mayor()
        ok, msg = self.manager.enact_policy("encourage_cultivation")
        self.assertTrue(ok, msg)
        self.assertEqual(len(self.manager.get_active_policies()), 1)
        self.assertEqual(
            self.manager.get_policy_effect("cultivation_speed_bonus"), 0.1
        )

    def test_enact_policy_cost_deducted(self):
        """颁布政策应扣除灵石与声望。"""
        self._make_mayor()
        before_stone = self.player.count_item("spirit_stone")
        before_rep = self.player.city_reputation[self.city_id]
        self.manager.enact_policy("encourage_cultivation")
        self.assertEqual(
            self.player.count_item("spirit_stone"),
            before_stone - 3000
        )
        self.assertEqual(
            self.player.city_reputation[self.city_id],
            before_rep - 100
        )

    def test_max_active_policies_limit(self):
        """超过同时生效政策上限后不能再颁布。"""
        self._make_mayor()
        # 依次颁布 3 个不同政策
        self.manager.enact_policy("encourage_cultivation")
        self.manager.enact_policy("market_tax_cut")
        self.manager.enact_policy("defense_drill")
        ok, msg = self.manager.enact_policy("alchemy_subsidy")
        self.assertFalse(ok)
        self.assertIn("不能超过", msg)

    def test_tick_monthly_expires_policy(self):
        """政策持续月数到期后应自动移除。"""
        self._make_mayor()
        self.manager.enact_policy("encourage_cultivation")
        # 推进 6 个月
        for _ in range(6):
            expired = self.manager.tick_monthly()
        self.assertEqual(len(self.manager.get_active_policies()), 0)
        self.assertIn("鼓励修炼", expired)

    def test_cannot_enact_duplicate_policy(self):
        """同一政策已生效时不能重复颁布。"""
        self._make_mayor()
        self.manager.enact_policy("encourage_cultivation")
        ok, msg = self.manager.enact_policy("encourage_cultivation")
        self.assertFalse(ok)
        self.assertIn("已生效", msg)

    def _make_mayor(self):
        """辅助方法：直接设置玩家为城主。"""
        state = self.player.city_policies[self.city_id]
        state["mayor_until"] = self.player.world.year * 12 + self.player.world.month + 24


if __name__ == "__main__":
    unittest.main()
