# -*- coding: utf-8 -*-
"""NPC 主动事件系统测试：道侣赠礼 / 师徒互动 / 宿敌寻衅 + 冷却与持久化。"""
import os
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from game.player import Player
from game.world import World
from game.events import EventPool
from game.item import ItemLibrary
from game.enemy import EnemyLibrary
from game.skill import SkillLibrary
from game.npc import NPCLibrary
from game.quest import QuestLibrary
from game.engine import GameEngine
from game.save_manager import SaveManager
from game.social_events import SocialEventManager


def _make_engine():
    tmp = tempfile.mkdtemp()
    player = Player(name="测试道友")
    world = World(config_dir="config")
    engine = GameEngine(
        player,
        world,
        EventPool(config_dir="config"),
        ItemLibrary(config_dir="config"),
        EnemyLibrary(config_dir="config"),
        SkillLibrary(config_dir="config"),
        NPCLibrary(config_dir="config"),
        QuestLibrary(config_dir="config"),
        save_manager=SaveManager(
            save_path=os.path.join(tmp, "save.json"),
            save_dir=os.path.join(tmp, "saves"),
        ),
    )
    return engine


def _mgr(engine):
    return engine.social_event_manager


class TestDaoLvGift(unittest.TestCase):
    def _ready_player(self, engine):
        p = engine.player
        p.companions = [{"npc_id": "npc_b", "name": "乙", "intimacy": 80}]
        return p

    def test_gift_triggers(self):
        e = _make_engine()
        p = self._ready_player(e)
        with patch("game.social_events.random.random", return_value=0.0), \
             patch("game.social_events.random.choice",
                   side_effect=lambda seq: seq[0]):
            _mgr(e).tick_monthly()
        # 收到物品（qi_pill 是池首）
        self.assertTrue(any(i.id == "qi_pill" for i in p.inventory))
        # 写入共同经历
        self.assertTrue(
            any("送来" in m for m in p.get_npc_memory("npc_b")["moments"]))

    def test_low_intimacy_no_gift(self):
        e = _make_engine()
        p = self._ready_player(e)
        p.companions[0]["intimacy"] = 10  # 低于门槛 40
        before = len(p.inventory)
        with patch("game.social_events.random.random", return_value=0.0):
            _mgr(e).tick_monthly()
        self.assertEqual(len(p.inventory), before)

    def test_cooldown_blocks(self):
        e = _make_engine()
        p = self._ready_player(e)
        with patch("game.social_events.random.random", return_value=0.0), \
             patch("game.social_events.random.choice",
                   side_effect=lambda seq: seq[0]):
            _mgr(e).tick_monthly()
        count1 = sum(1 for i in p.inventory if i.id == "qi_pill")
        p.social_event_state["dao_lv_gift:npc_b"] = 99999  # 冷却远未到
        with patch("game.social_events.random.random", return_value=0.0):
            _mgr(e).tick_monthly()
        count2 = sum(1 for i in p.inventory if i.id == "qi_pill")
        self.assertEqual(count1, count2)


class TestMasterTeaching(unittest.TestCase):
    def test_teaching_grants_qi(self):
        e = _make_engine()
        p = e.player
        p.disciples = [{"npc_id": "npc_d", "name": "丁", "realm_id": "qi_refining_3"}]
        qi0 = p.qi
        with patch("game.social_events.random.random", return_value=0.0), \
             patch("game.social_events.random.choice",
                   side_effect=lambda seq: seq[0]):
            _mgr(e).tick_monthly()
        self.assertGreater(p.qi, qi0)
        self.assertTrue(
            any("聆教" in m for m in p.get_npc_memory("npc_d")["moments"]))

    def test_no_disciple_no_event(self):
        e = _make_engine()
        qi0 = e.player.qi
        with patch("game.social_events.random.random", return_value=0.0):
            _mgr(e).tick_monthly()
        self.assertEqual(e.player.qi, qi0)


class TestRivalAmbush(unittest.TestCase):
    def test_ambush_costs_health(self):
        e = _make_engine()
        p = e.player
        p.grudges = {"npc_e": {"level": 3, "reason": "夺宝之仇", "start_month": 1}}
        hp0 = p.health
        with patch("game.social_events.random.random", return_value=0.0):
            _mgr(e).tick_monthly()
        self.assertLess(p.health, hp0)
        self.assertTrue(p.is_alive())   # 演练口径：不致死
        self.assertTrue(
            any("寻衅" in m for m in p.get_npc_memory("npc_e")["moments"]))

    def test_no_grudge_no_event(self):
        e = _make_engine()
        hp0 = e.player.health
        with patch("game.social_events.random.random", return_value=0.0):
            _mgr(e).tick_monthly()
        self.assertEqual(e.player.health, hp0)


class TestPersistAndConfig(unittest.TestCase):
    def test_state_roundtrip(self):
        e = _make_engine()
        e.player.social_event_state = {"dao_lv_gift:npc_b": 100}
        d = e.player.to_dict()
        restored = Player.from_dict(d, ItemLibrary(config_dir="config"))
        self.assertEqual(
            restored.social_event_state, {"dao_lv_gift:npc_b": 100})

    def test_config_override(self):
        """config/social_events.json 可覆盖 chance（改 1.0 → 必触发）。"""
        e = _make_engine()
        e.player.grudges = {"npc_e": {"level": 2, "reason": "x", "start_month": 1}}
        hp0 = e.player.health
        # 默认 chance 0.05 + random=0.99 → 不触发
        with patch("game.social_events.random.random", return_value=0.99):
            _mgr(e).tick_monthly()
        self.assertEqual(e.player.health, hp0)
        # 配置 chance=1.0 + random=0.99 → 必触发
        cfg_path = os.path.join("config", "social_events.json")
        bak = open(cfg_path, encoding="utf-8").read()
        try:
            import json
            cfg = json.load(open(cfg_path, encoding="utf-8"))
            cfg["rival_ambush"]["chance"] = 1.0
            json.dump(cfg, open(cfg_path, "w", encoding="utf-8"),
                      ensure_ascii=False)
            mgr = SocialEventManager(
                e.player, npc_library=e.npc_library,
                item_library=e.item_library, world=e.world,
                config_dir="config",
            )
            with patch("game.social_events.random.random", return_value=0.99):
                mgr.tick_monthly()
            self.assertLess(e.player.health, hp0)
        finally:
            open(cfg_path, "w", encoding="utf-8").write(bak)


if __name__ == "__main__":
    unittest.main()
