# -*- coding: utf-8 -*-
"""F-04 天下大事弹窗冒烟测试（无头）。

构造真实 GameEngine，启动事件链并推进到决策节点，验证 WorldEventsDialog
能正常刷新、渲染状态条与抉择按钮，且点击抉择可推进事件链（不抛异常）。
"""
import unittest
from unittest.mock import patch

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
from ui.world_events_dialog import WorldEventsDialog


class TestWorldEventsDialog(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def _make_engine(self):
        player = Player(name="t")
        world = World(config_dir="config")
        world.year = 5
        event_pool = EventPool(config_dir="config")
        item_lib = ItemLibrary(config_dir="config")
        enemy_lib = EnemyLibrary(config_dir="config")
        skill_lib = SkillLibrary(config_dir="config")
        npc_lib = NPCLibrary(config_dir="config")
        quest_lib = QuestLibrary(config_dir="config")
        return GameEngine(
            player, world, event_pool, item_lib, enemy_lib, skill_lib,
            npc_lib, quest_lib, save_manager=None, config_dir="config",
        )

    def test_dialog_refresh_and_choose(self):
        engine = self._make_engine()
        wem = engine.world_event_manager
        # 启动并推进到决策节点
        wem._start_chain("demon_invasion")
        wem._advance_chain("demon_invasion")
        wem._advance_chain("demon_invasion")
        self.assertTrue(
            engine.player.active_event_chains["demon_invasion"]["awaiting_choice"]
        )

        dialog = WorldEventsDialog(engine)
        # 刷新不应抛异常，且渲染了 5 个状态条
        dialog.refresh()
        self.assertEqual(len(dialog._state_bars), 5)

        # 模拟玩家抉择：点击"主动出击"（index 0）
        with patch("game.world_event.random.random", return_value=0.0):
            dialog._choose("demon_invasion", 0)
        self.assertEqual(
            engine.player.active_event_chains["demon_invasion"]["current_stage"], "2a"
        )
        # 刷新后界面状态仍正常
        dialog.refresh()
        dialog.close()


if __name__ == "__main__":
    unittest.main()
