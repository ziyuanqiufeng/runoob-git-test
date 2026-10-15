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


class TestRealmGatedEvents(unittest.TestCase):
    """终局专属事件：min_realm_order 境界门槛过滤。"""

    def _player(self, realm_id):
        from game.player import Player
        p = Player(name="测试")
        p.realm_id = realm_id
        return p

    def test_low_realm_excluded(self):
        """元婴玩家抽不到终局专属事件（order<19 全过滤）。"""
        pool = EventPool(config_dir=CFG)
        for _ in range(60):
            ev = pool.draw("explore", player=self._player("nascent_soul"))
            self.assertIsNotNone(ev)
            self.assertLess(ev.get("min_realm_order", 0), 19,
                            f"元婴不应抽到 {ev['id']}（min_realm_order=19+）")

    def test_high_realm_included(self):
        """炼虚圆满玩家候选池包含终局事件（draw 有概率抽中）。"""
        pool = EventPool(config_dir=CFG)
        seen = set()
        for _ in range(120):
            ev = pool.draw("explore", player=self._player("lianxu_peak"))
            if ev:
                seen.add(ev["id"])
        self.assertTrue(
            {"divine_soul_roam", "heaven_gate_echo", "void_refine"} & seen,
            "120 次抽取应至少命中一个终局专属事件")

    def test_gated_events_configured(self):
        """三个终局事件的 min_realm_order 配置正确。"""
        pool = EventPool(config_dir=CFG)
        expect = {"divine_soul_roam": 19, "heaven_gate_echo": 20, "void_refine": 21}
        for eid, order in expect.items():
            ev = pool.get_event(eid)
            self.assertIsNotNone(ev, eid)
            self.assertEqual(ev.get("min_realm_order"), order, eid)


class TestModeGatedEvents(unittest.TestCase):
    """周目模式专属事件：required_mode 过滤。"""

    def _player(self, mode):
        from game.player import Player
        p = Player(name="测试")
        p.game_mode = mode
        return p

    def test_standard_excluded(self):
        """standard 模式抽不到模式专属事件。"""
        pool = EventPool(config_dir=CFG)
        for _ in range(60):
            ev = pool.draw("explore", player=self._player("standard"))
            self.assertIsNotNone(ev)
            self.assertFalse(ev.get("required_mode"),
                             f"standard 不应抽到 {ev['id']}")

    def test_demonic_mode_hits(self):
        """魔道独行模式能抽中专属事件。"""
        pool = EventPool(config_dir=CFG)
        seen = set()
        for _ in range(150):
            ev = pool.draw("explore", player=self._player("demonic_lone"))
            if ev:
                seen.add(ev["id"])
        self.assertTrue(
            {"demonic_hunt", "demonic_bargain"} & seen,
            "150 次抽取应命中至少一个魔道专属事件")

    def test_mortal_mode_hits(self):
        """凡人挑战模式能抽中专属事件。"""
        pool = EventPool(config_dir=CFG)
        seen = set()
        for _ in range(150):
            ev = pool.draw("explore", player=self._player("mortal_challenge"))
            if ev:
                seen.add(ev["id"])
        self.assertIn("mortal_will", seen)
