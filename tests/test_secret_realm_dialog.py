# -*- coding: utf-8 -*-
"""F-03 秘境探索弹窗冒烟测试（无头）。

构造真实 GameEngine，验证：设置界面/探索界面可正常构建；卡牌增益的
施加与还原正确；feature 开关关闭时按钮被禁用。不依赖真实战斗 GUI。
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
from ui.secret_realm_dialog import SecretRealmDialog
from ui.action_panel import ActionPanel


class TestSecretRealmDialog(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def _make_engine(self):
        player = Player(name="t")
        world = World(config_dir="config")
        world.year = 5
        return GameEngine(
            player, world, EventPool(config_dir="config"),
            ItemLibrary(config_dir="config"), EnemyLibrary(config_dir="config"),
            SkillLibrary(config_dir="config"), NPCLibrary(config_dir="config"),
            QuestLibrary(config_dir="config"),
            save_manager=None, config_dir="config",
        )

    def test_setup_view_builds(self):
        engine = self._make_engine()
        dialog = SecretRealmDialog(engine)
        self.assertTrue(hasattr(dialog, "realm_combo"))
        self.assertTrue(hasattr(dialog, "diff_combo"))
        dialog.close()

    def test_run_view_builds_and_mods(self):
        engine = self._make_engine()
        engine.secret_realm_manager.unlock("fire_realm")
        engine.secret_realm_manager.start_run("fire_realm", "normal", None)
        dialog = SecretRealmDialog(engine)
        dialog._show_run_view()
        self.assertTrue(hasattr(dialog, "map_view"))
        # 卡牌增益施加与还原
        p = engine.player
        orig = p.base_attack
        dialog._apply_combat_mods({"attack_pct": 0.5, "defense_pct": 0.0, "max_hp_flat": 0})
        self.assertEqual(p.base_attack, int(orig * 1.5))
        dialog._restore_combat_mods()
        self.assertEqual(p.base_attack, orig)
        dialog.close()

    def test_button_gated_by_feature_flag(self):
        engine = self._make_engine()
        engine._feature_flags["roguelike_secret_realm"] = False
        panel = ActionPanel(engine)
        panel.refresh_buttons()
        self.assertFalse(panel._button_map["secret_realm"].isEnabled())
        panel.close()


if __name__ == "__main__":
    unittest.main()
