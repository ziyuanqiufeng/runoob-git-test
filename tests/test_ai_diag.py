# -*- coding: utf-8 -*-
"""AI 服务诊断测试（mock urlopen，不真实联网）。"""
import json
import os
import shutil
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, patch
from unittest.mock import patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from PySide6.QtWidgets import QApplication

app = QApplication.instance() or QApplication([])

from game import ai_diag
from ui.settings_dialog import SettingsDialog

_MODELS_BODY = {
    "data": [{"id": "agnes-2.5-flash"}, {"id": "agnes-image-2.1-flash"}]
}


def _make_cfg_with_key():
    """tmp/config 目录 + 含 key 的 ai_config.json。"""
    tmp = tempfile.mkdtemp()
    cfg = os.path.join(tmp, "config")
    os.makedirs(cfg, exist_ok=True)
    json.dump(
        {"api_key": "sk-test", "base_url": "https://apihub.agnes-ai.com/v1/chat/completions"},
        open(os.path.join(cfg, "ai_config.json"), "w", encoding="utf-8"),
    )
    return cfg


class TestDiagnoseAI(unittest.TestCase):
    def setUp(self):
        self.cfg = _make_cfg_with_key()
        # 隔离环境变量，避免宿主机 AGNES_API_KEY 干扰
        env = {k: v for k, v in os.environ.items() if k != "AGNES_API_KEY"}
        self._env_patch = patch.dict(os.environ, env, clear=True)
        self._env_patch.start()
        self.addCleanup(self._env_patch.stop)

    def test_no_key_reports_missing(self):
        empty_cfg = tempfile.mkdtemp()
        result = ai_diag.diagnose_ai(empty_cfg)
        self.assertFalse(result["key_present"])
        self.assertIn("未配置", result["detail"])

    def test_success_reports_model_available(self):
        with patch("game.ai_diag._API_ROOT", "https://fake/v1"), \
             patch("urllib.request.urlopen") as mock_urlopen:
            mock_urlopen.return_value.__enter__.return_value.read.return_value = (
                json.dumps(_MODELS_BODY).encode("utf-8")
            )
            result = ai_diag.diagnose_ai(self.cfg)
        self.assertTrue(result["key_present"])
        self.assertTrue(result["reachable"])
        self.assertTrue(result["image_model_ok"])
        self.assertIn("可用", result["detail"])

    def test_401_reports_invalid_key(self):
        import urllib.error
        err = urllib.error.HTTPError(
            "http://x", 401, "unauthorized", None, None
        )
        with patch("urllib.request.urlopen", side_effect=err):
            result = ai_diag.diagnose_ai(self.cfg)
        self.assertTrue(result["key_present"])
        self.assertFalse(result["reachable"])
        self.assertIn("401", result["detail"])

    def test_network_error_reports_unreachable(self):
        with patch("urllib.request.urlopen", side_effect=OSError("超时")):
            result = ai_diag.diagnose_ai(self.cfg)
        self.assertFalse(result["reachable"])
        self.assertIn("网络不可达", result["detail"])

    def test_image_model_missing_warns(self):
        body = {"data": [{"id": "agnes-2.5-flash"}]}  # 无图模型
        with patch("game.ai_diag._API_ROOT", "https://fake/v1"), \
             patch("urllib.request.urlopen") as mock_urlopen:
            mock_urlopen.return_value.__enter__.return_value.read.return_value = (
                json.dumps(body).encode("utf-8")
            )
            result = ai_diag.diagnose_ai(self.cfg)
        self.assertTrue(result["reachable"])
        self.assertFalse(result["image_model_ok"])
        self.assertIn("未找到", result["detail"])


class TestSettingsDiagSection(unittest.TestCase):
    """设置面板诊断按钮（offscreen，worker 直接 run 同步验证）。"""

    def setUp(self):
        self.cfg = _make_cfg_with_key()
        env = {k: v for k, v in os.environ.items() if k != "AGNES_API_KEY"}
        self._env_patch = patch.dict(os.environ, env, clear=True)
        self._env_patch.start()
        self.addCleanup(self._env_patch.stop)

    def test_worker_emits_result(self):
        engine = MagicMock()
        engine.config_dir = self.cfg
        worker = SettingsDialog.__mro__  # 占位防误用
        from ui.settings_dialog import _AIDiagWorker
        results = []
        w = _AIDiagWorker(self.cfg)
        w.signals.finished.connect(results.append)
        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_urlopen.return_value.__enter__.return_value.read.return_value = (
                json.dumps(_MODELS_BODY).encode("utf-8")
            )
            w.run()
        self.assertEqual(len(results), 1)
        self.assertTrue(results[0]["image_model_ok"])

    def test_done_updates_label(self):
        engine = MagicMock()
        engine.config_dir = self.cfg
        dlg = SettingsDialog(engine=engine)
        dlg._on_ai_diag_done({"key_present": True, "reachable": True,
                              "image_model_ok": True, "detail": "连接正常，key 有效"})
        self.assertIn("连接正常", dlg.ai_diag_result.text())


if __name__ == "__main__":
    unittest.main()
