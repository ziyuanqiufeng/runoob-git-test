# -*- coding: utf-8 -*-
"""事件文案厚度测试（2026-10-30）。

覆盖三层：
1. 数据层：events.json 每个事件都有 2 条以上 descriptions 变体，
   长度在 40~140 字之间，同事件变体不重复。
2. 描写池层：story_flavors.json 的 opener/environment/state/closer
   池子规模守门（防止未来被误改回小池子，复读感回归）。
3. 行为层：StoryGenerator.pick_description 优先取变体、无变体回退
   description；Engine._apply_event 在 AI 动态剧情关闭时也取变体，
   且不污染 EventPool 缓存的配置对象。
"""
import json
import os
import random
import sys
import unittest
from unittest.mock import patch

from PySide6.QtWidgets import QApplication

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from game.player import Player
from game.world import World
from game.events import EventPool
from game.item import ItemLibrary
from game.enemy import EnemyLibrary
from game.skill import SkillLibrary
from game.npc import NPCLibrary
from game.quest import QuestLibrary
from game.engine import GameEngine
from game.save_manager import SaveManager
from game.story_generator import StoryGenerator

CONFIG_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config")
MIN_VARIANTS = 2
MIN_LEN = 40
MAX_LEN = 140


def _load_events():
    with open(os.path.join(CONFIG_DIR, "events.json"), "r", encoding="utf-8") as f:
        return json.load(f)


def _load_flavors():
    with open(os.path.join(CONFIG_DIR, "story_flavors.json"), "r", encoding="utf-8") as f:
        return json.load(f)


class TestEventTextData(unittest.TestCase):
    """events.json 文案数据守门。"""

    def setUp(self):
        self.events = _load_events()

    def test_every_event_has_variants(self):
        """每个事件都必须有至少 MIN_VARIANTS 条 descriptions 变体。"""
        missing = [
            e["id"] for e in self.events
            if len(e.get("descriptions") or []) < MIN_VARIANTS
        ]
        self.assertEqual([], missing, f"以下事件变体不足：{missing}")

    def test_variant_length_in_range(self):
        """变体长度须落在 40~140 字，防止灌水或截断。"""
        bad = []
        for e in self.events:
            for idx, text in enumerate(e.get("descriptions") or []):
                if not (MIN_LEN <= len(text) <= MAX_LEN):
                    bad.append(f"{e['id']}[{idx}]={len(text)}")
        self.assertEqual([], bad, f"变体长度越界：{bad}")

    def test_variants_not_duplicated(self):
        """同一事件的多条变体不得完全重复。"""
        dup = []
        for e in self.events:
            texts = e.get("descriptions") or []
            if len(set(texts)) != len(texts):
                dup.append(e["id"])
        self.assertEqual([], dup, f"变体重复：{dup}")

    def test_legacy_description_kept(self):
        """旧 description 字段必须保留（旧存档/AI 提示词兼容）。"""
        missing = [e["id"] for e in self.events if not e.get("description")]
        self.assertEqual([], missing, f"缺少 description：{missing}")

    def test_variants_differ_from_legacy_description(self):
        """变体应为扩写文本，不得原样照抄旧 description。"""
        same = []
        for e in self.events:
            legacy = e.get("description", "")
            if legacy and legacy in (e.get("descriptions") or []):
                same.append(e["id"])
        self.assertEqual([], same, f"变体与旧文案相同：{same}")


class TestStoryFlavorScale(unittest.TestCase):
    """描写池规模守门（池子太小会让重复游历立刻露馅）。"""

    def setUp(self):
        self.data = _load_flavors()

    def test_opener_and_closer_pool(self):
        self.assertGreaterEqual(len(self.data.get("openers", [])), 12)
        self.assertGreaterEqual(len(self.data.get("closers", [])), 8)

    def test_environment_pool_per_type(self):
        envs = self.data.get("environments", {})
        for loc_type in ("city", "sect", "wild"):
            self.assertGreaterEqual(
                len(envs.get(loc_type, [])), 6,
                f"{loc_type} 环境描写不足 6 条",
            )

    def test_state_pool_per_key(self):
        states = self.data.get("states", {})
        keys = (
            "heart_demon_high", "heart_demon_low", "red_dust_bonded",
            "heaven_gaze_high", "righteous", "demonic",
        )
        for key in keys:
            self.assertGreaterEqual(
                len(states.get(key, [])), 4, f"{key} 心境描写不足 4 条",
            )


class TestPickDescription(unittest.TestCase):
    """StoryGenerator.pick_description 行为。"""

    def setUp(self):
        self.gen = StoryGenerator(config_dir=CONFIG_DIR)

    def test_prefers_variants(self):
        event = {"description": "旧文案", "descriptions": ["变体甲", "变体乙"]}
        seen = set()
        rng = random.Random(0)
        for _ in range(40):
            seen.add(self.gen.pick_description(event, rng))
        self.assertEqual({"变体甲", "变体乙"}, seen)
        self.assertNotIn("旧文案", seen)

    def test_fallback_to_legacy_description(self):
        self.assertEqual("旧文案", self.gen.pick_description({"description": "旧文案"}))

    def test_empty_variants_fallback(self):
        event = {"description": "旧文案", "descriptions": []}
        self.assertEqual("旧文案", self.gen.pick_description(event))

    def test_render_event_uses_variant(self):
        event = {"description": "旧文案", "descriptions": ["变体甲", "变体乙"]}
        text = self.gen.render_event(
            event, Player(name="测试"), {"type": "wild"}, rng=random.Random(3)
        )
        self.assertTrue(("变体甲" in text) or ("变体乙" in text))
        self.assertNotIn("旧文案", text)

    def test_rendered_text_varies_across_runs(self):
        """同一事件连续渲染应出现不同文本（变体 + 描写池共同作用）。"""
        event = {"description": "旧文案", "descriptions": ["变体甲", "变体乙"]}
        player = Player(name="测试")
        texts = {
            self.gen.render_event(event, player, {"type": "wild"}, rng=random.Random(i))
            for i in range(12)
        }
        self.assertGreater(len(texts), 1, "连续渲染文本完全一致，变体机制失效")


class TestApplyEventUsesVariant(unittest.TestCase):
    """Engine._apply_event 的文案落点（AI 开关两种形态）。"""

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.player = Player(name="测试修士")
        self.save_path = "test_event_texts_save.json"
        self.engine = GameEngine(
            self.player,
            World(config_dir=CONFIG_DIR),
            EventPool(config_dir=CONFIG_DIR),
            ItemLibrary(config_dir=CONFIG_DIR),
            EnemyLibrary(config_dir=CONFIG_DIR),
            SkillLibrary(config_dir=CONFIG_DIR),
            NPCLibrary(config_dir=CONFIG_DIR),
            QuestLibrary(config_dir=CONFIG_DIR),
            save_manager=SaveManager(save_path=self.save_path),
        )
        self.location = {"name": "测试荒山", "type": "wild"}

    def tearDown(self):
        if os.path.exists(self.save_path):
            os.remove(self.save_path)

    def _event(self):
        return {
            "id": "find_herb",
            "name": "灵草奇遇",
            "description": "旧文案",
            "descriptions": ["变体甲内容", "变体乙内容"],
            "effects": {"qi": 10},
        }

    def _run_apply(self):
        logs = []
        with patch.object(self.engine, "notify", side_effect=logs.append):
            self.engine._apply_event(self._event(), self.location)
        return "\n".join(str(x) for x in logs)

    def _set_flag(self, flag, enabled):
        """只改内存开关，不落盘——set_feature_flag 会写真实 feature_flags.json，
        测试若用它会把默认开关改掉，污染此后所有会话（本项目已踩过一次）。"""
        self.engine._feature_flags[flag] = bool(enabled)

    def test_ai_off_uses_variant(self):
        """ai_dynamic_event 关闭时仍取变体，不显示旧文案。"""
        self._set_flag("ai_dynamic_event", False)
        joined = self._run_apply()
        self.assertIn("灵草奇遇", joined)
        self.assertTrue(("变体甲内容" in joined) or ("变体乙内容" in joined))
        self.assertNotIn("旧文案", joined)

    def test_ai_on_renders_with_flavor_and_variant(self):
        """ai_dynamic_event 开启时文案含变体与环境描写（比旧文案更厚）。"""
        self._set_flag("ai_dynamic_event", True)
        self._set_flag("ai_llm_story", False)
        joined = self._run_apply()
        self.assertTrue(("变体甲内容" in joined) or ("变体乙内容" in joined))
        self.assertGreater(len(joined), len("【灵草奇遇】" + "旧文案"))

    def test_event_dict_not_polluted(self):
        """_apply_event 不得把渲染结果写回配置对象（否则变体只生效一次）。"""
        self._set_flag("ai_dynamic_event", True)
        self._set_flag("ai_llm_story", False)
        event = self._event()
        with patch.object(self.engine, "notify", side_effect=lambda *a, **k: None):
            self.engine._apply_event(event, self.location)
        self.assertEqual("旧文案", event["description"])
        self.assertEqual(["变体甲内容", "变体乙内容"], event["descriptions"])


if __name__ == "__main__":
    unittest.main()
