# -*- coding: utf-8 -*-
"""存档安全加固测试：原子写入、滚动备份、删除异常保护。"""
import json
import os
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from game.player import Player
from game.world import World
from game.save_manager import SaveManager


def _make_manager():
    tmp = tempfile.mkdtemp()
    return SaveManager(
        save_path=os.path.join(tmp, "save.json"),
        save_dir=os.path.join(tmp, "saves"),
    ), tmp


class TestAtomicSave(unittest.TestCase):
    """原子写入 + 滚动备份。"""

    def setUp(self):
        self.sm, self.tmp = _make_manager()
        self.player = Player(name="测试")
        self.world = World(config_dir="config")

    def test_save_no_tmp_leftover(self):
        path = self.sm.save(self.player, self.world, slot="s1")
        self.assertTrue(os.path.exists(path))
        self.assertFalse(os.path.exists(path + ".tmp"))
        with open(path, encoding="utf-8") as f:
            data = json.load(f)  # 必须是有效完整 JSON
        self.assertEqual(data["player"]["name"], "测试")

    def test_backup_created_on_second_save(self):
        self.sm.save(self.player, self.world, slot="s1")
        self.sm.save(self.player, self.world, slot="s1")  # 第二次触发备份
        backup_dir = os.path.join(self.tmp, "saves", "backups")
        backups = [f for f in os.listdir(backup_dir) if f.startswith("s1_")]
        self.assertEqual(len(backups), 1)

    def test_backup_rotation_keeps_five(self):
        backup_dir = os.path.join(self.tmp, "saves", "backups")
        os.makedirs(backup_dir, exist_ok=True)
        for i in range(7):  # 预置 7 份旧备份
            with open(os.path.join(backup_dir, f"s1_20260101_00000{i}.json"), "w") as f:
                f.write("{}")
        open(os.path.join(self.tmp, "saves", "s1.json"), "w").write("{}")  # 旧主档
        with patch("os.remove") as mock_remove:
            self.sm.save(self.player, self.world, slot="s1")
        # 7 旧 + 1 新 = 8 份，保留 5 → 应清理 3 份
        self.assertEqual(mock_remove.call_count, 3)

    def test_backup_failure_not_blocking(self):
        self.sm.save(self.player, self.world, slot="s1")
        with patch("shutil.copy2", side_effect=OSError("磁盘满")):
            path = self.sm.save(self.player, self.world, slot="s1")  # 不应抛异常
        self.assertTrue(os.path.exists(path))

    def test_list_slots_ignores_backups_dir(self):
        self.sm.save(self.player, self.world, slot="s1")
        self.sm.save(self.player, self.world, slot="s1")  # 产生 backups/
        names = [s["name"] for s in self.sm.list_slots()]
        self.assertEqual(names, ["s1"])  # backups 子目录不算槽位


class TestDeleteSlotSafety(unittest.TestCase):
    """删除异常保护。"""

    def setUp(self):
        self.sm, self.tmp = _make_manager()

    def test_delete_missing_returns_false(self):
        self.assertFalse(self.sm.delete_slot("不存在"))

    def test_delete_success(self):
        path = os.path.join(self.tmp, "saves", "s1.json")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        open(path, "w").write("{}")
        self.assertTrue(self.sm.delete_slot("s1"))
        self.assertFalse(os.path.exists(path))

    def test_delete_io_error_returns_false_no_raise(self):
        path = os.path.join(self.tmp, "saves", "s1.json")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        open(path, "w").write("{}")
        with patch("os.remove", side_effect=OSError("被占用")):
            self.assertFalse(self.sm.delete_slot("s1"))  # 不抛异常


if __name__ == "__main__":
    unittest.main()
