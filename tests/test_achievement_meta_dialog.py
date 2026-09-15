# -*- coding: utf-8 -*-
"""F-06 / F-07 弹窗冒烟测试（无头）。"""
import unittest

from PySide6.QtWidgets import QApplication

from game.player import Player
from game.world import World
from game.events import EventPool
from game.item import ItemLibrary
from game.enemy import EnemyLibrary
from game.skill import SkillLibrary
from game.npc import NPCLibrary
from game.quest import QuestLibrary
from game.engine import GameEngine

from ui.achievement_dialog import AchievementDialog
from ui.difficulty_mode_dialog import DifficultyModeDialog
from ui.action_panel import ActionPanel


class TestAchievementMetaDialog(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def _make_engine(self):
        player = Player(name="t")
        engine = GameEngine(
            player, World(config_dir="config"), EventPool(config_dir="config"),
            ItemLibrary(config_dir="config"), EnemyLibrary(config_dir="config"),
            SkillLibrary(config_dir="config"), NPCLibrary(config_dir="config"),
            QuestLibrary(config_dir="config"),
            save_manager=None, config_dir="config",
        )
        return engine

    def test_achievement_dialog_builds(self):
        engine = self._make_engine()
        dialog = AchievementDialog(engine)
        self.assertTrue(hasattr(dialog, "engine"))
        dialog.close()

    def test_difficulty_mode_dialog_builds(self):
        engine = self._make_engine()
        dialog = DifficultyModeDialog(engine, engine.player, new_game=True)
        self.assertGreater(len(dialog._diff_radios), 0)
        self.assertGreater(len(dialog._mode_radios), 0)
        dialog.close()

    def test_action_panel_has_difficulty_mode_button(self):
        engine = self._make_engine()
        panel = ActionPanel(engine)
        self.assertIn("difficulty_mode", panel._button_map)
        panel.close()


if __name__ == "__main__":
    unittest.main()
