# -*- coding: utf-8 -*-
"""维度③·M24：战斗前可部署法宝预览确认弹窗。

列出玩家持有的、可在战斗中部署的生活法宝（符箓 / 阵盘），逐项展示增益描述与
持有数量，玩家勾选后确认，逐件消耗并施加临时战斗增益。既可在开战前由主界面自动
弹出，也可在战斗中通过「部署法宝」按钮随时打开。

纯 UI 层加法：不修改引擎与配置，复用 engine.get_deployable_battle_consumables
与 engine.deploy_battle_consumable 既有接口。
"""
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QCheckBox, QPushButton, QFrame
)
from PySide6.QtCore import Qt


class DeployPreviewDialog(QDialog):
    """战斗前 / 战斗中部署法宝的多选预览确认弹窗。"""

    def __init__(self, engine, parent=None):
        super().__init__(parent)
        self.setWindowTitle("部署法宝 · 预览确认")
        self.setMinimumWidth(420)
        self.engine = engine
        self._checks = {}  # item_id -> QCheckBox

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("开战前，你可部署以下生活法宝为临时增益（每件消耗 1 个）："))

        deployable = engine.get_deployable_battle_consumables()
        self._deployable = deployable
        if not deployable:
            layout.addWidget(QLabel("（当前背包中没有可部署的法宝）"))
        else:
            for d in deployable:
                item_row = QFrame()
                item_row.setFrameShape(QFrame.Shape.StyledPanel)
                row_layout = QVBoxLayout(item_row)
                row_layout.setContentsMargins(8, 6, 8, 6)

                cb = QCheckBox(f"{d['name']}  ×{d['count']}")
                cb.setChecked(True)
                cb.setToolTip(f"部署后将消耗 1 个「{d['name']}」")
                self._checks[d["item_id"]] = cb
                row_layout.addWidget(cb)

                desc_lbl = QLabel(d.get("desc", ""))
                desc_lbl.setWordWrap(True)
                desc_lbl.setStyleSheet("color: #7f8c8d; padding-left: 22px;")
                row_layout.addWidget(desc_lbl)

                layout.addWidget(item_row)

        btn_row = QHBoxLayout()
        self.ok_btn = QPushButton("确认部署")
        self.ok_btn.clicked.connect(self.accept)
        cancel_btn = QPushButton("暂不部署")
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(self.ok_btn)
        btn_row.addWidget(cancel_btn)
        layout.addLayout(btn_row)

    def chosen_item_ids(self):
        """返回被勾选的 item_id 列表（保持配置出现顺序）。"""
        return [iid for iid, cb in self._checks.items() if cb.isChecked()]

    @staticmethod
    def deploy_chosen(engine, item_ids):
        """逐件部署给定法宝，返回实际部署成功的 item_id 列表。"""
        deployed = []
        for iid in item_ids:
            ok, _ = engine.deploy_battle_consumable(iid)
            if ok:
                deployed.append(iid)
        return deployed

    @staticmethod
    def run(engine, parent=None):
        """弹出并（若确认）部署，返回部署成功的 item_id 列表；取消返回空列表。"""
        dlg = DeployPreviewDialog(engine, parent)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            return DeployPreviewDialog.deploy_chosen(engine, dlg.chosen_item_ids())
        return []
