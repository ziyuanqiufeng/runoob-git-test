# -*- coding: utf-8 -*-
"""心魔·道心引擎接线集成测试（维度①）。

验证：突破大境界且心魔过高 → 触发心魔劫幻境；
     心魔系统受 feature_flags.heart_demon 门控；
     心魔劫抉择经引擎 apply_heart_demon_tribulation_choice 落地。
"""
import unittest
from unittest import mock

from game.player import Player
from game.world import World
from game.events import EventPool
from game.item import ItemLibrary
from game.enemy import EnemyLibrary
from game.skill import SkillLibrary
from game.npc import NPCLibrary
from game.quest import QuestLibrary
from game.engine import GameEngine
import game.engine as engine_mod


def _make_engine():
    player = Player(name="engine_test")
    engine = GameEngine(
        player, World(config_dir="config"), EventPool(config_dir="config"),
        ItemLibrary(config_dir="config"), EnemyLibrary(config_dir="config"),
        SkillLibrary(config_dir="config"), NPCLibrary(config_dir="config"),
        QuestLibrary(config_dir="config"),
        save_manager=None, config_dir="config",
    )
    return engine


class TestEngineHeartDemonWiring(unittest.TestCase):
    def test_feature_flag_enabled_by_default(self):
        engine = _make_engine()
        self.assertTrue(engine.is_feature_enabled("heart_demon"))

    def test_major_breakthrough_with_high_heart_demon_triggers_tribulation(self):
        engine = _make_engine()
        captured = []
        engine.notify = lambda m: captured.append(m)

        # 置于大境界圆满（筑基圆满），修为满，心魔高
        engine.player.realm_id = "foundation_peak"
        engine.player.qi = 18000
        engine.player.heart_demon = 80

        # 强制突破失败（random=0.99），避免境界变更带来的级联副作用
        with mock.patch.object(engine_mod.random, "random", return_value=0.99):
            engine.breakthrough()

        trib_msg = [m for m in captured if m.startswith("__HEART_DEMON_TRIBULATION__:")]
        self.assertTrue(trib_msg, "高心魔大境界突破应触发心魔劫幻境通知")
        self.assertIsNotNone(engine.pending_heart_demon_scenario)

    def test_apply_tribulation_choice_through_engine(self):
        engine = _make_engine()
        # 直接走引擎封装：先置心魔高 & 取一个真实场景
        engine.player.heart_demon = 80
        scenario = engine.mental_state_manager.get_heart_demon_tribulation_scenario(
            rng=engine_mod.random
        )
        self.assertIsNotNone(scenario)
        sid = scenario["id"]
        cid = scenario["choices"][0]["id"]
        ok, msg = engine.apply_heart_demon_tribulation_choice(sid, cid)
        self.assertTrue(ok)
        self.assertIsNone(engine.pending_heart_demon_scenario)

    def test_monthly_tick_registered_and_runs(self):
        engine = _make_engine()
        engine.player.heart_demon = 50
        before = engine.player.heart_demon
        engine._tick_mental_state()
        self.assertLess(engine.player.heart_demon, before)


if __name__ == "__main__":
    unittest.main()
