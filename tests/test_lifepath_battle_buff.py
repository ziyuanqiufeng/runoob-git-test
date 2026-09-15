# -*- coding: utf-8 -*-
"""维度③·M15 生活流派法宝「战斗部署型增益」测试（无头）。

验证：符箓(talisman_paper)/阵盘(array_disk) 经 engine.deploy_battle_consumable
部署为战斗临时增益 buff（削敌攻/增己攻/护盾），消耗物品且随战斗重置；
无可部署物/非部署物（如补气丹 qi_pill）部署应失败且不消耗；
战斗中 start_combat 对符箓/阵法流派（lifepath_auto_deploy）自动部署。
"""
import unittest

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


class TestLifepathBattleBuff(unittest.TestCase):
    """生活流派法宝战斗部署增益（维度③·M15）。"""

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def _make_engine(self, stones=0):
        player = Player(name="生活法宝测试")
        engine = GameEngine(
            player, World(config_dir="config"), EventPool(config_dir="config"),
            ItemLibrary(config_dir="config"), EnemyLibrary(config_dir="config"),
            SkillLibrary(config_dir="config"), NPCLibrary(config_dir="config"),
            QuestLibrary(config_dir="config"), save_manager=None, config_dir="config",
        )
        for _ in range(stones):
            player.add_item(engine.item_library.create("spirit_stone"))
        return engine

    def _create_enemy(self, **kwargs):
        data = {
            "id": "test_enemy", "name": "测试敌人", "alignment": "neutral",
            "hp": 100, "attack": 10, "defense": 0, "exp": 0, "loot": [],
        }
        data.update(kwargs)
        return Enemy.from_dict(data)

    def _add_item(self, engine, item_id, n=1):
        for _ in range(n):
            engine.player.add_item(engine.item_library.create(item_id))

    # -------- 1. 符箓部署：削敌攻 + 护盾 + 退包 --------
    def test_deploy_talisman_applies_enemy_atk_down_and_shield(self):
        engine = self._make_engine()
        self._add_item(engine, "talisman_paper")
        engine.start_combat(self._create_enemy())
        ok, msg = engine.deploy_battle_consumable("talisman_paper")
        self.assertTrue(ok)
        # 消耗 1 个符箓
        self.assertEqual(engine.player.count_item("talisman_paper"), 0)
        # 敌方攻击削弱增益已施加
        self.assertEqual(len(engine.enemy_attack_down), 1)
        self.assertAlmostEqual(engine.enemy_attack_down[0]["ratio"], 0.15)
        self.assertEqual(engine.enemy_attack_down[0]["turns"], 3)
        # 护盾增益
        self.assertEqual(engine.player_shield, 30)

    # -------- 2. 阵盘部署：增己攻 + 退包 --------
    def test_deploy_array_applies_player_atk_up(self):
        engine = self._make_engine()
        self._add_item(engine, "array_disk")
        engine.start_combat(self._create_enemy())
        ok, msg = engine.deploy_battle_consumable("array_disk")
        self.assertTrue(ok)
        self.assertEqual(engine.player.count_item("array_disk"), 0)
        self.assertEqual(len(engine.player_attack_up), 1)
        self.assertAlmostEqual(engine.player_attack_up[0]["ratio"], 0.20)
        self.assertEqual(engine.player_attack_up[0]["turns"], 3)

    # -------- 3. 无物品部署应失败且不施加 --------
    def test_deploy_without_item_fails(self):
        engine = self._make_engine()
        engine.start_combat(self._create_enemy())
        ok, msg = engine.deploy_battle_consumable("talisman_paper")
        self.assertFalse(ok)
        self.assertEqual(len(engine.enemy_attack_down), 0)

    # -------- 4. 非部署物（补气丹）部署应失败且不消耗 --------
    def test_deploy_non_deployable_item_fails(self):
        engine = self._make_engine()
        self._add_item(engine, "qi_pill")
        ok, msg = engine.deploy_battle_consumable("qi_pill")
        self.assertFalse(ok)
        # 不应消耗
        self.assertEqual(engine.player.count_item("qi_pill"), 1)

    # -------- 5. 战斗开始自动部署（需玩家主动开启 auto_deploy）--------
    def test_auto_deploy_on_combat_start_when_enabled(self):
        engine = self._make_engine()
        ok, msg = engine.choose_life_path("talisman")
        self.assertTrue(ok)
        # M17：择流派默认不自动部署（消除流派战斗增益不对称）
        self.assertFalse(engine.player.lifepath_auto_deploy)
        self._add_item(engine, "talisman_paper")
        engine.start_combat(self._create_enemy())
        # 默认未自动部署：道具保留，战斗增益未施加
        self.assertEqual(len(engine.enemy_attack_down), 0)
        self.assertEqual(engine.player.count_item("talisman_paper"), 1)
        # 玩家在面板勾选自动部署后，开战自动部署
        engine.player.lifepath_auto_deploy = True
        engine.start_combat(self._create_enemy())
        self.assertEqual(len(engine.enemy_attack_down), 1)
        self.assertEqual(engine.player_shield, 30)
        self.assertEqual(engine.player.count_item("talisman_paper"), 0)

    # -------- 6. 未选生活流派不自动部署 --------
    def test_no_auto_deploy_without_lifepath(self):
        engine = self._make_engine()
        self.assertFalse(engine.player.lifepath_auto_deploy)
        self._add_item(engine, "talisman_paper")
        engine.start_combat(self._create_enemy())
        self.assertEqual(len(engine.enemy_attack_down), 0)
        # 物品未被自动消耗
        self.assertEqual(engine.player.count_item("talisman_paper"), 1)

    # -------- 7. 下一场战斗 buff 重置（法宝耗尽不再部署）--------
    def test_combat_restores_buffs_next_fight(self):
        engine = self._make_engine()
        engine.choose_life_path("talisman")
        engine.player.lifepath_auto_deploy = True  # 显式开启自动部署
        self._add_item(engine, "talisman_paper")
        engine.start_combat(self._create_enemy())
        self.assertEqual(len(engine.enemy_attack_down), 1)
        self.assertEqual(engine.player_shield, 30)
        # 第二场：法宝已耗尽，自动部署不再触发，战斗内 buff 被重置
        engine.start_combat(self._create_enemy())
        self.assertEqual(len(engine.enemy_attack_down), 0)
        self.assertEqual(engine.player_shield, 0)

    # -------- 8. 可部署法宝查询（维度③·M16）--------
    def test_get_deployable_lists_held_battle_consumables(self):
        engine = self._make_engine()
        # 未择流派、无货：空
        self.assertEqual(engine.get_deployable_battle_consumables(), [])
        self._add_item(engine, "talisman_paper", 2)
        self._add_item(engine, "array_disk", 1)
        deployable = engine.get_deployable_battle_consumables()
        ids = {d["item_id"] for d in deployable}
        self.assertEqual(ids, {"talisman_paper", "array_disk"})
        by_id = {d["item_id"]: d for d in deployable}
        self.assertEqual(by_id["talisman_paper"]["count"], 2)
        self.assertEqual(by_id["talisman_paper"]["name"], "镇心符·镇魂")
        # 非部署物（补气丹）不计入
        self._add_item(engine, "qi_pill", 5)
        self.assertEqual(
            {d["item_id"] for d in engine.get_deployable_battle_consumables()},
            {"talisman_paper", "array_disk"},
        )

    # -------- 9. 玩家关闭自动部署开关后，开战不再无脑消耗（维度③·M16）--------
    def test_toggle_off_auto_deploy_prevents_auto_consume(self):
        engine = self._make_engine()
        engine.choose_life_path("talisman")
        # 玩家主动关闭自动部署（等同百家争鸣面板的勾选框）
        engine.player.lifepath_auto_deploy = False
        self._add_item(engine, "talisman_paper", 3)
        engine.start_combat(self._create_enemy())
        # 未自动部署：道具保留，战斗增益未施加
        self.assertEqual(engine.player.count_item("talisman_paper"), 3)
        self.assertEqual(len(engine.enemy_attack_down), 0)
        self.assertEqual(engine.player_shield, 0)
        # 仍可手动部署
        ok, msg = engine.deploy_battle_consumable("talisman_paper")
        self.assertTrue(ok)
        self.assertEqual(engine.player.count_item("talisman_paper"), 2)
        self.assertEqual(len(engine.enemy_attack_down), 1)


if __name__ == "__main__":
    unittest.main()
