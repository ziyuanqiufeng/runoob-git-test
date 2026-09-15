# -*- coding: utf-8 -*-
"""维度③ 引擎接线 + 弹窗冒烟测试（无头）。

验证：engine 正确构造 hundred_schools_manager 并注册月度插座；
cultivate 月度结算不异常；自创功法/立派/生活流派动作经引擎可达；
生活流派精熟可化解心魔劫（heart_demon flag 协同）；新弹窗可无错构建。
"""
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

from ui.hundred_schools_dialog import HundredSchoolsDialog
from ui.action_panel import ActionPanel


class TestHundredSchoolsEngineWiring(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def _make_engine(self, realm="golden_core_early", stones=200):
        player = Player(name="维度3接线")
        player.realm_id = realm
        for _ in range(stones):
            from game.item import Item
            player.add_item(Item(
                item_id="spirit_stone", name="灵石", item_type="currency", value=1,
                description="", effects={}, stackable=True, max_stack=99, count=1,
            ))
        engine = GameEngine(
            player, World(config_dir="config"), EventPool(config_dir="config"),
            ItemLibrary(config_dir="config"), EnemyLibrary(config_dir="config"),
            SkillLibrary(config_dir="config"), NPCLibrary(config_dir="config"),
            QuestLibrary(config_dir="config"),
            save_manager=None, config_dir="config",
        )
        return engine

    def test_manager_constructed_and_registered(self):
        engine = self._make_engine()
        self.assertTrue(hasattr(engine, "hundred_schools_manager"))
        cb_names = [getattr(cb, "__name__", str(cb)) for cb, flag in engine._monthly_tick_hooks]
        self.assertIn("_tick_hundred_schools", cb_names)
        # flag 门控为 hundred_schools
        flags = [f for cb, f in engine._monthly_tick_hooks if getattr(cb, "__name__", "") == "_tick_hundred_schools"]
        self.assertEqual(flags[0], "hundred_schools")

    def test_cultivate_runs_tick_without_error(self):
        engine = self._make_engine()
        engine.cultivate(months=3)
        # 未立派时不应反哺灵石
        self.assertEqual(engine.player.count_item("spirit_stone"), 200)

    def test_found_sect_and_feedback_via_engine(self):
        engine = self._make_engine(stones=100)
        ok, msg = engine.found_sect("青云宗")
        self.assertTrue(ok)
        self.assertEqual(engine.player.founded_sect["name"], "青云宗")
        self.assertEqual(engine.player.count_item("spirit_stone"), 50)
        # 迁至安全城池闭关，避免野外随机袭击打断 cultivate（内部 break），
        # 否则气运/反哺月度结算偶发不被执行，导致断言不稳定。
        engine.player.location_id = "luoxia_city"
        # 闭关数月，气运累积并反哺灵石
        engine.cultivate(months=5)
        self.assertGreater(engine.player.founded_sect["qi_yun"], 0)
        self.assertGreater(engine.player.count_item("spirit_stone"), 50)

    def test_create_technique_via_engine(self):
        engine = self._make_engine(stones=200)
        ok, msg = engine.create_technique("太上忘情诀", "剑修", "dao_heart")
        self.assertTrue(ok)
        self.assertEqual(len(engine.player.self_created_techniques), 1)
        # 月度结算增益道心
        ms0 = engine.player.mental_state
        engine.cultivate(months=2)
        self.assertGreaterEqual(engine.player.mental_state, ms0)

    def test_choose_life_path_via_engine(self):
        engine = self._make_engine(stones=50)
        ok, msg = engine.choose_life_path("alchemy")
        self.assertTrue(ok)
        self.assertEqual(engine.player.life_path, "alchemy")
        self.assertEqual(engine.player.life_path_proficiency, 0)

    def test_life_path_mitigates_heart_demon_tribulation(self):
        engine = self._make_engine(stones=50)
        engine.choose_life_path("talisman")
        # 强行拉满精进度
        for _ in range(120):
            engine.hundred_schools_manager.tick_monthly()
        # 生活流派精熟后，化解判定返回 bool 且长程至少一次可为真
        import random
        random.seed(1)
        saw_true = False
        saw_false = False
        for _ in range(200):
            r = engine.hundred_schools_manager.should_mitigate_heart_demon_tribulation()
            saw_true = saw_true or r
            saw_false = saw_false or (not r)
        self.assertTrue(saw_true)
        self.assertTrue(saw_false)

    def test_dialog_builds(self):
        engine = self._make_engine()
        dlg = HundredSchoolsDialog(engine, parent=None)
        self.assertIsNotNone(dlg)
        dlg.accept()

    def test_action_panel_has_button(self):
        engine = self._make_engine()
        panel = ActionPanel(engine)
        self.assertIn("hundred_schools", panel._button_map)
        self.assertTrue(panel._button_map["hundred_schools"].isEnabled())

    def test_create_technique_registers_usable_skill(self):
        engine = self._make_engine(stones=200)
        ok, msg = engine.create_technique("太上忘情诀", "剑修", "dao_heart")
        self.assertTrue(ok)
        tech = engine.player.self_created_techniques[-1]
        sid = tech["skill_id"]
        # 自创功法被注册为真实 Skill 且玩家已学会
        self.assertIn(sid, engine.skill_library.skills)
        self.assertIn(sid, engine.player.skills)
        sk = engine.skill_library.get(sid)
        self.assertEqual(sk.base_damage, 30)  # 剑修模板
        self.assertEqual(sk.element, "metal")  # dao_heart → metal

    def test_reload_reregisters_self_created_skills(self):
        """模拟读档：新引擎从同一 player 重建，skill_library 应重注册自创功法。"""
        engine = self._make_engine(stones=200)
        engine.create_technique("太上忘情诀", "剑修", "dao_heart")
        sid = engine.player.self_created_techniques[-1]["skill_id"]
        # 新引擎（等同读档后重建）应自动重注册
        reload_engine = self._make_engine_from_player(engine.player)
        self.assertIn(sid, reload_engine.skill_library.skills)
        self.assertIn(sid, reload_engine.player.skills)
        self.assertEqual(reload_engine.skill_library.get(sid).base_damage, 30)

    def test_tick_produces_life_path_item_via_engine(self):
        engine = self._make_engine(stones=50)
        engine.choose_life_path("talisman")
        # 推满精进度以越过 min_proficiency(3)
        for _ in range(5):
            engine.hundred_schools_manager.tick_monthly()
        self.assertGreaterEqual(engine.player.life_path_proficiency, 3)
        # 对齐 age_months 到 every_months(2) 的倍数，触发产出
        engine.player.age_months = 2
        before = engine.player.count_item("talisman_paper")
        engine._tick_hundred_schools()
        after = engine.player.count_item("talisman_paper")
        self.assertEqual(after, before + 1)

    def _make_engine_from_player(self, player):
        engine = GameEngine(
            player, World(config_dir="config"), EventPool(config_dir="config"),
            ItemLibrary(config_dir="config"), EnemyLibrary(config_dir="config"),
            SkillLibrary(config_dir="config"), NPCLibrary(config_dir="config"),
            QuestLibrary(config_dir="config"),
            save_manager=None, config_dir="config",
        )
        return engine


if __name__ == "__main__":
    unittest.main()
