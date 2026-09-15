# -*- coding: utf-8 -*-
"""扩展系统单元与集成测试。

覆盖成就、年表、支线任务、悬赏板、图鉴、声望、心法、灵植、
拍卖行、神通、个人灵兽、秘境、遗迹、世界 BOSS、传送阵、战斗扩展、
信件传闻、师徒等管理器，以及 engine.py 中的事件钩子。
"""
import os
import unittest
from unittest.mock import patch

from PySide6.QtWidgets import QApplication

from game.player import Player
from game.world import World
from game.events import EventPool
from game.item import ItemLibrary
from game.enemy import Enemy, EnemyLibrary
from game.skill import SkillLibrary
from game.npc import NPC, NPCLibrary
from game.quest import QuestLibrary
from game.engine import GameEngine
from game.save_manager import SaveManager
from game.achievement import AchievementManager
from game.chronicle import ChronicleManager
from game.side_quest import SideQuestManager
from game.bounty_board import BountyBoardManager
from game.compendium import CompendiumManager
from game.reputation import ReputationManager
from game.mind_method import MindMethodManager
from game.farm import FarmManager
from game.auction_house import AuctionHouseManager
from game.divine_art import DivineArtManager
from game.personal_beast import PersonalBeastManager
from game.secret_realm import SecretRealmManager
from game.ruin import RuinManager
from game.world_boss import WorldBossManager
from game.teleport import TeleportManager
from game.combat_extension import CombatExtensionManager
from game.letter_rumor import LetterRumorManager
from game.master_disciple import MasterDiscipleManager
from game.economy import EconomyConfig


class TestExtensionManagers(unittest.TestCase):
    """各扩展管理器的独立单元测试。"""

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.item_lib = ItemLibrary(config_dir="config")
        self.player = Player(name="测试修士")
        self.world = World(config_dir="config")

    def test_achievement_kill_count(self):
        """击杀计数成就应正确触发。"""
        mgr = AchievementManager(self.player, self.item_lib)
        # 未发生击杀事件时，进度为 0，不应解锁
        self.assertEqual(self.player.achievement_progress.get("kill_count", 0), 0)
        # 第一次击杀事件触发成就（旧 first_kill 与 F-06 新增的青铜击杀成就均可能解锁）
        unlocked = mgr.check("kill")
        ids = [u[0] for u in unlocked]
        self.assertIn("first_kill", ids)
        self.assertTrue(any(u[0].startswith("a_bronze") for u in unlocked))
        # 已解锁的成就不再重复触发
        self.assertFalse(mgr.check("kill"))

    def test_chronicle_record(self):
        """年表应记录时间、年龄与文本。"""
        mgr = ChronicleManager(self.player, self.world)
        mgr.record("测试事件", category="test")
        self.assertEqual(len(self.player.chronicle), 1)
        entry = self.player.chronicle[0]
        self.assertEqual(entry["text"], "测试事件")
        self.assertEqual(entry["category"], "test")
        self.assertEqual(entry["year"], self.world.year)

    def test_side_quest_accept_and_progress(self):
        """支线任务接取与进度推进。"""
        mgr = SideQuestManager(self.player, self.item_lib)
        # 清剿狼患任务在青云可接
        ok, msg = mgr.accept("side_hunt_wolves")
        self.assertTrue(ok)
        self.assertIn("清剿狼患", msg)

        # 推进击杀进度
        completed = mgr.update_progress("kill", enemy_id="wolf", count=5)
        self.assertIn("side_hunt_wolves", completed)
        self.assertIn("side_hunt_wolves", self.player.completed_side_quests)

    def test_bounty_accept_and_complete(self):
        """悬赏板接取与完成。"""
        mgr = BountyBoardManager(self.player, self.item_lib, self.world)
        mgr.refresh()
        available = mgr.get_available()
        self.assertGreater(len(available), 0)

        bid = available[0]["bounty_id"]
        ok, msg = mgr.accept(bid)
        self.assertTrue(ok)
        self.assertEqual(len(self.player.active_bounties), 1)

        # 完成悬赏：按目标数量累计击杀
        enemy_id = available[0]["enemy_id"]
        target_count = available[0]["count"]
        completed = []
        for _ in range(target_count):
            completed = mgr.update_kill(enemy_id)
        self.assertEqual(len(completed), 1)
        self.assertEqual(len(self.player.active_bounties), 0)

    def test_compendium_record(self):
        """图鉴应正确记录敌人、物品、技能。"""
        mgr = CompendiumManager(self.player)
        mgr.record_enemy("wolf")
        mgr.record_enemy("wolf")
        mgr.record_item("spirit_stone")
        mgr.record_skill("fireball")

        self.assertEqual(self.player.bestiary.get("wolf"), 2)
        self.assertIn("spirit_stone", self.player.item_compendium)
        self.assertIn("fireball", self.player.skill_compendium)

        completion = mgr.get_completion()
        self.assertEqual(completion["enemies"], 1)
        self.assertEqual(completion["items"], 1)
        self.assertEqual(completion["skills"], 1)

    def test_reputation_adjust_and_level(self):
        """声望调整与等级称号计算。"""
        mgr = ReputationManager(self.player)
        val, title = mgr.adjust("qingyun_reputation", 350)
        self.assertEqual(val, 350)
        self.assertEqual(title, "青云义士")
        self.assertEqual(mgr.get_discount("qingyun_reputation"), 0.3)


class TestEngineEventHooks(unittest.TestCase):
    """Engine 事件钩子的集成测试。"""

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
        self.save_path = "test_extensions_save.json"
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

    def _create_weak_enemy(self, enemy_id="test_enemy", alignment="neutral"):
        return Enemy.from_dict({
            "id": enemy_id,
            "name": "测试敌人",
            "alignment": alignment,
            "hp": 1,
            "attack": 1,
            "defense": 0,
            "exp": 0,
            "loot": [],
        })

    def test_kill_enemy_hooks(self):
        """击杀敌人应触发图鉴、成就、年表等钩子。"""
        enemy = self._create_weak_enemy(enemy_id="wolf")
        self.player.base_attack = 100
        self.player.health = 100
        self.engine.start_combat(enemy)

        with patch("game.engine.random.random", return_value=0.9):
            logs, result = self.engine.combat_round(enemy, "attack")
        self.assertEqual(result, "win")

        # 图鉴记录
        self.assertEqual(self.player.bestiary.get("wolf"), 1)
        # 年表记录
        self.assertTrue(
            any("斩杀" in e["text"] for e in self.player.chronicle)
        )
        # 战斗统计
        self.assertGreater(self.player.combat_stats["wins"], 0)

    def test_kill_righteous_affects_reputation(self):
        """击杀正道敌人应提升魔道声望。"""
        enemy = self._create_weak_enemy(enemy_id="righteous_test", alignment="righteous")
        self.player.base_attack = 100
        self.player.health = 100
        self.engine.start_combat(enemy)

        with patch("game.engine.random.random", return_value=0.9):
            logs, result = self.engine.combat_round(enemy, "attack")
        self.assertEqual(result, "win")

        self.assertGreater(
            self.player.reputation.get("demonic_reputation", 0), 0
        )

    def test_gain_item_hooks(self):
        """获得物品应触发图鉴与支线任务进度。"""
        # 先接取送药委托
        self.engine.side_quest_manager.accept("side_herb_delivery")
        # 给予百年灵草
        for _ in range(3):
            item = self.item_lib.create("century_herb")
            self.player.add_item(item)
            self.engine._on_gain_item("century_herb", 1)

        self.assertIn("century_herb", self.player.item_compendium)
        self.assertIn("side_herb_delivery", self.player.completed_side_quests)

    def test_learn_skill_hooks(self):
        """习得技能应触发图鉴钩子。"""
        self.player.learn_skill("fireball")
        self.engine._on_learn_skill("fireball")
        self.assertIn("fireball", self.player.skill_compendium)

    def test_travel_hooks(self):
        """旅行应触发年表与支线进度。"""
        # 先完成内门考核，解锁九渊森林
        self.player.completed_quests.append("inner_disciple")
        # 先接取寻找走失弟子任务
        self.engine.side_quest_manager.accept("side_find_disciple")
        self.engine.travel("jiuyuan_senlin")

        self.assertTrue(
            any("抵达" in e["text"] for e in self.player.chronicle)
        )
        self.assertIn("side_find_disciple", self.player.completed_side_quests)

    def test_complete_quest_hooks(self):
        """完成任务应触发年表钩子。"""
        # 使用配置中存在的任务，模拟其已在进行中
        quest_id = "kill_wolves"
        self.player.quest_progress[quest_id] = 0
        # 手动调用完成
        self.engine.complete_quest(quest_id)
        self.assertTrue(
            any("完成任务" in e["text"] for e in self.player.chronicle)
        )


class TestOtherExtensionManagers(unittest.TestCase):
    """其他扩展管理器的单元测试（心法、灵植、拍卖行、探索、社交等）。"""

    def setUp(self):
        self.item_lib = ItemLibrary(config_dir="config")
        self.enemy_lib = EnemyLibrary(config_dir="config")
        self.npc_lib = NPCLibrary(config_dir="config")
        self.player = Player(name="测试修士")
        self.world = World(config_dir="config")

    def _give_stones(self, count):
        """给玩家一定数量的灵石。"""
        for _ in range(count):
            item = self.item_lib.create("spirit_stone")
            if item:
                self.player.add_item(item)

    def test_mind_method_learn_and_equip(self):
        """心法学习与装备应提供修炼加成。"""
        mgr = MindMethodManager(self.player)
        # 清心诀无属性限制，炼气一层即可学习
        ok, msg = mgr.learn("clear_mind_method")
        self.assertTrue(ok, msg)
        self.assertIn("clear_mind_method", self.player.learned_mind_methods)

        ok, msg = mgr.equip("clear_mind_method")
        self.assertTrue(ok, msg)
        self.assertEqual(self.player.equipped_mind_method, "clear_mind_method")
        self.assertGreater(mgr.get_cultivation_speed_bonus(), 0)

    def test_farm_grow_and_harvest(self):
        """灵植应能生长并收获。"""
        mgr = FarmManager(self.player, self.item_lib, self.world)
        # 春季（4 月）种植百年灵草， growth=2 + watered=1 即可成熟
        self.world.month = 4
        self.player.farm_plots = [{
            "crop_id": "century_herb_crop",
            "growth": 2,
            "state": "growing",
            "watered": True,
        }]
        logs = mgr.tick_monthly()
        self.assertTrue(any("成熟" in log for log in logs), logs)

        ok, msg = mgr.harvest(0)
        self.assertTrue(ok, msg)
        self.assertGreater(self.player.count_item("century_herb"), 0)

    def test_farm_plant_requires_seed(self):
        """播种应消耗种子，缺少种子时失败。"""
        mgr = FarmManager(self.player, self.item_lib, self.world)
        # 没有种子时不能种植
        ok, msg = mgr.plant(0, "century_herb_crop")
        self.assertFalse(ok)

        # 给予种子后应能种植
        for _ in range(3):
            item = self.item_lib.create("century_herb_seed")
            if item:
                self.player.add_item(item)
        ok, msg = mgr.plant(0, "century_herb_crop")
        self.assertTrue(ok, msg)
        self.assertEqual(self.player.count_item("century_herb_seed"), 2)

    def test_auction_house_bid_and_settle(self):
        """拍卖行应能出价并结算获得物品。"""
        self._give_stones(100)
        mgr = AuctionHouseManager(self.player, self.item_lib, self.world)
        mgr.refresh(lot_pool=["jade_pendant"], count=1)
        lots = mgr.get_lots()
        self.assertEqual(len(lots), 1)

        base_price = lots[0]["current_price"]
        ok, msg = mgr.bid(0, base_price + 10)
        self.assertTrue(ok, msg)

        ok, msg = mgr.settle(0)
        self.assertTrue(ok, msg)
        self.assertEqual(self.player.count_item("jade_pendant"), 1)

    def test_divine_art_learn(self):
        """满足境界与悟道点后应能领悟神通。"""
        self.player.realm_id = "foundation_peak"
        self.player.enlightenment_points = 10
        mgr = DivineArtManager(self.player)
        ok, msg = mgr.learn("thunder_law")
        self.assertTrue(ok, msg)
        self.assertIn("thunder_law", self.player.divine_arts)
        self.assertGreater(mgr.get_element_damage_bonus("metal"), 0)

    def test_personal_beast_capture_and_bonus(self):
        """捕捉个人灵兽应提供对应战斗加成。"""
        mgr = PersonalBeastManager(self.player, self.item_lib)
        ok, msg = mgr.capture("wolf", "小青", "combat")
        self.assertTrue(ok, msg)
        self.assertEqual(len(self.player.personal_beasts), 1)
        self.assertEqual(mgr.get_combat_bonus(), 2)

    def test_secret_realm_unlock_and_enter(self):
        """秘境解锁、进入与敌人生成。"""
        self.player.realm_id = "qi_refining_5"
        mgr = SecretRealmManager(self.player, self.enemy_lib, self.item_lib)
        ok, msg = mgr.unlock("fire_realm")
        self.assertTrue(ok, msg)
        self.assertIn("fire_realm", self.player.unlocked_secret_realms)

        ok, msg = mgr.can_enter("fire_realm")
        self.assertTrue(ok, msg)

        enemies = mgr.generate_floor_enemies("fire_realm", 0)
        self.assertGreater(len(enemies), 0)
        self.assertIsNotNone(mgr.get_boss("fire_realm"))

    def test_ruin_explore_cooldown(self):
        """遗迹探索应记录冷却时间。"""
        self.player.realm_id = "qi_refining_6"
        mgr = RuinManager(self.player, self.enemy_lib, self.item_lib, self.world)
        ok, msg = mgr.explore("alchemy_cave")
        self.assertTrue(ok, msg)
        self.assertIn("alchemy_cave", self.player.explored_ruins)

        # 冷却期间不能再次探索
        ok, msg = mgr.can_explore("alchemy_cave")
        self.assertFalse(ok)

    def test_world_boss_spawn_and_defeat(self):
        """世界 BOSS 刷新与击败状态。"""
        mgr = WorldBossManager(self.world, self.enemy_lib)
        cfg = mgr.spawn("ancient_qilin")
        self.assertIsNotNone(cfg)
        self.assertIn("ancient_qilin", self.world.active_world_bosses)
        self.assertGreater(len(mgr.get_active_bosses("qingyun")), 0)

        mgr.defeat("ancient_qilin")
        self.assertNotIn("ancient_qilin", self.world.active_world_bosses)

    def test_teleport_unlock_and_travel(self):
        """传送阵解锁与快速旅行。"""
        self._give_stones(10)
        mgr = TeleportManager(self.player, self.world)
        ok, msg = mgr.unlock("heifeng")
        self.assertTrue(ok, msg)
        self.assertIn("heifeng", self.player.unlocked_teleports)

        self.player.location_id = "qingyun"
        ok, msg = mgr.teleport("heifeng")
        self.assertTrue(ok, msg)
        self.assertEqual(self.player.location_id, "heifeng")

    def test_combat_extension_buff_and_combo(self):
        """战斗扩展的 BUFF、连携与伤害统计。"""
        mgr = CombatExtensionManager(self.player, self.world)
        mgr.start_battle()
        self.assertEqual(self.player.combat_stats["total_battles"], 1)

        mgr.apply_buff("test_buff", "测试 BUFF", 2, {"attack_mult": 0.2})
        self.assertEqual(len(mgr.buffs), 1)
        effects = mgr.get_buff_effects()
        self.assertEqual(effects.get("attack_mult"), 0.2)

        mgr.record_skill_used("fireball")
        bonus = mgr.check_combo("flame_burst")
        self.assertGreater(bonus, 0)

        mgr.record_damage(50)
        self.assertEqual(self.player.combat_stats["total_damage_dealt"], 50)

    def test_letter_rumor_hear_and_effect(self):
        """信件管理与传闻效果。"""
        mgr = LetterRumorManager(self.player, self.world)
        mgr.add_letter("market_keeper", "测试信件内容")
        self.assertEqual(len(self.player.letters), 1)
        self.assertFalse(self.player.letters[0]["read"])

        # 玩家当前在青云，可听闻上古麒麟传闻
        rumor = mgr.hear_rumor()
        self.assertIsNotNone(rumor)

        # 应用传闻效果：刷新世界 BOSS
        class FakeEngine:
            pass

        fake = FakeEngine()
        fake.world_boss_manager = WorldBossManager(self.world, self.enemy_lib)
        mgr.apply_rumor_effect(rumor["id"], fake)
        self.assertIn("ancient_qilin", self.world.active_world_bosses)

    def test_master_disciple_take_master(self):
        """拜师应在 NPC 允许时成功。"""
        mgr = MasterDiscipleManager(self.player, self.npc_lib)
        # elder_qing 在配置中已标记可收徒
        ok, msg = mgr.take_master("elder_qing")
        self.assertTrue(ok, msg)
        self.assertEqual(self.player.master_id, "elder_qing")


class TestNPCBehavior(unittest.TestCase):
    """NPC 昼夜作息、关系网、记忆对话、动态事件与价格平衡测试。"""

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
        self.engine = GameEngine(
            self.player,
            self.world,
            self.event_pool,
            self.item_lib,
            self.enemy_lib,
            self.skill_lib,
            self.npc_lib,
            self.quest_lib,
        )

    def test_npc_schedule_active(self):
        """NPC 作息应正确判断活跃时段，包括跨午夜情况。"""
        npc = NPC(
            npc_id="test_npc",
            name="测试 NPC",
            location="qingyun",
            description="",
            dialog="",
            quests=[],
            schedule={"active_hours": [8, 20], "rest_location": "qingyun", "rest_dialog": "休息"},
        )
        self.assertTrue(npc.is_active_at(8))
        self.assertTrue(npc.is_active_at(19))
        self.assertFalse(npc.is_active_at(20))
        self.assertFalse(npc.is_active_at(6))

        night_npc = NPC(
            npc_id="night_npc",
            name="夜间 NPC",
            location="qingyun",
            description="",
            dialog="",
            quests=[],
            schedule={"active_hours": [22, 6], "rest_location": "qingyun", "rest_dialog": "休息"},
        )
        self.assertTrue(night_npc.is_active_at(23))
        self.assertTrue(night_npc.is_active_at(2))
        self.assertFalse(night_npc.is_active_at(12))

    def test_npc_dynamic_spawn_conditions(self):
        """动态 NPC 应根据条件筛选。"""
        npc = NPC(
            npc_id="dynamic_test",
            name="动态测试",
            location="qingyun",
            description="",
            dialog="",
            quests=[],
            dynamic_spawn={"condition": "always", "locations": ["qingyun"], "chance": 1.0},
        )
        self.npc_lib.npcs["dynamic_test"] = npc
        candidates = self.npc_lib.get_dynamic_spawn_candidates(self.player, self.world)
        self.assertIn(npc, candidates)
        found = self.engine.check_dynamic_npcs("qingyun")
        self.assertIn(npc, found)

    def test_npc_dialog_priority(self):
        """NPC 对话优先级：节日 > 记忆 > 好感度 > 默认。"""
        npc = NPC(
            npc_id="dialog_test",
            name="对话测试",
            location="qingyun",
            description="",
            dialog="默认",
            quests=[],
            relationship_dialogs=[{"min_relationship": 5, "dialog": "好感"}],
            festival_dialogs=[{"festival_id": "spring_festival", "dialog": "节日"}],
            memory_dialogs=[{"memory_key": "helped", "expected_value": True, "dialog": "记忆"}],
        )
        self.assertEqual(npc.get_dialog(0, festival_id="spring_festival"), "节日")
        self.assertEqual(npc.get_dialog(0, player_memory={"helped": True}), "记忆")
        self.assertEqual(npc.get_dialog(5), "好感")
        self.assertEqual(npc.get_dialog(0), "默认")

    def test_price_balance_within_bounds(self):
        """购买与出售价格应始终处于合理区间内，避免倒卖套利。"""
        market = self.npc_lib.get("market_keeper")
        item = self.item_lib.get("sword_manual")
        base_value = item.value  # 50

        buy = self.engine.get_buy_price("sword_manual", market)
        sell = self.engine.get_sell_price(item, market)
        self.assertGreater(buy, sell)
        self.assertGreaterEqual(buy, int(base_value * 0.75))
        self.assertLessEqual(buy, int(base_value * 3.0))
        self.assertLessEqual(sell, int(base_value * 0.7))

    def test_price_relationship_discount(self):
        """好感度提升应降低购买价、提高出售价。"""
        market = self.npc_lib.get("market_keeper")
        item = self.item_lib.get("sword_manual")

        buy_low = self.engine.get_buy_price("sword_manual", market)
        sell_low = self.engine.get_sell_price(item, market)
        self.player.npc_relationships["market_keeper"] = 10
        buy_high = self.engine.get_buy_price("sword_manual", market)
        sell_high = self.engine.get_sell_price(item, market)

        self.assertLess(buy_high, buy_low)
        self.assertGreater(sell_high, sell_low)

    def test_price_festival_discount(self):
        """节日期间购买应享受额外折扣。"""
        market = self.npc_lib.get("market_keeper")
        # 先设为非节日，获取原价
        self.world.month = 2
        self.world.day = 2
        normal = self.engine.get_buy_price("sword_manual", market)

        # 将世界时间设为春节（market_keeper 配置了春节对话）
        self.world.month = 1
        self.world.day = 1
        festival = self.engine.get_buy_price("sword_manual", market)
        self.assertLess(festival, normal)

    def test_relationship_network_price(self):
        """与 NPC 好友关系好应降价，与敌人关系好应加价。"""
        npc = self.npc_lib.get("jian_master")
        if not npc or not npc.npc_relationships:
            self.skipTest("无关系网 NPC 可供测试")
        friend_id = npc.npc_relationships.get("friends", [None])[0]
        if not friend_id:
            self.skipTest("该 NPC 无好友关系")

        base_buy = self.engine.get_buy_price("ancient_scroll", npc)
        # 与好友关系好
        self.player.npc_relationships[friend_id] = 10
        friendly_buy = self.engine.get_buy_price("ancient_scroll", npc)
        # 与好友关系差
        self.player.npc_relationships[friend_id] = 0
        unfriendly_buy = self.engine.get_buy_price("ancient_scroll", npc)
        self.assertLess(friendly_buy, unfriendly_buy)

    def test_faction_price_multiplier(self):
        """阵营偏好应影响价格修正系数。"""
        npc = NPC(
            npc_id="faction_test",
            name="阵营测试",
            location="qingyun",
            description="",
            dialog="",
            quests=[],
            faction_affinity={"righteous": 1.2, "evil": 0.3, "neutral": 1.0},
        )
        righteous_mult = npc.get_faction_price_multiplier("righteous")
        evil_mult = npc.get_faction_price_multiplier("evil")
        self.assertLess(righteous_mult, evil_mult)

    def test_npc_movement(self):
        """配置了 wandering 的 NPC 应按概率移动到 possible_locations 中的地点。"""
        npc = NPC(
            npc_id="move_test",
            name="移动测试",
            location="qingyun",
            description="",
            dialog="",
            quests=[],
            movement={
                "wandering": True,
                "possible_locations": ["heifeng", "luoxia_city"],
                "move_chance": 1.0,
            },
        )
        self.assertIsNone(npc.current_location)
        npc.update_location(self.world)
        self.assertIn(npc.current_location, ["heifeng", "luoxia_city"])

    def test_npc_library_update_movements(self):
        """NPCLibrary.update_movements 应推进所有 NPC 的移动状态。"""
        npc = NPC(
            npc_id="lib_move_test",
            name="库移动测试",
            location="qingyun",
            description="",
            dialog="",
            quests=[],
            movement={
                "wandering": True,
                "possible_locations": ["heifeng"],
                "move_chance": 1.0,
            },
        )
        self.npc_lib.npcs["lib_move_test"] = npc
        self.npc_lib.update_movements(self.world)
        self.assertEqual(npc.current_location, "heifeng")
        # get_by_location 应能按 current_location 找到 NPC
        found = self.npc_lib.get_by_location("heifeng")
        self.assertIn(npc, found)

    def test_engine_record_memory(self):
        """Engine 应能记录 NPC 关键选择与访问。"""
        self.engine.record_npc_choice("market_keeper", "helped", True)
        memory = self.player.get_npc_memory("market_keeper")
        self.assertEqual(memory["choices"]["helped"], True)

        self.engine.record_npc_visit("market_keeper")
        memory = self.player.get_npc_memory("market_keeper")
        self.assertEqual(memory["visit_count"], 1)
        self.assertIsNotNone(memory["last_visit"])

    def test_memory_dialog(self):
        """NPC 应根据玩家记忆返回对应的记忆对话。"""
        npc = NPC(
            npc_id="memory_dialog_test",
            name="记忆对话测试",
            location="qingyun",
            description="",
            dialog="默认",
            quests=[],
            memory_dialogs=[
                {"memory_key": "saved_child", "expected_value": True, "dialog": "多谢你救了那孩子。"}
            ],
        )
        self.assertEqual(npc.get_dialog(0), "默认")
        self.assertEqual(
            npc.get_dialog(0, player_memory={"saved_child": True}),
            "多谢你救了那孩子。",
        )

    def test_relationship_network_propagation(self):
        """调整 NPC 好感时应按关系网传播给好友/师徒/敌人。"""
        # 使用配置中已有的剑修宗师及其关系网
        npc = self.npc_lib.get("jian_master")
        if not npc or not npc.npc_relationships:
            self.skipTest("无关系网 NPC 可供测试")
        friend_id = npc.npc_relationships.get("friends", [None])[0]
        if not friend_id:
            self.skipTest("该 NPC 无好友关系")

        self.player.npc_relationships[npc.id] = 0
        self.player.npc_relationships[friend_id] = 0
        self.engine.adjust_npc_relationship(npc.id, 10)
        # 主 NPC 好感提升到 10
        self.assertEqual(self.player.npc_relationships[npc.id], 10)
        # 好友应获得 30% 传播加成
        self.assertGreater(self.player.npc_relationships[friend_id], 0)


class TestEconomy(unittest.TestCase):
    """经济配置与地点类型价格修正测试。"""

    def setUp(self):
        self.economy = EconomyConfig(config_dir="config")

    def test_economy_config_load(self):
        """经济配置应正确加载并提供默认参数。"""
        buy, sell = self.economy.get_base_multipliers()
        self.assertGreater(buy, sell)
        limits = self.economy.get_price_limits()
        self.assertIn("buy_min", limits)
        self.assertIn("sell_max", limits)

    def test_location_type_modifier(self):
        """不同地点类型应返回不同的价格修正。"""
        city_buy, city_sell = self.economy.get_location_type_modifier("city")
        wild_buy, wild_sell = self.economy.get_location_type_modifier("wild")
        # 城市购买更便宜、出售更贵
        self.assertLess(city_buy, wild_buy)
        self.assertGreater(city_sell, wild_sell)

    def test_engine_location_type_price_diff(self):
        """同一 NPC 在不同地点类型下应产生不同价格。"""
        item_lib = ItemLibrary(config_dir="config")
        enemy_lib = EnemyLibrary(config_dir="config")
        skill_lib = SkillLibrary(config_dir="config")
        npc_lib = NPCLibrary(config_dir="config")
        quest_lib = QuestLibrary(config_dir="config")
        player = Player(name="测试修士")
        world = World(config_dir="config")
        event_pool = EventPool(config_dir="config")
        engine = GameEngine(
            player, world, event_pool, item_lib, enemy_lib, skill_lib, npc_lib, quest_lib
        )
        # 构造一个归属地在城市、但实际位置可变的测试 NPC
        npc = NPC(
            npc_id="eco_test_merchant",
            name="经济测试商人",
            location="luoxia_city",
            description="",
            dialog="",
            quests=[],
        )
        item = item_lib.get("sword_manual")

        # 默认在落霞城（city）
        city_buy = engine.get_buy_price("sword_manual", npc)
        city_sell = engine.get_sell_price(item, npc)

        # 临时移动到青云山（wild）
        npc.current_location = "qingyun"
        wild_buy = engine.get_buy_price("sword_manual", npc)
        wild_sell = engine.get_sell_price(item, npc)

        # 荒野购买更贵、出售更便宜
        self.assertGreater(wild_buy, city_buy)
        self.assertLess(wild_sell, city_sell)


if __name__ == "__main__":
    unittest.main()
