# -*- coding: utf-8 -*-
"""
城市热点可视化编辑器。

用于在城池俯瞰图上拖拽调整建筑热点位置、形状与大小，
并实时导出 `config/city_maps.json`。

使用方法：
    python tools/city_hotspot_editor.py
"""
import json
import os
import sys

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QComboBox, QPushButton, QListWidget,
    QMessageBox, QFileDialog, QGroupBox, QRadioButton, QButtonGroup
)
from PySide6.QtCore import Qt, QRect, QPoint, Signal
from PySide6.QtGui import QPixmap, QPainter, QColor, QPen, QBrush, QFont


CONFIG_DIR = "config"
LOCATIONS_PATH = os.path.join(CONFIG_DIR, "locations.json")
CITY_MAPS_PATH = os.path.join(CONFIG_DIR, "city_maps.json")

# 建筑配色（与城市对话框一致）
BUILDING_COLORS = {
    "city_lord_hall": "#8e44ad",
    "inn": "#d35400",
    "market": "#27ae60",
    "arena": "#c0392b",
    "alchemy_pavilion": "#2980b9",
    "library": "#16a085",
    "smithy": "#7f8c8d",
    "beast_park": "#8d6e63",
    "aquatic_shop": "#0288d1",
}


def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


class HotspotEditorCanvas(QWidget):
    """地图编辑画布：显示背景图与可拖拽的热点。"""

    hotspot_selected = Signal(int)
    hotspot_moved = Signal(int, list)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.pixmap = QPixmap()
        self.hotspots = []
        self.selected_index = -1
        self.current_shape = "rect"
        self.dragging = False
        self.drag_start = None
        self.drag_hotspot_index = -1
        self.setMouseTracking(True)
        self.setMinimumSize(640, 400)

    def set_pixmap(self, pixmap):
        self.pixmap = pixmap
        self.update()

    def set_hotspots(self, hotspots):
        self.hotspots = hotspots
        self.update()

    def set_current_shape(self, shape):
        self.current_shape = shape

    def _image_rect(self):
        """背景图在画布中居中缩放后的矩形。"""
        if self.pixmap.isNull():
            return self.rect()
        scaled = self.pixmap.scaled(self.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
        x = (self.width() - scaled.width()) // 2
        y = (self.height() - scaled.height()) // 2
        return QRect(x, y, scaled.width(), scaled.height())

    def _image_to_widget(self, x_pct, y_pct):
        """百分比坐标 -> 画布像素坐标。"""
        img_rect = self._image_rect()
        return QPoint(
            int(img_rect.left() + x_pct * img_rect.width()),
            int(img_rect.top() + y_pct * img_rect.height()),
        )

    def _widget_to_image(self, pos):
        """画布像素坐标 -> 百分比坐标。"""
        img_rect = self._image_rect()
        x = (pos.x() - img_rect.left()) / img_rect.width() if img_rect.width() else 0
        y = (pos.y() - img_rect.top()) / img_rect.height() if img_rect.height() else 0
        return [max(0.0, min(1.0, x)), max(0.0, min(1.0, y))]

    def _hotspot_rect(self, hotspot):
        """根据热点百分比坐标计算画布矩形。"""
        x1, y1, x2, y2 = hotspot["coords"]
        p1 = self._image_to_widget(x1, y1)
        p2 = self._image_to_widget(x2, y2)
        return QRect(p1.x(), p1.y(), p2.x() - p1.x(), p2.y() - p1.y())

    def _hit_test(self, pos):
        """命中检测，返回热点索引。"""
        for i in range(len(self.hotspots) - 1, -1, -1):
            rect = self._hotspot_rect(self.hotspots[i])
            if rect.contains(pos):
                return i
        return -1

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.fillRect(self.rect(), QColor(40, 40, 40))

        # 背景图
        img_rect = self._image_rect()
        if not self.pixmap.isNull():
            painter.drawPixmap(img_rect, self.pixmap)
        else:
            painter.setPen(QPen(QColor(100, 100, 100), 1, Qt.DotLine))
            painter.drawRect(img_rect.adjusted(2, 2, -2, -2))

        # 绘制热点
        font = QFont("Microsoft YaHei", 9, QFont.Bold)
        painter.setFont(font)
        for i, hotspot in enumerate(self.hotspots):
            rect = self._hotspot_rect(hotspot)
            bid = hotspot.get("id", "")
            color = QColor(BUILDING_COLORS.get(bid, "#3498db"))
            is_selected = i == self.selected_index

            fill = QColor(color)
            fill.setAlpha(90 if is_selected else 50)
            painter.setBrush(QBrush(fill))

            pen = QPen(color, 2 if is_selected else 1)
            painter.setPen(pen)

            shape = hotspot.get("shape", "rect")
            if shape == "circle":
                cx, cy = rect.center().x(), rect.center().y()
                r = min(rect.width(), rect.height()) // 2
                painter.drawEllipse(QPoint(cx, cy), r, r)
            elif shape == "diamond":
                cx, cy = rect.center().x(), rect.center().y()
                rx, ry = rect.width() // 2, rect.height() // 2
                points = [(cx, cy - ry), (cx + rx, cy), (cx, cy + ry), (cx - rx, cy)]
                painter.drawPolygon([QPoint(x, y) for x, y in points])
            else:
                painter.drawRoundedRect(rect, 6, 6)

            # 名称
            name = hotspot.get("name", bid)
            painter.setPen(QPen(QColor(255, 255, 255), 1))
            painter.drawText(rect, Qt.AlignCenter, name)

        painter.end()

    def mousePressEvent(self, event):
        idx = self._hit_test(event.pos())
        if idx >= 0:
            self.selected_index = idx
            self.dragging = True
            self.drag_start = event.pos()
            self.drag_hotspot_index = idx
            self.hotspot_selected.emit(idx)
        else:
            self.selected_index = -1
            self.dragging = False
            self.hotspot_selected.emit(-1)
        self.update()

    def mouseMoveEvent(self, event):
        if self.dragging and self.drag_hotspot_index >= 0:
            dx = event.pos().x() - self.drag_start.x()
            dy = event.pos().y() - self.drag_start.y()
            self.drag_start = event.pos()

            hotspot = self.hotspots[self.drag_hotspot_index]
            img_rect = self._image_rect()
            dx_pct = dx / img_rect.width() if img_rect.width() else 0
            dy_pct = dy / img_rect.height() if img_rect.height() else 0

            new_coords = [
                max(0.0, min(1.0, hotspot["coords"][0] + dx_pct)),
                max(0.0, min(1.0, hotspot["coords"][1] + dy_pct)),
                max(0.0, min(1.0, hotspot["coords"][2] + dx_pct)),
                max(0.0, min(1.0, hotspot["coords"][3] + dy_pct)),
            ]
            hotspot["coords"] = new_coords
            self.hotspot_moved.emit(self.drag_hotspot_index, new_coords)
            self.update()

    def mouseReleaseEvent(self, event):
        self.dragging = False
        self.drag_hotspot_index = -1

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.update()


class CityHotspotEditor(QMainWindow):
    """城市热点编辑器主窗口。"""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("城市热点编辑器")
        self.resize(1200, 700)

        self.locations = load_json(LOCATIONS_PATH)
        self.locations_with_bg = [loc for loc in self.locations if loc.get("background_image")]
        self.location_map = {loc["id"]: loc for loc in self.locations}

        if os.path.exists(CITY_MAPS_PATH):
            self.city_maps = load_json(CITY_MAPS_PATH)
        else:
            self.city_maps = []
        self.city_map_index = {}

        central = QWidget()
        self.setCentralWidget(central)
        layout = QHBoxLayout(central)

        # === 左侧控制面板 ===
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setSpacing(10)

        # 城市选择
        left_layout.addWidget(QLabel("选择城市："))
        self.city_combo = QComboBox()
        for loc in self.locations_with_bg:
            self.city_combo.addItem(f"{loc['name']} ({loc['id']})", loc["id"])
        self.city_combo.currentIndexChanged.connect(self._on_city_changed)
        left_layout.addWidget(self.city_combo)

        # 新建热点形状
        shape_group = QGroupBox("新建热点形状")
        shape_layout = QVBoxLayout(shape_group)
        self.shape_group = QButtonGroup(self)
        for shape, label in [("rect", "矩形"), ("circle", "圆形"), ("diamond", "菱形")]:
            radio = QRadioButton(label)
            radio.setChecked(shape == "rect")
            self.shape_group.addButton(radio, {"rect": 0, "circle": 1, "diamond": 2}[shape])
            shape_layout.addWidget(radio)
        self.shape_group.idClicked.connect(self._on_shape_changed)
        left_layout.addWidget(shape_group)

        # 建筑选择
        left_layout.addWidget(QLabel("未配置建筑："))
        self.building_combo = QComboBox()
        left_layout.addWidget(self.building_combo)

        add_btn = QPushButton("+ 添加热点")
        add_btn.clicked.connect(self._add_hotspot)
        left_layout.addWidget(add_btn)

        left_layout.addWidget(QLabel("热点列表："))
        self.hotspot_list = QListWidget()
        self.hotspot_list.currentRowChanged.connect(self._on_list_selection_changed)
        left_layout.addWidget(self.hotspot_list)

        delete_btn = QPushButton("- 删除选中热点")
        delete_btn.clicked.connect(self._delete_selected_hotspot)
        left_layout.addWidget(delete_btn)

        save_btn = QPushButton("💾 保存 city_maps.json")
        save_btn.clicked.connect(self._save)
        left_layout.addWidget(save_btn)

        export_btn = QPushButton("📤 另存为...")
        export_btn.clicked.connect(self._export_as)
        left_layout.addWidget(export_btn)

        left_layout.addStretch()
        layout.addWidget(left_panel, 1)

        # === 右侧画布 ===
        self.canvas = HotspotEditorCanvas()
        self.canvas.hotspot_selected.connect(self._on_canvas_selection_changed)
        self.canvas.hotspot_moved.connect(self._on_hotspot_moved)
        layout.addWidget(self.canvas, 4)

        # === 状态栏 ===
        self.statusBar().showMessage("选择一个城市开始编辑")

        if self.city_combo.count() > 0:
            self._on_city_changed(0)

    def _current_city_id(self):
        return self.city_combo.currentData()

    def _current_city_config(self):
        city_id = self._current_city_id()
        for cfg in self.city_maps:
            if cfg.get("city_id") == city_id:
                return cfg
        return None

    def _ensure_city_config(self):
        """确保当前城市有配置条目。"""
        city_id = self._current_city_id()
        cfg = self._current_city_config()
        if cfg is None:
            loc = self.location_map[city_id]
            bg = loc.get("background_image", f"assets/city_bg/{city_id}.png")
            cfg = {"city_id": city_id, "map_image": bg, "hotspots": []}
            self.city_maps.append(cfg)
        return cfg

    def _load_pixmap(self, city_id):
        loc = self.location_map[city_id]
        bg = loc.get("background_image")
        if bg:
            path = os.path.join("assets", "city_bg", bg)
            if os.path.exists(path):
                return QPixmap(path)
        return QPixmap()

    def _on_city_changed(self, index):
        if index < 0:
            return
        city_id = self._current_city_id()
        cfg = self._ensure_city_config()
        self.canvas.set_pixmap(self._load_pixmap(city_id))
        self.canvas.set_hotspots(cfg.get("hotspots", []))
        self.canvas.selected_index = -1
        self._refresh_building_combo()
        self._refresh_hotspot_list()
        self.statusBar().showMessage(f"当前城市：{self.location_map[city_id]['name']}")

    def _on_shape_changed(self, shape_id):
        shapes = {0: "rect", 1: "circle", 2: "diamond"}
        self.canvas.set_current_shape(shapes.get(shape_id, "rect"))

    def _refresh_building_combo(self):
        self.building_combo.clear()
        city_id = self._current_city_id()
        loc = self.location_map.get(city_id, {})
        cfg = self._current_city_config() or {"hotspots": []}
        existing_ids = {h["id"] for h in cfg.get("hotspots", [])}
        for building in loc.get("buildings", []):
            bid = building.get("id")
            if bid and bid not in existing_ids:
                self.building_combo.addItem(f"{building['name']} ({bid})", bid)
        if self.building_combo.count() == 0:
            self.building_combo.addItem("（所有建筑已配置）", "")

    def _refresh_hotspot_list(self):
        self.hotspot_list.clear()
        cfg = self._current_city_config()
        if cfg is None:
            return
        for hotspot in cfg.get("hotspots", []):
            text = f"{hotspot.get('name', hotspot['id'])} [{hotspot.get('shape', 'rect')}] " \
                   f"({', '.join(f'{c:.2f}' for c in hotspot['coords'])})"
            self.hotspot_list.addItem(text)

    def _add_hotspot(self):
        bid = self.building_combo.currentData()
        if not bid:
            QMessageBox.information(self, "提示", "当前没有可添加的建筑。")
            return
        city_id = self._current_city_id()
        loc = self.location_map[city_id]
        building = next((b for b in loc.get("buildings", []) if b.get("id") == bid), {})
        cfg = self._ensure_city_config()
        # 默认在地图中心偏下位置生成一个 0.15x0.15 的热点，并附带默认图片路径
        hotspot = {
            "id": bid,
            "name": building.get("name", bid),
            "shape": self.canvas.current_shape,
            "coords": [0.42, 0.42, 0.58, 0.58],
            "image": f"assets/city_buildings/{city_id}/{bid}.png",
            "image_hover": f"assets/city_buildings/{city_id}/{bid}_hover.png",
            "nameplate_offset": [0, -20],
        }
        cfg["hotspots"].append(hotspot)
        self.canvas.set_hotspots(cfg["hotspots"])
        self._refresh_building_combo()
        self._refresh_hotspot_list()
        self.hotspot_list.setCurrentRow(len(cfg["hotspots"]) - 1)

    def _delete_selected_hotspot(self):
        row = self.hotspot_list.currentRow()
        if row < 0:
            return
        cfg = self._ensure_city_config()
        cfg["hotspots"].pop(row)
        self.canvas.selected_index = -1
        self.canvas.set_hotspots(cfg["hotspots"])
        self._refresh_building_combo()
        self._refresh_hotspot_list()

    def _on_canvas_selection_changed(self, index):
        self.hotspot_list.setCurrentRow(index)
        self.canvas.selected_index = index
        self.canvas.update()

    def _on_list_selection_changed(self, row):
        self.canvas.selected_index = row
        self.canvas.update()

    def _on_hotspot_moved(self, index, coords):
        cfg = self._ensure_city_config()
        cfg["hotspots"][index]["coords"] = coords
        self._refresh_hotspot_list()
        self.hotspot_list.setCurrentRow(index)

    def _save(self):
        save_json(CITY_MAPS_PATH, self.city_maps)
        self.statusBar().showMessage(f"已保存到 {CITY_MAPS_PATH}")
        QMessageBox.information(self, "保存成功", f"已保存到 {CITY_MAPS_PATH}")

    def _export_as(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "另存为", CITY_MAPS_PATH, "JSON 文件 (*.json)"
        )
        if path:
            save_json(path, self.city_maps)
            self.statusBar().showMessage(f"已导出到 {path}")


def main():
    app = QApplication(sys.argv)
    editor = CityHotspotEditor()
    editor.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
