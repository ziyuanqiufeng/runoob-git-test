"""宗门灵兽园与坐骑单元测试。"""
import os
import unittest
from unittest.mock import patch

from PySide6.QtWidgets import QApplication

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


class TestSectBeastGarden(unittest.TestCase):
    """灵兽园相关测试用例。"""

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.item_lib = ItemLibrary(config_dir="config")
        self.enemy_lib = EnemyLibrary(config_dir="config")
        self.skill_lib = SkillLibrary(config_dir="config")
        self.npc_lib = NPCLibrary(config_dir="config")
        self.quest_lib = QuestLibrary(config_dir="config")

        self.player = Player(name="测试修士")
        self.world = World(config_dir="config")
        self.event_pool = EventPool(config_dir="config")
        self.save_path = "test_sect_beast_save.json"
        self.engine = GameEngine(
            self.player,
            self.world,
            self.event_pool,
            self.item_lib,
            self.enemy_lib,
            self.skill_lib,
            self.npc_lib,
            self.quest_lib,
            save_manager=SaveManager(save_path=self.save_path),
        )

    def tearDown(self):
        if os.path.exists(self.save_path):
            os.remove(self.save_path)

    def _join_sect(self):
        """加入天剑宗并提升到内门弟子，给予足够贡献。"""
        self.engine.sect_manager.join_sect("tianjian_sect")
        self.player.sect_rank = "inner"
        self.player.sect_contribution = 10000
        self.player.sect_loyalty = 100

    def test_get_available_beasts_requires_sect(self):
        """未加入宗门时灵兽列表为空。"""
        self.assertEqual(self.engine.sect_manager.get_available_beasts(), [])

    def test_get_available_beasts_after_join(self):
        """加入宗门后可看到本宗灵兽。"""
        self._join_sect()
        beasts = self.engine.sect_manager.get_available_beasts()
        self.assertEqual(len(beasts), 3)
        self.assertEqual(beasts[0]["id"], "tianjian_sword_eagle")

    def test_can_adopt_requires_sect(self):
        """未加入宗门不能领养。"""
        ok, msg = self.engine.sect_manager.can_adopt_beast("tianjian_sword_eagle")
        self.assertFalse(ok)
        self.assertIn("尚未加入", msg)

    def test_can_adopt_requires_rank(self):
        """职位不足不能领养高阶灵兽。"""
        self._join_sect()
        ok, msg = self.engine.sect_manager.can_adopt_beast("tianjian_cloud_tiger")
        self.assertFalse(ok)
        self.assertIn("职位", msg)

    def test_can_adopt_requires_contribution(self):
        """贡献不足不能领养。"""
        self._join_sect()
        self.player.sect_contribution = 0
        ok, msg = self.engine.sect_manager.can_adopt_beast("tianjian_sword_eagle")
        self.assertFalse(ok)
        self.assertIn("贡献", msg)

    def test_can_adopt_full_capacity(self):
        """灵兽栏满后不能领养。"""
        self._join_sect()
        # 天剑宗灵兽栏上限为 3
        self.engine.sect_manager.adopt_beast("tianjian_sword_eagle")
        self.engine.sect_manager.adopt_beast("tianjian_spirit_deer")
        self.engine.sect_manager.adopt_beast("tianjian_cloud_tiger")  # 需要 core，但 capacity 检查在 rank 之前？不，rank 检查先
        # 换一个方式：直接塞满 beasts 列表
        self.player.beasts = [
            {"beast_id": f"fake_{i}"} for i in range(3)
        ]
        ok, msg = self.engine.sect_manager.can_adopt_beast("tianjian_sword_eagle")
        self.assertFalse(ok)
        self.assertIn("已满", msg)

    def test_adopt_beast_success(self):
        """成功领养灵兽。"""
        self._join_sect()
        con_before = self.player.sect_contribution
        ok, msg = self.engine.sect_manager.adopt_beast("tianjian_sword_eagle")
        self.assertTrue(ok, msg)
        self.assertEqual(self.player.sect_contribution, con_before - 3000)
        self.assertEqual(len(self.player.beasts), 1)
        self.assertEqual(self.player.beasts[0]["beast_id"], "tianjian_sword_eagle")
        self.assertEqual(self.player.beasts[0]["type"], "combat")

    def test_cannot_adopt_duplicate(self):
        """同一灵兽不能重复领养。"""
        self._join_sect()
        self.engine.sect_manager.adopt_beast("tianjian_sword_eagle")
        ok, msg = self.engine.sect_manager.can_adopt_beast("tianjian_sword_eagle")
        self.assertFalse(ok)
        self.assertIn("已经拥有", msg)

    def test_release_beast(self):
        """放生灵兽。"""
        self._join_sect()
        self.engine.sect_manager.adopt_beast("tianjian_sword_eagle")
        ok, msg = self.engine.sect_manager.release_beast("tianjian_sword_eagle")
        self.assertTrue(ok, msg)
        self.assertEqual(len(self.player.beasts), 0)

    def test_combat_bonus(self):
        """战斗型灵兽提供攻击加成。"""
        self._join_sect()
        self.engine.sect_manager.adopt_beast("tianjian_sword_eagle")
        self.assertEqual(self.engine.sect_manager.get_beast_combat_bonus(), 10)

    def test_mount_bonus(self):
        """坐骑型灵兽提供赶路减免。"""
        self._join_sect()
        self.player.sect_rank = "core"
        self.engine.sect_manager.adopt_beast("tianjian_cloud_tiger")
        self.assertEqual(self.engine.sect_manager.get_beast_mount_bonus(), 1)

    def test_resource_bonus(self):
        """资源型灵兽概率产出资源。"""
        self._join_sect()
        self.engine.sect_manager.adopt_beast("tianjian_spirit_deer")
        with patch("game.sect.random.random", return_value=0.0):
            drops = self.engine.sect_manager.get_beast_resource_bonus()
        self.assertEqual(len(drops), 1)
        self.assertEqual(drops[0][0], "century_herb")


if __name__ == "__main__":
    unittest.main()
