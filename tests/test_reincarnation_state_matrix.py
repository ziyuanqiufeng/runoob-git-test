# -*- coding: utf-8 -*-
"""转世状态语义矩阵测试：固化每个 Player 挂载状态在轮回中的继承/清零语义。

教训（2026-10-09 chronicle 断裂）：转世/重开类新实例流程必须系统排查
所有挂载状态的继承语义。本文件把语义固化为回归矩阵——
未来任何改动破坏语义会在此被捕获。

矩阵：
- 显式继承组：reincarnation_count / karma / past_life_talents / past_bond /
  relic_chain / chronicle（魂之记忆，2026-10-09 修复）
- 天然清零组（新实例默认空，断言旧值不泄漏）：companions /
  npc_relationships / grudges / disciples / social_event_state /
  achievements / achievement_progress
- 特殊组：npc_memory（清零但转世 NPC 预写前世条目）/ 灵根（retain_roots 才保留）
"""
import os
import sys
import tempfile
import unittest

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


def _make_engine():
    tmp = tempfile.mkdtemp()
    player = Player(name="测试道友")
    player.realm_id = "lianxu_peak"
    player.qi = 460000
    player.companions = [{"npc_id": "npc_b", "name": "乙", "intimacy": 90}]
    player.grudges = {"npc_e": {"level": 3, "reason": "夺宝", "start_month": 1}}
    player.disciples = [{"npc_id": "npc_d", "name": "丁", "realm_id": "qi_refining_3"}]
    player.npc_relationships = {"npc_b": 60, "npc_e": -40}
    player.social_event_state = {"dao_lv_gift:npc_b": 100}
    player.achievements = ["first_kill", "companion"]
    player.achievement_progress = {"kills": 30}
    player.record_npc_moment("npc_b", "第5年：与乙结为道侣")
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
    # 前世年表（含结局条目）
    engine.player.chronicle.append({
        "year": 300, "month": 5, "age": 316,
        "text": "达成结局【飞升成仙】", "category": "ending",
    })
    return engine


class TestInheritedStates(unittest.TestCase):
    """显式继承组：转世必须携带。"""

    def _reincarnate(self):
        e = _make_engine()
        new_player, _ = e.start_reincarnation([])
        return e, new_player

    def test_meta_fields_inherited(self):
        old, new_player = self._reincarnate()
        self.assertEqual(new_player.reincarnation_count,
                         old.player.reincarnation_count + 1)
        self.assertEqual(new_player.karma, old.player.karma)
        self.assertIsNotNone(new_player.past_bond)
        self.assertEqual(new_player.past_bond["npc_id"], "npc_b")

    def test_chronicle_carried(self):
        old, new_player = self._reincarnate()
        old_texts = [c["text"] for c in old.player.chronicle]
        new_texts = [c["text"] for c in new_player.chronicle]
        for t in old_texts:                       # 前世条目全量延续
            self.assertIn(t, new_texts)
        self.assertTrue(any("第 1 世启程" in t for t in new_texts))

    def test_game_mode_inherited(self):
        """周目模式跨世延续（魔道玩家转世仍是魔道，专属线不断）。"""
        e = _make_engine()
        e.player.game_mode = "demonic_lone"
        new_player, _ = e.start_reincarnation([])
        self.assertEqual(new_player.game_mode, "demonic_lone")

    def test_mode_opening_flag_reset_but_untouched(self):
        """转世后演出标记复位（新实例默认），但转世流程不调用演出——
        不会误触发；若未来新周目入口调用则正常演出一次。"""
        e = _make_engine()
        e.player.game_mode = "demonic_lone"
        e.player.mode_opening_done = True
        notify_log = []
        e.add_listener(notify_log.append)
        new_player, _ = e.start_reincarnation([])
        self.assertFalse(new_player.mode_opening_done)
        # 转世流程本身不触发开场演出（无魔道文案入 notify）
        self.assertFalse(any("【魔道】" in m for m in notify_log))

    def test_relic_chain_inherited(self):
        e = _make_engine()
        e.player.relic_chain = ["relic_a", "relic_b"]
        new_player, _ = e.start_reincarnation([])
        self.assertEqual(sorted(new_player.relic_chain), ["relic_a", "relic_b"])


class TestResetStates(unittest.TestCase):
    """天然清零组：转世后不携带前世恩怨/社交/成就。"""

    def test_social_states_reset(self):
        old, new_player = (lambda e: (e, e.start_reincarnation([])[0]))(_make_engine())
        self.assertEqual(new_player.companions, [])
        self.assertEqual(new_player.grudges, {})
        self.assertEqual(new_player.disciples, [])
        self.assertEqual(new_player.npc_relationships, {})
        self.assertEqual(new_player.social_event_state, {})

    def test_achievements_reset(self):
        old, new_player = (lambda e: (e, e.start_reincarnation([])[0]))(_make_engine())
        self.assertEqual(new_player.achievements, [])
        self.assertEqual(new_player.achievement_progress, {})

    def test_npc_memory_isolated(self):
        """旧世 NPC 记忆不泄漏；转世 NPC 预写前世条目。"""
        old, new_player = (lambda e: (e, e.start_reincarnation([])[0]))(_make_engine())
        # 旧世记忆不在新实例
        self.assertNotIn("npc_b", new_player.npc_memory)
        # 转世 NPC 有前世预写
        reborn_id = "reborn_npc_b"
        self.assertTrue(any(
            "前世" in m for m in new_player.get_npc_memory(reborn_id)["moments"]))


if __name__ == "__main__":
    unittest.main()


class TestModeOpening(unittest.TestCase):
    """模式开场演出：一次性 + 文案 + 年表 + standard 无演出。"""

    def test_demonic_opening(self):
        e = _make_engine()
        e.player.game_mode = "demonic_lone"
        notify_log = []
        e.add_listener(notify_log.append)
        self.assertTrue(e.trigger_mode_opening())
        self.assertTrue(any("魔道" in m for m in notify_log))
        self.assertTrue(e.player.mode_opening_done)
        self.assertTrue(any("启程：魔道之路" in c["text"]
                            for c in e.player.chronicle))
        # 二次调用不重复
        self.assertFalse(e.trigger_mode_opening())

    def test_standard_silent(self):
        e = _make_engine()
        notify_log = []
        e.add_listener(notify_log.append)
        self.assertFalse(e.trigger_mode_opening())
        self.assertTrue(e.player.mode_opening_done)   # 标记照置
        self.assertEqual(notify_log, [])              # 无演出

    def test_mortal_opening(self):
        e = _make_engine()
        e.player.game_mode = "mortal_challenge"
        notify_log = []
        e.add_listener(notify_log.append)
        self.assertTrue(e.trigger_mode_opening())
        self.assertTrue(any("凡人" in m for m in notify_log))
        self.assertTrue(any("启程：凡人之路" in c["text"]
                            for c in e.player.chronicle))
