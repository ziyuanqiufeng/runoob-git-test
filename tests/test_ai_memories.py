# -*- coding: utf-8 -*-
"""AI 喂料测试：NPC 记忆注入剧情提示词与 pending ctx。"""
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
from game.ai_story_generator import AIStoryGenerator


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


_EVENT = {
    "id": "ancient_ruin", "name": "上古遗迹",
    "description": "你发现一处上古遗迹。",
    "condition": "explore", "effects": {"qi": 50},
}
_LOCATION = {"id": "loc_wild", "name": "荒郊", "type": "wild"}


class TestPromptInjection(unittest.TestCase):
    """_build_prompt：记忆注入与不注入两种形态。"""

    def _generator(self):
        return AIStoryGenerator(config_dir="config")

    def test_prompt_without_memories(self):
        prompt = self._generator()._build_prompt(
            _EVENT, Player(), _LOCATION, realm_name="元婴期")
        self.assertNotIn("共同往事", prompt)

    def test_prompt_with_memories(self):
        e = _make_engine()
        e.player.record_npc_moment("npc_b", "第3年：与乙结为道侣，誓同修大道")
        prompt = self._generator()._build_prompt(
            _EVENT, e.player, _LOCATION, realm_name="元婴期",
            npc_memories=e._collect_recent_memories(),
        )
        self.assertIn("共同往事", prompt)
        self.assertIn("誓同修大道", prompt)


class TestCtxCollection(unittest.TestCase):
    """_apply_event 的 pending ctx 携带 npc_memories。"""

    def test_pending_ctx_has_memories(self):
        e = _make_engine()
        e.player.record_npc_moment("npc_b", "第3年：与乙双修，情意愈笃")
        e.player.record_npc_moment("npc_c", "第4年：与丙论道")
        flags = {"ai_dynamic_event": True, "ai_llm_story": True}
        with patch.object(e, "is_feature_enabled",
                          side_effect=lambda k: flags.get(k, False)), \
             patch.object(e, "notify"):
            e._apply_event(dict(_EVENT), dict(_LOCATION))
        ctx = e.pop_pending_ai_event()
        self.assertIsNotNone(ctx)
        self.assertIn("npc_memories", ctx)
        self.assertTrue(any("双修" in m for m in ctx["npc_memories"]))

    def test_collect_recent_limits(self):
        e = _make_engine()
        for i in range(6):
            e.player.record_npc_moment("npc_a", f"条目{i}")
        recent = e._collect_recent_memories(limit=3)
        self.assertEqual(recent, ["条目3", "条目4", "条目5"])


if __name__ == "__main__":
    unittest.main()
