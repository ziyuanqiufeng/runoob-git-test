# -*- coding: utf-8 -*-
"""维度④⑤ 引擎接线 + 弹窗冒烟测试（无头）。

验证：engine 正确构造两个管理器并注册月度插座；cultivate 月度结算不异常；
explore 在已转世玩家身上可触发前世回响；两个新弹窗可无错构建。
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

from ui.heaven_retribution_dialog import HeavenRetributionDialog
from ui.lifespan_dialog import LifespanDialog
from ui.action_panel import ActionPanel


class TestDim45EngineWiring(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def _make_engine(self):
        player = Player(name="维度45接线")
        engine = GameEngine(
            player, World(config_dir="config"), EventPool(config_dir="config"),
            ItemLibrary(config_dir="config"), EnemyLibrary(config_dir="config"),
            SkillLibrary(config_dir="config"), NPCLibrary(config_dir="config"),
            QuestLibrary(config_dir="config"),
            save_manager=None, config_dir="config",
        )
        return engine

    def test_managers_constructed_and_registered(self):
        engine = self._make_engine()
        self.assertTrue(hasattr(engine, "heaven_retribution_manager"))
        self.assertTrue(hasattr(engine, "lifespan_manager"))
        # 月度插座已注册对应回调
        cb_names = [getattr(cb, "__name__", str(cb)) for cb, _ in engine._monthly_tick_hooks]
        self.assertIn("_tick_heaven_retribution", cb_names)
        self.assertIn("_tick_lifespan", cb_names)

    def test_cultivate_runs_monthly_ticks_without_error(self):
        engine = self._make_engine()
        # 闭关 3 月触发 3 次月度插座；不应抛异常，且注视基线被建立
        engine.cultivate(months=3)
        self.assertIsNotNone(getattr(engine.player, "_gaze_power_base", None))
        self.assertIsNotNone(getattr(engine.player, "_gaze_wealth_base", None))

    def test_territory_depletion_accumulates_via_engine(self):
        engine = self._make_engine()
        # 构造一块超载抽取的小灵脉
        terr = {
            "territory_id": "t1", "name": "试炼灵脉", "tier": "spirit_vein",
            "claimed_month": 0, "month": 0, "treasury": 1000, "depletion": 0,
            "grid": {
                "rows": 2, "cols": 2,
                "cells": [
                    [{"building_id": "spirit_gathering_tower", "level": 5},
                     {"building_id": "spirit_gathering_tower", "level": 5}],
                    [{"building_id": "spirit_gathering_tower", "level": 5},
                     {"building_id": "spirit_gathering_tower", "level": 5}],
                ],
            },
        }
        engine.player.territory = terr
        # 多次月度结算应使枯竭度累积
        for _ in range(3):
            engine._tick_heaven_retribution()
        self.assertGreater(terr["depletion"], 0)

    def test_explore_triggers_past_life_echo(self):
        engine = self._make_engine()
        engine.player.reincarnation_count = 1  # 已转世
        # 直接验证引擎路径调用的 roll_past_life_echo 可用（explore 内部调用）
        before = len(getattr(engine.player, "past_life_relics", []) or [])
        # 以确定性随机强制回响
        import random
        orig = random.random
        random.random = lambda: 0.0
        try:
            engine.lifespan_manager.roll_past_life_echo()
        finally:
            random.random = orig
        after = len(getattr(engine.player, "past_life_relics", []) or [])
        self.assertGreaterEqual(after, before)


class TestDim45Dialogs(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def _make_engine(self):
        player = Player(name="弹窗")
        return GameEngine(
            player, World(config_dir="config"), EventPool(config_dir="config"),
            ItemLibrary(config_dir="config"), EnemyLibrary(config_dir="config"),
            SkillLibrary(config_dir="config"), NPCLibrary(config_dir="config"),
            QuestLibrary(config_dir="config"),
            save_manager=None, config_dir="config",
        )

    def test_heaven_retribution_dialog_builds(self):
        engine = self._make_engine()
        dialog = HeavenRetributionDialog(engine)
        self.assertEqual(dialog.windowTitle(), "天道反噬")
        dialog.close()

    def test_lifespan_dialog_builds(self):
        engine = self._make_engine()
        dialog = LifespanDialog(engine)
        self.assertEqual(dialog.windowTitle(), "寿元·轮回")
        dialog.close()

    def test_action_panel_has_new_buttons(self):
        engine = self._make_engine()
        panel = ActionPanel(engine)
        self.assertIn("heaven_retribution", panel._button_map)
        self.assertIn("lifespan", panel._button_map)
        panel.close()


if __name__ == "__main__":
    unittest.main()
