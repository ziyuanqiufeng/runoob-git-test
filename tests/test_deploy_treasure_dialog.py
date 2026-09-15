# -*- coding: utf-8 -*-
"""维度③·M24 战斗前可部署法宝预览确认弹窗测试（无头）。

验证：
- DeployPreviewDialog 构造时为每件可部署法宝生成勾选框，默认全勾选；
- chosen_item_ids 正确反映勾选状态（取消勾选即从列表剔除）；
- deploy_chosen 逐件部署、消耗物品、仅返回成功项、跳过不可部署项；
- run 在 exec 返回 Accepted 时走真实部署路径；
- combat_dialog「部署法宝」按钮调用 DeployPreviewDialog.run 并写日志刷新。
"""
import unittest
from unittest.mock import patch

from PySide6.QtWidgets import QApplication, QDialog

from game.player import Player
from game.world import World
from game.events import EventPool
from game.item import ItemLibrary
from game.enemy import Enemy, EnemyLibrary
from game.skill import SkillLibrary
from game.npc import NPCLibrary
from game.quest import QuestLibrary
from game.engine import GameEngine

from ui.deploy_treasure_dialog import DeployPreviewDialog
from ui.combat_dialog import CombatDialog


class TestDeployPreviewDialog(unittest.TestCase):
    """部署预览确认弹窗（维度③·M24）。"""

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def _make_engine(self):
        player = Player(name="部署预览测试")
        engine = GameEngine(
            player, World(config_dir="config"), EventPool(config_dir="config"),
            ItemLibrary(config_dir="config"), EnemyLibrary(config_dir="config"),
            SkillLibrary(config_dir="config"), NPCLibrary(config_dir="config"),
            QuestLibrary(config_dir="config"), save_manager=None, config_dir="config",
        )
        return engine

    def _add_item(self, engine, item_id, n=1):
        for _ in range(n):
            engine.player.add_item(engine.item_library.create(item_id))

    def _create_enemy(self, **kwargs):
        data = {
            "id": "test_enemy", "name": "测试敌人", "alignment": "neutral",
            "hp": 100, "attack": 10, "defense": 0, "exp": 0, "loot": [],
        }
        data.update(kwargs)
        return Enemy.from_dict(data)

    # ---- 1. 构造生成勾选框，默认全勾选 ----
    def test_builds_checks_all_checked_by_default(self):
        engine = self._make_engine()
        self._add_item(engine, "talisman_paper")
        self._add_item(engine, "array_disk")
        engine.start_combat(self._create_enemy())

        dlg = DeployPreviewDialog(engine)
        self.assertEqual(set(dlg._checks.keys()), {"talisman_paper", "array_disk"})
        self.assertEqual(dlg.chosen_item_ids(), ["talisman_paper", "array_disk"])

    # ---- 2. 取消勾选即从选择中剔除 ----
    def test_unchecked_excluded_from_chosen(self):
        engine = self._make_engine()
        self._add_item(engine, "talisman_paper")
        self._add_item(engine, "array_disk")
        engine.start_combat(self._create_enemy())

        dlg = DeployPreviewDialog(engine)
        dlg._checks["array_disk"].setChecked(False)
        self.assertEqual(dlg.chosen_item_ids(), ["talisman_paper"])

    # ---- 3. 无可部署物时为空，chosen 为空 ----
    def test_no_deployables_yields_empty(self):
        engine = self._make_engine()
        engine.start_combat(self._create_enemy())
        dlg = DeployPreviewDialog(engine)
        self.assertEqual(dlg._checks, {})
        self.assertEqual(dlg.chosen_item_ids(), [])

    # ---- 4. deploy_chosen 逐件部署、消耗、仅返回成功项 ----
    def test_deploy_chosen_deploys_and_consumes(self):
        engine = self._make_engine()
        self._add_item(engine, "talisman_paper", 2)  # 2 个符箓
        engine.start_combat(self._create_enemy())

        deployed = DeployPreviewDialog.deploy_chosen(
            engine, ["talisman_paper", "array_disk"]  # 阵盘未持有，应跳过
        )
        self.assertEqual(deployed, ["talisman_paper"])
        self.assertEqual(engine.player.count_item("talisman_paper"), 1)
        # 符箓增益应已生效（削敌攻 + 护盾）
        self.assertEqual(len(engine.enemy_attack_down), 1)
        self.assertEqual(engine.player_shield, 30)

    # ---- 5. deploy_chosen 空列表返回空 ----
    def test_deploy_chosen_empty(self):
        engine = self._make_engine()
        engine.start_combat(self._create_enemy())
        self.assertEqual(DeployPreviewDialog.deploy_chosen(engine, []), [])

    # ---- 6. run 在 exec=Accepted 时走真实部署路径 ----
    def test_run_deploys_when_accepted(self):
        engine = self._make_engine()
        self._add_item(engine, "array_disk")
        engine.start_combat(self._create_enemy())
        with patch.object(DeployPreviewDialog, "exec",
                          return_value=QDialog.DialogCode.Accepted):
            deployed = DeployPreviewDialog.run(engine, None)
        self.assertEqual(deployed, ["array_disk"])
        self.assertEqual(len(engine.player_attack_up), 1)  # 阵盘增己攻

    # ---- 7. run 在 exec=Rejected 时不部署 ----
    def test_run_no_deploy_when_rejected(self):
        engine = self._make_engine()
        self._add_item(engine, "talisman_paper")
        engine.start_combat(self._create_enemy())
        with patch.object(DeployPreviewDialog, "exec",
                          return_value=QDialog.DialogCode.Rejected):
            deployed = DeployPreviewDialog.run(engine, None)
        self.assertEqual(deployed, [])
        self.assertEqual(engine.player.count_item("talisman_paper"), 1)  # 未消耗


class TestCombatDialogDeployButton(unittest.TestCase):
    """战斗弹窗「部署法宝」按钮接入预览弹窗（维度③·M24）。"""

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def _make_engine(self):
        player = Player(name="按钮测试")
        engine = GameEngine(
            player, World(config_dir="config"), EventPool(config_dir="config"),
            ItemLibrary(config_dir="config"), EnemyLibrary(config_dir="config"),
            SkillLibrary(config_dir="config"), NPCLibrary(config_dir="config"),
            QuestLibrary(config_dir="config"), save_manager=None, config_dir="config",
        )
        return engine

    def _create_enemy(self, **kwargs):
        data = {
            "id": "test_enemy", "name": "测试敌人", "alignment": "neutral",
            "hp": 100, "attack": 10, "defense": 0, "exp": 0, "loot": [],
        }
        data.update(kwargs)
        return Enemy.from_dict(data)

    def test_deploy_button_opens_preview_and_logs(self):
        engine = self._make_engine()
        engine.player.add_item(engine.item_library.create("talisman_paper"))
        enemy = self._create_enemy()
        engine.start_combat(enemy)

        dialog = CombatDialog(engine.player, enemy, engine)
        # 用 fake run 替代真实模态弹窗（避免阻塞），验证按钮接线
        fake = lambda eng, parent: ["talisman_paper"]
        with patch("ui.combat_dialog.DeployPreviewDialog.run", side_effect=fake):
            dialog._on_deploy_treasure()
        # 日志应体现部署结果
        full_log = dialog.log_edit.toPlainText()
        self.assertIn("部署了", full_log)
        self.assertIn("1 件法宝", full_log)


if __name__ == "__main__":
    unittest.main()
