# -*- coding: utf-8 -*-
"""存档兼容性专项：旧档缺新字段时的默认值 / 全量往返 / 转世兼容。

背景：v1.0.0 → v1.1.0 期间新增了 6 个持久化字段
（trial_tower_best / meta_collection / npc_quests / pending_start_items /
hostile_factions / game_mode / mode_opening_done / past_bond），
旧存档载入必须无异常且取合理默认值。
"""
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from game.player import Player
from game.item import ItemLibrary


def _lib():
    return ItemLibrary(config_dir="config")


# 一份"远古存档"：只含 v1.0.0 之前就有的核心字段
LEGACY_SAVE = {
    "name": "旧档道友",
    "save_version": 1,
    "realm_id": "qi_refining_1",
    "qi": 100,
    "health": 80,
    "max_health": 100,
    "karma": 0,
    "reincarnation_count": 1,
    "npc_relationships": {},
    "chronicle": [],
}


class TestLegacySaveCompat(unittest.TestCase):

    def test_legacy_load_no_error(self):
        p = Player.from_dict(dict(LEGACY_SAVE), _lib())
        self.assertEqual(p.name, "旧档道友")
        # 新字段全部取默认值
        self.assertEqual(p.trial_tower_best, 0)
        self.assertEqual(p.meta_collection, {"endings": [], "npcs": []})
        self.assertEqual(p.npc_quests, {})
        self.assertEqual(p.pending_start_items, [])
        self.assertEqual(p.hostile_factions, [])
        self.assertEqual(p.game_mode, "standard")
        self.assertFalse(p.mode_opening_done)
        self.assertIsNone(p.past_bond)

    def test_roundtrip_after_legacy_load(self):
        """旧档载入 → to_dict → 再载入，不丢失且新字段就位。"""
        p = Player.from_dict(dict(LEGACY_SAVE), _lib())
        p.trial_tower_best = 7
        p.npc_quests["npc_x"] = {"accepted": True, "done": False}
        d = p.to_dict()
        p2 = Player.from_dict(d, _lib())
        self.assertEqual(p2.trial_tower_best, 7)
        self.assertEqual(p2.npc_quests["npc_x"]["accepted"], True)

    def test_full_roundtrip_all_persisted_fields(self):
        """全字段往返：to_dict → from_dict → to_dict 深度相等。"""
        p = Player(name="往返道友")
        p.trial_tower_best = 5
        p.meta_collection = {"endings": ["ascend_immortal"], "npcs": ["npc_a"]}
        p.npc_quests = {"npc_a": {"accepted": True, "done": True, "type": "collect"}}
        p.hostile_factions = ["righteous"]
        p.game_mode = "heaven_cycle"
        p.mode_opening_done = True
        p.past_bond = {"npc_id": "npc_a", "name": "甲", "bond_type": "dao_lv",
                       "intimacy": 80}
        d1 = p.to_dict()
        p2 = Player.from_dict(d1, _lib())
        d2 = p2.to_dict()
        for key in ("trial_tower_best", "meta_collection", "npc_quests",
                    "hostile_factions", "game_mode", "mode_opening_done",
                    "past_bond"):
            self.assertEqual(d1[key], d2[key], f"字段 {key} 往返不一致")

    def test_partial_new_fields(self):
        """部分新字段存在、部分缺失（中间版本存档）也要兼容。"""
        data = dict(LEGACY_SAVE)
        data["trial_tower_best"] = 12
        data["game_mode"] = "demonic_lone"
        p = Player.from_dict(data, _lib())
        self.assertEqual(p.trial_tower_best, 12)
        self.assertEqual(p.game_mode, "demonic_lone")
        self.assertEqual(p.meta_collection, {"endings": [], "npcs": []})

    def test_legacy_with_pending_start_items(self):
        """旧档带 pending 未发放物品：载入后仍可发放。"""
        data = dict(LEGACY_SAVE)
        data["pending_start_items"] = ["spirit_stone"]
        p = Player.from_dict(data, _lib())
        self.assertEqual(p.pending_start_items, ["spirit_stone"])


if __name__ == "__main__":
    unittest.main()
