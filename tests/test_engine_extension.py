# -*- coding: utf-8 -*-
"""M0 前置改造测试：功能开关（feature_flags）与月度结算订阅注册表。

验证点：
1. feature_flags.json 缺失/合法/嵌套/损坏 时的加载行为（向后兼容）；
2. is_feature_enabled 的缺省开启语义；
3. register_monthly_tick / _run_registered_monthly_ticks 的注册、按 flag 开关、异常隔离；
4. 注册表接入 cultivate 月度循环后，按月份正确触发（对旧系统零影响）。
"""
import json
import os
import tempfile
import unittest
from unittest.mock import patch, MagicMock

from game.engine import GameEngine
from game.player import Player
from game.world import World
from game.events import EventPool
from game.item import ItemLibrary
from game.enemy import EnemyLibrary
from game.skill import SkillLibrary
from game.npc import NPCLibrary
from game.quest import QuestLibrary


class _FakeEngine:
    """仅用于单元测试 _load_feature_flags 逻辑的轻量替身（避免加载完整配置）。"""

    def __init__(self, config_dir):
        self.config_dir = config_dir
        self.notifies = []

    def notify(self, msg):
        self.notifies.append(msg)

    # 复用真实实现，仅依赖 self.config_dir 与 self.notify
    _load_feature_flags = GameEngine._load_feature_flags


class TestFeatureFlagsLoading(unittest.TestCase):
    def test_missing_file_defaults_empty(self):
        with tempfile.TemporaryDirectory() as d:
            fake = _FakeEngine(d)
            self.assertEqual(fake._load_feature_flags(), {})

    def test_valid_flags_dict(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "feature_flags.json")
            with open(path, "w", encoding="utf-8") as f:
                json.dump({"family": True, "territory": False}, f)
            fake = _FakeEngine(d)
            self.assertEqual(
                fake._load_feature_flags(),
                {"family": True, "territory": False},
            )

    def test_valid_flags_nested(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "feature_flags.json")
            with open(path, "w", encoding="utf-8") as f:
                json.dump({"flags": {"roguelike_secret_realm": False}}, f)
            fake = _FakeEngine(d)
            self.assertEqual(
                fake._load_feature_flags(),
                {"roguelike_secret_realm": False},
            )

    def test_malformed_json_defaults_empty_and_notifies(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "feature_flags.json")
            with open(path, "w", encoding="utf-8") as f:
                f.write("{ not valid json")
            fake = _FakeEngine(d)
            self.assertEqual(fake._load_feature_flags(), {})
            self.assertTrue(any("解析失败" in n for n in fake.notifies))


class _EngineTestBase(unittest.TestCase):
    def _make_engine(self, config_dir="config"):
        item_lib = ItemLibrary(config_dir=config_dir)
        enemy_lib = EnemyLibrary(config_dir=config_dir)
        skill_lib = SkillLibrary(config_dir=config_dir)
        npc_lib = NPCLibrary(config_dir=config_dir)
        quest_lib = QuestLibrary(config_dir=config_dir)
        player = Player(name="测试修士")
        world = World(config_dir=config_dir)
        event_pool = EventPool(config_dir=config_dir)
        return GameEngine(
            player, world, event_pool,
            item_lib, enemy_lib, skill_lib,
            npc_lib, quest_lib, save_manager=None, config_dir=config_dir,
        )


class TestFeatureFlagAPI(_EngineTestBase):
    def setUp(self):
        self.engine = self._make_engine()

    def test_default_enabled_when_no_flags(self):
        self.engine._feature_flags = {}
        self.assertTrue(self.engine.is_feature_enabled("anything"))

    def test_unknown_flag_defaults_enabled(self):
        self.engine._feature_flags = {"family": False}
        self.assertTrue(self.engine.is_feature_enabled("territory"))

    def test_known_flag_respected(self):
        self.engine._feature_flags = {"family": False}
        self.assertFalse(self.engine.is_feature_enabled("family"))
        self.engine._feature_flags = {"family": True}
        self.assertTrue(self.engine.is_feature_enabled("family"))


class TestMonthlyTickRegistry(_EngineTestBase):
    def setUp(self):
        self.engine = self._make_engine()

    def test_empty_registry_is_noop(self):
        # 不应抛异常，也不应改变任何状态
        self.engine._run_registered_monthly_ticks()

    def test_callback_invoked_and_flag_gating(self):
        calls = []
        cb = lambda: calls.append(1)
        idx = self.engine.register_monthly_tick(cb, flag="family")
        self.assertIsInstance(idx, int)

        # flag 关闭 -> 不执行
        self.engine._feature_flags = {"family": False}
        self.engine._run_registered_monthly_ticks()
        self.assertEqual(calls, [])

        # flag 开启 -> 执行
        self.engine._feature_flags = {"family": True}
        self.engine._run_registered_monthly_ticks()
        self.assertEqual(calls, [1])

        # flag=None -> 不受开关控制，始终执行
        self.engine._feature_flags = {"family": False}
        self.engine.register_monthly_tick(cb, flag=None)
        self.engine._run_registered_monthly_ticks()
        self.assertEqual(calls, [1, 1])

    def test_exception_isolated(self):
        def bad():
            raise RuntimeError("boom")
        good = MagicMock()
        self.engine.register_monthly_tick(bad, flag=None)
        self.engine.register_monthly_tick(good, flag=None)
        # 不应抛出；坏回调被隔离，好回调仍执行
        self.engine._run_registered_monthly_ticks()
        good.assert_called_once()

    def test_runs_each_cultivate_month(self):
        calls = []
        self.engine.register_monthly_tick(lambda: calls.append(1), flag=None)
        patches = [
            patch.object(self.engine.weather_manager, "get_cultivation_speed_bonus", return_value=0.0),
            patch.object(self.engine.weather_manager, "advance", return_value=(False, None, None, None, None)),
            patch.object(self.engine.mental_state_manager, "get_cultivation_speed_bonus", return_value=0.0),
            patch.object(self.engine.residence_manager, "get_cultivation_speed_bonus", return_value=0.0),
            patch.object(self.engine.mental_state_manager, "tick_monthly", return_value=(0, 0, [])),
            patch.object(self.engine.residence_manager, "tick_monthly", return_value={"production": [], "raid": None}),
            patch.object(self.engine.world_event_manager, "tick", return_value=None),
            patch("game.engine.random.random", return_value=1.0),
        ]
        for p in patches:
            p.start()
        try:
            self.engine.cultivate(3)
        finally:
            for p in patches:
                p.stop()
        # 注册表回调应随 3 个月度循环触发 3 次
        self.assertEqual(len(calls), 3)


if __name__ == "__main__":
    unittest.main()
