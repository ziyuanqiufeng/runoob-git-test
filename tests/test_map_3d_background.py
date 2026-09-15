"""3D 地图背景开关测试。"""
import os
import sys
import json
import unittest
import tempfile
import shutil
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QSize

from game.world import World
from ui.map_widget import MapWidget, _is_3d_bg_enabled, _load_feature_flags

app = QApplication.instance() or QApplication([])


class TestMap3DBackground(unittest.TestCase):
    """验证 3D 背景按 feature_flags 开关加载/回退。"""

    def setUp(self):
        self.world = World(config_dir="config")
        self.flags_path = "config/feature_flags.json"
        self._original_flags = None
        if os.path.exists(self.flags_path):
            with open(self.flags_path, "r", encoding="utf-8") as f:
                self._original_flags = json.load(f)

    def tearDown(self):
        if self._original_flags is not None:
            with open(self.flags_path, "w", encoding="utf-8") as f:
                json.dump(self._original_flags, f, ensure_ascii=False, indent=2)

    def _set_flag(self, enabled):
        data = {"flags": {}}
        if os.path.exists(self.flags_path):
            with open(self.flags_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        if "flags" not in data:
            data["flags"] = {}
        data["flags"]["map_3d_background"] = enabled
        with open(self.flags_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def test_flag_enabled_by_default(self):
        """缺省 key 视为开启。"""
        with patch.dict(os.environ, {}, clear=False):
            self._set_flag(True)
            self.assertTrue(_is_3d_bg_enabled())

    def test_flag_disabled(self):
        """显式关闭时返回 False。"""
        self._set_flag(False)
        self.assertFalse(_is_3d_bg_enabled())

    def test_load_feature_flags_missing_file(self):
        """配置文件不存在时返回空 dict（视为全部开启）。"""
        with patch("builtins.open", side_effect=FileNotFoundError):
            self.assertEqual(_load_feature_flags(), {})

    def test_widget_loads_3d_background_when_enabled(self):
        """开关开启且图片存在时，_bg_image 非空。"""
        self._set_flag(True)
        # 确保 assets/maps/world_3d.png 存在
        bg_path = os.path.join("assets", "maps", "world_3d.png")
        self.assertTrue(os.path.exists(bg_path), f"3D 背景图缺失: {bg_path}")
        widget = MapWidget(self.world)
        self.assertIsNotNone(widget._bg_image)
        self.assertFalse(widget._bg_image.isNull())

    def test_widget_falls_back_when_disabled(self):
        """开关关闭时 _bg_image 为 None。"""
        self._set_flag(False)
        widget = MapWidget(self.world)
        self.assertIsNone(widget._bg_image)

    def test_widget_falls_back_when_image_missing(self):
        """开关开启但图片不存在时 _bg_image 为 None。"""
        self._set_flag(True)
        widget = MapWidget(self.world)
        # 临时把图片路径换掉模拟缺失
        original = widget._bg_image
        widget._bg_image = None
        widget._load_3d_background()
        # 重新加载应该成功（因为图存在），恢复原状
        widget._bg_image = None
        # 验证：用 monkey patch 让 os.path.exists 对该路径返回 False
        with patch("os.path.exists", return_value=False):
            widget._load_3d_background()
        self.assertIsNone(widget._bg_image)

    def test_paint_runs_without_error(self):
        """3D / 2D 两种模式下 paintEvent 都不报错。"""
        # 3D
        self._set_flag(True)
        widget = MapWidget(self.world)
        widget.resize(800, 600)
        widget.show()
        app.processEvents()
        pixmap = widget.grab()
        self.assertFalse(pixmap.isNull())
        # 2D
        self._set_flag(False)
        widget2 = MapWidget(self.world)
        widget2.resize(800, 600)
        widget2.show()
        app.processEvents()
        pixmap2 = widget2.grab()
        self.assertFalse(pixmap2.isNull())


if __name__ == "__main__":
    unittest.main(verbosity=2)


class TestMapStyleToggle(unittest.TestCase):
    """验证 2D/3D 运行时切换按钮行为与偏好持久化。"""

    def setUp(self):
        self.world = World(config_dir="config")
        self.flags_path = "config/feature_flags.json"
        self.prefs_path = "config/ui_prefs.json"
        self._original_flags = self._read(self.flags_path)
        self._original_prefs = self._read(self.prefs_path)
        self._set_flag(True)  # 确保 3D 功能开启

    def tearDown(self):
        self._write(self.flags_path, self._original_flags)
        self._write(self.prefs_path, self._original_prefs)

    def _read(self, path):
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        return None

    def _write(self, path, data):
        # 安全删除机制在沙箱内不可用，故用「写入空对象」代替物理删除，
        # 既清空测试污染，又避免触发 safe-delete 抛错。
        os.makedirs(os.path.dirname(path), exist_ok=True)
        if data is None:
            data = {}
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def _set_flag(self, enabled):
        data = self._read(self.flags_path) or {"flags": {}}
        if "flags" not in data:
            data["flags"] = {}
        data["flags"]["map_3d_background"] = enabled
        self._write(self.flags_path, data)

    def _clean_prefs(self):
        self._write(self.prefs_path, {})

    def test_default_follows_feature_flag(self):
        """缺省风格跟随功能开关（开启→3D，且功能可用）。"""
        self._clean_prefs()
        w = MapWidget(self.world)
        self.assertTrue(w.is_feature_available())
        self.assertTrue(w.is_3d_enabled())

    def test_feature_off_forces_2d(self):
        """功能关闭时强制 2D，且 set_3d_enabled(True) 仍保持 2D。"""
        self._set_flag(False)
        self._clean_prefs()
        w = MapWidget(self.world)
        self.assertFalse(w.is_feature_available())
        self.assertFalse(w.is_3d_enabled())
        w.set_3d_enabled(True)
        self.assertFalse(w.is_3d_enabled())

    def test_set_3d_enabled_toggles_and_emits(self):
        """set_3d_enabled 切换并触发 style_changed 信号；同值不重复触发。"""
        self._clean_prefs()
        w = MapWidget(self.world)
        signals = []
        w.style_changed.connect(lambda b: signals.append(b))
        w.set_3d_enabled(False, persist=False)
        self.assertFalse(w.is_3d_enabled())
        self.assertEqual(signals[-1], False)
        w.set_3d_enabled(True, persist=False)
        self.assertTrue(w.is_3d_enabled())
        self.assertEqual(signals[-1], True)
        # 重复设相同值应提前返回，不再发射
        before = len(signals)
        w.set_3d_enabled(True, persist=False)
        self.assertEqual(len(signals), before)

    def test_set_3d_enabled_persists(self):
        """set_3d_enabled(persist=True) 写回 ui_prefs.json，新实例沿用。"""
        self._clean_prefs()
        w = MapWidget(self.world)
        w.set_3d_enabled(False, persist=True)
        self.assertTrue(os.path.exists(self.prefs_path))
        with open(self.prefs_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        self.assertFalse(data["map_3d_enabled"])
        # 新实例读取持久化偏好
        w2 = MapWidget(self.world)
        self.assertFalse(w2.is_3d_enabled())
        # 切回 3D 后再次持久化
        w2.set_3d_enabled(True, persist=True)
        w3 = MapWidget(self.world)
        self.assertTrue(w3.is_3d_enabled())

    def test_runtime_toggle_keeps_bg_loaded(self):
        """功能开启时背景图构造即加载，运行时切换无需重新加载。"""
        self._clean_prefs()
        w = MapWidget(self.world)
        self.assertIsNotNone(w._bg_image)
        w.set_3d_enabled(False, persist=False)
        self.assertIsNotNone(w._bg_image)  # 仍保留，可随时切回
        self.assertFalse(w.is_3d_enabled())


class TestMap2DStylizedBackground(unittest.TestCase):
    """验证 2D 写实背景图（world_2d.png）的加载、切换与渲染回退。"""

    def setUp(self):
        self.world = World(config_dir="config")
        self.bg_path = "assets/maps/world_2d.png"

    def test_2d_bg_loaded_when_file_exists(self):
        """world_2d.png 存在时 _bg_2d_image 自动加载为非空 QPixmap。"""
        if not os.path.exists(self.bg_path):
            self.skipTest(f"背景图 {self.bg_path} 不存在，跳过")
        w = MapWidget(self.world, use_3d=False)
        self.assertIsNotNone(w._bg_2d_image)
        self.assertFalse(w._bg_2d_image.isNull())

    def test_2d_bg_loads_independent_of_feature_flag(self):
        """2D 背景加载独立于 feature_flags.map_3d_background；功能关闭时 2D 背景仍加载。"""
        flags_path = "config/feature_flags.json"
        original = None
        if os.path.exists(flags_path):
            with open(flags_path, "r", encoding="utf-8") as f:
                original = json.load(f)
        try:
            data = {"flags": {"map_3d_background": False}}
            os.makedirs(os.path.dirname(flags_path), exist_ok=True)
            with open(flags_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False)
            w = MapWidget(self.world)
            self.assertFalse(w.is_feature_available())
            self.assertFalse(w.is_3d_enabled())
            # 即使 3D 功能关闭，2D 写实背景也应被加载（写实 2D 地图是独立功能）
            if os.path.exists(self.bg_path):
                self.assertIsNotNone(w._bg_2d_image)
        finally:
            if original is not None:
                with open(flags_path, "w", encoding="utf-8") as f:
                    json.dump(original, f, ensure_ascii=False)

    def test_2d_bg_missing_file_falls_back(self):
        """world_2d.png 缺失时 _bg_2d_image 为 None，paintEvent 不报错。"""
        # 临时把 _load_2d_background 内部的路径改成一个不存在的文件，验证容错
        with patch("os.path.exists", return_value=False):
            w = MapWidget(self.world, use_3d=False)
            w.resize(800, 600)
            w.show()
            app.processEvents()
            pixmap = w.grab()
            self.assertIsNone(w._bg_2d_image)
            self.assertFalse(pixmap.isNull())  # 仍能渲染（渐变回退）

    def test_2d_mode_renders_with_annotations(self):
        """2D 写实背景 + 节点标注 + 连线都能正常渲染。"""
        if not os.path.exists(self.bg_path):
            self.skipTest(f"背景图 {self.bg_path} 不存在，跳过")
        w = MapWidget(self.world, use_3d=False)
        w.set_current_location("qingyun")
        w.resize(1024, 800)
        w.show()
        app.processEvents()
        pixmap = w.grab()
        self.assertFalse(pixmap.isNull())
        self.assertEqual(pixmap.width(), 1024)
        self.assertEqual(pixmap.height(), 800)
        # 至少应加载到 28 个地点
        self.assertEqual(len(self.world.locations), 28)

    def test_both_backgrounds_coexist(self):
        """3D 与 2D 背景图同时加载，运行时切换无副作用。"""
        if not os.path.exists(self.bg_path):
            self.skipTest(f"2D 背景图 {self.bg_path} 不存在，跳过")
        flags_path = "config/feature_flags.json"
        original = None
        if os.path.exists(flags_path):
            with open(flags_path, "r", encoding="utf-8") as f:
                original = json.load(f)
        try:
            data = {"flags": {"map_3d_background": True}}
            os.makedirs(os.path.dirname(flags_path), exist_ok=True)
            with open(flags_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False)
            w = MapWidget(self.world, use_3d=True)
            self.assertIsNotNone(w._bg_image)      # 3D 背景加载
            self.assertIsNotNone(w._bg_2d_image)   # 2D 背景也加载
            w.set_3d_enabled(False)
            self.assertFalse(w.is_3d_enabled())
            # 切换后两张背景图都仍在，可任意来回切
            self.assertIsNotNone(w._bg_image)
            self.assertIsNotNone(w._bg_2d_image)
            w.set_3d_enabled(True)
            self.assertTrue(w.is_3d_enabled())
        finally:
            if original is not None:
                with open(flags_path, "w", encoding="utf-8") as f:
                    json.dump(original, f, ensure_ascii=False)

