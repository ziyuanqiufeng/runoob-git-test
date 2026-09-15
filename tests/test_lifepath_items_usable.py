# -*- coding: utf-8 -*-
"""M14：生活流派产出物「可用化」端到端测试（无头）。

维度③ 生活流派（丹/器/符/阵）月度产出的真实物品，如今应可被消耗/装备并生效：
- 符箓 talisman_paper：镇心符，道心+4 / 心魔-3 / 气血+20，服用后退包；
- 阵盘 array_disk：聚灵阵，修为+80 / 悟性+2，服用后退包；
- 灵木剑 spirit_wood_sword：可装备武器（攻击+8）；
- 补气丹 qi_pill：可服用恢复修为（既有 pill 路径）。
同时验证 use_item 对道心/心魔的钳制（0-100）以及消耗品使用后正确退包（不再无限复用）。
"""
import unittest

from game.player import Player
from game.world import World
from game.events import EventPool
from game.item import ItemLibrary, Item
from game.enemy import EnemyLibrary
from game.skill import SkillLibrary
from game.npc import NPCLibrary
from game.quest import QuestLibrary
from game.engine import GameEngine


class TestLifePathItemsUsable(unittest.TestCase):
    def _make_engine(self, realm="golden_core_early", stones=200):
        player = Player(name="生活流派可用化")
        player.realm_id = realm
        for _ in range(stones):
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

    def _produce(self, engine, path, every, min_prof):
        """择生活流派并稳定产出一件物品（对齐 age_months 到 every 的倍数）。"""
        engine.choose_life_path(path)
        for _ in range(min_prof):
            engine.hundred_schools_manager.tick_monthly()
        self.assertGreaterEqual(engine.player.life_path_proficiency, min_prof)
        engine.player.age_months = every  # every % every == 0 → 触发产出
        before = engine.player.count_item(
            engine.hundred_schools_manager.config.get_life_path()["produce"][path]["item_id"]
        )
        engine._tick_hundred_schools()
        item_id = engine.hundred_schools_manager.config.get_life_path()["produce"][path]["item_id"]
        after = engine.player.count_item(item_id)
        self.assertEqual(after, before + 1)
        return item_id

    # ---------------- 符箓：镇心符（道心/心魔/气血） ----------------
    def test_talisman_paper_applies_and_consumes(self):
        engine = self._make_engine()
        engine.player.mental_state = 50
        engine.player.heart_demon = 30
        engine.player.health = 50
        item_id = self._produce(engine, "talisman", every=2, min_prof=3)
        item = [i for i in engine.player.inventory if i.id == item_id][0]
        before_count = engine.player.count_item(item_id)
        ok = engine.use_item(item)
        self.assertTrue(ok)
        # 效果生效
        self.assertEqual(engine.player.mental_state, 54)   # 50 + 4
        self.assertEqual(engine.player.heart_demon, 27)    # 30 - 3
        self.assertEqual(engine.player.health, 70)         # 50 + 20
        # 退包
        self.assertEqual(engine.player.count_item(item_id), before_count - 1)

    def test_talisman_mental_state_clamped_at_100(self):
        engine = self._make_engine()
        engine.player.mental_state = 98
        engine.player.heart_demon = 0
        item_id = self._produce(engine, "talisman", every=2, min_prof=3)
        item = [i for i in engine.player.inventory if i.id == item_id][0]
        engine.use_item(item)
        self.assertEqual(engine.player.mental_state, 100)  # 98 + 4 钳制

    def test_talisman_heart_demon_clamped_at_0(self):
        engine = self._make_engine()
        engine.player.mental_state = 50
        engine.player.heart_demon = 2
        item_id = self._produce(engine, "talisman", every=2, min_prof=3)
        item = [i for i in engine.player.inventory if i.id == item_id][0]
        engine.use_item(item)
        self.assertEqual(engine.player.heart_demon, 0)     # 2 - 3 钳制

    # ---------------- 阵盘：聚灵阵（修为/悟性） ----------------
    def test_array_disk_applies_and_consumes(self):
        engine = self._make_engine()
        engine.player.wisdom = 5
        qi0 = engine.player.qi
        item_id = self._produce(engine, "array", every=4, min_prof=6)
        item = [i for i in engine.player.inventory if i.id == item_id][0]
        before_count = engine.player.count_item(item_id)
        ok = engine.use_item(item)
        self.assertTrue(ok)
        self.assertEqual(engine.player.qi, qi0 + 80)       # 修为 +80
        self.assertEqual(engine.player.wisdom, 7)         # 悟性 +2
        self.assertEqual(engine.player.count_item(item_id), before_count - 1)

    # ---------------- 器修：灵木剑可装备 ----------------
    def test_spirit_wood_sword_equips(self):
        engine = self._make_engine()
        item_id = self._produce(engine, "artifact", every=6, min_prof=8)
        item = [i for i in engine.player.inventory if i.id == item_id][0]
        self.assertIn(item, engine.player.inventory)
        ok = engine.use_item(item)
        self.assertTrue(ok)
        # 武器进入装备槽，离开背包
        self.assertIsNotNone(engine.player.equipment.get("weapon"))
        self.assertEqual(engine.player.equipment["weapon"].id, item_id)
        self.assertNotIn(item, engine.player.inventory)

    # ---------------- 丹道：补气丹可服用 ----------------
    def test_qi_pill_usable(self):
        engine = self._make_engine()
        qi0 = engine.player.qi
        item_id = self._produce(engine, "alchemy", every=3, min_prof=5)
        item = [i for i in engine.player.inventory if i.id == item_id][0]
        before_count = engine.player.count_item(item_id)
        ok = engine.use_item(item)
        self.assertTrue(ok)
        self.assertEqual(engine.player.qi, qi0 + 50)       # 修为 +50
        self.assertEqual(engine.player.count_item(item_id), before_count - 1)


if __name__ == "__main__":
    unittest.main()
