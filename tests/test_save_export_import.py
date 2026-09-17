# -*- coding: utf-8 -*-
"""存档导出/导入测试：zip 往返、立绘打包与路径修复、无效包容错。"""
import json
import os
import sys
import tempfile
import unittest
import zipfile

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from PIL import Image

from game.player import Player
from game.world import World
from game.save_manager import SaveManager


def _make_manager():
    tmp = tempfile.mkdtemp()
    sm = SaveManager(
        save_path=os.path.join(tmp, "save.json"),
        save_dir=os.path.join(tmp, "saves"),
    )
    return sm, tmp


def _make_player():
    p = Player(name="导出道友")
    p.realm_id = "foundation_early"
    p.location_id = "luoxia_city"
    return p


class TestExportImport(unittest.TestCase):
    def setUp(self):
        self.sm, self.tmp = _make_manager()
        self.player = _make_player()
        self.world = World(config_dir="config")
        self.sm.save(self.player, self.world, slot="my_slot")
        self.zip_path = os.path.join(self.tmp, "share.zip")

    def test_export_creates_zip(self):
        data = self.sm.export_slot("my_slot", self.zip_path)
        self.assertIsNotNone(data)
        self.assertTrue(os.path.exists(self.zip_path))
        with zipfile.ZipFile(self.zip_path) as zf:
            self.assertIn("save.json", zf.namelist())

    def test_export_missing_slot_returns_none(self):
        self.assertIsNone(self.sm.export_slot("不存在", self.zip_path))

    def test_import_roundtrip_same_data(self):
        self.sm.export_slot("my_slot", self.zip_path)
        slot = self.sm.import_slot(self.zip_path, base_name="回来")
        self.assertIsNotNone(slot)
        loaded = self.sm.load(self.player, self.world, slot=slot) if False else None
        # 直接读 JSON 验证数据一致
        with open(self.sm._resolve_path(slot), encoding="utf-8") as f:
            data = json.load(f)
        self.assertEqual(data["player"]["name"], "导出道友")
        self.assertEqual(data["player"]["realm_id"], "foundation_early")

    def test_import_slot_name_conflict_auto_numbered(self):
        self.sm.export_slot("my_slot", self.zip_path)
        s1 = self.sm.import_slot(self.zip_path, base_name="分身")
        s2 = self.sm.import_slot(self.zip_path, base_name="分身")
        self.assertEqual(s1, "分身")       # 首次导入用原名
        self.assertNotEqual(s1, s2)        # 二次冲突自动加序号

    def test_invalid_zip_returns_none(self):
        bad = os.path.join(self.tmp, "bad.zip")
        with open(bad, "w") as f:
            f.write("not a zip")
        self.assertIsNone(self.sm.import_slot(bad))

    def test_zip_without_save_json_returns_none(self):
        bad = os.path.join(self.tmp, "empty.zip")
        with zipfile.ZipFile(bad, "w") as zf:
            zf.writestr("other.txt", "hi")
        self.assertIsNone(self.sm.import_slot(bad))

    def test_portrait_packed_and_path_fixed(self):
        # 给玩家一张自定义立绘
        portrait = os.path.join(self.tmp, "my_face.png")
        Image.new("RGB", (32, 32), (10, 200, 120)).save(portrait)
        self.player.portrait = portrait
        self.sm.save(self.player, self.world, slot="my_slot")

        self.sm.export_slot("my_slot", self.zip_path)
        with zipfile.ZipFile(self.zip_path) as zf:
            self.assertIn("portrait.png", zf.namelist())

        slot = self.sm.import_slot(self.zip_path, base_name="有立绘")
        with open(self.sm._resolve_path(slot), encoding="utf-8") as f:
            data = json.load(f)
        new_portrait = data["player"]["portrait"]
        self.assertTrue(os.path.exists(new_portrait))  # 路径已修复且文件存在
        self.assertIn("imported_", new_portrait.replace("\\", "/"))

    def test_corrupt_portrait_skipped_gracefully(self):
        """损坏立绘：跳过释放与路径改写，导入本身仍成功。"""
        portrait = os.path.join(self.tmp, "broken.png")
        with open(portrait, "wb") as f:
            f.write(b"this is not a png at all")
        self.player.portrait = portrait
        self.sm.save(self.player, self.world, slot="my_slot")

        self.sm.export_slot("my_slot", self.zip_path)
        slot = self.sm.import_slot(self.zip_path, base_name="坏立绘")
        self.assertIsNotNone(slot)  # 导入不因立绘损坏而失败
        with open(self.sm._resolve_path(slot), encoding="utf-8") as f:
            data = json.load(f)
        # 路径未被改写为 imported_*（损坏立绘未释放）
        self.assertNotIn("imported_", data["player"]["portrait"].replace("\\", "/"))
        # assets/portraits 下没有新增损坏文件
        imported = [f for f in os.listdir("assets/portraits")
                    if f.startswith("imported_") and os.path.getsize(
                        os.path.join("assets/portraits", f)) < 40]
        self.assertEqual(imported, [])


if __name__ == "__main__":
    unittest.main()
