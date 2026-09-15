import unittest

from game.player import Player
from game.world import World
from game.sect import SectLibrary, SectManager
from game.item import ItemLibrary
from game.skill import SkillLibrary
from game.enemy import EnemyLibrary
from game.follower import FollowerLibrary
from game.diplomatic_mission import DiplomaticMissionLibrary


class DummyWorld:
    """测试用世界对象，提供年月与地点查询。"""

    def __init__(self, year=1, month=1):
        self.year = year
        self.month = month

    def advance(self, months=1):
        """推进指定月数。"""
        total = self.year * 12 + self.month + months - 1
        self.year = total // 12
        self.month = total % 12 + 1

    def get_location(self, location_id):
        """返回测试地点数据。"""
        return {"id": location_id, "name": location_id}

    def get_realm(self, realm_id):
        """返回测试境界数据。"""
        return {"name": realm_id, "max_qi": 100, "breakthrough_rate": 0.5, "lifespan_bonus": 0}

    def next_realm(self, realm_id):
        """测试用境界后继。"""
        order = list(Player.REALM_ORDER.keys())
        if realm_id in order:
            idx = order.index(realm_id)
            if idx + 1 < len(order):
                return order[idx + 1]
        return None


class TestSectBounty(unittest.TestCase):
    """宗门悬赏榜单元测试。"""

    def setUp(self):
        """初始化测试所需的玩家与宗门管理器。"""
        self.player = Player("测试修士")
        self.world = DummyWorld(year=1, month=1)
        self.item_library = ItemLibrary(config_dir="config")
        self.skill_library = SkillLibrary(config_dir="config")
        self.enemy_library = EnemyLibrary(config_dir="config")
        self.sect_library = SectLibrary(config_dir="config")
        self.follower_library = FollowerLibrary(config_dir="config")
        self.diplomatic_mission_library = DiplomaticMissionLibrary(config_dir="config")
        self.manager = SectManager(
            self.player,
            self.sect_library,
            self.item_library,
            self.skill_library,
            self.enemy_library,
            self.follower_library,
            self.diplomatic_mission_library,
            self.world,
        )

    def _join_sect(self, sect_id="tianjian_sect"):
        """辅助方法：让玩家加入指定宗门。"""
        self.manager.join_sect(sect_id)

    def test_get_bounty_board_requires_sect(self):
        """未加入宗门时悬赏榜为空。"""
        self.assertEqual(self.manager.get_bounty_board(), [])

    def test_get_bounty_board_by_rank(self):
        """不同职位可接取的悬赏不同。"""
        self._join_sect()
        # 外门弟子只能看到 outer 悬赏
        board = self.manager.get_bounty_board()
        self.assertTrue(all(b["required_rank"] == "outer" for b in board))

        # 晋升为内门后应能看到 inner 悬赏
        self.player.sect_rank = "inner"
        board = self.manager.get_bounty_board()
        self.assertTrue(any(b["required_rank"] == "inner" for b in board))

    def test_accept_bounty(self):
        """接取悬赏后玩家状态正确。"""
        self._join_sect()
        bounty_id = self.manager.get_bounty_board()[0]["id"]
        ok, msg = self.manager.accept_bounty(bounty_id)
        self.assertTrue(ok, msg)
        self.assertIsNotNone(self.player.sect_active_bounty)
        self.assertEqual(self.player.sect_active_bounty["bounty_id"], bounty_id)
        self.assertEqual(self.player.sect_active_bounty["progress"], 0)

    def test_cannot_accept_multiple_bounties(self):
        """同时只能进行一个悬赏。"""
        self._join_sect()
        board = self.manager.get_bounty_board()
        self.manager.accept_bounty(board[0]["id"])
        ok, msg = self.manager.can_accept_bounty(board[0]["id"])
        self.assertFalse(ok)
        self.assertIn("已有一个进行中的悬赏", msg)

    def test_update_bounty_progress(self):
        """击杀目标敌人会推进悬赏进度。"""
        self._join_sect()
        bounty = self.manager.get_bounty_board()[0]
        self.manager.accept_bounty(bounty["id"])

        # 击杀非目标敌人不应推进进度
        result = self.manager.update_bounty_progress("tiger")
        self.assertIsNone(result)
        self.assertEqual(self.player.sect_active_bounty["progress"], 0)

        # 击杀目标敌人应推进进度
        target = bounty["target_enemy"]
        for _ in range(bounty["target_count"] - 1):
            result = self.manager.update_bounty_progress(target)
            self.assertIsNone(result)
            self.assertIsNotNone(self.player.sect_active_bounty)

        # 最后一次击杀应完成悬赏并发放奖励
        contribution_before = self.player.sect_contribution
        result = self.manager.update_bounty_progress(target)
        self.assertIsNotNone(result)
        ok, msg = result
        self.assertTrue(ok, msg)
        self.assertIsNone(self.player.sect_active_bounty)
        self.assertGreater(self.player.sect_contribution, contribution_before)

    def test_complete_bounty_no_active(self):
        """没有进行中的悬赏时无法完成。"""
        ok, msg = self.manager.complete_bounty()
        self.assertFalse(ok)
        self.assertIn("没有进行中的悬赏", msg)

    def test_leave_sect_clears_bounty(self):
        """退出宗门会清空当前悬赏。"""
        self._join_sect()
        board = self.manager.get_bounty_board()
        self.manager.accept_bounty(board[0]["id"])
        self.manager.leave_sect()
        self.assertIsNone(self.player.sect_active_bounty)


if __name__ == "__main__":
    unittest.main()
