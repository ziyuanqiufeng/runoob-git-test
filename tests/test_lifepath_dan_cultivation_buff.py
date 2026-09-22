"""M18：维度③ 丹道「灵力温养」持续修炼增益测试。

覆盖：
- 服用补气丹：立得修为 + 持续增益生效（months/amount 设置）
- cultivate 月度循环：增益每月附加并到期递减至 0
- 存档 round-trip：cultivation_boost_months/amount 持久化
- 非丹道物品（符箓）不触发持续修炼增益
"""

import unittest

from game.engine import GameEngine
from game.player import Player
from game.world import World
from game.events import EventPool
from game.item import ItemLibrary
from game.enemy import EnemyLibrary
from game.skill import SkillLibrary
from game.npc import NPCLibrary
from game.quest import QuestLibrary


def _make_engine():
    """构建无头引擎（不引 PySide6）。"""
    return GameEngine(
        Player(),
        World(config_dir="config"),
        EventPool(config_dir="config"),
        ItemLibrary(config_dir="config"),
        EnemyLibrary(config_dir="config"),
        SkillLibrary(config_dir="config"),
        NPCLibrary(config_dir="config"),
        QuestLibrary(config_dir="config"),
        save_manager=None,
        config_dir="config",
    )


class TestDanCultivationBuff(unittest.TestCase):
    # -------- 1. 补气丹：即时修为 + 持续增益设置 --------
    def test_qi_pill_applies_instant_and_boost(self):
        engine = _make_engine()
        engine.player.add_item(engine.item_library.create("qi_pill"))
        pill = [i for i in engine.player.inventory if i.id == "qi_pill"][0]
        q0 = engine.player.qi
        ok = engine.use_item(pill)
        self.assertTrue(ok)
        # 即时修为 +50（乘境界成长系数）
        self.assertEqual(engine.player.qi, q0 + int(50 * engine._realm_qi_scale()))
        # 持续增益：3 个月，每月 +40（乘境界成长系数）
        self.assertEqual(engine.player.cultivation_boost_months, 3)
        self.assertEqual(engine.player.cultivation_boost_amount,
                         int(40 * engine._realm_qi_scale()))

    # -------- 2. cultivate：增益每月附加并到期递减 --------
    def test_cultivation_boost_adds_monthly_and_expires(self):
        engine = _make_engine()
        # 设为安全城池，避免野外随机袭击打断闭关（确定性）
        engine.player.location_id = "luoxia_city"
        engine.player.cultivation_boost_months = 3
        engine.player.cultivation_boost_amount = 40
        q0 = engine.player.qi
        engine.cultivate(months=3)
        # 3 个月内至少获得 3×40 = 120 点（增益保底，顿悟只增不减）
        self.assertGreaterEqual(engine.player.qi - q0, 120)
        # 增益到期归零
        self.assertEqual(engine.player.cultivation_boost_months, 0)

    # -------- 3. 存档 round-trip --------
    def test_boost_round_trip_save_load(self):
        engine = _make_engine()
        engine.player.cultivation_boost_months = 5
        engine.player.cultivation_boost_amount = 25
        data = engine.player.to_dict()
        p2 = Player.from_dict(data, engine.item_library)
        self.assertEqual(p2.cultivation_boost_months, 5)
        self.assertEqual(p2.cultivation_boost_amount, 25)

    # -------- 4. 非丹道物品不触发持续增益 --------
    def test_non_dan_item_no_boost(self):
        engine = _make_engine()
        engine.player.add_item(engine.item_library.create("talisman_paper"))
        tal = [i for i in engine.player.inventory if i.id == "talisman_paper"][0]
        ok = engine.use_item(tal)
        self.assertTrue(ok)
        # 符箓不应设置丹道持续增益
        self.assertEqual(engine.player.cultivation_boost_months, 0)
        self.assertEqual(engine.player.cultivation_boost_amount, 0)


if __name__ == "__main__":
    unittest.main()
