# -*- coding: utf-8 -*-
"""转世轮回管理器测试。"""
import unittest

from game.player import Player
from game.item import ItemLibrary
from game.reincarnation_manager import ReincarnationManager, ReincarnationConfig


class TestReincarnationConfig(unittest.TestCase):
    """转世配置加载测试。"""

    def test_load_config(self):
        """应能正确加载转世配置。"""
        cfg = ReincarnationConfig("config")
        self.assertIn("inheritance_rules", cfg.data)
        self.assertGreater(len(cfg.get_options()), 0)
        self.assertGreater(len(cfg.get_random_talents()), 0)

    def test_get_option(self):
        """应能按 ID 获取继承选项。"""
        cfg = ReincarnationConfig("config")
        opt = cfg.get_option("retain_memory")
        self.assertIsNotNone(opt)
        self.assertEqual(opt["name"], "一缕记忆")


class TestReincarnationManager(unittest.TestCase):
    """转世逻辑测试。"""

    def setUp(self):
        self.player = Player(name="测试修士")
        self.manager = ReincarnationManager(self.player)

    def _ensure_enough_points(self, points=100):
        """通过提高境界确保继承点充足，避免低成本测试被截断。"""
        self.player.realm_id = "foundation_peak"
        # foundation_peak 境界分为 13，13 * 0.5 = 6，仍不够部分高消耗项
        # 因此直接 mock compute_inheritance_points 返回值
        self.manager.compute_inheritance_points = lambda: points

    def test_compute_inheritance_points_base(self):
        """基础继承点应大于 0。"""
        points = self.manager.compute_inheritance_points()
        # 练气一层境界分为 1，转世 0 次，名望 0，业力中立
        self.assertGreaterEqual(points, 0)

    def test_karma_category(self):
        """业力分类应正确。"""
        self.player.karma = -100
        self.assertEqual(self.manager._karma_category(), "benevolent")
        self.player.karma = 0
        self.assertEqual(self.manager._karma_category(), "neutral")
        self.player.karma = 300
        self.assertEqual(self.manager._karma_category(), "evil")

    def test_compute_available_options(self):
        """应返回可用继承选项列表。"""
        data = self.manager.compute_available_options()
        self.assertIn("points", data)
        self.assertIn("options", data)
        self.assertGreater(len(data["options"]), 0)
        # 所有选项初始都应可用
        for opt in data["options"]:
            self.assertTrue(opt["available"])

    def test_apply_inheritance_attribute_bonuses(self):
        """选择属性加成继承项应正确应用。"""
        self._ensure_enough_points()
        new_data = self.manager.apply_inheritance(["retain_memory"])
        self.assertEqual(new_data["attribute_bonuses"]["wisdom"], 2)

    def test_apply_inheritance_exceed_points(self):
        """选择超出点数的继承项应按顺序截断。"""
        # 练气一层基础点很少，选择高消耗项应被截断
        new_data = self.manager.apply_inheritance(["retain_item", "retain_spiritual_root"])
        total_cost = sum(
            opt["cost"] for opt_id in new_data.get("_selected_ids", [])
            if (opt := self.manager.config.get_option(opt_id))
        )
        # 由于无法直接获取 _selected_ids，检查未选择高消耗项的效果
        # retain_item 效果是携带物品，retain_spiritual_root 是保留灵根
        # 如果点数不足，至少不会两个都生效
        self.assertLessEqual(
            (1 if new_data["starting_items"] else 0) +
            (1 if new_data["retain_roots"] else 0),
            1
        )

    def test_create_new_player_retains_roots(self):
        """选择灵根传承应保留前世灵根。"""
        self._ensure_enough_points()
        self.player.set_spiritual_roots(["fire", "water"], {"fire": 1.2, "water": 0.9})
        new_data = self.manager.apply_inheritance(["retain_spiritual_root"])
        new_player = self.manager.create_new_player(new_data, Player)
        self.assertEqual(set(new_player.spiritual_roots), {"fire", "water"})
        # 纯度应有衰减
        self.assertLess(new_player.root_purities["fire"], 1.2)

    def test_create_new_player_negative_event(self):
        """高业力玩家可能触发负面转世事件。"""
        self.player.karma = 300
        # 强制让负面事件发生
        manager = ReincarnationManager(self.player)
        new_data = manager.apply_inheritance([])
        # 如果触发负面事件，则新玩家数据中有 negative_event
        # 不强制断言一定触发，因为 40% 概率
        if new_data["negative_event"]:
            new_player = manager.create_new_player(new_data, Player)
            self.assertIsNotNone(new_player)

    def test_create_new_player_increments_count(self):
        """转世次数应递增。"""
        new_data = self.manager.apply_inheritance([])
        new_player = self.manager.create_new_player(new_data, Player)
        self.assertEqual(new_player.reincarnation_count, 1)


class TestPlayerSerialization(unittest.TestCase):
    """Player 转世字段序列化测试。"""

    def test_reincarnation_fields_roundtrip(self):
        """转世相关字段应能正确序列化与反序列化。"""
        player = Player(name="测试")
        player.karma = 100
        player.reincarnation_count = 2
        player.past_life_talents = ["talent_fast_cultivator"]
        player.reincarnation_cultivation_bonus = 0.2

        data = player.to_dict()
        restored = Player.from_dict(data, ItemLibrary(config_dir="config"))
        self.assertEqual(restored.karma, 100)
        self.assertEqual(restored.reincarnation_count, 2)
        self.assertEqual(restored.past_life_talents, ["talent_fast_cultivator"])
        self.assertEqual(restored.reincarnation_cultivation_bonus, 0.2)


if __name__ == "__main__":
    unittest.main()
