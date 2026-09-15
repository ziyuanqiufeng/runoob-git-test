# -*- coding: utf-8 -*-
"""主角头像 UI 测试。

验证状态面板、战斗界面、对话界面能正确加载并显示玩家头像，
以及头像边框颜色随境界变化的逻辑。
"""
import os
import shutil
import tempfile
import unittest
from unittest.mock import patch

from PySide6.QtWidgets import QApplication
from PIL import Image

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
from game.portrait_generator import generate_portrait, get_major_realm_portrait_path
from ui.status_panel import StatusPanel, _get_realm_border_color
from ui.character_creation_dialog import CharacterCreationDialog
from ui.combat_dialog import CombatDialog
from ui.dialogue_dialog import DialogueDialog


class TestRealmBorderColor(unittest.TestCase):
    """头像边框颜色随境界变化。"""

    def test_qi_refining_color(self):
        self.assertEqual(_get_realm_border_color("qi_refining_1"), "#95a5a6")

    def test_foundation_color(self):
        self.assertEqual(_get_realm_border_color("foundation_early"), "#2ecc71")

    def test_golden_core_color(self):
        self.assertEqual(_get_realm_border_color("golden_core_mid"), "#f1c40f")

    def test_nascent_soul_color(self):
        self.assertEqual(_get_realm_border_color("nascent_soul"), "#9b59b6")

    def test_unknown_realm_defaults(self):
        self.assertEqual(_get_realm_border_color("unknown"), "#95a5a6")


class TestCharacterCreationDialog(unittest.TestCase):
    """角色创建弹窗。"""

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_default_values(self):
        dialog = CharacterCreationDialog()
        self.assertEqual(dialog.get_name(), "无名散修")
        self.assertIn("protagonist_default.png", dialog.get_portrait())

    def test_custom_name(self):
        dialog = CharacterCreationDialog()
        dialog.name_edit.setText("测试道者")
        self.assertEqual(dialog.get_name(), "测试道者")

    def test_gender_selection(self):
        """性别选择应正确返回 male/female。"""
        dialog = CharacterCreationDialog()
        # 默认男性
        self.assertEqual(dialog.get_gender(), "male")
        # 切换为女性
        dialog.gender_combo.setCurrentIndex(1)
        self.assertEqual(dialog.get_gender(), "female")


class TestPortraitGenerator(unittest.TestCase):
    """立绘生成器测试。"""

    def test_build_prompt_includes_gender_and_elements(self):
        """提示词应包含性别、灵根、流派、境界与画风信息。"""
        player = Player(name="测试")
        player.gender = "female"
        player.set_spiritual_roots(["fire", "water"])
        player.cultivation_path = "jian"
        player.realm_id = "golden_core_early"
        from game.portrait_generator import build_prompt
        prompt = build_prompt(player)
        self.assertIn("woman", prompt.lower())
        self.assertIn("sword cultivator", prompt.lower())
        self.assertIn("fire", prompt.lower())
        self.assertIn("water", prompt.lower())
        self.assertIn("Golden Core", prompt)
        self.assertIn("style", prompt.lower())

    def test_generate_portrait_fallback(self):
        """AI 接口不可用时，应回退到本地占位图。"""
        player = Player(name="测试")
        player.gender = "male"
        with tempfile.TemporaryDirectory() as tmpdir:
            ok, path = generate_portrait(player, output_dir=tmpdir, use_ai=False)
            self.assertTrue(ok)
            self.assertTrue(os.path.exists(path))
            # 占位图应能被 PIL 正常打开
            with Image.open(path) as img:
                self.assertGreater(img.width, 0)

    def test_generate_default_portrait_resource(self):
        """默认资源生成函数应按规则产出可打开的图片。"""
        from game.portrait_generator import generate_default_portrait_resource
        with tempfile.TemporaryDirectory() as tmpdir:
            path = generate_default_portrait_resource(
                "foundation", "jian", "female", output_dir=tmpdir, size=64
            )
            self.assertTrue(path.endswith("protagonist_foundation_jian_female.png"))
            self.assertTrue(os.path.exists(path))
            with Image.open(path) as img:
                self.assertEqual(img.width, 64)
                self.assertEqual(img.height, 64)

    def test_generate_all_default_portrait_resources(self):
        """应生成 3 境界 × 10 流派 × 2 性别 = 60 张默认立绘。"""
        from game.portrait_generator import generate_all_default_portrait_resources
        with tempfile.TemporaryDirectory() as tmpdir:
            paths = generate_all_default_portrait_resources(output_dir=tmpdir, size=32)
            self.assertEqual(len(paths), 60)
            for path in paths:
                self.assertTrue(os.path.exists(path))

    def test_ensure_default_portrait_resources_only_fills_missing(self):
        """ensure_default_portrait_resources 应只补齐缺失文件，不重复生成已有文件。"""
        from game.portrait_generator import ensure_default_portrait_resources
        with tempfile.TemporaryDirectory() as tmpdir:
            generated, total = ensure_default_portrait_resources(output_dir=tmpdir, size=32)
            self.assertEqual(generated, total)
            # 再次调用时无缺失
            generated2, total2 = ensure_default_portrait_resources(output_dir=tmpdir, size=32)
            self.assertEqual(generated2, 0)
            self.assertEqual(total2, total)


class TestStatusPanelPortrait(unittest.TestCase):
    """状态面板头像显示。"""

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.player = Player(name="测试修士")
        self.world = World(config_dir="config")
        self.panel = StatusPanel(self.player, self.world)

    def test_portrait_label_exists(self):
        self.assertIsNotNone(self.panel.portrait_label)
        self.assertEqual(self.panel.portrait_label.size().width(), 80)

    def test_default_portrait_loaded(self):
        self.panel.update_status()
        self.assertFalse(self.panel.portrait_label.text())
        self.assertFalse(self.panel.portrait_label.pixmap().isNull())

    def test_realm_border_color_applied(self):
        self.player.realm_id = "golden_core_early"
        self.player.cultivation_path = "jian"
        self.panel.update_status()
        style = self.panel.portrait_label.styleSheet()
        self.assertIn("#f1c40f", style)

    def test_portrait_glow_effect_on_breakthrough(self):
        """大境界突破后头像光效应被激活。"""
        self.player.portrait_glow_until_month = (
            (self.world.year - 1) * 12 + (self.world.month - 1) + 1
        )
        self.panel.update_status()
        # 光效通过 QGraphicsDropShadowEffect 实现
        self.assertIsNotNone(self.panel.portrait_label.graphicsEffect())

    def test_portrait_glow_effect_expired(self):
        """光效过期后不应再存在。"""
        self.player.portrait_glow_until_month = 0
        self.panel.update_status()
        self.assertIsNone(self.panel.portrait_label.graphicsEffect())


class TestCombatDialogPortrait(unittest.TestCase):
    """战斗界面玩家头像显示。"""

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
            save_manager=SaveManager(save_path="test_portrait_combat.json"),
        )
        enemy_data = self.enemy_lib.get("wolf")
        enemy = Enemy.from_dict(enemy_data)
        self.dialog = CombatDialog(self.player, enemy, self.engine)

    def tearDown(self):
        if os.path.exists("test_portrait_combat.json"):
            os.remove("test_portrait_combat.json")

    def test_player_portrait_exists(self):
        self.assertIsNotNone(self.dialog.player_portrait)
        self.assertFalse(self.dialog.player_portrait.pixmap().isNull())


class TestDialogueDialogPortrait(unittest.TestCase):
    """对话界面玩家头像显示。"""

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
            save_manager=SaveManager(save_path="test_portrait_dialogue.json"),
        )

    def tearDown(self):
        if os.path.exists("test_portrait_dialogue.json"):
            os.remove("test_portrait_dialogue.json")

    def test_player_portrait_label_exists(self):
        dialog = DialogueDialog(self.engine, "fufeng_lord_greeting", parent=None)
        self.assertIsNotNone(dialog.player_portrait_label)
        self.assertFalse(dialog.player_portrait_label.pixmap().isNull())
        dialog.close()

    def test_npc_portrait_uses_qpixmap(self):
        """NPC 头像应通过 QPixmap 加载，而不是 stylesheet 的 background-image。"""
        # 为 NPC 创建一个临时头像文件
        tmpdir = tempfile.mkdtemp()
        portrait_path = os.path.join(tmpdir, "test_npc.png")
        Image.new("RGB", (64, 64), color=(100, 150, 200)).save(portrait_path)
        try:
            npc = self.engine.npc_library.get("fufeng_lord")
            npc.portrait = portrait_path
            dialog = DialogueDialog(self.engine, "fufeng_lord_greeting", parent=None)
            # 渲染首节点后，NPC 头像标签应显示 QPixmap
            self.assertFalse(dialog.portrait_label.pixmap().isNull())
            dialog.close()
        finally:
            shutil.rmtree(tmpdir)


class TestBreakthroughPortraitSwitch(unittest.TestCase):
    """大境界突破头像切换测试。"""

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
            save_manager=SaveManager(save_path="test_portrait_breakthrough.json"),
        )

    def tearDown(self):
        if os.path.exists("test_portrait_breakthrough.json"):
            os.remove("test_portrait_breakthrough.json")

    def _make_portrait_file(self, path):
        """生成一个临时头像文件。"""
        Image.new("RGB", (64, 64), color=(200, 200, 200)).save(path)

    def test_major_breakthrough_switches_portrait(self):
        """大境界突破成功且存在高阶头像资源时，应自动切换头像。"""
        # 准备筑基期高阶头像（使用最精确匹配规则）
        foundation_portrait = "assets/portraits/protagonist_foundation_fa_male.png"
        self._make_portrait_file(foundation_portrait)

        # 设置玩家为练气圆满并充满修为
        self.player.realm_id = "qi_refining_9"
        realm = self.world.get_realm(self.player.realm_id)
        self.player.qi = realm["max_qi"]

        # 屏蔽渡劫弹窗与随机性，确保突破成功；同时固定头像匹配结果
        patches = [
            patch.object(self.engine.weather_manager, "get_breakthrough_bonus", return_value=0.0),
            patch.object(self.engine.mental_state_manager, "on_breakthrough"),
            patch("random.random", return_value=0.0),
            patch("game.engine.find_best_portrait_resource", return_value=foundation_portrait),
        ]
        for p in patches:
            p.start()
        try:
            self.engine.breakthrough()
            self.assertEqual(self.player.realm_id, "foundation_early")
            self.assertEqual(self.player.portrait, foundation_portrait)
            # 光效应被激活（持续 12 个月）
            total_months = self.engine._world_total_months()
            self.assertTrue(self.player.is_portrait_glow_active(total_months))
        finally:
            for p in patches:
                p.stop()
        # 清理本次测试创建的临时头像
        if os.path.exists(foundation_portrait):
            os.remove(foundation_portrait)

    def test_major_breakthrough_glow_without_portrait(self):
        """大境界突破成功但无高阶头像资源时，应启用光效边框。"""
        self.player.realm_id = "foundation_peak"
        realm = self.world.get_realm(self.player.realm_id)
        self.player.qi = realm["max_qi"]

        # 屏蔽渡劫弹窗与随机性，并模拟无高阶头像资源可用
        patches = [
            patch.object(self.engine.weather_manager, "get_breakthrough_bonus", return_value=0.0),
            patch.object(self.engine.mental_state_manager, "on_breakthrough"),
            patch("random.random", return_value=0.0),
            patch("game.engine.find_best_portrait_resource", return_value=None),
        ]
        for p in patches:
            p.start()
        try:
            old_portrait = self.player.portrait
            self.engine.breakthrough()
            self.assertEqual(self.player.realm_id, "golden_core_early")
            # 无高阶资源时不切换头像
            self.assertEqual(self.player.portrait, old_portrait)
            total_months = self.engine._world_total_months()
            self.assertTrue(self.player.is_portrait_glow_active(total_months))
        finally:
            for p in patches:
                p.stop()


if __name__ == "__main__":
    unittest.main()
