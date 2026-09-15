import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from game.save_manager import SaveManager
from game.player import Player
from game.world import World
from game.item import ItemLibrary


class TestSaveManagerMulti(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.save_dir = os.path.join(self.tmp, "saves")
        self.sm = SaveManager(
            save_path=os.path.join(self.tmp, "save.json"),
            save_dir=self.save_dir,
        )
        self.item_library = ItemLibrary(config_dir="config")

    def _make_player_world(self, name="测试道友"):
        player = Player(name=name)
        world = World(config_dir="config")
        return player, world

    def test_default_resolves_to_save_json(self):
        self.assertEqual(self.sm._resolve_path(None), self.sm.save_path)

    def test_save_and_load_slot(self):
        player, world = self._make_player_world("逍遥子")
        self.sm.save(player, world, slot="slot_a")
        self.assertTrue(self.sm.exists(slot="slot_a"))
        loaded = self.sm.load(self.item_library, config_dir="config", slot="slot_a")
        self.assertIsNotNone(loaded)
        p, _ = loaded
        self.assertEqual(p.name, "逍遥子")

    def test_list_slots_includes_saved(self):
        p1, w1 = self._make_player_world("甲")
        self.sm.save(p1, w1, slot="alpha")
        p2, w2 = self._make_player_world("乙")
        self.sm.save(p2, w2, slot="beta")
        names = [s["name"] for s in self.sm.list_slots()]
        self.assertIn("alpha", names)
        self.assertIn("beta", names)

    def test_allocate_slot_unique(self):
        self.assertEqual(self.sm.allocate_slot("修仙存档"), "修仙存档")
        p, w = self._make_player_world("修仙存档")
        self.sm.save(p, w, slot="修仙存档")
        self.assertEqual(self.sm.allocate_slot("修仙存档"), "修仙存档_1")

    def test_delete_slot(self):
        p, w = self._make_player_world("待删")
        self.sm.save(p, w, slot="todelete")
        self.assertTrue(self.sm.exists(slot="todelete"))
        self.assertTrue(self.sm.delete_slot("todelete"))
        self.assertFalse(self.sm.exists(slot="todelete"))

    def test_legacy_compat(self):
        # 旧单存档路径保存（不指定 slot）
        p, w = self._make_player_world("旧档道友")
        self.sm.save(p, w)
        slots = self.sm.list_slots()
        names = [s["name"] for s in slots]
        self.assertIn(SaveManager.LEGACY_SLOT, names)
        loaded = self.sm.load(
            self.item_library, config_dir="config", slot=SaveManager.LEGACY_SLOT
        )
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded[0].name, "旧档道友")

    def test_migrate_old_version(self):
        # 构造一个 version=0 的旧存档，确保迁移不报错
        real_world = World(config_dir="config").to_dict()
        old_data = {
            "version": 0,
            "player": {"name": "远古道友"},
            "world": real_world,
        }
        os.makedirs(self.save_dir, exist_ok=True)
        path = os.path.join(self.save_dir, "old.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(old_data, f, ensure_ascii=False)
        loaded = self.sm.load(self.item_library, config_dir="config", slot="old")
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded[0].name, "远古道友")


if __name__ == "__main__":
    unittest.main(verbosity=2)
