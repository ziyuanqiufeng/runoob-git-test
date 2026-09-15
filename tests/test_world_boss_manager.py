"""世界 BOSS 管理器单元测试。"""
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
from game.world_boss import WorldBossManager


class TestWorldBossManager(unittest.TestCase):
    """世界 BOSS 刷新、战斗、奖励相关测试用例。"""

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
        self.save_path = "test_world_boss_save.json"
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
        self.manager = self.engine.world_boss_manager

    def tearDown(self):
        if os.path.exists(self.save_path):
            os.remove(self.save_path)

    def _reach_realm(self, realm_id):
        """将玩家境界提升到指定 ID。"""
        self.player.realm_id = realm_id

    def test_spawn_creates_active_boss(self):
        """手动刷新应在 world 中创建活跃 BOSS。"""
        boss_cfg = self.manager.spawn("ancient_qilin")
        self.assertIsNotNone(boss_cfg)
        self.assertIn("ancient_qilin", self.world.active_world_bosses)
        self.assertEqual(
            self.world.active_world_bosses["ancient_qilin"]["location"],
            "qingyun",
        )

    def test_tick_spawns_when_realm_met(self):
        """玩家境界达到要求后，tick 应首次刷新 BOSS。"""
        self._reach_realm("foundation_peak")  # order 13 >= 12
        self.assertEqual(len(self.manager.get_active_bosses()), 0)
        self.manager.tick(self.player)
        # 上古麒麟应出现，血魔尊者尚不满足 order 14
        self.assertIn("ancient_qilin", self.world.active_world_bosses)
        self.assertNotIn("blood_demon", self.world.active_world_bosses)

    def test_tick_does_not_spawn_below_realm(self):
        """境界不足时 tick 不应刷新 BOSS。"""
        self._reach_realm("foundation_early")  # order 10 < 12
        self.manager.tick(self.player)
        self.assertEqual(len(self.manager.get_active_bosses()), 0)

    def test_tick_respects_respawn_cooldown(self):
        """击败后未过重生月份不应重新刷新。"""
        self._reach_realm("golden_core_early")  # order 14
        self.manager.tick(self.player)
        self.assertIn("blood_demon", self.world.active_world_bosses)

        # 模拟击败，设置击败时间为当前月
        self.manager.defeat("blood_demon")
        self.assertNotIn("blood_demon", self.world.active_world_bosses)
        self.assertIn("blood_demon", self.world.defeated_world_bosses)

        # 下个月 tick，冷却 80 个月，不应刷新
        self.world.month += 1
        self.manager.tick(self.player)
        self.assertNotIn("blood_demon", self.world.active_world_bosses)

    def test_tick_respawns_after_cooldown(self):
        """击败后经过足够月份应重新刷新。"""
        self._reach_realm("golden_core_early")
        self.manager.tick(self.player)
        self.manager.defeat("blood_demon")

        # 推进 80 个月
        self.world.month += 80
        self.manager.tick(self.player)
        self.assertIn("blood_demon", self.world.active_world_bosses)

    def test_create_enemy_marks_boss_id(self):
        """根据 BOSS 配置创建敌人应带有 boss_id 与 BOSS 名。"""
        enemy = self.manager.create_enemy("ancient_qilin")
        self.assertIsNotNone(enemy)
        self.assertEqual(enemy.boss_id, "ancient_qilin")
        self.assertEqual(enemy.name, "上古麒麟残魂")

    def test_grant_defeat_rewards(self):
        """击败奖励应发放修为与配置物品。"""
        qi_before = self.player.qi
        messages, gained_names = self.manager.grant_defeat_rewards(
            self.player, self.item_lib, "ancient_qilin"
        )
        # 参与奖励含 100 修为
        self.assertEqual(self.player.qi, qi_before + 100)
        self.assertIn("修为 +100", messages)
        # 掉落与参与奖励物品应进入背包
        self.assertTrue(len(gained_names) > 0)
        self.assertTrue(any("灵石" in name for name in gained_names))

    def test_defeat_records_time(self):
        """击败后应清除活跃状态并记录击败月份。"""
        self._reach_realm("foundation_peak")
        self.manager.tick(self.player)
        self.assertIn("ancient_qilin", self.world.active_world_bosses)

        current_month = self.world.year * 12 + self.world.month
        self.assertTrue(self.manager.defeat("ancient_qilin"))
        self.assertNotIn("ancient_qilin", self.world.active_world_bosses)
        self.assertEqual(
            self.world.defeated_world_bosses["ancient_qilin"],
            current_month,
        )

    def test_get_active_bosses_by_location(self):
        """按地点过滤应只返回该地点的活跃 BOSS。"""
        self._reach_realm("foundation_peak")
        self.manager.tick(self.player)
        qingyun_bosses = self.manager.get_active_bosses(location_id="qingyun")
        self.assertEqual(len(qingyun_bosses), 1)
        self.assertEqual(qingyun_bosses[0]["id"], "ancient_qilin")

    def test_engine_finish_world_boss_combat_win(self):
        """Engine 在世界 BOSS 战斗胜利后应发放奖励并移除 BOSS。"""
        self._reach_realm("foundation_peak")
        self.manager.tick(self.player)
        self.engine.pending_world_boss_id = "ancient_qilin"
        qi_before = self.player.qi

        self.engine.finish_world_boss_combat("win")

        self.assertGreater(self.player.qi, qi_before)
        self.assertNotIn("ancient_qilin", self.world.active_world_bosses)
        self.assertIsNone(self.engine.pending_world_boss_id)

    def test_engine_finish_world_boss_combat_lose(self):
        """Engine 在世界 BOSS 战斗失败后不应发放奖励。"""
        self._reach_realm("foundation_peak")
        self.manager.tick(self.player)
        self.engine.pending_world_boss_id = "ancient_qilin"
        qi_before = self.player.qi

        self.engine.finish_world_boss_combat("lose")

        self.assertEqual(self.player.qi, qi_before)
        # 失败后 BOSS 仍活跃
        self.assertIn("ancient_qilin", self.world.active_world_bosses)
        self.assertIsNone(self.engine.pending_world_boss_id)


if __name__ == "__main__":
    unittest.main()
