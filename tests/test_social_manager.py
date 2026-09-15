# -*- coding: utf-8 -*-
"""社交管理器单元测试：论道、双修、收徒、恩怨链。"""
import unittest

from game.player import Player
from game.npc import NPC, NPCLibrary
from game.world import World
from game.social_manager import SocialManager


class FixedRNG:
    """固定序列的伪随机数生成器。"""

    def __init__(self, values):
        self.values = list(values)
        self.index = 0

    def random(self):
        value = self.values[self.index % len(self.values)]
        self.index += 1
        return value

    def randint(self, a, b):
        value = self.values[self.index % len(self.values)]
        self.index += 1
        return a + int(value * (b - a))

    def uniform(self, a, b):
        value = self.values[self.index % len(self.values)]
        self.index += 1
        return a + value * (b - a)


class TestSocialManager(unittest.TestCase):
    """SocialManager 核心功能测试。"""

    def setUp(self):
        """初始化测试玩家、NPC 库与社交管理器。"""
        self.player = Player(name="测试修士")
        self.player.wisdom = 10
        self.player.gender = "male"
        self.player.realm_id = "foundation_early"
        self.player.max_qi = 1000
        self.player.qi = 0
        self.world = World(config_dir="config")
        self.npc_library = NPCLibrary(config_dir="config")
        self.manager = SocialManager(
            self.player, self.npc_library, self.world
        )
        # 创建测试用 NPC
        self.npc_female = NPC(
            npc_id="test_female",
            name="女修",
            location="qingyun",
            description="测试女修",
            dialog="你好",
            quests=[],
            gender="female",
            realm_id="qi_refining_5",
            wisdom=8,
            age=20,
        )
        self.npc_male = NPC(
            npc_id="test_male",
            name="男修",
            location="qingyun",
            description="测试男修",
            dialog="你好",
            quests=[],
            gender="male",
            realm_id="qi_refining_3",
            wisdom=6,
            age=18,
        )
        self.npc_library.npcs["test_female"] = self.npc_female
        self.npc_library.npcs["test_male"] = self.npc_male

    def test_debate_success(self):
        """论道胜利应提升好感度与悟性。"""
        # 玩家悟性 10 + roll 0.5，NPC 悟性 8 + roll 0.5，玩家胜
        rng = FixedRNG([0.5, 0.5])
        before_wisdom = self.player.wisdom
        success, msg, win = self.manager.debate("test_female", rng=rng)
        self.assertTrue(success)
        self.assertTrue(win)
        self.assertEqual(self.player.get_npc_relationship("test_female"), 1)
        self.assertEqual(self.player.debate_record["wins"], 1)

    def test_debate_failure(self):
        """论道失败应降低好感度。"""
        rng = FixedRNG([0.0, 1.0])
        success, msg, win = self.manager.debate("test_female", rng=rng)
        self.assertTrue(success)
        self.assertFalse(win)
        self.assertEqual(self.player.get_npc_relationship("test_female"), -1)
        self.assertEqual(self.player.debate_record["losses"], 1)

    def test_debate_with_grudge_blocked(self):
        """有恩怨时不可论道。"""
        self.player.add_grudge("test_female", 1, "测试恩怨")
        ok, msg = self.manager.can_debate("test_female")
        self.assertFalse(ok)
        self.assertIn("恩怨", msg)

    def test_dual_cultivate_requirements(self):
        """双修需要异性且好感度足够。"""
        # 同性不可双修
        ok, msg = self.manager.can_dual_cultivate("test_male")
        self.assertFalse(ok)
        self.assertIn("同性", msg)
        # 异性但好感度不足
        ok, msg = self.manager.can_dual_cultivate("test_female")
        self.assertFalse(ok)
        self.assertIn("好感度", msg)

    def test_dual_cultivate_success(self):
        """满足条件时双修应增加修为与好感度。"""
        self.player.increase_npc_relationship("test_female", 5)
        rng = FixedRNG([0.5])
        before_qi = self.player.qi
        success, msg = self.manager.dual_cultivate("test_female", rng=rng)
        self.assertTrue(success)
        self.assertGreater(self.player.qi, before_qi)
        self.assertEqual(self.player.get_npc_relationship("test_female"), 6)

    def test_accept_disciple_requires_higher_realm(self):
        """收徒需要玩家境界高于 NPC。"""
        self.player.increase_npc_relationship("test_male", 5)
        # 玩家筑基初期 vs NPC 练气五层，应可收徒
        ok, msg = self.manager.can_accept_disciple("test_male")
        self.assertTrue(ok)

    def test_accept_disciple_blocked_by_lower_realm(self):
        """玩家境界不高于 NPC 时不可收徒。"""
        self.player.increase_npc_relationship("test_male", 5)
        self.player.realm_id = "qi_refining_1"
        ok, msg = self.manager.can_accept_disciple("test_male")
        self.assertFalse(ok)
        self.assertIn("境界", msg)

    def test_accept_disciple(self):
        """成功收徒后应加入徒弟列表。"""
        self.player.increase_npc_relationship("test_male", 5)
        success, msg = self.manager.accept_disciple("test_male")
        self.assertTrue(success)
        self.assertEqual(len(self.player.disciples), 1)
        self.assertEqual(self.player.disciples[0]["npc_id"], "test_male")

    def test_teach_disciple(self):
        """教导徒弟应提升进度。"""
        self.player.disciples.append({
            "npc_id": "test_male",
            "name": "男修",
            "realm_id": "qi_refining_3",
            "progress": 0,
            "loyalty": 50,
        })
        success, msg = self.manager.teach_disciple("test_male")
        self.assertTrue(success)
        self.assertGreater(self.player.disciples[0]["progress"], 0)

    def test_grudge_and_resolve(self):
        """结怨与化解恩怨。"""
        success, msg = self.manager.add_grudge("test_male", "言语冲突")
        self.assertTrue(success)
        self.assertTrue(self.player.has_grudge("test_male"))
        # 好感度为负时不可化解
        self.player.decrease_npc_relationship("test_male", 10)
        ok, msg = self.manager.resolve_grudge("test_male")
        self.assertFalse(ok)
        # 提升好感度后化解
        self.player.increase_npc_relationship("test_male", 10)
        ok, msg = self.manager.resolve_grudge("test_male")
        self.assertTrue(ok)
        self.assertFalse(self.player.has_grudge("test_male"))

    def test_grudge_adds_revenge_target(self):
        """恩怨等级达到 3 时应加入复仇目标。"""
        self.manager.add_grudge("test_male", "重大冲突")
        self.manager.add_grudge("test_male", "再次冲突")
        self.manager.add_grudge("test_male", "第三次冲突")
        self.assertIn("test_male", self.player.revenge_targets)

    def test_tick_grudges_decay(self):
        """低等级恩怨应随时间衰减。"""
        self.player.grudges["test_male"] = {
            "level": 1, "reason": "小摩擦", "start_month": 0
        }
        self.world.month = 6
        events = self.manager.tick_grudges()
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["type"], "grudge_decay")
        self.assertFalse(self.player.has_grudge("test_male"))

    def test_on_npc_killed_clears_grudge(self):
        """击杀 NPC 后应清理恩怨，并使其亲友结怨。"""
        self.player.add_grudge("test_male", 1, "测试")
        self.player.revenge_targets.append("test_male")
        events = self.manager.on_npc_killed("test_male")
        self.assertFalse(self.player.has_grudge("test_male"))
        self.assertNotIn("test_male", self.player.revenge_targets)


if __name__ == "__main__":
    unittest.main()
