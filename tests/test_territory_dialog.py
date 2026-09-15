# -*- coding: utf-8 -*-
"""F-02 领地弹窗冒烟测试（无头）。

构造真实 GameEngine，验证：占领视图 / 总览视图可正常构建；功能开关关闭
时 action_panel 的领地按钮被禁用。
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

from ui.territory_dialog import TerritoryDialog
from ui.territory_build_dialog import TerritoryBuildDialog
from ui.territory_defense_dialog import TerritoryDefenseDialog
from ui.action_panel import ActionPanel


class TestTerritoryDialog(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def _make_engine(self, realm="nascent_soul", stones=40000):
        player = Player(name="t")
        player.realm_id = realm
        player.reputation = {}
        world = World(config_dir="config")
        lib = ItemLibrary(config_dir="config")
        for _ in range(stones):
            player.add_item(lib.create("spirit_stone"))
        engine = GameEngine(
            player, world, EventPool(config_dir="config"),
            lib, EnemyLibrary(config_dir="config"),
            SkillLibrary(config_dir="config"), NPCLibrary(config_dir="config"),
            QuestLibrary(config_dir="config"),
            save_manager=None, config_dir="config",
        )
        return engine

    def test_claim_view_builds(self):
        engine = self._make_engine()
        dialog = TerritoryDialog(engine)
        # 元婴期 + 灵石充足，应展示可占领地图下拉框
        self.assertTrue(hasattr(dialog, "map_combo"))
        self.assertGreater(dialog.map_combo.count(), 0)
        dialog.close()

    def test_overview_builds_after_claim(self):
        engine = self._make_engine()
        ok, msg = engine.territory_manager.claim("qingyun_lingmai")
        self.assertTrue(ok, msg)
        dialog = TerritoryDialog(engine)
        self.assertTrue(hasattr(dialog, "grid"))
        dialog.close()

    def test_build_dialog_instantiates(self):
        engine = self._make_engine()
        engine.territory_manager.claim("qingyun_lingmai")
        dlg = TerritoryBuildDialog(engine.territory_manager)
        self.assertIsNotNone(dlg)
        dlg.close()

    def test_defense_dialog_instantiates(self):
        engine = self._make_engine()
        engine.territory_manager.claim("qingyun_lingmai")
        dlg = TerritoryDefenseDialog(engine.territory_manager)
        self.assertIsNotNone(dlg)
        dlg.close()

    def test_button_gated_by_feature_flag(self):
        engine = self._make_engine()
        engine._feature_flags["territory"] = False
        panel = ActionPanel(engine)
        panel.refresh_buttons()
        self.assertFalse(panel._button_map["territory"].isEnabled())
        panel.close()


if __name__ == "__main__":
    unittest.main()
