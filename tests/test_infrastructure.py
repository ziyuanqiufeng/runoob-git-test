# -*- coding: utf-8 -*-
import json
import os
import unittest

from game.player import Player
from game.world import World
from game.item import ItemLibrary
from game.save_manager import SaveManager
from tools.validate_configs import validate_all


class TestValidateConfigs(unittest.TestCase):
    """配置校验工具测试。"""

    def test_validate_current_configs_pass(self):
        """当前 config 目录应通过校验。"""
        errors = validate_all("config")
        self.assertEqual(errors, [])

    def test_validate_invalid_json(self):
        """非法 JSON 应被检测。"""
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            with open(os.path.join(tmpdir, "broken.json"), "w", encoding="utf-8") as f:
                f.write("{not valid json")
            errors = validate_all(tmpdir)
            self.assertTrue(any("JSON 解析失败" in e for e in errors))

    def test_validate_duplicate_id(self):
        """重复 id 应被检测。"""
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            with open(os.path.join(tmpdir, "items.json"), "w", encoding="utf-8") as f:
                json.dump([{"id": "a"}, {"id": "a"}], f)
            errors = validate_all(tmpdir)
            self.assertTrue(any("重复 id" in e for e in errors))


class TestSaveManager(unittest.TestCase):
    """存档管理器测试。"""

    def setUp(self):
        self.save_path = "test_infrastructure_save.json"
        self.item_lib = ItemLibrary(config_dir="config")

    def tearDown(self):
        if os.path.exists(self.save_path):
            os.remove(self.save_path)

    def test_save_includes_version(self):
        """存档文件应包含版本号。"""
        player = Player(name="测试")
        world = World(config_dir="config")
        manager = SaveManager(save_path=self.save_path)
        manager.save(player, world)

        with open(self.save_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        self.assertEqual(data["version"], SaveManager.SAVE_VERSION)

    def test_load_restores_player_and_world(self):
        """读档后应恢复玩家与世界状态。"""
        player = Player(name="测试修士")
        player.qi = 1234
        world = World(config_dir="config")
        world.year = 10
        world.month = 5
        manager = SaveManager(save_path=self.save_path)
        manager.save(player, world)

        loaded = manager.load(self.item_lib, config_dir="config")
        self.assertIsNotNone(loaded)
        loaded_player, loaded_world = loaded
        self.assertEqual(loaded_player.name, "测试修士")
        self.assertEqual(loaded_player.qi, 1234)
        self.assertEqual(loaded_world.year, 10)
        self.assertEqual(loaded_world.month, 5)

    def test_migrate_old_save(self):
        """旧存档（无 version）应被迁移并补充新字段。"""
        old_data = {
            "player": {"name": "旧存档"},
            "world": {"year": 1, "month": 1},
        }
        with open(self.save_path, "w", encoding="utf-8") as f:
            json.dump(old_data, f)

        manager = SaveManager(save_path=self.save_path)
        loaded = manager.load(self.item_lib, config_dir="config")
        self.assertIsNotNone(loaded)
        player, world = loaded
        self.assertEqual(player.mental_state, 50)
        self.assertEqual(player.heart_demon, 0)
        self.assertEqual(player.residence, None)
        self.assertEqual(player.companions, [])


if __name__ == "__main__":
    unittest.main()
