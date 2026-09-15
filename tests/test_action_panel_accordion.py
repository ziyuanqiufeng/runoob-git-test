# -*- coding: utf-8 -*-
"""手风琴折叠面板（Accordion）的专项测试。

覆盖：
- _AccordionGroup：折叠/展开行为、头部文字（箭头+组名+数量）、body 可见性
- ActionPanel：默认互斥模式、默认展开"修行"、API 完全兼容（_button_map 完整、Signal 全保留）
- 模式切换：exclusive vs multi
- 与现有 _button_map / refresh_buttons 协作
"""
import json
import os
import sys
import unittest

# 确保 anaconda 运行环境优先（PySide6 + 本项目依赖）
_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

# 与项目其他测试一致：在无显示环境下走 offscreen 渲染
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QCheckBox

# 确保 QApplication 存在（offscreen 即可）
_app = QApplication.instance() or QApplication([])

from ui.action_panel import ActionPanel, _AccordionGroup, _BUTTON_GROUPS  # noqa: E402


class _FakePlayer:
    """满足 ActionPanel.refresh_buttons 所需的最小 player 桩。"""

    REALM_ORDER = {"qi_refining": 4, "foundation": 10, "golden_core": 14, "nascent_soul": 18}
    realm_id = "qi_refining"
    red_dust_active = False
    founded_sect = None
    heaven_gaze = 0

    def has_feature(self, name):
        # 默认让所有功能可解锁，便于测基础连通性
        return True


class _FakeEngine:
    """满足 ActionPanel 所需的最小 engine 桩。"""

    def __init__(self):
        self.player = _FakePlayer()
        self._signals = {}

    def is_feature_enabled(self, flag):
        return True

    def is_action_unlocked(self, action_name):
        return True

    def get_unlock_hint(self, action_name):
        return ""

    def notify(self, *a, **k):
        pass


class TestAccordionGroup(unittest.TestCase):
    """单组手风琴：_AccordionGroup 的基本行为。"""

    def setUp(self):
        self.engine = _FakeEngine()
        self.buttons = [
            ("alpha", "甲", "🅰", "alpha tip", "open_alpha"),
            ("beta", "乙", "🅱", "beta tip", "open_beta"),
            ("gamma", "丙", "🅲", "gamma tip", "open_gamma"),
        ]
        self.group = _AccordionGroup("测试组", self.buttons, parent=None)

    def test_initial_state_collapsed(self):
        """初始状态应该是折叠：body 不可见、header 未 checked。"""
        self.assertFalse(self.group.is_expanded())
        self.assertFalse(self.group.body.isVisible())

    def test_header_text_collapsed_uses_right_arrow_and_count(self):
        """折叠时头部文字应为：▶  测试组  (3)"""
        self.assertIn("▶", self.group.header.text())
        self.assertIn("测试组", self.group.header.text())
        self.assertIn("(3)", self.group.header.text())

    def test_header_text_expanded_uses_down_arrow(self):
        """展开时头部文字应为：▼  测试组  (3)"""
        self.group.set_expanded(True, emit_signal=False)
        self.assertIn("▼", self.group.header.text())
        self.assertIn("测试组", self.group.header.text())
        self.assertIn("(3)", self.group.header.text())

    def test_toggle_changes_body_hidden_state(self):
        """点击切换会改变 body 的 hidden 状态（offscreen 下用 isHidden 替代 isVisible）。"""
        self.assertTrue(self.group.body.isHidden())
        self.group.set_expanded(True, emit_signal=False)
        self.assertFalse(self.group.body.isHidden(), "展开后 body 应不再 hidden")
        self.group.set_expanded(False, emit_signal=False)
        self.assertTrue(self.group.body.isHidden(), "折叠后 body 应回到 hidden")

    def test_toggled_signal_emits(self):
        """toggled 信号应正确发出 (group_name, expanded)。"""
        received = []
        self.group.toggled.connect(lambda name, exp: received.append((name, exp)))
        self.group.set_expanded(True, emit_signal=True)
        self.group.set_expanded(False, emit_signal=True)
        self.assertEqual(received, [("测试组", True), ("测试组", False)])

    def test_set_expanded_no_signal(self):
        """set_expanded(expanded, emit_signal=False) 不应触发信号（互斥收起用）。"""
        received = []
        self.group.toggled.connect(lambda name, exp: received.append((name, exp)))
        self.group.set_expanded(True, emit_signal=False)
        self.assertEqual(received, [])

    def test_child_buttons_count_and_named(self):
        """子按钮数与配置一致，且每个按钮可被按 action_name 找到。"""
        self.assertEqual(len(self.group._child_buttons), 3)
        for btn, (name, text, _emoji, _tip, _action) in zip(self.group._child_buttons, self.buttons):
            self.assertEqual(btn.property("action_name"), name)
            self.assertEqual(btn.text(), text)


class TestActionPanelAccordion(unittest.TestCase):
    """ActionPanel：手风琴模式 + API 兼容。"""

    def setUp(self):
        self.engine = _FakeEngine()
        self.panel = ActionPanel(self.engine)

    def test_groups_count_matches_config(self):
        """_BUTTON_GROUPS 数量应等于 _groups 数量（当前 7：修行/行动/养成管理/修行进阶/心境世界/见闻/系统）。"""
        self.assertEqual(len(self.panel._groups), len(_BUTTON_GROUPS))
        self.assertEqual(set(self.panel._groups.keys()), {g[0] for g in _BUTTON_GROUPS})

    def test_default_mode_is_exclusive(self):
        """默认模式应是互斥（按用户推荐：保持界面整洁）。"""
        self.assertEqual(self.panel._mode, ActionPanel.MODE_EXCLUSIVE)

    def test_default_group_修行_is_expanded(self):
        """默认应展开"修行"组（最常用：闭关+突破）。"""
        self.assertTrue(self.panel._groups["修行"].is_expanded())
        for name, group in self.panel._groups.items():
            if name != "修行":
                self.assertFalse(group.is_expanded(), f"{name} 应保持折叠")

    def test_exclusive_mode_collapses_others(self):
        """互斥模式下，点开新组时其他已展开组应自动收起。"""
        # 默认"修行"已展开
        self.assertTrue(self.panel._groups["修行"].is_expanded())
        # 点开"行动"
        self.panel._groups["行动"].set_expanded(True, emit_signal=True)
        self.assertTrue(self.panel._groups["行动"].is_expanded())
        self.assertFalse(self.panel._groups["修行"].is_expanded(), "互斥：原组应自动收起")
        # 再点开"系统"
        self.panel._groups["系统"].set_expanded(True, emit_signal=True)
        self.assertTrue(self.panel._groups["系统"].is_expanded())
        self.assertFalse(self.panel._groups["行动"].is_expanded())

    def test_multi_mode_allows_multiple_expanded(self):
        """切到 multi 模式后，多个组可同时展开。"""
        self.panel.set_mode(ActionPanel.MODE_MULTI)
        self.panel._groups["修行"].set_expanded(True, emit_signal=True)
        self.panel._groups["行动"].set_expanded(True, emit_signal=True)
        self.panel._groups["系统"].set_expanded(True, emit_signal=True)
        self.assertTrue(self.panel._groups["修行"].is_expanded())
        self.assertTrue(self.panel._groups["行动"].is_expanded())
        self.assertTrue(self.panel._groups["系统"].is_expanded())

    def test_button_map_contains_all_actions(self):
        """_button_map 应包含 _BUTTON_GROUPS 中所有 action（保证旧 API 兼容）。"""
        all_actions = {b[0] for group in _BUTTON_GROUPS for b in group[1]}
        self.assertEqual(set(self.panel._button_map.keys()), all_actions)

    def test_signals_compatibility(self):
        """所有旧版 Signal 应继续存在（防止无意中删除）。"""
        required_signals = [
            "open_inventory", "open_map", "open_npc", "open_craft_life_treasure",
            "open_equipment", "open_sect", "open_residence", "open_mind_method",
            "open_farm", "open_achievement", "open_side_quest", "open_auction_house",
            "open_bounty_board", "open_compendium", "open_world_events",
            "open_secret_realm", "open_family", "open_territory", "open_difficulty_mode",
            "open_heart_demon", "open_heaven_retribution", "open_lifespan",
            "open_red_dust", "open_hundred_schools", "save_game", "load_game",
        ]
        for sig_name in required_signals:
            self.assertTrue(
                hasattr(self.panel, sig_name),
                f"缺失信号: {sig_name}",
            )

    def test_refresh_buttons_still_works(self):
        """refresh_buttons 应能正常调用而不抛异常。"""
        try:
            self.panel.refresh_buttons()
        except Exception as e:
            self.fail(f"refresh_buttons 抛异常: {e}")

    def test_collapsed_group_height_is_small(self):
        """折叠态单组高度应较小（≤ 50px），避免总高爆炸。"""
        # 用一个全新且全部折叠的 panel
        panel2 = ActionPanel(self.engine)
        # 收起"修行"（默认是展开的）
        panel2._groups["修行"].set_expanded(False, emit_signal=True)
        # 单组 sizeHint 高度应 ≤ 50
        h = panel2._groups["修行"].sizeHint().height()
        self.assertLessEqual(
            h, 50,
            f"折叠态单组过高 ({h}px)，未能解决拥挤问题",
        )

    def test_expanded_body_height_proportional(self):
        """展开态 body 高度应随按钮数增加（不重叠）。"""
        # "系统"组有 3 按钮，展开后 body 高度应 > 折叠态
        sys_group = self.panel._groups["系统"]
        h_collapsed = sys_group.sizeHint().height()
        sys_group.set_expanded(True, emit_signal=False)
        h_expanded = sys_group.sizeHint().height()
        self.assertGreater(h_expanded, h_collapsed)
        # 展开态 body 高度应至少能容纳 2 行按钮 (≈ 130px)
        self.assertGreaterEqual(h_expanded, 130)


class TestActionPanelVisualLayout(unittest.TestCase):
    """视觉布局：整体高度爆炸问题已解决。"""

    def setUp(self):
        self.engine = _FakeEngine()
        self.panel = ActionPanel(self.engine)

    def test_total_panel_size_reasonable(self):
        """默认态（修行展开、其余折叠）总高应在合理范围（≤ 500px）。"""
        # 调整尺寸到推荐宽度
        self.panel.resize(280, 600)
        self.panel.adjustSize()
        # sizeHint 高度用于布局参考
        h = self.panel.sizeHint().height()
        self.assertLessEqual(
            h, 500,
            f"默认态总高过高 ({h}px)，手风琴未解决拥挤问题",
        )

    def test_only_one_group_expanded_by_default(self):
        """默认态（互斥+修行展开）下，应只有 1 个组的 header 是 checked。"""
        checked_count = sum(
            1 for g in self.panel._groups.values() if g.header.isChecked()
        )
        self.assertEqual(checked_count, 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)


class TestAccordionModeToggle(unittest.TestCase):
    """顶部 '允许多组同时展开' 勾选框：UI 切换行为。"""

    def setUp(self):
        self.engine = _FakeEngine()
        self.panel = ActionPanel(self.engine)

    def test_mode_toggle_checkbox_exists_and_reflects_default(self):
        """应存在勾选框，且默认互斥下未勾选。"""
        self.assertTrue(hasattr(self.panel, "_mode_toggle"))
        self.assertIsInstance(self.panel._mode_toggle, QCheckBox)
        self.assertEqual(self.panel._mode, ActionPanel.MODE_EXCLUSIVE)
        self.assertFalse(self.panel._mode_toggle.isChecked())

    def test_toggle_checkbox_switches_to_multi(self):
        """勾选 → 切到 multi，且可同时展开多个组。"""
        self.panel._mode_toggle.setChecked(True)
        self.assertEqual(self.panel._mode, ActionPanel.MODE_MULTI)
        self.panel._groups["修行"].set_expanded(True, emit_signal=True)
        self.panel._groups["行动"].set_expanded(True, emit_signal=True)
        self.assertTrue(self.panel._groups["修行"].is_expanded())
        self.assertTrue(self.panel._groups["行动"].is_expanded())

    def test_toggle_checkbox_back_to_exclusive(self):
        """先勾选再取消 → 回互斥，展开新组会收起其他。"""
        self.panel._mode_toggle.setChecked(True)
        self.panel._mode_toggle.setChecked(False)
        self.assertEqual(self.panel._mode, ActionPanel.MODE_EXCLUSIVE)
        self.panel._groups["修行"].set_expanded(True, emit_signal=True)
        self.panel._groups["行动"].set_expanded(True, emit_signal=True)
        self.assertTrue(self.panel._groups["行动"].is_expanded(),
                        "互斥模式下展开的新组应保持展开")
        self.assertFalse(self.panel._groups["修行"].is_expanded(),
                         "互斥模式下展开新组应自动收起旧组")


class TestAccordionModePrefPersistence(unittest.TestCase):
    """模式偏好持久化到 config/ui_prefs.json。"""

    def setUp(self):
        import tempfile
        self.tmp = tempfile.mkdtemp()
        self.engine = _FakeEngine()
        self.engine.config_dir = self.tmp
        self.panel = ActionPanel(self.engine)

    def test_pref_default_exclusive_when_no_file(self):
        """无偏好文件时默认互斥、未勾选。"""
        self.assertEqual(self.panel._mode, ActionPanel.MODE_EXCLUSIVE)
        self.assertFalse(self.panel._mode_toggle.isChecked())

    def test_pref_persists_multi_and_reloaded(self):
        """勾选后写入 ui_prefs.json，新实例读回 multi。"""
        self.panel._mode_toggle.setChecked(True)
        pref_path = os.path.join(self.tmp, "ui_prefs.json")
        self.assertTrue(os.path.exists(pref_path))
        with open(pref_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        self.assertTrue(data["accordion_multi_expand"])
        panel2 = ActionPanel(self.engine)
        self.assertEqual(panel2._mode, ActionPanel.MODE_MULTI)
        self.assertTrue(panel2._mode_toggle.isChecked())

    def test_pref_persists_exclusive(self):
        """先勾选再取消，写回 false。"""
        self.panel._mode_toggle.setChecked(True)
        self.panel._mode_toggle.setChecked(False)
        pref_path = os.path.join(self.tmp, "ui_prefs.json")
        with open(pref_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        self.assertFalse(data["accordion_multi_expand"])


class TestAccordionScrollArea(unittest.TestCase):
    """ActionPanel + QScrollArea：多组展开时内容溢出，可滚动查看。"""

    def test_panel_overflows_small_viewport_when_all_expanded(self):
        """全展开时，ActionPanel 的 sizeHint 高度应大于小 viewport → 滚动条会出现。"""
        from PySide6.QtWidgets import QScrollArea
        engine = _FakeEngine()
        panel = ActionPanel(engine)
        panel._mode_toggle.setChecked(True)
        for name in panel._groups:
            panel._groups[name].set_expanded(True, emit_signal=False)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(panel)
        # 故意把 viewport 调小，触发垂直滚动
        scroll.resize(280, 200)
        # 内部 panel 的 sizeHint 高度应 > viewport 高度
        self.assertGreater(
            panel.sizeHint().height(),
            scroll.viewport().height(),
            "全展开时 panel 高度应超过小 viewport，触发滚动条",
        )

    def test_action_panel_default_fits_viewport(self):
        """默认态（仅 修行 展开）下，ActionPanel 应能放进普通 viewport。"""
        from PySide6.QtWidgets import QScrollArea
        engine = _FakeEngine()
        panel = ActionPanel(engine)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(panel)
        scroll.resize(280, 600)
        # 默认态总高 ≤ 500（addStretch 也不应超过 viewport）
        self.assertLessEqual(panel.sizeHint().height(), 500)
