# -*- coding: utf-8 -*-
"""事件池内容完整性测试：结构、唯一性、物品引用、抽取可达。"""
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from game.events import EventPool

CFG = "config"
VALID_EFFECT_KEYS = {"qi", "health", "item", "item_count"}


def _load_items():
    with open(os.path.join(CFG, "items.json"), encoding="utf-8") as f:
        data = json.load(f)
    items = data if isinstance(data, list) else data.get("items", [])
    return {i["id"] for i in items if isinstance(i, dict) and i.get("id")}


class TestEventsContent(unittest.TestCase):
    """config/events.json 结构与引用完整性。"""

    @classmethod
    def setUpClass(cls):
        with open(os.path.join(CFG, "events.json"), encoding="utf-8") as f:
            cls.events = json.load(f)
        cls.pool = EventPool(config_dir=CFG)
        cls.item_ids = _load_items()

    def test_minimum_size(self):
        self.assertGreaterEqual(len(self.events), 30)  # 内容池不宜太薄

    def test_ids_unique(self):
        ids = [e["id"] for e in self.events]
        self.assertEqual(len(ids), len(set(ids)))

    def test_required_fields(self):
        for e in self.events:
            self.assertIn("id", e)
            self.assertIn("name", e)
            self.assertIn("description", e)
            self.assertIn("weight", e)
            self.assertGreater(e["weight"], 0)

    def test_conditions_explore(self):
        """引擎只按 explore 条件抽取，所有事件必须匹配。"""
        for e in self.events:
            self.assertEqual(e["condition"], "explore", e["id"])

    def test_effect_keys_valid(self):
        for e in self.events:
            for key in (e.get("effects") or {}):
                self.assertIn(key, VALID_EFFECT_KEYS, f"{e['id']}: {key}")

    def test_item_refs_exist(self):
        for e in self.events:
            item = (e.get("effects") or {}).get("item")
            if item:
                self.assertIn(item, self.item_ids, e["id"])

    def test_trigger_flags_bool(self):
        for e in self.events:
            for flag in ("trigger_combat", "trigger_merchant", "trigger_secret_realm"):
                if flag in e:
                    self.assertIsInstance(e[flag], bool, e["id"])

    def test_all_events_reachable(self):
        """3000 次抽取应覆盖全部事件（低权重事件也可达）。"""
        counts = set()
        for _ in range(3000):
            counts.add(self.pool.draw("explore")["id"])
        all_ids = {e["id"] for e in self.events}
        self.assertEqual(counts, all_ids)

    def test_location_weights_reference_valid_events(self):
        """所有地点 event_weights 的键必须是已存在的事件 id。"""
        with open(os.path.join(CFG, "locations.json"), encoding="utf-8") as f:
            locs = json.load(f)
        locs = locs if isinstance(locs, list) else locs.get("locations", [])
        all_ids = {e["id"] for e in self.events}
        for loc in locs:
            for event_id in (loc.get("event_weights") or {}):
                self.assertIn(
                    event_id, all_ids,
                    f"地点 {loc.get('id')} 引用了不存在的事件 {event_id}",
                )

    def test_location_weights_complete(self):
        """每个地点应为全部事件配置权重（避免新事件在各地点频率雷同）。"""
        with open(os.path.join(CFG, "locations.json"), encoding="utf-8") as f:
            locs = json.load(f)
        locs = locs if isinstance(locs, list) else locs.get("locations", [])
        all_ids = {e["id"] for e in self.events}
        for loc in locs:
            covered = set(loc.get("event_weights") or {})
            missing = all_ids - covered
            self.assertFalse(
                missing,
                f"地点 {loc.get('id')} 缺少事件权重: {sorted(missing)}",
            )


class TestEventDedup(unittest.TestCase):
    """去重窗口：避免连续抽出同一事件。"""

    def setUp(self):
        self.pool = EventPool(config_dir=CFG)

    def test_recent_window_no_immediate_repeat(self):
        """候选充足时，连续 5 次抽取互不重复。"""
        ids = [self.pool.draw("explore")["id"] for _ in range(5)]
        self.assertEqual(len(ids), len(set(ids)))

    def test_window_slides_allow_repeat_later(self):
        """窗口滑动：事件滑出窗口后可再次出现（用大权重保证确定性）。"""
        first = self.pool.draw("explore")["id"]
        # 模拟 first 已滑出窗口：清空并塞入 5 个其他事件 id
        self.pool._recent.clear()
        others = [e["id"] for e in self.pool.events if e["id"] != first]
        self.pool._recent.extend(others[:5])
        # 把 first 权重调大 → 必然可被抽中（证明滑出窗口后可重复）
        self.pool.event_map[first]["weight"] = 10000
        picked = self.pool.draw("explore")["id"]
        self.assertEqual(picked, first)

    def test_no_dedup_when_disabled(self):
        """avoid_recent=False 保持纯随机行为（50 次内必有重复）。"""
        ids = [self.pool.draw("explore", avoid_recent=False)["id"] for _ in range(50)]
        self.assertLess(len(set(ids)), 50)

    def test_single_event_pool_fallback(self):
        """候选只剩 1 个时回退全候选，不返回 None。"""
        from game.events import EventPool as EP
        pool = EP.__new__(EP)  # 跳过 __init__，手工构造单事件池
        pool.events = [{"id": "only_one", "condition": "explore", "weight": 10}]
        pool.event_map = {e["id"]: e for e in pool.events}
        pool._recent = __import__("collections").deque(maxlen=5)
        for _ in range(3):
            self.assertEqual(pool.draw("explore")["id"], "only_one")


if __name__ == "__main__":
    unittest.main()
