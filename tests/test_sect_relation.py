"""
宗门关系系统单元测试。
覆盖：NPC 价格修正、敌对/友好关系判定、NPC 界面禁用、显式 sect_id 优先、挑衅逻辑。
"""
import os
import unittest

from PySide6.QtWidgets import QApplication, QListWidgetItem
from PySide6.QtCore import Qt

from game.player import Player
from game.world import World
from game.events import EventPool
from game.item import ItemLibrary
from game.enemy import EnemyLibrary
from game.skill import SkillLibrary
from game.npc import NPCLibrary, NPC
from game.quest import QuestLibrary
from game.engine import GameEngine
from game.save_manager import SaveManager
from ui.npc_dialog import NPCDialog


class TestSectRelation(unittest.TestCase):
    """宗门关系相关测试用例。"""

    @classmethod
    def setUpClass(cls):
        # Qt 应用全局唯一
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
        self.save_path = "test_sect_save.json"
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

        self.herb = self.item_lib.get("century_herb")

    def tearDown(self):
        if os.path.exists(self.save_path):
            os.remove(self.save_path)

    # ---------------- 价格修正 ----------------

    def test_neutral_price_when_no_sect(self):
        """未加入宗门时，所有宗门 NPC 的宗门价格修正应为中性（1.0）。

        注意：最终售价还会受地点类型等因素影响，因此只校验宗门修正本身。
        """
        for npc_id in ["tianjian_elder", "zixiao_master", "xie_master"]:
            npc = self.npc_lib.get(npc_id)
            buy_mult, sell_mult = self.engine.get_sect_price_multiplier(npc)
            self.assertEqual(
                buy_mult,
                1.0,
                f"{npc.name} 购买宗门修正应在未入宗门时保持中性",
            )
            self.assertEqual(
                sell_mult,
                1.0,
                f"{npc.name} 出售宗门修正应在未入宗门时保持中性",
            )

    def test_same_sect_no_discount(self):
        """同宗门 NPC 保持原价。"""
        self.engine.sect_manager.join_sect("tianjian_sect")
        npc = self.npc_lib.get("tianjian_elder")
        base_buy = self.engine.get_buy_price("century_herb", None)
        base_sell = self.engine.get_sell_price(self.herb, None)
        self.assertEqual(self.engine.get_buy_price("century_herb", npc), base_buy)
        self.assertEqual(self.engine.get_sell_price(self.herb, npc), base_sell)

    def test_friendly_discount(self):
        """友好宗门 NPC 购买价格应低于基准。"""
        self.engine.sect_manager.join_sect("tianjian_sect")
        npc = self.npc_lib.get("zixiao_master")
        base_buy = self.engine.get_buy_price("century_herb", None)
        friendly_buy = self.engine.get_buy_price("century_herb", npc)
        self.assertLess(friendly_buy, base_buy, "友好宗门购买价应打折")

    def test_hostile_markup(self):
        """敌对宗门 NPC 购买涨价、出售压价。"""
        self.engine.sect_manager.join_sect("tianjian_sect")
        npc = self.npc_lib.get("xie_master")
        base_buy = self.engine.get_buy_price("century_herb", None)
        base_sell = self.engine.get_sell_price(self.herb, None)
        hostile_buy = self.engine.get_buy_price("century_herb", npc)
        hostile_sell = self.engine.get_sell_price(self.herb, npc)
        self.assertGreater(hostile_buy, base_buy, "敌对宗门购买价应加价")
        self.assertLess(hostile_sell, base_sell, "敌对宗门出售价应压价")

    # ---------------- 关系判定 ----------------

    def test_relation_status_bidirectional_hostile(self):
        """宗门敌对关系应双向生效：玩家在天剑宗，血魔宗配置敌对天剑宗即视为敌对。"""
        self.engine.sect_manager.join_sect("tianjian_sect")
        status = self.engine.sect_manager.get_relation_status("xie_mo_cult")
        self.assertEqual(status, "hostile")

    def test_relation_status_bidirectional_friendly(self):
        """宗门友好关系应双向生效。"""
        self.engine.sect_manager.join_sect("tianjian_sect")
        status = self.engine.sect_manager.get_relation_status("zixiao_palace")
        self.assertEqual(status, "friendly")

    # ---------------- 显式 sect_id 优先 ----------------

    def test_sect_id_priority_over_location(self):
        """NPC 的 sect_id 应优先于 location 用于宗门关系判定。"""
        self.engine.sect_manager.join_sect("tianjian_sect")
        # 构造一个 location 为天剑宗、但显式归属血魔宗的 NPC
        npc = NPC(
            npc_id="test_traitor",
            name="测试叛宗者",
            location="tianjian_sect",
            description="",
            dialog="",
            quests=[],
            sect_id="xie_mo_cult",
        )
        # 应按 sect_id 判定为敌对，购买价涨价
        base_buy = self.engine.get_buy_price("century_herb", None)
        hostile_buy = self.engine.get_buy_price("century_herb", npc)
        self.assertGreater(hostile_buy, base_buy)

    # ---------------- NPC 界面 ----------------

    def test_hostile_npc_blocks_quest_and_skill(self):
        """敌对宗门 NPC 的任务与技能列表应被禁用提示替代。"""
        self.engine.sect_manager.join_sect("tianjian_sect")
        dialog = NPCDialog(self.engine)

        npc = self.npc_lib.get("xie_master")
        item = QListWidgetItem(npc.name)
        item.setData(256, npc)
        dialog._on_npc_selected(item)

        self.assertEqual(dialog.quest_list.count(), 1)
        self.assertIn("无法接取任务", dialog.quest_list.item(0).text())
        self.assertEqual(dialog.skill_list.count(), 1)
        self.assertIn("无法拜师学技", dialog.skill_list.item(0).text())

    def test_friendly_npc_keeps_quest_and_skill(self):
        """友好/同宗门 NPC 的任务与技能列表正常显示。"""
        self.engine.sect_manager.join_sect("tianjian_sect")
        dialog = NPCDialog(self.engine)

        npc = self.npc_lib.get("tianjian_elder")
        item = QListWidgetItem(npc.name)
        item.setData(256, npc)
        dialog._on_npc_selected(item)

        self.assertGreater(dialog.quest_list.count(), 0)
        self.assertTrue(dialog.quest_list.item(0).flags() & Qt.ItemIsEnabled)
        self.assertGreater(dialog.skill_list.count(), 0)
        self.assertTrue(dialog.skill_list.item(0).flags() & Qt.ItemIsEnabled)

    # ---------------- 挑衅逻辑 ----------------

    def test_provoke_worsens_relation_and_adds_wanted(self):
        """挑衅敌对宗门 NPC 会降低关系并加入通缉。"""
        self.engine.sect_manager.join_sect("tianjian_sect")
        npc = self.npc_lib.get("xie_master")
        rel_before = self.engine.sect_manager.get_sect_relationship("xie_mo_cult")
        self.assertNotIn("xie_mo_cult", self.player.sect_wanted_by)

        # 固定随机数，避免概率触发战斗导致断言不稳定；这里只测非战斗分支
        import random
        old_random = random.random
        random.random = lambda: 0.9  # > 0.5 时触发非战斗分支
        try:
            combat = self.engine.provoke_sect_npc(npc)
        finally:
            random.random = old_random

        self.assertFalse(combat)
        rel_after = self.engine.sect_manager.get_sect_relationship("xie_mo_cult")
        self.assertLess(rel_after, rel_before)
        self.assertIn("xie_mo_cult", self.player.sect_wanted_by)


if __name__ == "__main__":
    unittest.main()
