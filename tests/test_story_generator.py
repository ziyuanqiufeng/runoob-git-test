# -*- coding: utf-8 -*-
"""动态剧情生成器测试。"""
import os
import random
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from game.story_generator import StoryGenerator
from game.player import Player


class TestStoryGenerator(unittest.TestCase):
    def setUp(self):
        self.gen = StoryGenerator(config_dir="config")

    def _event(self, desc="你在山谷中发现一株百年灵草，服用后修为大涨。"):
        return {"id": "find_herb", "name": "灵草奇遇", "description": desc}

    def test_render_nonempty_and_contains_desc(self):
        p = Player(name="测试")
        text = self.gen.render_event(self._event(), p, {"type": "wild"}, rng=random.Random(1))
        self.assertTrue(text)
        self.assertIn("百年灵草", text)

    def test_env_varies_by_location_type(self):
        p = Player(name="测试")
        rng = random.Random(7)
        t_city = self.gen.render_event(self._event(), p, {"type": "city"}, rng=rng)
        rng = random.Random(7)
        t_wild = self.gen.render_event(self._event(), p, {"type": "wild"}, rng=rng)
        self.assertNotEqual(t_city, t_wild)

    def test_heart_demon_high_adds_state(self):
        p = Player(name="测试")
        p.heart_demon = 90
        flavors = self.gen._state_flavors(p)
        self.assertTrue(any(("心魔" in f) or ("躁" in f) for f in flavors))

    def test_red_dust_bonded_adds_state(self):
        p = Player(name="测试")
        p.red_dust_bonds = [{"type": "love", "name": "甲"}]
        flavors = self.gen._state_flavors(p)
        self.assertTrue(any(("红尘" in f) or ("牵挂" in f) or ("心头一暖" in f) for f in flavors))

    def test_deterministic_with_seed(self):
        p = Player(name="测试")
        e = self._event()
        a = self.gen.render_event(e, p, {"type": "wild"}, rng=random.Random(42))
        b = self.gen.render_event(e, p, {"type": "wild"}, rng=random.Random(42))
        self.assertEqual(a, b)


if __name__ == "__main__":
    unittest.main()
