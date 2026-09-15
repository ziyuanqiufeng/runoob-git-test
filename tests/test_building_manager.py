# -*- coding: utf-8 -*-
"""城池建筑与声望系统测试。

验证 BuildingManager 对建筑等级、城池声望、升级条件的计算，
以及与 engine 中任务、炼丹、演武场等系统的联动。
"""
import os
import unittest

from game.player import Player
from game.world import World
from game.events import EventPool
from game.item import ItemLibrary
from game.enemy import Enemy, EnemyLibrary
from game.skill import SkillLibrary
from game.npc import NPCLibrary
from game.quest import QuestLibrary
from game.engine import GameEngine
from game.save_manager import SaveManager
from game.building_manager import BuildingManager


class TestBuildingManager(unittest.TestCase):
    """城池建筑管理器单元测试。"""

    def setUp(self):
        """每个测试用例初始化独立的玩家与世界。"""
        self.item_lib = ItemLibrary(config_dir="config")
        self.player = Player(name="测试修士")
        self.world = World(config_dir="config")
        self.manager = BuildingManager(self.player, self.world, config_dir="config")

    def test_default_building_level(self):
        """未升级过的建筑默认等级应为 1。"""
        level = self.manager.get_building_level("alchemy_pavilion")
        self.assertEqual(level, 1)

    def test_max_level(self):
        """应能正确读取配置中的最高等级。"""
        # 炼丹阁配置有 3 个等级
        self.assertEqual(self.manager.get_max_level("alchemy_pavilion"), 3)
        # 水族商行配置有 2 个等级
        self.assertEqual(self.manager.get_max_level("aquatic_shop"), 2)

    def test_current_effects(self):
        """默认等级应返回对应效果。"""
        effects = self.manager.get_current_effects("alchemy_pavilion")
        self.assertIn("success_rate_bonus", effects)
        self.assertIn("unlock_recipes", effects)

    def test_reputation_gain_and_level(self):
        """增加声望后应正确计算声望等级。"""
        city_id = "qingyun"
        # 初始为陌生
        self.assertEqual(self.manager.get_reputation_level(city_id), "陌生")
        self.manager.gain_city_reputation(city_id, 100)
        self.assertEqual(self.manager.get_city_reputation(city_id), 100)
        self.assertEqual(self.manager.get_reputation_level(city_id), "友善")
        self.manager.gain_city_reputation(city_id, 300)
        self.assertEqual(self.manager.get_reputation_level(city_id), "尊敬")
        self.manager.gain_city_reputation(city_id, 300)
        self.assertEqual(self.manager.get_reputation_level(city_id), "崇拜")

    def test_reputation_never_negative(self):
        """声望扣减不应低于 0。"""
        self.manager.gain_city_reputation("qingyun", -50)
        self.assertEqual(self.manager.get_city_reputation("qingyun"), 0)

    def test_can_upgrade_missing_next_level(self):
        """超过最高等级后不可升级。"""
        self.player.building_levels["aquatic_shop"] = 2
        ok, reason = self.manager.can_upgrade("aquatic_shop", "xuanshui")
        self.assertFalse(ok)
        self.assertIn("最高等级", reason)

    def test_can_upgrade_realm_not_met(self):
        """境界不足时应阻止升级。"""
        # 炼丹阁 2 级需要 realm_order >= 4
        self.player.realm_id = "qi_refining_1"
        self.manager.gain_city_reputation("qingyun", 9999)
        ok, reason = self.manager.can_upgrade("alchemy_pavilion", "qingyun")
        self.assertFalse(ok)
        self.assertIn("境界", reason)

    def test_can_upgrade_reputation_not_met(self):
        """城池声望不足时应阻止升级。"""
        # 炼丹阁 2 级需要声望 100
        self.player.realm_id = "qi_refining_4"
        ok, reason = self.manager.can_upgrade("alchemy_pavilion", "qingyun")
        self.assertFalse(ok)
        self.assertIn("声望", reason)

    def test_can_upgrade_material_not_met(self):
        """材料不足时应阻止升级。"""
        self.player.realm_id = "qi_refining_4"
        self.manager.gain_city_reputation("qingyun", 100)
        ok, reason = self.manager.can_upgrade("alchemy_pavilion", "qingyun")
        self.assertFalse(ok)
        self.assertIn("材料不足", reason)

    def test_upgrade_building_success(self):
        """满足条件时应成功升级并扣除材料。"""
        self.player.realm_id = "qi_refining_4"
        self.manager.gain_city_reputation("qingyun", 100)
        # 添加足够灵石与低阶灵草
        for _ in range(500):
            self.player.add_item(self.item_lib.create("spirit_stone"))
        for _ in range(20):
            self.player.add_item(self.item_lib.create("low_herb"))

        ok, msg = self.manager.upgrade_building("alchemy_pavilion", "qingyun")
        self.assertTrue(ok)
        self.assertIn("升级", msg)
        self.assertEqual(self.manager.get_building_level("alchemy_pavilion"), 2)
        # 材料应被扣除
        self.assertEqual(self.player.count_item("spirit_stone"), 0)
        self.assertEqual(self.player.count_item("low_herb"), 0)

    def test_upgrade_building_locked_by_realm(self):
        """不满足条件时升级应失败。"""
        ok, msg = self.manager.upgrade_building("alchemy_pavilion", "qingyun")
        self.assertFalse(ok)
        self.assertEqual(self.manager.get_building_level("alchemy_pavilion"), 1)

    def test_building_effects_after_upgrade(self):
        """升级后建筑效果应更新。"""
        self.player.realm_id = "qi_refining_4"
        self.manager.gain_city_reputation("qingyun", 100)
        for _ in range(500):
            self.player.add_item(self.item_lib.create("spirit_stone"))
        for _ in range(20):
            self.player.add_item(self.item_lib.create("low_herb"))

        self.manager.upgrade_building("alchemy_pavilion", "qingyun")
        effects = self.manager.get_current_effects("alchemy_pavilion")
        self.assertEqual(effects.get("success_rate_bonus"), 0.05)
        self.assertIn("foundation_pill_recipe", effects.get("unlock_recipes", []))


class TestBuildingManagerPersistence(unittest.TestCase):
    """验证玩家数据中的声望与建筑等级可正确序列化/反序列化。"""

    def setUp(self):
        self.item_lib = ItemLibrary(config_dir="config")
        self.player = Player(name="测试修士")
        self.world = World(config_dir="config")

    def test_save_load_roundtrip(self):
        """保存并加载后声望与建筑等级应保持不变。"""
        self.player.city_reputation["qingyun"] = 150
        self.player.building_levels["alchemy_pavilion"] = 2
        data = self.player.to_dict()
        restored = Player.from_dict(data, self.item_lib)
        self.assertEqual(restored.city_reputation.get("qingyun"), 150)
        self.assertEqual(restored.building_levels.get("alchemy_pavilion"), 2)

    def test_save_version_in_new_save(self):
        """新玩家存档应包含当前版本号。"""
        data = self.player.to_dict()
        self.assertEqual(data.get("save_version"), Player.SAVE_VERSION)

    def test_old_save_migration(self):
        """旧存档（无 save_version/city_reputation/building_levels）应被迁移。"""
        # 模拟一个缺少新字段的旧存档
        data = self.player.to_dict()
        del data["save_version"]
        del data["city_reputation"]
        del data["building_levels"]
        restored = Player.from_dict(data, self.item_lib)
        self.assertEqual(restored.save_version, Player.SAVE_VERSION)
        self.assertEqual(restored.city_reputation, {})
        self.assertEqual(restored.building_levels, {})

    def test_player_default_portrait(self):
        """新玩家应拥有默认主角头像路径。"""
        self.assertTrue(self.player.portrait)
        self.assertIn("protagonist_default.png", self.player.portrait)

    def test_portrait_save_load_roundtrip(self):
        """主角头像路径应正确序列化与反序列化。"""
        self.player.portrait = "assets/portraits/custom.png"
        data = self.player.to_dict()
        restored = Player.from_dict(data, self.item_lib)
        self.assertEqual(restored.portrait, "assets/portraits/custom.png")

    def test_old_save_portrait_migration(self):
        """旧存档缺少 portrait 字段时应补全默认值。"""
        data = self.player.to_dict()
        del data["save_version"]
        del data["portrait"]
        restored = Player.from_dict(data, self.item_lib)
        self.assertTrue(restored.portrait)
        self.assertIn("protagonist_default.png", restored.portrait)


class TestBuildingReputationSources(unittest.TestCase):
    """验证城池声望的其他获取途径。"""

    def setUp(self):
        """构造完整 GameEngine 以调用 engine 级声望接口。"""
        self.item_lib = ItemLibrary(config_dir="config")
        self.enemy_lib = EnemyLibrary(config_dir="config")
        self.skill_lib = SkillLibrary(config_dir="config")
        self.npc_lib = NPCLibrary(config_dir="config")
        self.quest_lib = QuestLibrary(config_dir="config")
        self.player = Player(name="测试修士")
        self.world = World(config_dir="config")
        self.event_pool = EventPool(config_dir="config")
        self.save_path = "test_building_reputation_save.json"
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

    def test_donate_to_city_success(self):
        """捐赠物品应扣除背包并增加城池声望。"""
        self.player.location_id = "qingyun"
        for _ in range(10):
            self.player.add_item(self.item_lib.create("spirit_stone"))
        # 灵石价值 10，捐 10 个应获得 10 声望
        ok, rep = self.engine.donate_to_city("spirit_stone", 10)
        self.assertTrue(ok)
        self.assertEqual(rep, 10)
        self.assertEqual(self.player.count_item("spirit_stone"), 0)
        self.assertEqual(self.engine.building_manager.get_city_reputation("qingyun"), 10)

    def test_donate_to_city_insufficient_items(self):
        """物品不足时捐赠应失败。"""
        self.player.location_id = "qingyun"
        ok, rep = self.engine.donate_to_city("spirit_stone", 10)
        self.assertFalse(ok)
        self.assertEqual(rep, 0)
        self.assertEqual(self.engine.building_manager.get_city_reputation("qingyun"), 0)

    def test_defense_combat_reputation(self):
        """城池防卫战胜利后应根据敌人强度获得声望。"""
        self.player.location_id = "qingyun"
        enemy_data = self.enemy_lib.get("wolf")
        enemy = Enemy.from_dict(enemy_data)
        rep = self.engine.gain_city_reputation_from_defense(enemy, city_id="qingyun")
        self.assertGreater(rep, 0)
        self.assertEqual(self.engine.building_manager.get_city_reputation("qingyun"), rep)

    def test_city_defense_flag_set_and_cleared(self):
        """start_combat 应正确设置/清除城池防卫战标记。"""
        enemy_data = self.enemy_lib.get("wolf")
        enemy = Enemy.from_dict(enemy_data)
        self.engine.start_combat(enemy, is_city_defense=True)
        self.assertTrue(self.engine.current_combat_is_city_defense)
        self.engine.end_combat()
        self.assertFalse(self.engine.current_combat_is_city_defense)


if __name__ == "__main__":
    unittest.main()
