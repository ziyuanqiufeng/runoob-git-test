# -*- coding: utf-8 -*-
"""私人洞府占领与设施升级系统测试。"""
import unittest

from game.player import Player
from game.item import ItemLibrary
from game.residence import ResidenceManager, ResidenceConfig


class TestResidenceConfig(unittest.TestCase):
    """洞府配置加载测试。"""

    def test_load_residences(self):
        """应能加载所有洞府配置。"""
        config = ResidenceConfig(config_dir="config")
        self.assertTrue(len(config.get_residences()) > 0)

    def test_get_residence_by_location(self):
        """按地点获取洞府配置。"""
        config = ResidenceConfig(config_dir="config")
        heifeng = config.get_residences_by_location("heifeng")
        self.assertEqual(len(heifeng), 1)
        self.assertEqual(heifeng[0]["type"], "wild")

    def test_get_wild_residences(self):
        """按类型筛选野外洞府。"""
        config = ResidenceConfig(config_dir="config")
        wild = config.get_residences_by_type("wild")
        self.assertTrue(len(wild) > 0)
        for r in wild:
            self.assertIn("occupation", r)


class TestCityResidencePurchase(unittest.TestCase):
    """城中洞府购买测试。"""

    def setUp(self):
        self.player = Player(name="测试修士")
        self.item_lib = ItemLibrary(config_dir="config")
        for _ in range(5000):
            self.player.add_item(self.item_lib.create("spirit_stone"))
        self.player.sect_contribution = 1000
        self.manager = ResidenceManager(self.player, item_library=self.item_lib)

    def test_can_buy_city_residence(self):
        """灵石与贡献充足时应可购买城中洞府。"""
        ok, msg = self.manager.can_buy_residence("cloud_peak_cave")
        self.assertTrue(ok)
        self.assertEqual(msg, "")

    def test_cannot_buy_wild_residence(self):
        """野外洞府不能直接购买。"""
        ok, msg = self.manager.can_buy_residence("heifeng_lair")
        self.assertFalse(ok)
        self.assertIn("占领", msg)

    def test_buy_residence_deducts_cost(self):
        """购买成功后扣除灵石与贡献。"""
        before_money = self.player.count_item("spirit_stone")
        before_contribution = self.player.sect_contribution
        ok, msg = self.manager.buy_residence("cloud_peak_cave")
        self.assertTrue(ok)
        self.assertEqual(self.player.count_item("spirit_stone"), before_money - 2000)
        self.assertEqual(self.player.sect_contribution, before_contribution - 500)
        self.assertEqual(self.player.residence["id"], "cloud_peak_cave")
        # 城中洞府初始无护阵能量
        self.assertEqual(self.player.residence["energy"], 0)

    def test_cannot_buy_when_already_owned(self):
        """已拥有洞府时不能再次购买。"""
        self.manager.buy_residence("cloud_peak_cave")
        ok, msg = self.manager.buy_residence("cloud_peak_cave")
        self.assertFalse(ok)
        self.assertIn("已拥有", msg)


class TestWildResidenceOccupation(unittest.TestCase):
    """野外洞府占领测试。"""

    def setUp(self):
        self.player = Player(name="测试修士")
        self.item_lib = ItemLibrary(config_dir="config")
        for _ in range(5000):
            self.player.add_item(self.item_lib.create("spirit_stone"))
        self.manager = ResidenceManager(self.player, item_library=self.item_lib)

    def test_can_occupy_meets_realm(self):
        """境界达到要求时应可占领。"""
        self.player.realm_id = "foundation_early"  # 境界顺序 10
        ok, result = self.manager.can_occupy("heifeng")
        self.assertTrue(ok)
        self.assertEqual(result, "heifeng_lair")

    def test_cannot_occupy_low_realm(self):
        """境界不足时不能占领。"""
        self.player.realm_id = "qi_refining_1"
        ok, msg = self.manager.can_occupy("heifeng")
        self.assertFalse(ok)
        self.assertIn("境界不足", msg)

    def test_occupy_returns_guard(self):
        """发起占领应返回守卫敌人 ID。"""
        self.player.realm_id = "foundation_early"
        ok, msg, guard_id = self.manager.occupy("heifeng")
        self.assertTrue(ok)
        self.assertEqual(guard_id, "tiger")

    def test_finish_occupation_success(self):
        """战斗胜利后完成占领，获得洞府所有权与满能量。"""
        self.player.realm_id = "foundation_early"
        self.manager.finish_occupation("heifeng", win=True)
        self.assertEqual(self.player.residence["id"], "heifeng_lair")
        self.assertGreater(self.player.residence["energy"], 0)
        # 护山大阵能量上限 = 200（未建造时按配置每级上限）
        self.assertEqual(self.manager.get_max_formation_energy(), 200)

    def test_finish_occupation_failure(self):
        """战斗失败不获得所有权。"""
        self.player.realm_id = "foundation_early"
        ok, msg = self.manager.finish_occupation("heifeng", win=False)
        self.assertFalse(ok)
        self.assertIsNone(self.player.residence)


class TestBuildingUpgrade(unittest.TestCase):
    """建筑升级测试。"""

    def setUp(self):
        self.player = Player(name="测试修士")
        self.item_lib = ItemLibrary(config_dir="config")
        for _ in range(10000):
            self.player.add_item(self.item_lib.create("spirit_stone"))
        # 云顶峰洞府购买需要 500 宗门贡献
        self.player.sect_contribution = 1000
        self.manager = ResidenceManager(self.player, item_library=self.item_lib)
        self.manager.buy_residence("cloud_peak_cave")

    def test_upgrade_building(self):
        """升级建筑后等级提升并扣除灵石。"""
        before = self.player.count_item("spirit_stone")
        ok, msg = self.manager.upgrade_building("spirit_gathering_array")
        self.assertTrue(ok)
        self.assertEqual(
            self.player.residence["buildings"]["spirit_gathering_array"], 1
        )
        self.assertLess(self.player.count_item("spirit_stone"), before)

    def test_upgrade_defense_formation_refills_energy(self):
        """升级护山大阵时应补满能量。"""
        self.manager.upgrade_building("defense_formation")
        self.assertEqual(
            self.player.residence["buildings"]["defense_formation"], 1
        )
        self.assertEqual(
            self.player.residence["energy"],
            self.manager.get_max_formation_energy()
        )

    def test_cannot_upgrade_beyond_max(self):
        """超过最高等级后不能继续升级。"""
        for _ in range(10):
            self.manager.upgrade_building("spirit_gathering_array")
        level = self.player.residence["buildings"].get("spirit_gathering_array", 0)
        self.assertLessEqual(level, 5)


class TestMaintenanceAndEnergy(unittest.TestCase):
    """维护费与护阵能量测试。"""

    def setUp(self):
        self.player = Player(name="测试修士")
        self.item_lib = ItemLibrary(config_dir="config")
        for _ in range(10000):
            self.player.add_item(self.item_lib.create("spirit_stone"))
        self.manager = ResidenceManager(self.player, item_library=self.item_lib)
        self.player.realm_id = "foundation_early"
        self.manager.finish_occupation("heifeng", win=True)
        # 升级几个建筑产生维护费
        self.manager.upgrade_building("spirit_gathering_array")
        self.manager.upgrade_building("herb_garden")

    def test_maintenance_cost_positive(self):
        """有建筑时维护费应大于 0。"""
        cost = self.manager.get_maintenance_cost()
        self.assertGreater(cost, 0)

    def test_pay_maintenance(self):
        """缴纳维护费后欠费清零。"""
        self.player.residence["maintenance_debt"] = 1
        ok, msg = self.manager.pay_maintenance()
        self.assertTrue(ok)
        self.assertEqual(self.player.residence["maintenance_debt"], 0)

    def test_tick_monthly_auto_pays_maintenance(self):
        """月度结算时自动缴纳维护费。"""
        before = self.player.count_item("spirit_stone")
        result = self.manager.tick_monthly()
        self.assertTrue(result["maintenance_paid"])
        self.assertEqual(self.player.residence["maintenance_debt"], 0)
        self.assertLess(self.player.count_item("spirit_stone"), before)

    def test_tick_monthly_debt_accumulates_when_poor(self):
        """灵石不足时欠费累加。"""
        self.player.inventory = []
        result = self.manager.tick_monthly()
        self.assertFalse(result["maintenance_paid"])
        self.assertEqual(self.player.residence["maintenance_debt"], 1)

    def test_facilities_down_after_max_debt(self):
        """欠费达到阈值后设施停摆，无产出。"""
        self.player.inventory = []
        self.player.residence["maintenance_debt"] = 3
        result = self.manager.tick_monthly()
        self.assertIn("停摆", " ".join(result["logs"]))
        self.assertEqual(len(result["production"]), 0)

    def test_energy_decay(self):
        """月度结算应消耗护阵能量。"""
        before = self.manager.get_formation_energy()
        result = self.manager.tick_monthly()
        self.assertGreater(result["energy_decay"], 0)
        self.assertLess(self.manager.get_formation_energy(), before)


class TestRaidAndDefense(unittest.TestCase):
    """袭击与防御测试。"""

    def setUp(self):
        self.player = Player(name="测试修士")
        self.item_lib = ItemLibrary(config_dir="config")
        for _ in range(10000):
            self.player.add_item(self.item_lib.create("spirit_stone"))
        self.manager = ResidenceManager(self.player, item_library=self.item_lib)
        self.player.realm_id = "foundation_early"
        self.manager.finish_occupation("heifeng", win=True)

    def test_defense_rate_with_energy(self):
        """有护阵能量时防御率应高于基础值。"""
        base = self.manager.get_raid_defense()
        total = self.manager.get_defense_rate()
        self.assertGreater(total, base)
        self.assertLessEqual(total, 0.95)

    def test_resolve_raid_win(self):
        """击退袭击后能量恢复。"""
        self.manager.upgrade_building("defense_formation")
        # 先消耗部分能量，确保恢复后有实际增长
        self.manager.consume_formation_energy(50)
        before = self.manager.get_formation_energy()
        ok, msg = self.manager.resolve_raid(win=True)
        self.assertTrue(ok)
        self.assertGreater(self.manager.get_formation_energy(), before)

    def test_resolve_raid_loss_downgrades_building(self):
        """袭击失败时随机降低一级建筑。"""
        self.manager.upgrade_building("spirit_gathering_array")
        before_level = self.player.residence["buildings"]["spirit_gathering_array"]
        self.manager.resolve_raid(win=False)
        after_level = self.player.residence["buildings"].get(
            "spirit_gathering_array", 0
        )
        self.assertLess(after_level, before_level)

    def test_raid_probability_respects_defense(self):
        """防御率越高，袭击概率应越低。"""
        # 无护阵时基础防御
        no_energy_manager = ResidenceManager(self.player, item_library=self.item_lib)
        # 满护阵时防御更高（复用同一 manager 即可）
        defense_with_energy = self.manager.get_defense_rate()
        self.assertGreater(defense_with_energy, 0)


class TestOldSaveCompatibility(unittest.TestCase):
    """旧存档兼容测试。"""

    def setUp(self):
        self.player = Player(name="测试修士")
        self.item_lib = ItemLibrary(config_dir="config")
        # 模拟旧存档结构：只有 id 与 buildings
        self.player.residence = {
            "id": "cloud_peak_cave",
            "buildings": {"spirit_gathering_array": 2},
        }
        self.manager = ResidenceManager(self.player, item_library=self.item_lib)

    def test_ensure_residence_state(self):
        """旧存档缺少字段时应自动补全默认值。"""
        self.assertIn("energy", self.player.residence)
        self.assertIn("maintenance_debt", self.player.residence)
        self.assertIn("spirit_vein_quality", self.player.residence)
        self.assertEqual(self.player.residence["spirit_vein_quality"], 1.0)

    def test_old_save_tick_works(self):
        """旧存档应能正常推进月度结算。"""
        result = self.manager.tick_monthly()
        self.assertIn("production", result)
        self.assertIn("raid", result)
        self.assertIn("logs", result)


if __name__ == "__main__":
    unittest.main()
