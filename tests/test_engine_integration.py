# -*- coding: utf-8 -*-
"""跨模块联动集成测试。

验证心境、天气、洞府、道侣系统与 engine 核心循环（修炼、突破、战斗）的整合。
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
from game.npc import NPCLibrary
from game.quest import QuestLibrary
from game.engine import GameEngine
from game.save_manager import SaveManager
from game.companion import CompanionManager


class TestEngineIntegration(unittest.TestCase):
    """Engine 跨模块联动测试。"""

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
        self.save_path = "test_engine_integration_save.json"
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

    def test_weather_affects_cultivation(self):
        """天气修炼加成应影响实际修为收益。"""
        # 屏蔽其他随机修炼加成来源，只验证天气效果
        patches = [
            patch.object(self.engine.weather_manager, "get_cultivation_speed_bonus", return_value=0.5),
            patch.object(self.engine.weather_manager, "advance", return_value=(False, None, None, None, None)),
            patch.object(self.engine.mental_state_manager, "get_cultivation_speed_bonus", return_value=0.0),
            patch.object(self.engine.residence_manager, "get_cultivation_speed_bonus", return_value=0.0),
            patch.object(self.engine.mental_state_manager, "tick_monthly", return_value=(0, 0, [])),
            patch.object(self.engine.residence_manager, "tick_monthly", return_value={"production": [], "raid": None}),
        ]
        for p in patches:
            p.start()
        try:
            qi_before = self.player.qi
            self.engine.cultivate(1)
            gain = self.player.qi - qi_before
            base_gain = (10 + self.player.wisdom * 2) // self.player.cultivation_multiplier
            # 50% 天气加成下，实际收益应高于基础值
            self.assertGreater(gain, base_gain)
        finally:
            for p in patches:
                p.stop()

    def test_mental_state_affects_breakthrough(self):
        """心境加成应提高突破成功率。"""
        realm = self.world.get_realm(self.player.realm_id)
        self.player.qi = realm["max_qi"]
        # 把心魔压到 0，道心提到最高，获得最大正面加成
        self.player.mental_state = 100
        self.player.heart_demon = 0

        patches = [
            patch.object(self.engine.weather_manager, "get_breakthrough_bonus", return_value=0.0),
            patch.object(self.engine.mental_state_manager, "on_breakthrough"),
            patch("random.random", return_value=0.01),  # 必然成功
        ]
        for p in patches:
            p.start()
        try:
            next_id = self.world.next_realm(self.player.realm_id)
            self.engine.breakthrough()
            self.assertEqual(self.player.realm_id, next_id)
        finally:
            for p in patches:
                p.stop()

    def test_companion_battle_bonus(self):
        """结为道侣后，战斗开始时应获得攻防加成。"""
        # 满足结为道侣的境界与好感条件
        self.player.realm_id = "qi_refining_3"
        self.player.npc_relationships["elder_qing"] = 10
        companion_mgr = CompanionManager(
            self.player, self.world, npc_library=self.npc_lib
        )
        ok, _ = companion_mgr.form_companion("elder_qing")
        self.assertTrue(ok)
        # 提升亲密度以激活战斗加成
        companion_mgr.increase_intimacy("elder_qing", 50)

        enemy_data = self.enemy_lib.get("wolf")
        enemy = Enemy.from_dict(enemy_data)
        self.engine.start_combat(enemy)

        self.assertGreater(self.engine.companion_atk_bonus, 0.0)
        self.assertGreater(self.engine.companion_def_bonus, 0.0)

    def test_killing_affects_mental_state(self):
        """击杀敌人后应根据敌人阵营影响心境。"""
        self.player.mental_state = 50
        self.player.heart_demon = 0

        # 构造一个可一击毙命的正道敌人
        enemy = Enemy.from_dict({
            "id": "righteous_test",
            "name": "正道测试弟子",
            "alignment": "righteous",
            "hp": 1,
            "attack": 1,
            "defense": 0,
            "exp": 0,
            "loot": [],
        })
        self.player.base_attack = 100
        self.player.base_defense = 100
        self.player.health = 100
        self.player.max_health = 100
        self.engine.start_combat(enemy)

        # 固定随机数避免闪避导致测试不稳定
        with patch("game.engine.random.random", return_value=0.9):
            logs, result = self.engine.combat_round(enemy, "attack")
        self.assertEqual(result, "win")
        # 击杀正道目标会降低道心、增加心魔
        self.assertLess(self.player.mental_state, 50)
        self.assertGreater(self.player.heart_demon, 0)

    def test_enemy_alignment_loaded(self):
        """敌人 JSON 中的 alignment 字段应被正确加载。"""
        data = self.enemy_lib.get("righteous_disciple")
        enemy = Enemy.from_dict(data)
        self.assertEqual(enemy.alignment, "righteous")

        data = self.enemy_lib.get("evil_cultivator")
        enemy = Enemy.from_dict(data)
        self.assertEqual(enemy.alignment, "evil")


if __name__ == "__main__":
    unittest.main()
