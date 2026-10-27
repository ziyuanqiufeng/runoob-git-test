# -*- coding: utf-8 -*-
"""模式/难度 effects 落地测试：验证纸面效应修复（乘区真实生效）。

覆盖：
- exp_mult 修炼乘区（难度 × 模式复合）
- reincarnation_cultivation_bonus（天赋加成）修炼乘区
- enemy_strength 敌人强度乘区
- meta_modifiers 并入 difficulty_modifiers
- hostile_factions 正道皆敌（NPC 初始关系落地）
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
from game.meta_manager import MetaManager


def _make_engine():
    tmp = tempfile.mkdtemp()
    player = Player(name="测试道友")
    engine = GameEngine(
        player,
        World(config_dir="config"),
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


class TestCultivationMultipliers(unittest.TestCase):
    """修炼乘区：exp_mult 与天赋加成真实生效。"""

    def _month_gain(self, engine):
        before = engine.player.qi
        engine.cultivate(1)
        return engine.player.qi - before

    def test_exp_mult_applied(self):
        base = _make_engine()
        boost = _make_engine()
        boost.player.difficulty_modifiers = {"exp_mult": 2.0}
        g_base = self._month_gain(base)
        g_boost = self._month_gain(boost)
        self.assertGreater(g_boost, g_base * 1.8)   # 约双倍（取整误差）

    def test_rebirth_bonus_applied(self):
        base = _make_engine()
        boost = _make_engine()
        boost.player.reincarnation_cultivation_bonus = 0.5
        g_base = self._month_gain(base)
        g_boost = self._month_gain(boost)
        self.assertGreater(g_boost, g_base * 1.4)   # +50%（取整误差）


class TestEnemyScaling(unittest.TestCase):
    """敌人强度乘区。"""

    def test_enemy_strength_applied(self):
        from game.enemy import Enemy
        e = _make_engine()
        enemy = Enemy(
            enemy_id="t1", name="测试妖兽", level=1, hp=100,
            attack=10, defense=5, description="d", loot={}, exp=0,
        )
        e.player.difficulty_modifiers = {"enemy_strength": 2.0}
        e._apply_difficulty_enemy_scaling(enemy)
        self.assertEqual(enemy.max_hp, 200)
        self.assertEqual(enemy.attack, 20)
        self.assertEqual(enemy.defense, 10)

    def test_enemy_strength_one_noop(self):
        from game.enemy import Enemy
        e = _make_engine()
        enemy = Enemy(
            enemy_id="t1", name="测试妖兽", level=1, hp=100,
            attack=10, defense=5, description="d", loot={}, exp=0,
        )
        e.player.difficulty_modifiers = {"enemy_strength": 1.0}
        e._apply_difficulty_enemy_scaling(enemy)
        self.assertEqual(enemy.max_hp, 100)


class TestMetaMerge(unittest.TestCase):
    """meta_modifiers 并入 difficulty_modifiers（复合乘区）。"""

    def test_merge(self):
        e = _make_engine()
        e.player.difficulty_modifiers = {"exp_mult": 1.0, "enemy_strength": 1.0}
        mgr = MetaManager(config_dir="config")
        mgr.apply_to_player(e.player, "heaven_cycle")
        self.assertAlmostEqual(
            e.player.difficulty_modifiers["exp_mult"], 1.15)
        self.assertAlmostEqual(
            e.player.difficulty_modifiers["enemy_strength"], 1.2)
        # 原始 meta_modifiers 保留
        self.assertAlmostEqual(e.player.meta_modifiers["exp_mult"], 1.15)


class TestHostileFactions(unittest.TestCase):
    """正道皆敌落地：正道 NPC 初始关系降为敌视。"""

    def test_apply_hostile(self):
        e = _make_engine()
        e.player.hostile_factions = ["righteous"]
        count = e.apply_hostile_factions()
        # 库中有 faction_affinity.righteous>0 的 NPC 时应有命中
        if count:
            righteous = [
                nid for nid, npc in e.npc_library.npcs.items()
                if (getattr(npc, "faction_affinity", {}) or {}).get("righteous", 0) > 0
            ]
            for nid in righteous:
                self.assertLessEqual(e.player.npc_relationships[nid], -30)

    def test_no_hostile_noop(self):
        e = _make_engine()
        e.player.hostile_factions = []
        self.assertEqual(e.apply_hostile_factions(), 0)


if __name__ == "__main__":
    unittest.main()


class TestStartItemsDelivery(unittest.TestCase):
    """模式开局赠礼：pending_start_items 真实发放并入包。"""

    def test_consume_start_items(self):
        e = _make_engine()
        e.player.pending_start_items = ["spirit_stone"]
        before = e.player.count_item("spirit_stone")
        names = e.consume_pending_start_items()
        self.assertEqual(len(names), 1)
        self.assertEqual(e.player.count_item("spirit_stone"), before + 1)
        self.assertEqual(e.player.pending_start_items, [])   # 清空防重复

    def test_empty_pending_noop(self):
        e = _make_engine()
        e.player.pending_start_items = []
        self.assertEqual(e.consume_pending_start_items(), [])

    def test_invalid_item_skipped(self):
        e = _make_engine()
        e.player.pending_start_items = ["not_exist_item", "spirit_stone"]
        names = e.consume_pending_start_items()
        self.assertEqual(len(names), 1)   # 无效 id 跳过，有效照发
