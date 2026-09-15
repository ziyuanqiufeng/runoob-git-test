# -*- coding: utf-8 -*-
"""洞府租赁与闭关修炼系统测试。"""
import unittest

from game.player import Player
from game.item import ItemLibrary
from game.cave_manager import CaveManager, CaveConfig


class TestCaveConfig(unittest.TestCase):
    """洞府配置加载测试。"""

    def test_load_caves(self):
        """应能加载所有洞府配置。"""
        config = CaveConfig(config_dir="config")
        self.assertTrue(len(config.caves) > 0)
        # 扶风城至少有两个洞府
        fufeng_caves = config.get_caves_by_location("fufeng_city")
        self.assertEqual(len(fufeng_caves), 2)

    def test_get_cave_by_id(self):
        """按 ID 获取洞府配置。"""
        config = CaveConfig(config_dir="config")
        cave = config.get_cave("fufeng_ling_cave")
        self.assertIsNotNone(cave)
        self.assertEqual(cave["location_id"], "fufeng_city")
        self.assertIn("closed_door_qi_bonus", cave["effects"])


class TestCaveManagerRent(unittest.TestCase):
    """洞府租赁逻辑测试。"""

    def setUp(self):
        self.player = Player(name="测试修士")
        self.item_lib = ItemLibrary(config_dir="config")
        # 给玩家充足灵石
        for _ in range(2000):
            self.player.add_item(self.item_lib.create("spirit_stone"))
        self.manager = CaveManager(self.player)

    def test_can_rent_with_enough_money(self):
        """灵石充足时应可租赁。"""
        ok, msg = self.manager.can_rent("fufeng_inn_cave", 3)
        self.assertTrue(ok)
        self.assertEqual(msg, "")

    def test_can_rent_without_enough_money(self):
        """灵石不足时应返回失败。"""
        poor_player = Player(name="穷修士")
        manager = CaveManager(poor_player)
        ok, msg = manager.can_rent("fufeng_inn_cave", 1)
        self.assertFalse(ok)
        self.assertIn("灵石不足", msg)

    def test_can_rent_exceed_max_months(self):
        """租赁总月数超过上限时应失败。"""
        ok, msg = self.manager.can_rent("fufeng_inn_cave", 13)
        self.assertFalse(ok)
        self.assertIn("不能超过", msg)

    def test_rent_cave_deducts_money(self):
        """租赁成功后应扣除灵石并增加租期。"""
        before = self.player.count_item("spirit_stone")
        ok, msg = self.manager.rent_cave("fufeng_inn_cave", 3)
        self.assertTrue(ok)
        self.assertEqual(self.player.count_item("spirit_stone"), before - 900)
        lease = self.manager.get_current_lease("fufeng_inn_cave")
        self.assertEqual(lease["remaining_months"], 3)

    def test_rent_same_cave_accumulates(self):
        """多次租赁同一洞府，租期应累加。"""
        self.manager.rent_cave("fufeng_inn_cave", 3)
        self.manager.rent_cave("fufeng_inn_cave", 2)
        lease = self.manager.get_current_lease("fufeng_inn_cave")
        self.assertEqual(lease["remaining_months"], 5)


class TestCaveManagerClosedDoor(unittest.TestCase):
    """闭关修炼逻辑测试。"""

    def setUp(self):
        self.player = Player(name="测试修士")
        self.item_lib = ItemLibrary(config_dir="config")
        for _ in range(2000):
            self.player.add_item(self.item_lib.create("spirit_stone"))
        self.manager = CaveManager(self.player)
        self.manager.rent_cave("fufeng_inn_cave", 6)

    def test_can_start_closed_door_after_rent(self):
        """租赁后应可开始闭关。"""
        ok, msg = self.manager.can_start_closed_door("fufeng_inn_cave", 3)
        self.assertTrue(ok)
        self.assertEqual(msg, "")

    def test_cannot_start_without_lease(self):
        """未租赁的洞府不能闭关。"""
        ok, msg = self.manager.can_start_closed_door("fufeng_ling_cave", 1)
        self.assertFalse(ok)
        self.assertIn("尚未租赁", msg)

    def test_cannot_start_longer_than_lease(self):
        """闭关月数不能超过剩余租期。"""
        ok, msg = self.manager.can_start_closed_door("fufeng_inn_cave", 12)
        self.assertFalse(ok)
        self.assertIn("剩余租期不足", msg)

    def test_start_closed_door_sets_state(self):
        """开始闭关后应设置剩余月数和洞府 ID。"""
        ok, msg, expected = self.manager.start_closed_door("fufeng_inn_cave", 3)
        self.assertTrue(ok)
        self.assertEqual(self.player.closed_door_remaining, 3)
        self.assertEqual(self.player.closed_door_cave_id, "fufeng_inn_cave")
        self.assertGreater(expected, 0)

    def test_tick_closed_door_gains_qi(self):
        """推进闭关一个月应增加修为并减少剩余月数。"""
        self.manager.start_closed_door("fufeng_inn_cave", 3)
        before_qi = self.player.qi
        qi_gain = self.manager.tick_closed_door()
        self.assertGreater(qi_gain, 0)
        self.assertEqual(self.player.qi, before_qi + qi_gain)
        self.assertEqual(self.player.closed_door_remaining, 2)

    def test_tick_closed_door_consumes_lease(self):
        """推进闭关同时消耗洞府租期。"""
        self.manager.start_closed_door("fufeng_inn_cave", 3)
        lease = self.manager.get_current_lease("fufeng_inn_cave")
        before = lease["remaining_months"]
        self.manager.tick_closed_door()
        self.assertEqual(lease["remaining_months"], before - 1)

    def test_cannot_start_when_already_in_closed_door(self):
        """已在闭关中时不能再开启新闭关。"""
        self.manager.start_closed_door("fufeng_inn_cave", 2)
        ok, msg, _ = self.manager.start_closed_door("fufeng_inn_cave", 1)
        self.assertFalse(ok)
        self.assertIn("已在闭关中", msg)

    def test_is_in_closed_door(self):
        """is_in_closed_door 应正确反映闭关状态。"""
        self.assertFalse(self.manager.is_in_closed_door())
        self.manager.start_closed_door("fufeng_inn_cave", 2)
        self.assertTrue(self.manager.is_in_closed_door())


class TestCaveManagerMonthlyTick(unittest.TestCase):
    """洞府每月推进测试。"""

    def setUp(self):
        self.player = Player(name="测试修士")
        self.item_lib = ItemLibrary(config_dir="config")
        for _ in range(2000):
            self.player.add_item(self.item_lib.create("spirit_stone"))
        self.manager = CaveManager(self.player)
        self.manager.rent_cave("fufeng_inn_cave", 2)

    def test_tick_monthly_reduces_lease(self):
        """非闭关期间每月推进应减少租期。"""
        expired = self.manager.tick_monthly()
        lease = self.manager.get_current_lease("fufeng_inn_cave")
        self.assertEqual(lease["remaining_months"], 1)
        self.assertEqual(len(expired), 0)

    def test_tick_monthly_expires_lease(self):
        """租期到期后应返回到期洞府名称并移除租约。"""
        self.manager.tick_monthly()
        expired = self.manager.tick_monthly()
        self.assertEqual(len(expired), 1)
        self.assertIn("扶风城郊静室", expired)
        self.assertIsNone(self.manager.get_current_lease("fufeng_inn_cave"))

    def test_tick_monthly_does_not_double_consume_during_closed_door(self):
        """闭关期间租期已在 tick_closed_door 扣除，tick_monthly 不应重复扣除。"""
        self.manager.start_closed_door("fufeng_inn_cave", 2)
        self.manager.tick_closed_door()  # 租期从 2 变为 1
        lease = self.manager.get_current_lease("fufeng_inn_cave")
        self.assertEqual(lease["remaining_months"], 1)
        # 月度推进不应再扣
        self.manager.tick_monthly()
        self.assertEqual(lease["remaining_months"], 1)


class TestCaveManagerCultivationBonus(unittest.TestCase):
    """修炼加成测试。"""

    def setUp(self):
        self.player = Player(name="测试修士")
        self.item_lib = ItemLibrary(config_dir="config")
        for _ in range(2000):
            self.player.add_item(self.item_lib.create("spirit_stone"))
        self.manager = CaveManager(self.player)

    def test_get_cultivation_bonus(self):
        """租赁洞府后应获得修炼速度加成。"""
        self.assertEqual(self.manager.get_cultivation_bonus(), 0)
        self.manager.rent_cave("fufeng_inn_cave", 1)
        bonus = self.manager.get_cultivation_bonus()
        self.assertAlmostEqual(bonus, 0.05, places=5)

    def test_cultivation_bonus_excludes_expired(self):
        """过期租约不应再提供加成。"""
        self.manager.rent_cave("fufeng_inn_cave", 1)
        lease = self.manager.get_current_lease("fufeng_inn_cave")
        lease["remaining_months"] = 0
        self.assertEqual(self.manager.get_cultivation_bonus(), 0)


if __name__ == "__main__":
    unittest.main()
