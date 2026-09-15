# -*- coding: utf-8 -*-
"""修行年谱弹窗测试。"""
import os
import sys
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from PySide6.QtWidgets import QApplication, QTabWidget

app = QApplication.instance() or QApplication([])

from game.player import Player
from game.world import World
from game.chronicle import ChronicleManager
from game.events import EventPool
from game.item import ItemLibrary
from game.enemy import EnemyLibrary
from game.skill import SkillLibrary
from game.npc import NPCLibrary
from game.quest import QuestLibrary
from game.engine import GameEngine
from game.save_manager import SaveManager
from ui.career_dialog import CareerDialog


def _make_player_with_entries():
    player = Player(name="测试道友")
    world = World(config_dir="config")
    mgr = ChronicleManager(player, world)
    mgr.record("突破至【练气期三层】", category="breakthrough")
    mgr.record("达成成就：【初出茅庐】！", category="achievement")
    mgr.record("你在市集闲逛。", category="event")
    return player, world


class TestCareerDialog(unittest.TestCase):
    def test_entries_shown_newest_first(self):
        player, world = _make_player_with_entries()
        dlg = CareerDialog(player, world)
        self.assertEqual(dlg.list_widget.count(), 3)
        first = dlg.list_widget.item(0).text()
        # 最后记录的一条（市集闲逛）应排在最前
        self.assertIn("市集", first)

    def test_summary_label(self):
        player, world = _make_player_with_entries()
        dlg = CareerDialog(player, world)
        summary_label = dlg.layout().itemAt(0).widget()
        self.assertIsNotNone(summary_label)
        self.assertIn("3", summary_label.text())  # 摘要含总条数

    def test_empty_career_hint(self):
        player = Player(name="空")
        dlg = CareerDialog(player, World(config_dir="config"))
        self.assertEqual(dlg.list_widget.count(), 1)  # 仅提示行
        self.assertIn("尚无记录", dlg.list_widget.item(0).text())

    def test_category_rendering(self):
        player, world = _make_player_with_entries()
        dlg = CareerDialog(player, world)
        texts = [dlg.list_widget.item(i).text() for i in range(3)]
        joined = "\n".join(texts)
        self.assertIn("突破", joined)
        self.assertIn("修真第", joined)


class TestCareerMilestones(unittest.TestCase):
    """大事件自动进入年表（结局/成就埋点）。"""

    def _make_engine(self):
        import tempfile
        tmp = tempfile.mkdtemp()
        player = Player(name="测试道友")
        return GameEngine(
            player, World(config_dir="config"), EventPool(config_dir="config"),
            ItemLibrary(config_dir="config"), EnemyLibrary(config_dir="config"),
            SkillLibrary(config_dir="config"), NPCLibrary(config_dir="config"),
            QuestLibrary(config_dir="config"),
            save_manager=SaveManager(save_path=os.path.join(tmp, "s.json"),
                                     save_dir=os.path.join(tmp, "sv")),
        )

    def test_ending_recorded(self):
        engine = self._make_engine()
        with patch("game.engine.random.random", return_value=0.0):  # 飞升必成
            engine._attempt_ascension()
        cats = [(e["category"], e["text"]) for e in engine.player.chronicle]
        self.assertTrue(any(c == "ending" and "飞升" in t for c, t in cats))

    def test_achievement_recorded(self):
        engine = self._make_engine()
        with patch.object(engine, "achievement_manager") as mock_am, \
             patch("game.engine.random.random", return_value=0.0):
            mock_am.check.return_value = [("a1", "初出茅庐")]
            engine.player.realm_id = "qi_refining_9"
            engine.player.qi = 10 ** 9
            engine.breakthrough()
        cats = [(e["category"], e["text"]) for e in engine.player.chronicle]
        self.assertTrue(any(c == "achievement" and "初出茅庐" in t for c, t in cats))


if __name__ == "__main__":
    unittest.main()
