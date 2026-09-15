# -*- coding: utf-8 -*-
"""秘境队伍编成弹窗（F-03，最多 3 人：玩家 + 至多 2 名追随者）。"""
from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QDialog, QLabel, QVBoxLayout, QHBoxLayout, QPushButton, QCheckBox, QFrame,
)

PATH_NAMES = {
    "fa": "法修", "ti": "体修", "jian": "剑修", "xie": "邪修",
    "dan": "丹修", "qi": "器修", "yu": "御兽", "hun": "魂修",
    "zhen": "阵修", "fu": "符修",
}


class PartyDialog(QDialog):
    party_selected = Signal(list)  # list of {"name", "path"}

    def __init__(self, player, follower_library, parent=None):
        super().__init__(parent)
        self.setWindowTitle("编成秘境小队")
        self.player = player
        self.follower_library = follower_library
        self.checkboxes = []  # (follower_dict, QCheckBox)
        self._build()

    def _build(self):
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("队长（必选）：你本人"))
        leader = QFrame()
        leader.setFrameShape(QFrame.Box)
        lv = QHBoxLayout(leader)
        lv.addWidget(QLabel(f"{self.player.name}  —  {PATH_NAMES.get(self.player.cultivation_path, self.player.cultivation_path)}"))
        layout.addWidget(leader)

        layout.addWidget(QLabel("可选追随者（最多 2 名，提供流派协同增益）："))
        for fid in self.follower_library.all_ids():
            f = self.follower_library.get(fid)
            if not f:
                continue
            cb = QCheckBox(f"{f.get('name', fid)}  —  {PATH_NAMES.get(f.get('path', ''), f.get('path', ''))}")
            self.checkboxes.append((f, cb))
            layout.addWidget(cb)

        hint = QLabel("提示：不同流派组合可触发协同（如 剑修+丹修 攻击+10%）。")
        hint.setStyleSheet("color:#888; font-size:11px;")
        layout.addWidget(hint)

        btn_row = QHBoxLayout()
        ok = QPushButton("确定")
        ok.clicked.connect(self._confirm)
        cancel = QPushButton("取消")
        cancel.clicked.connect(self.reject)
        btn_row.addWidget(ok)
        btn_row.addWidget(cancel)
        layout.addLayout(btn_row)

    def _confirm(self):
        party = [{"name": self.player.name, "path": self.player.cultivation_path}]
        selected = [f for f, cb in self.checkboxes if cb.isChecked()]
        for f in selected[:2]:
            party.append({"name": f.get("name", ""), "path": f.get("path", "")})
        self.party_selected.emit(party)
        self.accept()
