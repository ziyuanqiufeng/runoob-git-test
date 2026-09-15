# -*- coding: utf-8 -*-
"""F-04 事件链（WorldEventManager 扩展）单元测试。

验证：功能开关关闭时链不触发；事件链完整生命周期
（启动 -> 月度推进 -> 玩家决策节点 -> 战斗/自动推进 -> 结束回滚）；
自动推进链无需决策即可完结；UI 查询接口正确暴露决策选项。
"""
import unittest
from unittest.mock import patch

from game.player import Player
from game.world import World
from game.npc import NPCLibrary
from game.enemy import EnemyLibrary
from game.item import ItemLibrary
from game.world_state import WorldStateManager
from game.world_event import WorldEventManager


def build(year=5, enabled=True):
    player = Player(name="t")
    world = World(config_dir="config")
    world.year = year
    npc_lib = NPCLibrary(config_dir="config")
    enemy_lib = EnemyLibrary(config_dir="config")
    item_lib = ItemLibrary(config_dir="config")
    notifies = []
    wsm = WorldStateManager(player, config_dir="config", notify_callback=notifies.append)
    wem = WorldEventManager(
        player, world, npc_lib, enemy_lib, item_lib,
        notify_callback=notifies.append,
        world_state_manager=wsm,
        is_feature_enabled=(lambda f: enabled),
    )
    return player, world, wsm, wem, notifies


class TestEventChains(unittest.TestCase):
    def test_flag_off_prevents_chain_start(self):
        player, world, wsm, wem, _ = build(year=5, enabled=False)
        for _ in range(50):
            wem.tick()
        self.assertEqual(player.active_event_chains, {})

    def test_chain_lifecycle_with_choice_and_revert(self):
        player, world, wsm, wem, _ = build(year=5, enabled=True)
        wem._start_chain("demon_invasion")
        self.assertIn("demon_invasion", player.active_event_chains)
        self.assertEqual(wsm.get("dark_qi"), 30.0)   # "+30%" -> +30 点
        self.assertEqual(wsm.get("npc_mood"), 40.0)  # -10 点

        # stage1 duration=2，推进两次到达决策节点
        wem._advance_chain("demon_invasion")
        self.assertEqual(player.active_event_chains["demon_invasion"]["remaining_months"], 1)
        wem._advance_chain("demon_invasion")
        self.assertTrue(player.active_event_chains["demon_invasion"]["awaiting_choice"])

        # 选择"主动出击"（index 0）：npc_mood +5 -> 45，进入 2a（战斗 + auto_next 3）
        with patch("game.world_event.random.random", return_value=0.0):
            ok = wem.choose_chain_option("demon_invasion", 0)
        self.assertTrue(ok)
        self.assertEqual(wsm.get("npc_mood"), 45.0)
        self.assertEqual(player.active_event_chains["demon_invasion"]["current_stage"], "2a")

        # stage2a duration=1 -> 推进后 auto_next 到 3
        wem._advance_chain("demon_invasion")
        self.assertEqual(player.active_event_chains["demon_invasion"]["current_stage"], "3")
        # stage3 duration=1 -> 推进后 ending 收尾
        wem._advance_chain("demon_invasion")

        self.assertNotIn("demon_invasion", player.active_event_chains)
        self.assertIn("demon_invasion", player.world_event_chain_history)
        # 效果应已精确回滚
        self.assertEqual(wsm.get("dark_qi"), 0.0)
        self.assertEqual(wsm.get("npc_mood"), 50.0)

    def test_get_active_chains_exposes_choices(self):
        player, world, wsm, wem, _ = build(year=5, enabled=True)
        wem._start_chain("demon_invasion")
        wem._advance_chain("demon_invasion")
        wem._advance_chain("demon_invasion")
        chains = wem.get_active_chains()
        self.assertEqual(len(chains), 1)
        self.assertTrue(chains[0]["awaiting_choice"])
        self.assertEqual(len(chains[0]["choices"]), 3)

    def test_auto_chain_completes_without_choice(self):
        player, world, wsm, wem, _ = build(year=5, enabled=True)
        wem._start_chain("spirit_tide")
        # stage1 duration=3 -> 4 次推进后进入 ending 并收尾
        for _ in range(4):
            wem._advance_chain("spirit_tide")
        self.assertNotIn("spirit_tide", player.active_event_chains)
        # lingqi 效果应已回滚到基准
        self.assertEqual(wsm.get("lingqi"), 100.0)


if __name__ == "__main__":
    unittest.main()
