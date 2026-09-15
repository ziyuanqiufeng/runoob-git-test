# -*- coding: utf-8 -*-
"""心魔·道心弹窗冒烟测试（无头）。"""
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

from ui.heart_demon_dialog import HeartDemonDialog
from ui.heart_demon_tribulation_dialog import HeartDemonTribulationDialog
from ui.action_panel import ActionPanel


class TestHeartDemonDialog(unittest.TestCase):
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

    def test_status_dialog_builds(self):
        engine = self._make_engine()
        dialog = HeartDemonDialog(engine)
        self.assertTrue(hasattr(dialog, "engine"))
        self.assertTrue(hasattr(dialog, "mgr"))
        dialog.close()

    def test_tribulation_dialog_loads_scenario(self):
        engine = self._make_engine()
        dialog = HeartDemonTribulationDialog(engine, "past_self")
        self.assertIsNotNone(dialog.scenario)
        self.assertEqual(dialog.scenario["id"], "past_self")
        dialog.close()

    def test_action_panel_has_heart_demon_button(self):
        engine = self._make_engine()
        panel = ActionPanel(engine)
        self.assertIn("heart_demon", panel._button_map)
        # 心魔系统默认开启，按钮应可用
        self.assertTrue(panel._button_map["heart_demon"].isEnabled())
        panel.close()


if __name__ == "__main__":
    unittest.main()
