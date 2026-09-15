# -*- coding: utf-8 -*-
"""RealmCardManager 单元测试（F-03 增益卡）。"""
import random
import unittest

from game.realm_card import RealmCardManager, parse_mod_value


class TestRealmCard(unittest.TestCase):
    def test_parse_mod_value(self):
        self.assertEqual(parse_mod_value("+30%"), ("pct", 0.3))
        self.assertEqual(parse_mod_value("-10%"), ("pct", -0.1))
        self.assertEqual(parse_mod_value("+50"), ("flat", 50.0))

    def test_draw_distinct(self):
        mgr = RealmCardManager("config")
        draws = mgr.draw(3, rng=random.Random(1))
        self.assertEqual(len(draws), 3)
        ids = [c["id"] for c in draws]
        self.assertEqual(len(set(ids)), 3)

    def test_draw_respects_count(self):
        mgr = RealmCardManager("config")
        draws = mgr.draw(99, rng=random.Random(2))
        # 不会超过卡池总数
        self.assertLessEqual(len(draws), len(mgr.all()))

    def test_aggregate_no_style(self):
        mgr = RealmCardManager("config")
        owned = [
            {"card_id": "iron_body", "stacks": 1},
            {"card_id": "vigor_heart", "stacks": 2},
        ]
        mods = mgr.aggregate(owned, player_path="fa")
        self.assertAlmostEqual(mods["defense_pct"], 0.2)
        self.assertEqual(mods["max_hp_flat"], 100)

    def test_aggregate_style_filter(self):
        mgr = RealmCardManager("config")
        owned = [{"card_id": "sword_intent_surge", "stacks": 2}]  # apply_to jian
        # 非剑修不生效
        self.assertEqual(mgr.aggregate(owned, player_path="fa")["attack_pct"], 0.0)
        # 剑修生效：0.3 * 2
        self.assertAlmostEqual(
            mgr.aggregate(owned, player_path="jian")["attack_pct"], 0.6
        )


if __name__ == "__main__":
    unittest.main()
