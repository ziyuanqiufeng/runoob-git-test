# -*- coding: utf-8 -*-
"""心魔劫幻境弹窗（维度①）。

大境界突破且心魔值过高时，由引擎通过 __HEART_DEMON_TRIBULATION__ 标记强制触发。
玩家在幻境中做出抉择，抉择会永久改变性格标签与后续事件概率。
"""
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QLabel, QPushButton, QMessageBox,
)
from PySide6.QtCore import Qt, Signal


class HeartDemonTribulationDialog(QDialog):
    """渲染单个心魔劫幻境场景，并把抉择回传给引擎。"""

    # 抉择已应用：(scenario_id, choice_id)
    scenario_resolved = Signal(str, str)

    def __init__(self, engine, scenario_id, parent=None):
        super().__init__(parent)
        self.engine = engine
        self.mgr = engine.mental_state_manager
        self.scenario_id = scenario_id
        self.scenario = self._load_scenario(scenario_id)
        self.setWindowTitle("心魔劫")
        self.resize(520, 480)
        self._build()

    def _load_scenario(self, scenario_id):
        cfg = self.mgr.config.get_heart_demon_tribulation()
        return next(
            (s for s in cfg.get("scenarios", []) if s.get("id") == scenario_id),
            None,
        )

    def _build(self):
        layout = QVBoxLayout(self)
        if not self.scenario:
            layout.addWidget(QLabel("（幻境消散，无物可觅……）"))
            QPushButton("离去", clicked=self.accept)
            return

        title = QLabel(f"【{self.scenario.get('name', '心魔劫')}】")
        title.setStyleSheet("font-size:16px; font-weight:bold; color:#c0392b;")
        layout.addWidget(title)

        desc = QLabel(self.scenario.get("description", ""))
        desc.setWordWrap(True)
        layout.addWidget(desc)

        layout.addWidget(QLabel("— 幻境中的抉择 —"))
        for choice in self.scenario.get("choices", []):
            btn = QPushButton(choice.get("text", choice.get("id", "？")))
            btn.setToolTip(choice.get("hint", ""))
            btn.clicked.connect(
                lambda _checked=False, cid=choice["id"]: self._choose(cid)
            )
            layout.addWidget(btn)

    def _choose(self, choice_id):
        ok, msg = self.engine.apply_heart_demon_tribulation_choice(
            self.scenario_id, choice_id
        )
        if ok:
            QMessageBox.information(self, "心魔劫", msg)
            self.scenario_resolved.emit(self.scenario_id, choice_id)
            self.accept()
        else:
            QMessageBox.warning(self, "心魔劫", msg)
