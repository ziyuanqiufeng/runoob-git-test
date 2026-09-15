# -*- coding: utf-8 -*-
"""AI 动态剧情异步化测试：离线秒渲染 + pending 上下文 + 后台 worker。"""
import os
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from PySide6.QtWidgets import QApplication

app = QApplication.instance() or QApplication([])

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
from ui.main_window import _AIStoryWorker

_EVENT = {"id": "find_herb", "name": "灵草奇遇",
          "description": "发现一株百年灵草", "effects": {"qi": 10}}
_LOCATION = {"type": "wild", "name": "青云山"}


def _make_engine():
    tmp = tempfile.mkdtemp()
    player = Player(name="测试道友")
    player.realm_id = "qi_refining_1"
    engine = GameEngine(
        player, World(config_dir="config"), EventPool(config_dir="config"),
        ItemLibrary(config_dir="config"), EnemyLibrary(config_dir="config"),
        SkillLibrary(config_dir="config"), NPCLibrary(config_dir="config"),
        QuestLibrary(config_dir="config"),
        save_manager=SaveManager(save_path=os.path.join(tmp, "s.json"),
                                 save_dir=os.path.join(tmp, "sv")),
    )
    return engine


class TestPendingAIEvent(unittest.TestCase):
    """_apply_event 的两段式：离线秒渲染 + pending 上下文。"""

    def setUp(self):
        self.engine = _make_engine()
        self.engine.player.location_id = "qingyun"

    def test_apply_sets_pending_and_notifies(self):
        flags = {"ai_dynamic_event": True, "ai_llm_story": True}
        with patch.object(self.engine, "is_feature_enabled",
                          side_effect=lambda k: flags.get(k, False)), \
             patch.object(self.engine, "notify") as mock_notify:
            self.engine._apply_event(dict(_EVENT), dict(_LOCATION))
        ctx = self.engine.pop_pending_ai_event()
        self.assertIsNotNone(ctx)
        self.assertEqual(ctx["event"]["id"], "find_herb")
        self.assertEqual(ctx["location"]["name"], "青云山")
        # 文案已用离线模板渲染（含事件描述，非原文）
        notified = [str(c.args[0]) for c in mock_notify.call_args_list]
        self.assertTrue(any("【灵草奇遇】" in n for n in notified))
        self.assertTrue(any("__AI_STORY_PENDING__" in n for n in notified))
        # pop 后清空
        self.assertIsNone(self.engine.pop_pending_ai_event())

    def test_llm_off_no_pending(self):
        flags = {"ai_dynamic_event": True, "ai_llm_story": False}
        with patch.object(self.engine, "is_feature_enabled",
                          side_effect=lambda k: flags.get(k, False)), \
             patch.object(self.engine, "notify"):
            self.engine._apply_event(dict(_EVENT), dict(_LOCATION))
        self.assertIsNone(self.engine.pop_pending_ai_event())

    def test_ai_dynamic_off_fixed_text(self):
        flags = {"ai_dynamic_event": False, "ai_llm_story": True}
        with patch.object(self.engine, "is_feature_enabled",
                          side_effect=lambda k: flags.get(k, False)), \
             patch.object(self.engine, "notify"):
            self.engine._apply_event(dict(_EVENT), dict(_LOCATION))
        self.assertIsNone(self.engine.pop_pending_ai_event())
        # qi 效果照常生效
        self.assertEqual(self.engine.player.qi, 10)


class TestAIStoryWorker(unittest.TestCase):
    """后台生成 worker 的成功/失败路径。"""

    def _engine_mock(self, result=None, raise_exc=False):
        engine = MagicMock()
        engine.world.get_realm.return_value = {"name": "炼气期一层"}
        if raise_exc:
            engine.ai_story_generator.generate_story.side_effect = Exception("网络错误")
        else:
            engine.ai_story_generator.generate_story.return_value = result
        return engine

    def test_worker_emits_generated_text(self):
        engine = self._engine_mock(result="荒陲偶逢玉芝。")
        results = []
        worker = _AIStoryWorker(engine, {"event": _EVENT, "location": _LOCATION})
        worker.signals.finished.connect(results.append)
        worker.run()
        self.assertEqual(results, ["荒陲偶逢玉芝。"])

    def test_worker_failure_emits_empty(self):
        engine = self._engine_mock(raise_exc=True)
        results = []
        worker = _AIStoryWorker(engine, {"event": _EVENT, "location": _LOCATION})
        worker.signals.finished.connect(results.append)
        worker.run()
        self.assertEqual(results, [""])


if __name__ == "__main__":
    unittest.main()
