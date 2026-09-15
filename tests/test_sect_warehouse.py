"""宗门仓库与捐献排行榜单元测试。"""
import os
import unittest

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


class TestSectWarehouse(unittest.TestCase):
    """宗门仓库与捐献排行榜相关测试用例。"""

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
        self.save_path = "test_warehouse_save.json"
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
        """加入天剑宗。"""
        self.engine.sect_manager.join_sect("tianjian_sect")

    def _give_item(self, item_id, count=1):
        """给玩家背包中添加指定数量的物品。"""
        for _ in range(count):
            item = self.item_lib.create(item_id)
            if item:
                self.player.add_item(item)

    def test_donate_item_goes_to_warehouse(self):
        """捐献物品应进入宗门仓库并增加累计捐献价值。"""
        self._join_sect()
        self._give_item("spirit_stone", 3)

        contribution_before = self.player.sect_contribution
        ok, msg = self.engine.sect_manager.donate_item("spirit_stone", 2)
        self.assertTrue(ok, msg)

        # 仓库中应有 2 个灵石
        self.assertEqual(self.player.sect_warehouse.get("spirit_stone"), 2)
        # 背包中应剩余 1 个
        self.assertEqual(self.player.count_item("spirit_stone"), 1)
        # 累计捐献价值 = 价值 10 × 2
        self.assertEqual(self.player.sect_donation_total, 20)
        # 贡献增加 = 10 × 2 × 0.5
        self.assertEqual(self.player.sect_contribution, contribution_before + 10)

    def test_donate_without_sect_fails(self):
        """未加入宗门时无法捐献。"""
        self._give_item("health_pill", 1)
        ok, msg = self.engine.sect_manager.donate_item("health_pill", 1)
        self.assertFalse(ok)
        self.assertIn("未加入", msg)

    def test_leaderboard_contains_player(self):
        """排行榜中应包含玩家条目。"""
        self._join_sect()
        leaderboard = self.engine.sect_manager.get_donation_leaderboard()
        player_entries = [e for e in leaderboard if e.get("is_player")]
        self.assertEqual(len(player_entries), 1)
        self.assertEqual(player_entries[0]["name"], self.player.name)

    def test_monthly_reward_for_first_place(self):
        """本月捐献排名第一时应发放奖励。"""
        self._join_sect()
        # 把玩家累计捐献拉到最高，确保排名第一
        self.player.sect_donation_total = 99999
        contribution_before = self.player.sect_contribution
        loyalty_before = self.player.sect_loyalty

        ok, msg = self.engine.sect_manager.check_monthly_donation_rewards(
            self.world.year, self.world.month
        )
        self.assertTrue(ok, msg)
        self.assertEqual(self.player.sect_contribution, contribution_before + 100)
        self.assertEqual(self.player.sect_loyalty, min(100, loyalty_before + 5))
        # 上月结算月份已更新
        self.assertEqual(
            self.player.sect_donation_last_reward_month,
            self.world.year * 12 + self.world.month,
        )

    def test_monthly_reward_only_once_per_month(self):
        """同一个月只能结算一次排行榜奖励。"""
        self._join_sect()
        self.player.sect_donation_total = 99999
        self.engine.sect_manager.check_monthly_donation_rewards(
            self.world.year, self.world.month
        )
        contribution_before = self.player.sect_contribution
        ok, msg = self.engine.sect_manager.check_monthly_donation_rewards(
            self.world.year, self.world.month
        )
        self.assertFalse(ok)
        self.assertEqual(msg, "")
        self.assertEqual(self.player.sect_contribution, contribution_before)

    def test_leave_sect_clears_warehouse(self):
        """退出宗门后仓库与累计捐献应清零。"""
        self._join_sect()
        self._give_item("demon_core", 2)
        self.engine.sect_manager.donate_item("demon_core", 2)
        self.assertGreater(self.player.sect_donation_total, 0)

        self.engine.sect_manager.leave_sect()
        self.assertEqual(self.player.sect_warehouse, {})
        self.assertEqual(self.player.sect_donation_total, 0)

    def test_warehouse_total_value(self):
        """仓库总价值应等于各物品价值 × 数量之和。"""
        self._join_sect()
        self.player.sect_warehouse = {
            "spirit_stone": 2,   # 价值 10
            "health_pill": 3,    # 价值 4
        }
        self.assertEqual(
            self.engine.sect_manager.get_warehouse_total_value(),
            10 * 2 + 4 * 3,
        )


if __name__ == "__main__":
    unittest.main()
