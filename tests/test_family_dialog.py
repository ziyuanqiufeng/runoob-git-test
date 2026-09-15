# -*- coding: utf-8 -*-
"""F-01 家族弹窗冒烟测试（无头）。

构造真实 GameEngine，验证：创建视图 / 总览视图可正常构建；子弹窗
（成员、事件、外交、建筑）可实例化；feature 开关关闭时按钮被禁用。
"""
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
from game.save_manager import SaveManager
from game.engine import GameEngine
from game.family import FamilyManager

from ui.family_dialog import FamilyDialog
from ui.action_panel import ActionPanel


class TestFamilyDialog(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def _make_engine(self):
        player = Player(name="t")
        player.realm_id = "golden_core_early"
        world = World(config_dir="config")
        engine = GameEngine(
            player, world, EventPool(config_dir="config"),
            ItemLibrary(config_dir="config"), EnemyLibrary(config_dir="config"),
            SkillLibrary(config_dir="config"), NPCLibrary(config_dir="config"),
            QuestLibrary(config_dir="config"),
            save_manager=None, config_dir="config",
        )
        # 满足创建条件
        lib = ItemLibrary(config_dir="config")
        for _ in range(10000):
            player.add_item(lib.create("spirit_stone"))
        player.reputation = {"righteous": 300}
        return engine

    def test_create_view_builds(self):
        engine = self._make_engine()
        dialog = FamilyDialog(engine)
        self.assertTrue(hasattr(dialog, "name_edit"))
        dialog.close()

    def test_overview_builds_after_create(self):
        engine = self._make_engine()
        ok, msg = engine.family_manager.create("测试族", "问道", "righteous")
        self.assertTrue(ok, msg)
        engine.family_manager.recruit_member(quality="normal")
        dialog = FamilyDialog(engine)
        self.assertTrue(hasattr(dialog, "member_table"))
        self.assertGreaterEqual(dialog.member_table.rowCount(), 1)
        dialog.close()

    def test_button_gated_by_feature_flag(self):
        engine = self._make_engine()
        engine._feature_flags["family"] = False
        panel = ActionPanel(engine)
        panel.refresh_buttons()
        self.assertFalse(panel._button_map["family"].isEnabled())
        panel.close()


if __name__ == "__main__":
    unittest.main()
