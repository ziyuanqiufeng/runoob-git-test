# -*- coding: utf-8 -*-
"""Agnes 文生图接入测试（不真实调 API，用 mock）。"""
import io
import json
import os
import sys
import tempfile
import unittest
import urllib.error
from unittest.mock import patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from PIL import Image

from game.player import Player
from game import portrait_generator as pg

import pytest


@pytest.fixture(autouse=True)
def _no_external_ai_calls():
    """覆盖 conftest 同名全局 fixture：本文件自管 AI mock。

    TestLoadApiKey 需要真实的 _load_ai_api_key 逻辑；其余测试各自
    patch 模块级函数/urlopen，不依赖全局保护。
    """
    yield


class _FakeResp:
    """模拟 urlopen 返回的响应对象。"""

    def __init__(self, data):
        self._data = data

    def read(self):
        return self._data

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def _png_bytes(size=(8, 8)):
    buf = io.BytesIO()
    Image.new("RGB", size, (255, 0, 0)).save(buf, format="PNG")
    return buf.getvalue()


class TestLoadApiKey(unittest.TestCase):
    def test_env_takes_priority(self):
        with patch.dict(os.environ, {"AGNES_API_KEY": "sk-env"}):
            self.assertEqual(pg._load_ai_api_key(), "sk-env")

    def test_reads_from_config(self):
        env = {k: v for k, v in os.environ.items() if k != "AGNES_API_KEY"}
        with patch.dict(os.environ, env, clear=True):
            key = pg._load_ai_api_key("config")
        self.assertTrue(key.startswith("sk-"))

    def test_missing_returns_empty(self):
        env = {k: v for k, v in os.environ.items() if k != "AGNES_API_KEY"}
        with patch.dict(os.environ, env, clear=True):
            self.assertEqual(pg._load_ai_api_key("不存在的目录"), "")


class TestGenerateViaAgnes(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.out = os.path.join(self.tmp, "gen.png")

    def test_no_key_returns_none(self):
        with patch.object(pg, "_load_ai_api_key", return_value=""):
            self.assertIsNone(pg._generate_via_agnes("p", self.out))

    def test_success_downloads_image(self):
        api_resp = json.dumps({"data": [{"url": "http://x/img.png"}]}).encode("utf-8")
        with patch.object(pg, "_load_ai_api_key", return_value="sk-test"):
            with patch("urllib.request.urlopen",
                       side_effect=[_FakeResp(api_resp), _FakeResp(_png_bytes())]):
                result = pg._generate_via_agnes("p", self.out)
        self.assertEqual(result, self.out)
        self.assertTrue(os.path.exists(self.out))

    def test_api_failure_returns_none(self):
        with patch.object(pg, "_load_ai_api_key", return_value="sk-test"):
            with patch("urllib.request.urlopen", side_effect=Exception("网络错误")):
                self.assertIsNone(pg._generate_via_agnes("p", self.out))

    def test_no_url_in_response_returns_none(self):
        api_resp = json.dumps({"data": []}).encode("utf-8")
        with patch.object(pg, "_load_ai_api_key", return_value="sk-test"):
            with patch("urllib.request.urlopen", side_effect=[_FakeResp(api_resp)]):
                self.assertIsNone(pg._generate_via_agnes("p", self.out))

    def test_invalid_image_returns_none(self):
        api_resp = json.dumps({"data": [{"url": "http://x/img.png"}]}).encode("utf-8")
        with patch.object(pg, "_load_ai_api_key", return_value="sk-test"):
            with patch("urllib.request.urlopen",
                       side_effect=[_FakeResp(api_resp), _FakeResp(b"not-an-image")]):
                self.assertIsNone(pg._generate_via_agnes("p", self.out))


class TestAgnesRetry(unittest.TestCase):
    """服务端队列满（503）的重试逻辑。"""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.out = os.path.join(self.tmp, "gen.png")
        self.api_resp = json.dumps({"data": [{"url": "http://x/img.png"}]}).encode("utf-8")

    def _http_error(self, code):
        return urllib.error.HTTPError("http://x", code, "err", None, io.BytesIO(b"queue full"))

    def test_503_retries_then_succeeds(self):
        with patch.object(pg, "_load_ai_api_key", return_value="sk-test"):
            with patch("time.sleep"):
                with patch("urllib.request.urlopen",
                           side_effect=[self._http_error(503), _FakeResp(self.api_resp), _FakeResp(_png_bytes())]):
                    result = pg._generate_via_agnes("p", self.out, retry_delay=0)
        self.assertEqual(result, self.out)

    def test_503_exhausted_returns_none(self):
        with patch.object(pg, "_load_ai_api_key", return_value="sk-test"):
            with patch("time.sleep"):
                with patch("urllib.request.urlopen",
                           side_effect=[self._http_error(503)] * 3) as mock_urlopen:
                    result = pg._generate_via_agnes("p", self.out, retry_delay=0, max_retries=3)
        self.assertIsNone(result)
        self.assertEqual(mock_urlopen.call_count, 3)

    def test_non_503_does_not_retry(self):
        with patch.object(pg, "_load_ai_api_key", return_value="sk-test"):
            with patch("urllib.request.urlopen",
                       side_effect=[self._http_error(400)]) as mock_urlopen:
                result = pg._generate_via_agnes("p", self.out, retry_delay=0, max_retries=3)
        self.assertIsNone(result)
        self.assertEqual(mock_urlopen.call_count, 1)


class TestGeneratePortraitFallback(unittest.TestCase):
    """无 key / 关闭 AI 时回退占位图。"""

    def _player(self):
        p = Player(name="测试")
        p.gender = "male"
        p.cultivation_path = "fa"
        p.realm_id = "qi_refining_1"
        return p

    def test_use_ai_false_generates_placeholder(self):
        tmp = tempfile.mkdtemp()
        ok, path = pg.generate_portrait(self._player(), output_dir=tmp, use_ai=False)
        self.assertTrue(ok)
        self.assertTrue(os.path.exists(path))

    def test_no_key_falls_back_to_placeholder(self):
        tmp = tempfile.mkdtemp()
        with patch.object(pg, "_load_ai_api_key", return_value=""):
            ok, path = pg.generate_portrait(self._player(), output_dir=tmp, use_ai=True)
        self.assertTrue(ok)
        self.assertTrue(os.path.exists(path))

    def test_build_prompt_contains_gender_and_style(self):
        p = self._player()
        p.set_spiritual_roots(["fire"])
        prompt = pg.build_prompt(p)
        self.assertIn("man", prompt)
        self.assertIn("fire", prompt)


if __name__ == "__main__":
    unittest.main()
