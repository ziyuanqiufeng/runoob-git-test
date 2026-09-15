# -*- coding: utf-8 -*-
"""维度② 引擎接线 + 弹窗冒烟测试（无头）。

验证：engine 正确构造 RedDustManager 并注册月度插座；cultivate 月度结算不异常；
feature_flags.red_dust 关闭时月度 tick 被跳过；新弹窗与按钮可无错构建。
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
from game.engine import GameEngine

from ui.red_dust_dialog import RedDustDialog
from ui.action_panel import ActionPanel


class TestRedDustEngineWiring(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def _make_engine(self):
        player = Player(name="红尘引擎接线")
        return GameEngine(
            player, World(config_dir="config"), EventPool(config_dir="config"),
            ItemLibrary(config_dir="config"), EnemyLibrary(config_dir="config"),
            SkillLibrary(config_dir="config"), NPCLibrary(config_dir="config"),
            QuestLibrary(config_dir="config"),
            save_manager=None, config_dir="config",
        )

    def test_manager_constructed_and_registered(self):
        engine = self._make_engine()
        self.assertTrue(hasattr(engine, "red_dust_manager"))
        cb_names = [getattr(cb, "__name__", str(cb)) for cb, _ in engine._monthly_tick_hooks]
        self.assertIn("_tick_red_dust", cb_names)

    def test_cultivate_runs_without_error(self):
        engine = self._make_engine()
        # 闭关 3 月触发多次月度插座；不应抛异常
        engine.cultivate(months=3)

    def test_flag_gating_skips_tick_when_disabled(self):
        engine = self._make_engine()
        # 模拟已入世
        engine.player.red_dust_active = True
        engine.player.red_dust_months = 0
        # 关闭 red_dust 开关
        engine._feature_flags = dict(engine._feature_flags)
        engine._feature_flags["red_dust"] = False
        engine._run_registered_monthly_ticks()
        self.assertEqual(engine.player.red_dust_months, 0)
        # 重新开启后应推进
        engine._feature_flags["red_dust"] = True
        engine._run_registered_monthly_ticks()
        self.assertEqual(engine.player.red_dust_months, 1)

    def test_engine_actions_delegate(self):
        engine = self._make_engine()
        ok, msg = engine.enter_red_dust()
        self.assertTrue(ok)
        ok, msg = engine.red_dust_experience()
        self.assertTrue(ok)
        # 设一个 pending 情劫并通过引擎抉择
        engine.player.red_dust_pending_qingjie = {
            "id": "qj", "name": "n", "description": "",
            "choices": [{"id": "a", "text": "t", "result_text": "r",
                         "effects": {"mental_delta": 1, "heart_delta": 0}}],
        }
        ok, msg = engine.apply_qingjie_choice("a")
        self.assertTrue(ok)
        self.assertIsNone(engine.player.red_dust_pending_qingjie)


class TestRedDustDialogs(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def _make_engine(self):
        player = Player(name="红尘弹窗")
        return GameEngine(
            player, World(config_dir="config"), EventPool(config_dir="config"),
            ItemLibrary(config_dir="config"), EnemyLibrary(config_dir="config"),
            SkillLibrary(config_dir="config"), NPCLibrary(config_dir="config"),
            QuestLibrary(config_dir="config"),
            save_manager=None, config_dir="config",
        )

    def test_red_dust_dialog_builds(self):
        engine = self._make_engine()
        dialog = RedDustDialog(engine)
        self.assertEqual(dialog.windowTitle(), "红尘炼心")
        dialog.close()

    def test_action_panel_has_red_dust_button(self):
        engine = self._make_engine()
        panel = ActionPanel(engine)
        self.assertIn("red_dust", panel._button_map)
        panel.close()


if __name__ == "__main__":
    unittest.main()
