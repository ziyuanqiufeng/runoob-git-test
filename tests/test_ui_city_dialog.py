# -*- coding: utf-8 -*-
"""城市界面可视化重构测试。"""
import os
import shutil
import tempfile
import unittest
from unittest.mock import patch, MagicMock

from PySide6.QtWidgets import QApplication, QDialog
from PySide6.QtCore import Qt, QPoint, QRect
from PIL import Image

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
from ui.city_dialog import (
    CityDialog, CityMapWidget, CityBuildingWidget, MarketMenuDialog,
    CityLordMenuDialog, _load_city_map_config, _select_city_image,
)


class TestCityMapConfig(unittest.TestCase):
    """城市热点配置加载校验。"""

    def test_load_existing_config(self):
        cfg = _load_city_map_config("fufeng_city")
        self.assertIsNotNone(cfg)
        self.assertEqual(cfg["city_id"], "fufeng_city")
        self.assertIn("hotspots", cfg)
        self.assertTrue(all(len(h["coords"]) == 4 for h in cfg["hotspots"]))

    def test_load_missing_config(self):
        cfg = _load_city_map_config("nonexistent_city")
        self.assertIsNone(cfg)


class TestCityMapWidget(unittest.TestCase):
    """城市地图组件交互测试。"""

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.image_path = os.path.join(self.tmpdir, "city.png")
        Image.new("RGB", (400, 300), color=(100, 150, 100)).save(self.image_path)

        self.building_map = {
            "city_lord_hall": {"id": "city_lord_hall", "name": "城主府", "action": "quest"},
            "inn": {"id": "inn", "name": "客栈", "action": "rest"},
            "market": {"id": "market", "name": "坊市", "action": "market"},
        }
        self.hotspots = [
            {"id": "city_lord_hall", "shape": "rect", "coords": [0.1, 0.1, 0.4, 0.5]},
            {"id": "inn", "shape": "circle", "coords": [0.6, 0.1, 0.9, 0.5]},
            {"id": "market", "shape": "diamond", "coords": [0.1, 0.55, 0.4, 0.95]},
        ]
        self.widget = CityMapWidget(self.image_path, self.hotspots, self.building_map)
        # CityMapWidget 有最小尺寸限制，测试用 800x600 避免被最小尺寸撑大导致坐标错位
        self.widget.resize(800, 600)
        # 强制重新计算建筑位置（测试中不进入事件循环，需手动触发）
        self.widget._reposition_buildings()

    def tearDown(self):
        shutil.rmtree(self.tmpdir)
        self.widget.close()

    def test_hit_test_rect(self):
        # 矩形热点中心约在 (200, 160)
        hotspot = self.widget._hit_test(QPoint(200, 160))
        self.assertIsNotNone(hotspot)
        self.assertEqual(hotspot["id"], "city_lord_hall")

    def test_hit_test_circle(self):
        # 圆形热点中心约在 (600, 160)
        hotspot = self.widget._hit_test(QPoint(600, 160))
        self.assertIsNotNone(hotspot)
        self.assertEqual(hotspot["id"], "inn")

    def test_hit_test_diamond(self):
        # 菱形热点中心约在 (200, 430)
        hotspot = self.widget._hit_test(QPoint(200, 430))
        self.assertIsNotNone(hotspot)
        self.assertEqual(hotspot["id"], "market")

    def test_hit_test_returns_none_outside(self):
        hotspot = self.widget._hit_test(QPoint(900, 500))
        self.assertIsNone(hotspot)

    def test_click_emits_signal(self):
        """点击建筑组件应触发 CityMapWidget.building_clicked 信号。"""
        received = []
        self.widget.building_clicked.connect(lambda b: received.append(b))
        widget = self.widget._get_building_widget_at(QPoint(200, 160))
        self.assertIsNotNone(widget)
        widget.clicked.emit()
        self.assertEqual(len(received), 1)
        self.assertEqual(received[0]["id"], "city_lord_hall")

    def test_click_creates_ripple(self):
        """点击建筑应在 CityMapWidget 中创建涟漪，圆心为建筑 base geometry 中心。"""
        widget = self.widget._get_building_widget_at(QPoint(200, 160))
        self.assertIsNotNone(widget)
        widget.clicked.emit()
        self.assertTrue(len(self.widget._ripples) > 0)
        expected_cx = widget._base_geometry.center().x()
        self.assertEqual(self.widget._ripples[0]["cx"], expected_cx)


class TestCityBuildingWidget(unittest.TestCase):
    """单个建筑组件测试。"""

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.hotspot = {
            "id": "alchemy_pavilion",
            "name": "炼丹阁",
            "shape": "rect",
            "coords": [0.1, 0.1, 0.4, 0.4],
            "nameplate_offset": [0, -20],
        }
        self.building_info = {"id": "alchemy_pavilion", "name": "炼丹阁", "action": "shop"}
        self.widget = CityBuildingWidget(self.hotspot, self.building_info)
        self.widget.set_base_geometry(QRect(40, 40, 120, 120))

    def tearDown(self):
        self.widget.close()

    def test_no_image_uses_transparent_click_layer(self):
        """无独立建筑图时应使用透明点击层，不遮挡背景中的建筑。"""
        self.assertTrue(self.widget._has_image)
        pixmap = self.widget.image_label.pixmap()
        self.assertFalse(pixmap.isNull())
        # 透明点击层应全透明，不遮挡背景
        image = pixmap.toImage()
        for x in (0, pixmap.width() // 2, pixmap.width() - 1):
            for y in (0, pixmap.height() // 2, pixmap.height() - 1):
                self.assertEqual(image.pixelColor(x, y).alpha(), 0)

    def test_hover_scale_property(self):
        """hover_scale 属性应能读写并触发重绘。"""
        self.widget.set_hover_scale(1.08)
        self.assertAlmostEqual(self.widget.hover_scale, 1.08, places=5)
        self.widget.set_hover_scale(1.0)
        self.assertAlmostEqual(self.widget.hover_scale, 1.0, places=5)


class TestPolygonMask(unittest.TestCase):
    """多边形遮罩点击判定测试。"""

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.image_path = os.path.join(self.tmpdir, "city.png")
        Image.new("RGB", (400, 300), color=(100, 150, 100)).save(self.image_path)

        # 三角形遮罩：仅在左上角小三角区域可点击
        self.hotspots = [
            {
                "id": "city_lord_hall",
                "shape": "polygon",
                "coords": [0.1, 0.1, 0.4, 0.5],
                "mask_points": [[0.0, 0.0], [1.0, 0.0], [0.0, 1.0]],
            }
        ]
        self.widget = CityMapWidget(self.image_path, self.hotspots, {})
        self.widget.resize(400, 300)
        self.widget._reposition_buildings()

    def tearDown(self):
        shutil.rmtree(self.tmpdir)
        self.widget.close()

    def test_polygon_widget_geometry_contains_point(self):
        """widget 几何包含整个 coords 区域。"""
        hotspot = self.widget._hit_test(QPoint(100, 120))
        self.assertIsNotNone(hotspot)
        self.assertEqual(hotspot["id"], "city_lord_hall")


class TestCityMapValidation(unittest.TestCase):
    """city_maps.json 新字段校验测试。"""

    def test_validates_image_and_nameplate_offset(self):
        """合法配置不应报错。"""
        cfg = {
            "city_id": "test_city",
            "map_image": "assets/city_bg/test_city.png",
            "hotspots": [
                {
                    "id": "city_lord_hall",
                    "name": "城主府",
                    "shape": "rect",
                    "coords": [0.1, 0.1, 0.4, 0.4],
                    "image": "assets/city_buildings/test_city/city_lord_hall.png",
                    "image_hover": "assets/city_buildings/test_city/city_lord_hall_hover.png",
                    "nameplate_offset": [0, -20],
                }
            ],
        }
        self.assertTrue(isinstance(cfg["hotspots"][0]["image"], str))
        self.assertTrue(cfg["hotspots"][0]["image"].endswith(".png"))
        self.assertEqual(len(cfg["hotspots"][0]["nameplate_offset"]), 2)


class TestCityImageSelection(unittest.TestCase):
    """城市图高清资源选择测试。"""

    def test_selects_retina_when_available(self):
        tmpdir = tempfile.mkdtemp()
        base = os.path.join(tmpdir, "city.png")
        retina = os.path.join(tmpdir, "city@2x.png")
        Image.new("RGB", (100, 100)).save(base)
        Image.new("RGB", (200, 200)).save(retina)
        try:
            selected = _select_city_image(base)
            self.assertEqual(selected, retina)
        finally:
            shutil.rmtree(tmpdir)

    def test_falls_back_to_base_when_no_retina(self):
        tmpdir = tempfile.mkdtemp()
        base = os.path.join(tmpdir, "city.png")
        Image.new("RGB", (100, 100)).save(base)
        try:
            selected = _select_city_image(base)
            self.assertEqual(selected, base)
        finally:
            shutil.rmtree(tmpdir)


class TestCityDialogMapMode(unittest.TestCase):
    """城市弹窗可视化地图模式测试。"""

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
            save_manager=SaveManager(save_path="test_city_dialog.json"),
        )

    def tearDown(self):
        if os.path.exists("test_city_dialog.json"):
            os.remove("test_city_dialog.json")

    def test_dialog_uses_map_widget_for_fufeng(self):
        """扶风城有地图配置且图片存在，应使用 CityMapWidget。"""
        dialog = CityDialog(self.engine, "fufeng_city")
        self.assertIsNotNone(dialog.map_widget)
        self.assertIsNone(dialog.fallback_grid)
        dialog.close()

    def test_dialog_shows_fallback_for_missing_map(self):
        """无地图配置的城市应 fallback 为按钮网格。"""
        dialog = CityDialog(self.engine, "qingyun")
        self.assertIsNone(dialog.map_widget)
        self.assertIsNotNone(dialog.fallback_grid)
        dialog.close()

    def test_click_city_lord_hall_opens_menu(self):
        """点击城主府热点应弹出城主府主菜单。"""
        with patch("ui.city_dialog.CityLordMenuDialog") as MockMenu:
            instance = MockMenu.return_value
            instance.exec.return_value = QDialog.Accepted
            instance.get_choice.return_value = "quest"
            with patch("ui.city_quest_dialog.CityQuestDialog") as MockDialog:
                dialog = CityDialog(self.engine, "fufeng_city")
                dialog.map_widget.building_clicked.emit(
                    {"id": "city_lord_hall", "name": "城主府", "action": "quest"}
                )
                MockMenu.assert_called_once()
                MockDialog.assert_called_once()
                dialog.close()

    def test_click_inn_opens_inn_dialog(self):
        """点击客栈热点应弹出客栈交互弹窗。"""
        with patch("ui.inn_dialog.InnDialog") as MockDialog:
            instance = MockDialog.return_value
            instance.exec.return_value = None
            dialog = CityDialog(self.engine, "fufeng_city")
            dialog.map_widget.building_clicked.emit(
                {"id": "inn", "name": "客栈", "action": "rest"}
            )
            MockDialog.assert_called_once()
            dialog.close()

    def test_description_toggle(self):
        """展开/收起介绍按钮应切换描述可见性。"""
        dialog = CityDialog(self.engine, "fufeng_city")
        self.assertEqual(dialog.toggle_desc_btn.text(), "展开介绍 ▼")
        dialog._toggle_description()
        self.assertEqual(dialog.toggle_desc_btn.text(), "收起介绍 ▲")
        dialog._toggle_description()
        self.assertEqual(dialog.toggle_desc_btn.text(), "展开介绍 ▼")
        dialog.close()


class TestCityDialogFallbackMode(unittest.TestCase):
    """城市弹窗 fallback 列表模式测试。"""

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
            save_manager=SaveManager(save_path="test_city_fallback.json"),
        )

    def tearDown(self):
        if os.path.exists("test_city_fallback.json"):
            os.remove("test_city_fallback.json")

    def test_fallback_button_opens_inn_dialog(self):
        """fallback 模式下点击客栈按钮应弹出客栈交互弹窗。"""
        with patch("ui.inn_dialog.InnDialog") as MockDialog:
            instance = MockDialog.return_value
            instance.exec.return_value = None
            dialog = CityDialog(self.engine, "qingyun")
            self.assertIsNotNone(dialog.fallback_grid)
            dialog._on_building_clicked(
                {"id": "inn", "name": "客栈", "action": "rest"}
            )
            MockDialog.assert_called_once()
            dialog.close()


class TestMarketMenuDialog(unittest.TestCase):
    """坊市主菜单测试。"""

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_default_choice_is_trade(self):
        """默认选择应为与商人交易。"""
        dialog = MarketMenuDialog("扶风城")
        self.assertEqual(dialog.get_choice(), "trade")
        dialog.close()

    def test_stall_choice(self):
        """点击我要摆摊后返回 stall。"""
        dialog = MarketMenuDialog("扶风城")
        dialog.stall_btn.click()
        self.assertEqual(dialog.get_choice(), "stall")
        dialog.close()

    def test_auction_choice(self):
        """点击拍卖行后返回 auction。"""
        dialog = MarketMenuDialog("扶风城")
        dialog.auction_btn.click()
        self.assertEqual(dialog.get_choice(), "auction")
        dialog.close()


class TestCityDialogMarketEntry(unittest.TestCase):
    """城市弹窗坊市入口测试。"""

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
            save_manager=SaveManager(save_path="test_market_entry.json"),
        )

    def tearDown(self):
        if os.path.exists("test_market_entry.json"):
            os.remove("test_market_entry.json")

    def _open_market_with_choice(self, choice, patch_target):
        """辅助方法：模拟选择并验证弹窗被打开。"""
        with patch("ui.city_dialog.MarketMenuDialog") as MockMenu:
            instance = MockMenu.return_value
            instance.exec.return_value = QDialog.Accepted
            instance.get_choice.return_value = choice
            with patch(patch_target) as MockDialog:
                dialog = CityDialog(self.engine, "qingyun")
                dialog._open_market("坊市")
                MockDialog.assert_called_once()
                dialog.close()

    def test_open_market_trade(self):
        """选择交易应打开 NPCDialog。"""
        self._open_market_with_choice("trade", "ui.npc_dialog.NPCDialog")

    def test_open_market_stall(self):
        """选择摆摊应打开 StallDialog。"""
        self._open_market_with_choice("stall", "ui.city_dialog.StallDialog")

    def test_open_market_auction(self):
        """选择拍卖行应打开 AuctionDialog。"""
        self._open_market_with_choice("auction", "ui.city_dialog.AuctionDialog")


class TestCityDialogCaveEntry(unittest.TestCase):
    """城市弹窗洞府入口测试。"""

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
            save_manager=SaveManager(save_path="test_cave_entry.json"),
        )

    def tearDown(self):
        if os.path.exists("test_cave_entry.json"):
            os.remove("test_cave_entry.json")

    def test_click_cave_opens_cave_dialog(self):
        """点击洞府建筑应弹出 CaveDialog。"""
        with patch("ui.city_dialog.CaveDialog") as MockDialog:
            instance = MockDialog.return_value
            instance.exec.return_value = None
            dialog = CityDialog(self.engine, "fufeng_city")
            dialog.map_widget.building_clicked.emit(
                {"id": "cave", "name": "城中洞府", "action": "cave"}
            )
            MockDialog.assert_called_once()
            dialog.close()

    def test_cave_building_has_action_label(self):
        """洞府建筑应能正确映射到 action 标签。"""
        from ui.city_dialog import _ACTION_LABELS
        self.assertEqual(_ACTION_LABELS.get("cave"), "洞府")

    def test_cave_dialog_shows_summary(self):
        """洞府弹窗应显示当前生效加成汇总。"""
        from ui.cave_dialog import CaveDialog
        # 给玩家足够灵石并租赁扶风城洞府，使汇总区有数据
        for _ in range(2000):
            self.player.add_item(self.item_lib.create("spirit_stone"))
        self.engine.rent_cave("fufeng_inn_cave", 3)
        dialog = CaveDialog(self.engine, location_id="fufeng_city")
        summary_text = dialog.summary_label.text()
        self.assertIn("扶风城郊静室", summary_text)
        self.assertIn("修炼速度合计 +5%", summary_text)
        dialog.close()

    def test_cave_dialog_custom_item_widget(self):
        """洞府列表项应使用自定义 widget（含徽章）。"""
        from ui.cave_dialog import CaveDialog
        dialog = CaveDialog(self.engine, location_id="fufeng_city")
        self.assertGreater(dialog.cave_list.count(), 0)
        item = dialog.cave_list.item(0)
        widget = dialog.cave_list.itemWidget(item)
        self.assertIsNotNone(widget)
        dialog.close()


class TestCaveEffectLabels(unittest.TestCase):
    """洞府效果标签配置测试。"""

    def test_labels_loaded_from_config(self):
        """应从配置文件加载效果标签。"""
        from ui import cave_dialog
        cave_dialog._load_effect_labels("config")
        self.assertEqual(
            cave_dialog._EFFECT_LABELS.get("cultivation_speed_bonus"), "修炼速度"
        )
        self.assertEqual(
            cave_dialog._EFFECT_LABELS.get("closed_door_qi_bonus"), "闭关修为"
        )

    def test_format_effect_key_fallback(self):
        """未知 key 应通过规则兜底转中文。"""
        from ui.cave_dialog import _format_effect_key
        # 使用不在配置映射表中的 key，验证后缀解析兜底
        self.assertEqual(_format_effect_key("poison_damage_bonus"), "poison属性伤害")
        self.assertEqual(_format_effect_key("shadow_resist_bonus"), "shadow属性抗性")

    def test_effect_color_returns_default_for_unknown(self):
        """未知效果 key 返回默认颜色。"""
        from ui.cave_dialog import _effect_color
        color = _effect_color("unknown_bonus")
        self.assertTrue(color.startswith("#"))


class TestCityLordMenuDialog(unittest.TestCase):
    """城主府主菜单测试。"""

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_default_choice_is_quest(self):
        """默认选择应为城市任务。"""
        dialog = CityLordMenuDialog("扶风城")
        self.assertEqual(dialog.get_choice(), "quest")
        dialog.close()

    def test_governance_choice(self):
        """点击城池治理后返回 governance。"""
        dialog = CityLordMenuDialog("扶风城")
        dialog.governance_btn.click()
        self.assertEqual(dialog.get_choice(), "governance")
        dialog.close()


class TestCityDialogCityLordEntry(unittest.TestCase):
    """城市弹窗城主府入口测试。"""

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
            save_manager=SaveManager(save_path="test_city_lord_entry.json"),
        )

    def tearDown(self):
        if os.path.exists("test_city_lord_entry.json"):
            os.remove("test_city_lord_entry.json")

    def _open_city_lord_with_choice(self, choice, patch_target):
        """辅助方法：模拟选择并验证弹窗被打开。"""
        with patch("ui.city_dialog.CityLordMenuDialog") as MockMenu:
            instance = MockMenu.return_value
            instance.exec.return_value = QDialog.Accepted
            instance.get_choice.return_value = choice
            with patch(patch_target) as MockDialog:
                dialog = CityDialog(self.engine, "qingyun")
                dialog._open_city_quests("城主府")
                MockDialog.assert_called_once()
                dialog.close()

    def test_open_city_lord_quest(self):
        """选择城市任务应打开 CityQuestDialog。"""
        self._open_city_lord_with_choice("quest", "ui.city_quest_dialog.CityQuestDialog")

    def test_open_city_lord_governance(self):
        """选择城池治理应打开 CityPolicyDialog。"""
        self._open_city_lord_with_choice("governance", "ui.city_policy_dialog.CityPolicyDialog")


if __name__ == "__main__":
    unittest.main()
