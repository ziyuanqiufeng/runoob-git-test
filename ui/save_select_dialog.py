import json
import os

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QListWidget, QPushButton,
    QMessageBox, QLabel, QFileDialog,
)
from PySide6.QtCore import Qt

from game.save_manager import SaveManager


class SaveSelectDialog(QDialog):
    """存档选择：列出所有槽位，可载入或删除。"""

    def __init__(self, parent=None, save_manager=None):
        super().__init__(parent)
        self.save_manager = save_manager or SaveManager()
        self.selected_slot = None
        self.slots = []
        self._realm_names = self._load_name_map("realms.json")
        self._location_names = self._load_name_map("locations.json")
        self._ending_names = self._load_name_map("endings.json")
        self.setWindowTitle("选择存档")
        self.setMinimumSize(640, 400)
        self._setup_ui()
        self._refresh_list()

    def _load_name_map(self, filename):
        """加载配置文件的 id→name 映射（境界/地点/结局）。"""
        mapping = {}
        try:
            path = os.path.join("config", filename)
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict) and "endings" in data:
                data = data["endings"]
            if isinstance(data, list):
                for item in data:
                    if isinstance(item, dict) and item.get("id"):
                        mapping[item["id"]] = item.get("name", item["id"])
        except (json.JSONDecodeError, OSError):
            pass
        return mapping

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        title = QLabel("选择一处存档，延续你的修行")
        title.setObjectName("saveSelectTitle")
        layout.addWidget(title)

        # 左侧存档列表 + 右侧详情预览
        body = QHBoxLayout()
        body.setSpacing(14)
        self.list_widget = QListWidget()
        self.list_widget.setObjectName("saveList")
        self.list_widget.itemDoubleClicked.connect(lambda _: self._on_load())
        self.list_widget.currentItemChanged.connect(self._on_select)
        body.addWidget(self.list_widget, 3)

        self.detail_label = QLabel("选中一个存档查看详情")
        self.detail_label.setObjectName("saveDetail")
        self.detail_label.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        self.detail_label.setWordWrap(True)
        self.detail_label.setTextFormat(Qt.RichText)
        body.addWidget(self.detail_label, 2)
        layout.addLayout(body, 1)

        btn_row = QHBoxLayout()
        self.btn_load = QPushButton("载入")
        self.btn_delete = QPushButton("删除")
        self.btn_export = QPushButton("导出")
        self.btn_import = QPushButton("导入")
        self.btn_cancel = QPushButton("返回")
        btn_row.addWidget(self.btn_load)
        btn_row.addWidget(self.btn_delete)
        btn_row.addWidget(self.btn_export)
        btn_row.addStretch(1)
        btn_row.addWidget(self.btn_import)
        btn_row.addWidget(self.btn_cancel)
        layout.addLayout(btn_row)

        self.btn_load.clicked.connect(self._on_load)
        self.btn_delete.clicked.connect(self._on_delete)
        self.btn_export.clicked.connect(self._on_export)
        self.btn_import.clicked.connect(self._on_import)
        self.btn_cancel.clicked.connect(self.reject)

        self._apply_style()

    def _apply_style(self):
        self.setStyleSheet("""
            QLabel#saveSelectTitle {
                font-size: 16px;
                color: #2c3e50;
            }
            QListWidget#saveList {
                background-color: #ffffff;
                border: 1px solid #dee2e6;
                border-radius: 8px;
                font-size: 14px;
                padding: 4px;
            }
            QListWidget#saveList::item {
                padding: 8px 10px;
                border-bottom: 1px solid #f0f0f0;
            }
            QListWidget#saveList::item:selected {
                background-color: #e8c97a;
                color: #1b2a4a;
            }
            QLabel#saveDetail {
                background-color: #f8f5ee;
                border: 1px solid #e8e0cc;
                border-radius: 8px;
                padding: 12px 14px;
                color: #444441;
                font-size: 13px;
                line-height: 1.6;
            }
        """)

    def _refresh_list(self):
        self.list_widget.clear()
        self.slots = self.save_manager.list_slots()
        for s in self.slots:
            text = f"{s['player_name']}    ·    {s['name']}"
            if s.get("saved_at"):
                text += f"    ·    {s['saved_at']}"
            self.list_widget.addItem(text)
        has = bool(self.slots)
        self.btn_load.setEnabled(has)
        self.btn_delete.setEnabled(has)
        self.btn_export.setEnabled(has)
        if has:
            self.list_widget.setCurrentRow(0)

    def _on_select(self, current, previous=None):
        """选中存档时刷新右侧详情。"""
        row = self.list_widget.currentRow()
        if row < 0 or row >= len(self.slots):
            self.detail_label.setText("选中一个存档查看详情")
            return
        self.detail_label.setText(self._render_detail(self.slots[row]["name"]))

    def _render_detail(self, slot_name):
        """生成存档详情文本。"""
        detail = self.save_manager.read_slot_detail(slot_name)
        if not detail:
            return "无法读取该存档的详情。"
        lines = [f"<b>道号</b>：{detail.get('player_name', '无名散修')}"]
        realm = self._realm_names.get(detail.get("realm_id") or "", "")
        if realm:
            lines.append(f"<b>境界</b>：{realm}")
        loc = self._location_names.get(detail.get("location_id") or "", "")
        if loc:
            lines.append(f"<b>地点</b>：{loc}")
        lines.append(f"<b>灵石</b>：{detail.get('spirit_stones', 0)}")
        if detail.get("age") is not None:
            lines.append(f"<b>年龄</b>：{detail.get('age')} 岁")
        if detail.get("year") is not None and detail.get("month") is not None:
            lines.append(f"<b>时长</b>：{detail.get('year')} 年 {detail.get('month')} 月")
        ending = self._ending_names.get(detail.get("ending_id") or "", "")
        if ending:
            lines.append(f"<b>结局</b>：{ending}")
        if detail.get("main_story_step"):
            lines.append(f"<b>主线</b>：已完成 {detail.get('main_story_step')} 章")
        if detail.get("saved_at"):
            lines.append(f"<b>保存于</b>：{detail.get('saved_at')}")
        return "<br>".join(lines)

    def _on_load(self):
        row = self.list_widget.currentRow()
        if row < 0 or row >= len(self.slots):
            return
        self.selected_slot = self.slots[row]["name"]
        self.accept()

    def _on_delete(self):
        row = self.list_widget.currentRow()
        if row < 0 or row >= len(self.slots):
            return
        slot = self.slots[row]["name"]
        name = self.slots[row]["player_name"]
        reply = QMessageBox.question(
            self, "删除存档",
            f"确定删除存档「{name}」({slot})？此操作不可恢复。",
            QMessageBox.Yes | QMessageBox.No,
        )
        if reply == QMessageBox.Yes:
            if not self.save_manager.delete_slot(slot):
                QMessageBox.warning(
                    self, "删除存档",
                    "删除失败：文件可能被占用或权限不足。\n存档未被删除。",
                )
            self._refresh_list()

    def _on_export(self):
        """导出选中槽位为 zip 分享包（含立绘）。"""
        row = self.list_widget.currentRow()
        if row < 0 or row >= len(self.slots):
            return
        slot = self.slots[row]["name"]
        dest, _ = QFileDialog.getSaveFileName(
            self, "导出存档", f"问道长生存档_{slot}.zip", "存档分享包 (*.zip)"
        )
        if not dest:
            return
        data = self.save_manager.export_slot(slot, dest)
        if data:
            QMessageBox.information(
                self, "导出存档",
                f"已导出到：\n{dest}\n\n可直接分享给其他玩家导入。",
            )
        else:
            QMessageBox.warning(self, "导出存档", "导出失败：存档不存在或已损坏。")

    def _on_import(self):
        """从 zip 分享包导入存档为新槽位。"""
        src, _ = QFileDialog.getOpenFileName(
            self, "导入存档", "", "存档分享包 (*.zip)"
        )
        if not src:
            return
        slot = self.save_manager.import_slot(src)
        if slot:
            self._refresh_list()
            QMessageBox.information(self, "导入存档", f"已导入为新存档「{slot}」。")
        else:
            QMessageBox.warning(
                self, "导入存档", "导入失败：文件不是有效的问道长生存档包。")
