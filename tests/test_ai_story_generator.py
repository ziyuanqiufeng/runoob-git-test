# -*- coding: utf-8 -*-
"""Agnes LLM 动态剧情生成器测试（不真实调 API，用 mock）。"""
import os
import sys
import unittest
from unittest.mock import patch

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from game.ai_story_generator import AIStoryGenerator
from game.player import Player


@pytest.fixture(autouse=True)
def _no_external_ai_calls():
    """覆盖 conftest 同名全局 fixture：本文件的 generate_story 单测
    需要走真实方法内部逻辑（自身已 mock urlopen/_api_key）。"""
    yield


class TestAIStoryGenerator(unittest.TestCase):
    def setUp(self):
        self.gen = AIStoryGenerator(config_dir="config")

    def _event(self):
        return {"id": "find_herb", "name": "灵草奇遇", "description": "发现一株百年灵草"}

    def test_state_desc_heart_demon(self):
        p = Player(name="测试")
        p.heart_demon = 90
        desc = self.gen._state_desc(p)
        self.assertIn("心魔", desc)

    def test_state_desc_red_dust(self):
        p = Player(name="测试")
        p.red_dust_bonds = [{"type": "love", "name": "甲"}]
        desc = self.gen._state_desc(p)
        self.assertIn("红尘", desc)

    def test_build_prompt_contains_info(self):
        p = Player(name="测试")
        prompt = self.gen._build_prompt(self._event(), p, {"name": "青云山", "type": "sect"}, "炼气期")
        self.assertIn("百年灵草", prompt)
        self.assertIn("青云山", prompt)
        self.assertIn("炼气期", prompt)

    def test_generate_no_key_returns_none(self):
        with patch.object(self.gen, "_api_key", return_value=""):
            self.assertIsNone(self.gen.generate_story(self._event(), Player(name="测试")))

    def test_generate_success(self):
        class _Resp:
            def read(self):
                return ('{"choices":[{"message":{"content":" 荒陲偶逢玉芝，惊见灵光暗生。 "}}]}').encode("utf-8")
            def __enter__(self):
                return self
            def __exit__(self, *a):
                return False

        with patch.object(self.gen, "_api_key", return_value="sk-test"):
            with patch("urllib.request.urlopen", return_value=_Resp()):
                text = self.gen.generate_story(self._event(), Player(name="测试"))
        self.assertEqual(text, "荒陲偶逢玉芝，惊见灵光暗生。")

    def test_generate_failure_returns_none(self):
        with patch.object(self.gen, "_api_key", return_value="sk-test"):
            with patch("urllib.request.urlopen", side_effect=Exception("网络错误")):
                self.assertIsNone(self.gen.generate_story(self._event(), Player(name="测试")))


if __name__ == "__main__":
    unittest.main()
