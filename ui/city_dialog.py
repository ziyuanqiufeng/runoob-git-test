# -*- coding: utf-8 -*-
"""
城池内部界面（场景化美术重构版）。

支持：
- 2.5D 城市俯瞰背景图
- 独立建筑图片（QLabel）+ 名牌标签
- 鼠标悬停缩放/光晕、点击涟漪
- 多边形点击遮罩
- 资源缺失时自动 fallback 为彩色占位块
- @2x 高清图自动切换
"""
import json
import os

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QGridLayout,
    QWidget, QSizePolicy
)
from ui.stall_dialog import StallDialog
from ui.auction_dialog import AuctionDialog
from ui.cave_dialog import CaveDialog
from PySide6.QtCore import Qt, Signal, QRect, QPoint, QTimer, QPropertyAnimation, QEasingCurve, Property
from PySide6.QtGui import QPixmap, QPainter, QColor, QPen, QBrush, QFont, QCursor, QRegion, QPolygon


# 默认建筑配色（fallback 占位块用）
_BUILDING_COLORS = {
    "city_lord_hall": "#8e44ad",
    "inn": "#d35400",
    "market": "#27ae60",
    "arena": "#c0392b",
    "alchemy_pavilion": "#2980b9",
    "library": "#16a085",
    "smithy": "#7f8c8d",
    "beast_park": "#8d6e63",
    "aquatic_shop": "#0288d1",
    "cave": "#5d4037",
}

_ACTION_LABELS = {
    "market": "交易",
    "rest": "歇息",
    "arena": "切磋",
    "quest": "任务",
    "beast_park": "灵兽",
    "aquatic_shop": "水系",
    "alchemy": "炼丹",
    "shop": "炼丹",
    "cave": "洞府",
}


def _load_city_map_config(city_id, config_dir="config"):
    """加载城市热点配置；没有对应配置则返回 None。"""
    path = os.path.join(config_dir, "city_maps.json")
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            configs = json.load(f)
        for cfg in configs:
            if cfg.get("city_id") == city_id:
                return cfg
    except (json.JSONDecodeError, IOError):
        return None
    return None


def _select_city_image(map_image_path):
    """根据屏幕 DPR 自动选择普通图或 @2x 高清图。"""
    if not map_image_path:
        return map_image_path
    base, ext = os.path.splitext(map_image_path)
    retina_path = f"{base}@2x{ext}"
    if os.path.exists(retina_path):
        return retina_path
    return map_image_path


class CityBuildingWidget(QWidget):
    """
    单个建筑组件：显示建筑图片、名牌，响应悬停/点击。

    当图片资源存在时显示真实美术资源；否则绘制彩色占位块。
    """

    clicked = Signal()
    hovered = Signal(bool)

    def __init__(self, hotspot, building_info, parent=None):
        super().__init__(parent)
        self.hotspot = hotspot
        self.building_info = building_info or {}
        self._normal_pixmap = QPixmap()
        self._hover_pixmap = QPixmap()
        self._has_image = False

        # 基础几何（未缩放时的正常尺寸）
        self._base_geometry = QRect()
        # 当前缩放比例（用于动画属性）
        self._hover_scale = 1.0

        self.setCursor(QCursor(Qt.PointingHandCursor))
        self.setAttribute(Qt.WA_TranslucentBackground)

        # 图片标签
        self.image_label = QLabel(self)
        self.image_label.setAttribute(Qt.WA_TranslucentBackground)
        self.image_label.setScaledContents(True)
        self.image_label.setAlignment(Qt.AlignCenter)

        # 名牌标签（悬浮在建筑上方）
        self.name_label = QLabel(self)
        self.name_label.setAttribute(Qt.WA_TranslucentBackground)
        self.name_label.setAlignment(Qt.AlignCenter)
        self.name_label.setStyleSheet(
            "QLabel { color: #fff; font-weight: bold; font-size: 13px; "
            "text-shadow: 1px 1px 2px #000; padding: 2px 8px; "
            "background-color: rgba(0,0,0,100); border-radius: 4px; }"
        )

        name = self.building_info.get("name", hotspot.get("name", "未知建筑"))
        action = _ACTION_LABELS.get(self.building_info.get("action"), "")
        self.name_label.setText(f"{name}\n{action}" if action else name)

        # 光晕效果（悬停时开启）
        self._glow_effect = None

        # 缩放动画
        self._scale_animation = QPropertyAnimation(self, b"hover_scale", self)
        self._scale_animation.setDuration(180)
        self._scale_animation.setEasingCurve(QEasingCurve.OutCubic)

        self._load_images()
        self._update_mask()

    # region 动画属性
    def get_hover_scale(self):
        return self._hover_scale

    def set_hover_scale(self, value):
        self._hover_scale = value
        self._apply_scale()

    hover_scale = Property(float, get_hover_scale, set_hover_scale)
    # endregion

    def _load_images(self):
        """
        建筑组件永远使用透明点击层。

        当前版本所有建筑已统一绘制在城市背景全景图中，不再使用任何独立建筑图片。
        该组件只负责接收鼠标事件、显示名牌与悬停高亮，不覆盖背景建筑本体。
        """
        self._normal_pixmap = QPixmap(1, 1)
        self._normal_pixmap.fill(Qt.transparent)
        self._hover_pixmap = self._normal_pixmap
        self._has_image = True

    def set_base_geometry(self, rect):
        """设置未缩放时的基础几何。"""
        self._base_geometry = QRect(rect)
        self._apply_scale()

    def _apply_scale(self):
        """根据当前缩放比例调整实际几何与图片。"""
        if not self._base_geometry.isValid():
            return
        scale = self._hover_scale
        base = self._base_geometry
        new_w = int(base.width() * scale)
        new_h = int(base.height() * scale)
        new_x = base.x() - (new_w - base.width()) // 2
        new_y = base.y() - (new_h - base.height()) // 2
        self.setGeometry(new_x, new_y, new_w, new_h)

        # 图片区域占满整个 widget（留出名牌空间）
        self.image_label.setGeometry(0, 0, new_w, new_h)
        # 根据缩放状态切换普通/高亮图
        pixmap = self._hover_pixmap if scale > 1.02 else self._normal_pixmap
        # 判断是否为程序生成的透明点击层（1x1 透明图）
        is_transparent_layer = (pixmap.width() <= 1 and pixmap.height() <= 1)
        if is_transparent_layer:
            if scale > 1.02:
                # 悬停时绘制高亮遮罩，让玩家明确知道选中哪座建筑
                self._draw_hover_overlay(new_w, new_h)
            else:
                self._draw_transparent_layer(new_w, new_h)
        else:
            self.image_label.setPixmap(pixmap.scaled(new_w, new_h, Qt.KeepAspectRatio, Qt.SmoothTransformation))

        # 名牌位置：建筑顶部居中 + 偏移
        offset = self.hotspot.get("nameplate_offset", [0, -20])
        name_w = min(new_w + 40, 160)
        name_h = 36
        name_x = (new_w - name_w) // 2 + offset[0]
        name_y = offset[1]
        self.name_label.setGeometry(name_x, name_y, name_w, name_h)

        # 缩放后重新计算点击遮罩，保证不规则建筑命中精确
        self._update_mask()

    def _draw_fallback_image(self, width, height):
        """没有图片资源时绘制彩色占位块。"""
        bid = self.hotspot.get("id", "")
        color = QColor(_BUILDING_COLORS.get(bid, "#3498db"))
        pixmap = QPixmap(width, height)
        pixmap.fill(Qt.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setBrush(QBrush(QColor(color.red(), color.green(), color.blue(), 120)))
        painter.setPen(QPen(color, 2))

        shape = self.hotspot.get("shape", "rect")
        if shape == "circle":
            r = min(width, height) // 2 - 2
            painter.drawEllipse(QPoint(width // 2, height // 2), r, r)
        elif shape == "diamond":
            points = [
                QPoint(width // 2, 4),
                QPoint(width - 4, height // 2),
                QPoint(width // 2, height - 4),
                QPoint(4, height // 2),
            ]
            painter.drawPolygon(points)
        else:
            painter.drawRoundedRect(2, 2, width - 4, height - 4, 8, 8)
        painter.end()
        self.image_label.setPixmap(pixmap)

    def _draw_transparent_layer(self, width, height):
        """绘制完全透明的点击层，不遮挡背景建筑。"""
        pixmap = QPixmap(width, height)
        pixmap.fill(Qt.transparent)
        self.image_label.setPixmap(pixmap)

    def _draw_hover_overlay(self, width, height):
        """悬停时绘制柔和高亮边框，提示玩家当前选中的建筑。"""
        bid = self.hotspot.get("id", "")
        color = QColor(_BUILDING_COLORS.get(bid, "#f1c40f"))
        pixmap = QPixmap(width, height)
        pixmap.fill(Qt.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)
        # 只保留细边框，不做大面积色块填充，避免遮挡背景建筑
        painter.setBrush(Qt.NoBrush)
        pen = QPen(color, 2)
        pen.setStyle(Qt.DotLine)
        painter.setPen(pen)

        shape = self.hotspot.get("shape", "rect")
        if shape == "circle":
            r = min(width, height) // 2 - 2
            painter.drawEllipse(QPoint(width // 2, height // 2), r, r)
        elif shape == "diamond":
            points = [
                QPoint(width // 2, 4),
                QPoint(width - 4, height // 2),
                QPoint(width // 2, height - 4),
                QPoint(4, height // 2),
            ]
            painter.drawPolygon(points)
        else:
            painter.drawRoundedRect(2, 2, width - 4, height - 4, 8, 8)
        painter.end()
        self.image_label.setPixmap(pixmap)

    def _update_mask(self):
        """根据热点形状或多边形遮罩设置点击区域。"""
        if not self._base_geometry.isValid():
            return
        w = self.width()
        h = self.height()
        if w <= 0 or h <= 0:
            return

        mask_points = self.hotspot.get("mask_points")
        if mask_points:
            poly_points = [QPoint(int(p[0] * w), int(p[1] * h)) for p in mask_points]
            region = QRegion(QPolygon(poly_points))
            self.setMask(region)
            return

        shape = self.hotspot.get("shape", "rect")
        if shape == "circle":
            cx, cy = w // 2, h // 2
            r = min(w, h) // 2
            region = QRegion(cx - r, cy - r, r * 2, r * 2, QRegion.Ellipse)
            self.setMask(region)
        elif shape == "diamond":
            points = [
                QPoint(w // 2, 0),
                QPoint(w, h // 2),
                QPoint(w // 2, h),
                QPoint(0, h // 2),
            ]
            self.setMask(QRegion(QPolygon(points)))
        else:
            self.clearMask()

    def enterEvent(self, event):
        self._set_hover(True)
        self.hovered.emit(True)
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._set_hover(False)
        self.hovered.emit(False)
        super().leaveEvent(event)

    def mousePressEvent(self, event):
        self._scale_animation.stop()
        self.set_hover_scale(0.95)
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        self._set_hover(True)
        self.clicked.emit()
        super().mouseReleaseEvent(event)

    def _set_hover(self, active):
        """设置悬停状态：缩放动画 + 光晕效果。"""
        target = 1.08 if active else 1.0
        self._scale_animation.stop()
        self._scale_animation.setStartValue(self._hover_scale)
        self._scale_animation.setEndValue(target)
        self._scale_animation.start()

        if active:
            if self._glow_effect is None:
                from PySide6.QtWidgets import QGraphicsDropShadowEffect
                self._glow_effect = QGraphicsDropShadowEffect(self)
                self._glow_effect.setBlurRadius(25)
                self._glow_effect.setOffset(0, 0)
                bid = self.hotspot.get("id", "")
                color = QColor(_BUILDING_COLORS.get(bid, "#f1c40f"))
                self._glow_effect.setColor(color)
                self.setGraphicsEffect(self._glow_effect)
        else:
            if self._glow_effect is not None:
                self.setGraphicsEffect(None)
                self._glow_effect = None


class CityMapWidget(QWidget):
    """城市俯瞰图容器：背景 + 建筑组件 + 点击涟漪。"""

    building_clicked = Signal(dict)
    building_hovered = Signal(dict)

    def __init__(self, map_image_path, hotspots, building_map, parent=None):
        super().__init__(parent)
        self.map_image_path = map_image_path
        self.hotspots = hotspots or []
        self.building_map = building_map or {}

        self._pixmap = QPixmap()
        selected_path = _select_city_image(map_image_path)
        if selected_path and os.path.exists(selected_path):
            self._pixmap.load(selected_path)

        self._ripples = []
        self._building_widgets = []
        self._hovered_building = None

        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        # 地图必须足够大，避免建筑被挤到窗口外形成“贴纸”效果
        self.setMinimumSize(900, 520)

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._on_animation_tick)
        self._timer.start(50)

        self._create_building_widgets()

    def _create_building_widgets(self):
        """根据热点配置创建建筑组件。"""
        for hotspot in self.hotspots:
            bid = hotspot.get("id", "")
            building = self.building_map.get(bid, {})
            widget = CityBuildingWidget(hotspot, building, parent=self)
            widget.clicked.connect(lambda w=widget, b=building, h=hotspot: self._on_building_clicked(w, b, h))
            widget.hovered.connect(lambda active, b=building: self._on_building_hovered(active, b))
            self._building_widgets.append(widget)
        self._reposition_buildings()

    def _reposition_buildings(self):
        """根据当前尺寸重新计算每个建筑的位置。"""
        img_rect = self._image_rect()
        for widget in self._building_widgets:
            hotspot = widget.hotspot
            x1, y1, x2, y2 = hotspot["coords"]
            bx = img_rect.left() + int(x1 * img_rect.width())
            by = img_rect.top() + int(y1 * img_rect.height())
            bw = int((x2 - x1) * img_rect.width())
            bh = int((y2 - y1) * img_rect.height())
            # 预留名牌空间：稍微向上扩展 widget 区域
            pad_top = 40
            widget.set_base_geometry(QRect(bx, by - pad_top, bw, bh + pad_top))

    def _image_rect(self):
        """背景图在 widget 中拉伸填满后的矩形（与 paintEvent 保持一致）。"""
        if self._pixmap.isNull():
            return self.rect()
        return QRect(0, 0, self.width(), self.height())

    def _on_building_clicked(self, widget, building, hotspot):
        """建筑被点击时触发涟漪并上报。"""
        bid = hotspot.get("id", "")
        color = _BUILDING_COLORS.get(bid, "#3498db")
        # 涟漪中心取建筑中心（基于 base geometry）
        geo = widget._base_geometry
        cx = geo.center().x()
        cy = geo.center().y()
        self._ripples.append({
            "cx": cx, "cy": cy, "radius": 5, "opacity": 180, "color": color,
        })
        self.building_clicked.emit(building)

    def _hit_test(self, pos):
        """判断坐标是否落在某个建筑组件上，返回对应 hotspot；未命中返回 None。"""
        for widget in self._building_widgets:
            if widget.geometry().contains(pos):
                return widget.hotspot
        return None

    def _get_building_widget_at(self, pos):
        """返回坐标处的 CityBuildingWidget 实例；未命中返回 None。"""
        for widget in self._building_widgets:
            if widget.geometry().contains(pos):
                return widget
        return None

    def _on_building_hovered(self, active, building):
        """建筑悬停状态变化。"""
        if active:
            self._hovered_building = building
            self.building_hovered.emit(building)
        elif self._hovered_building == building:
            self._hovered_building = None
            self.building_hovered.emit({})

    def _on_animation_tick(self):
        """更新涟漪扩散。"""
        changed = False
        new_ripples = []
        for ripple in self._ripples:
            ripple["radius"] += 4
            ripple["opacity"] -= 8
            if ripple["opacity"] > 0:
                new_ripples.append(ripple)
                changed = True
        if len(new_ripples) != len(self._ripples):
            changed = True
        self._ripples = new_ripples
        if changed:
            self.update()

    def paintEvent(self, event):
        """绘制背景图与涟漪。"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        # 背景：忽略原始比例拉伸填满整个组件，避免窗口 resize 后出现灰边
        if not self._pixmap.isNull():
            scaled = self._pixmap.scaled(self.size(), Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
            painter.drawPixmap(0, 0, scaled)
        else:
            painter.fillRect(self.rect(), QColor(230, 230, 230))
            painter.setPen(QPen(QColor(150, 150, 150), 1, Qt.DotLine))
            painter.drawRect(self.rect().adjusted(2, 2, -2, -2))

        # 涟漪
        for ripple in self._ripples:
            color = QColor(ripple["color"])
            color.setAlpha(ripple["opacity"])
            pen = QPen(color, 3)
            painter.setPen(pen)
            painter.setBrush(Qt.NoBrush)
            painter.drawEllipse(
                QPoint(ripple["cx"], ripple["cy"]),
                ripple["radius"], ripple["radius"]
            )

        painter.end()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._reposition_buildings()


class CityLordMenuDialog(QDialog):
    """城主府主菜单：选择城市任务或城池治理。"""

    def __init__(self, city_name, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"【{city_name}·城主府】")
        self.resize(320, 200)

        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(20, 20, 20, 20)

        title = QLabel(f"<h2>{city_name}·城主府</h2>")
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)

        desc = QLabel("城主府巍峨耸立，既是处理城中事务之所，也是城主颁布政令之地。")
        desc.setWordWrap(True)
        desc.setAlignment(Qt.AlignCenter)
        desc.setStyleSheet("color: #666; font-size: 12px;")
        layout.addWidget(desc)

        self.quest_btn = QPushButton("📜 城市任务")
        self.quest_btn.setToolTip("查看并领取城中发布的动态任务。")
        self.quest_btn.clicked.connect(self.accept)
        layout.addWidget(self.quest_btn)

        self.governance_btn = QPushButton("⚖️ 城池治理")
        self.governance_btn.setToolTip("参与城主竞选或颁布城池政策。")
        self.governance_btn.clicked.connect(self._on_governance)
        layout.addWidget(self.governance_btn)

        self._choice = "quest"  # 默认选择城市任务

    def _on_governance(self):
        self._choice = "governance"
        self.accept()

    def get_choice(self):
        return self._choice


class MarketMenuDialog(QDialog):
    """坊市主菜单：选择交易、摆摊或拍卖行。"""

    def __init__(self, city_name, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"【{city_name}·坊市】")
        self.resize(320, 220)

        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(20, 20, 20, 20)

        title = QLabel(f"<h2>{city_name}·坊市</h2>")
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)

        desc = QLabel("熙熙攘攘的修仙坊市，各类灵材、丹药、法器在此流通。")
        desc.setWordWrap(True)
        desc.setAlignment(Qt.AlignCenter)
        desc.setStyleSheet("color: #666; font-size: 12px;")
        layout.addWidget(desc)

        self.trade_btn = QPushButton("🛒 与坊市商人交易")
        self.trade_btn.setToolTip("购买或出售常见丹药、材料、符箓。")
        self.trade_btn.clicked.connect(self.accept)
        layout.addWidget(self.trade_btn)

        self.stall_btn = QPushButton("📦 我要摆摊")
        self.stall_btn.setToolTip("将背包物品上架到坊市，每月有概率被其他修士买走。")
        self.stall_btn.clicked.connect(self._on_stall)
        layout.addWidget(self.stall_btn)

        self.auction_btn = QPushButton("🔨 拍卖行")
        self.auction_btn.setToolTip("参与本月稀有拍品竞拍，价高者得。")
        self.auction_btn.clicked.connect(self._on_auction)
        layout.addWidget(self.auction_btn)

        self._choice = "trade"  # 默认选择交易

    def _on_stall(self):
        self._choice = "stall"
        self.accept()

    def _on_auction(self):
        self._choice = "auction"
        self.accept()

    def get_choice(self):
        return self._choice


class CityDialog(QDialog):
    """城池内部弹窗，优先展示可视化地图，缺失时 fallback 为按钮网格。"""

    def __init__(self, engine, location_id, parent=None):
        super().__init__(parent)
        self.engine = engine
        self.location_id = location_id
        self.location = self.engine.world.get_location(location_id) or {}

        city_name = self.location.get("name", "城池")
        self.setWindowTitle(f"【{city_name}】")
        # 窗口尺寸与 800x480 背景图比例匹配，给标题栏/信息栏/底部栏预留空间
        self.resize(1000, 760)

        self._buildings = self.location.get("buildings", [])
        self._building_map = {b.get("id"): b for b in self._buildings if b.get("id")}

        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(12, 12, 12, 12)

        # === 顶部标题栏 ===
        title_bar = QWidget()
        title_bar.setStyleSheet(
            "background-color: rgba(255, 255, 255, 180); border-radius: 8px;"
        )
        title_layout = QHBoxLayout(title_bar)
        title_layout.setContentsMargins(12, 6, 12, 6)

        self.title_label = QLabel(f"<h2>{city_name}</h2>")
        self.title_label.setStyleSheet("color: #2c3e50;")
        title_layout.addWidget(self.title_label)
        title_layout.addStretch()

        self.toggle_desc_btn = QPushButton("展开介绍 ▼")
        self.toggle_desc_btn.setStyleSheet(
            "QPushButton { background: transparent; color: #3498db; border: none; }"
            "QPushButton:hover { color: #2980b9; }"
        )
        self.toggle_desc_btn.setCursor(Qt.PointingHandCursor)
        self.toggle_desc_btn.clicked.connect(self._toggle_description)
        title_layout.addWidget(self.toggle_desc_btn)
        layout.addWidget(title_bar)

        # === 城市介绍卷轴（默认收起）===
        self.desc_scroll = QLabel()
        self.desc_scroll.setWordWrap(True)
        self.desc_scroll.setText(self.location.get("description", "这是一座繁华的修仙城池。"))
        self.desc_scroll.setStyleSheet(
            "background-color: #fdfbf7; color: #5d4037; "
            "border: 1px solid #d7ccc8; border-radius: 6px; "
            "padding: 10px; font-size: 13px;"
        )
        self.desc_scroll.setVisible(False)
        layout.addWidget(self.desc_scroll)

        # === 城池事件提示条（妖兽攻城等）===
        self.event_banner = QPushButton()
        self.event_banner.setCursor(Qt.PointingHandCursor)
        self.event_banner.setStyleSheet(
            "QPushButton { background-color: #c0392b; color: white; "
            "border-radius: 6px; padding: 8px; font-size: 14px; font-weight: bold; }"
            "QPushButton:hover { background-color: #e74c3c; }"
        )
        self.event_banner.clicked.connect(self._open_city_defense)
        self._refresh_event_banner()
        layout.addWidget(self.event_banner)

        # === 中央地图或按钮区 ===
        self.map_config = _load_city_map_config(location_id)
        self.map_widget = None
        self.fallback_grid = None

        if self._can_use_map():
            self._setup_map_view(layout)
        else:
            self._setup_fallback_buttons(layout)

        # === 建筑详情提示栏 ===
        self.building_info_label = QLabel("将鼠标移到建筑上查看详情，点击建筑进入功能")
        self.building_info_label.setWordWrap(True)
        self.building_info_label.setStyleSheet(
            "background: #f8f9fa; border-radius: 6px; padding: 8px; color: #555; font-size: 13px;"
        )
        layout.addWidget(self.building_info_label)

        # === 底部操作栏 ===
        bottom_layout = QHBoxLayout()
        bottom_layout.setSpacing(10)

        develop_btn = QPushButton("🏯 城池发展")
        develop_btn.setToolTip("查看城池声望与升级城内建筑。")
        develop_btn.clicked.connect(self._open_building_upgrade)
        bottom_layout.addWidget(develop_btn)

        npc_btn = QPushButton("🗣 拜访城中人物")
        npc_btn.setToolTip("查看当前地点的 NPC，可接任务、拜师、交易")
        npc_btn.clicked.connect(self._on_visit_npcs)
        bottom_layout.addWidget(npc_btn)

        bottom_layout.addStretch()

        leave_btn = QPushButton("离开")
        leave_btn.setToolTip("离开城池")
        leave_btn.setStyleSheet(
            "QPushButton { background-color: #8d6e63; color: white; "
            "border-radius: 6px; padding: 8px 20px; font-weight: bold; }"
            "QPushButton:hover { background-color: #6d4c41; }"
            "QPushButton:pressed { background-color: #5d4037; }"
        )
        leave_btn.clicked.connect(self.accept)
        bottom_layout.addWidget(leave_btn)

        layout.addLayout(bottom_layout)

    def _can_use_map(self):
        """判断是否能使用可视化地图。"""
        if not self.map_config:
            return False
        image_path = self.map_config.get("map_image")
        if not image_path or not os.path.exists(_select_city_image(image_path)):
            return False
        if not self.map_config.get("hotspots"):
            return False
        return True

    def _setup_map_view(self, layout):
        """创建可视化地图组件。"""
        image_path = self.map_config.get("map_image")
        hotspots = self.map_config.get("hotspots", [])

        self.map_widget = CityMapWidget(image_path, hotspots, self._building_map)
        self.map_widget.building_clicked.connect(self._on_building_clicked)
        self.map_widget.building_hovered.connect(self._on_building_hovered)
        layout.addWidget(self.map_widget, 1)

    def _setup_fallback_buttons(self, layout):
        """地图不可用时展示旧版按钮网格。"""
        info = QLabel("未找到城市地图资源，已切换为列表模式。")
        info.setStyleSheet("color: #e67e22; font-size: 12px;")
        layout.addWidget(info)

        self.fallback_grid = QGridLayout()
        self.fallback_grid.setSpacing(12)
        self._build_building_buttons()
        layout.addLayout(self.fallback_grid)

    def _build_building_buttons(self):
        """根据 location 的 buildings 数据创建建筑按钮（fallback 用）。"""
        if not self._buildings:
            self.fallback_grid.addWidget(
                QLabel("此地尚未记录任何建筑。"), 0, 0
            )
            return

        columns = 3
        for index, building in enumerate(self._buildings):
            name = building.get("name", "未知建筑")
            action = building.get("action")
            label = f"{name}\n（{_ACTION_LABELS.get(action, '')}）"
            btn = QPushButton(label)
            bid = building.get("id", "")
            color = _BUILDING_COLORS.get(bid, "#3498db")
            btn.setStyleSheet(
                f"QPushButton {{ background: {color}; color: white; "
                f"border-radius: 6px; padding: 10px; font-weight: bold; }}"
                f"QPushButton:hover {{ background: #2c3e50; }}"
            )
            btn.setToolTip(building.get("description", ""))
            btn.clicked.connect(
                lambda checked, b=building: self._on_building_clicked(b)
            )
            row = index // columns
            col = index % columns
            self.fallback_grid.addWidget(btn, row, col)

    def _toggle_description(self):
        """切换城市介绍的显示/隐藏。"""
        visible = self.desc_scroll.isHidden()
        self.desc_scroll.setVisible(visible)
        self.toggle_desc_btn.setText("收起介绍 ▲" if visible else "展开介绍 ▼")

    def _on_building_hovered(self, building):
        """鼠标悬停在建筑上时更新详情提示。"""
        if not building:
            self.building_info_label.setText("将鼠标移到建筑上查看详情，点击建筑进入功能")
            return
        name = building.get("name", "未知建筑")
        desc = building.get("description", "暂无介绍。")
        action = building.get("action")
        action_text = _ACTION_LABELS.get(action, "")
        text = f"<b>{name}</b>"
        if action_text:
            text += f" [{action_text}]"
        text += f"<br>{desc}"
        self.building_info_label.setText(text)

    def _on_building_clicked(self, building):
        """点击建筑时触发对应玩法。"""
        action = building.get("action")
        if not action:
            return

        if action == "rest":
            self._enter_inn(building.get("name", "客栈"))
        elif action == "market":
            self._open_market(building.get("name", "坊市"))
        elif action == "arena":
            self._enter_arena(building.get("name", "演武场"))
        elif action == "quest":
            self._open_city_quests(building.get("name", "城主府"))
        elif action == "beast_park":
            self._enter_beast_park(building.get("name", "万兽园"))
        elif action == "aquatic_shop":
            self._open_aquatic_shop(building.get("name", "水族商行"))
        elif action in ("alchemy", "shop"):
            self._open_alchemy_pavilion(building.get("name", "炼丹阁"))
        elif action == "cave":
            self._enter_cave(building.get("name", "洞府"))

    def _enter_inn(self, name):
        """进入客栈，可选择歇息或打听消息。"""
        from ui.inn_dialog import InnDialog
        dialog = InnDialog(self.engine, inn_name=name, parent=self)
        dialog.exec()

    def _enter_cave(self, name):
        """进入洞府租赁与闭关修炼界面。"""
        dialog = CaveDialog(self.engine, location_id=self.location_id, parent=self)
        dialog.exec()

    def _open_market(self, name):
        """打开坊市主菜单，可选择交易、摆摊或拍卖行。"""
        city_name = self.location.get("name", name)
        menu = MarketMenuDialog(city_name, parent=self)
        if menu.exec() != QDialog.Accepted:
            return

        choice = menu.get_choice()
        if choice == "trade":
            from ui.npc_dialog import NPCDialog
            merchant = self.engine.open_city_market()
            dialog = NPCDialog(self.engine, preset_npc=merchant, parent=self)
            dialog.exec()
        elif choice == "stall":
            dialog = StallDialog(self.engine, parent=self)
            dialog.exec()
        elif choice == "auction":
            dialog = AuctionDialog(self.engine, parent=self)
            dialog.exec()

    def _enter_arena(self, name):
        """进入演武场。"""
        from ui.arena_dialog import ArenaDialog
        dialog = ArenaDialog(self.engine, parent=self)
        dialog.exec()

    def _open_city_quests(self, name):
        """打开城主府主菜单，可选择城市任务或城池治理。"""
        city_name = self.location.get("name", name)
        menu = CityLordMenuDialog(city_name, parent=self)
        if menu.exec() != QDialog.Accepted:
            return

        choice = menu.get_choice()
        if choice == "quest":
            from ui.city_quest_dialog import CityQuestDialog
            dialog = CityQuestDialog(self.engine, parent=self)
            dialog.exec()
        elif choice == "governance":
            from ui.city_policy_dialog import CityPolicyDialog
            dialog = CityPolicyDialog(self.engine, city_id=self.location_id, parent=self)
            dialog.exec()

    def _enter_beast_park(self, name):
        """进入万兽园。"""
        from ui.beast_park_dialog import BeastParkDialog
        dialog = BeastParkDialog(self.engine, parent=self)
        dialog.exec()

    def _open_aquatic_shop(self, name):
        """打开水族商行。"""
        from ui.npc_dialog import NPCDialog
        merchant = self.engine.visit_aquatic_shop()
        dialog = NPCDialog(self.engine, preset_npc=merchant, parent=self)
        dialog.exec()

    def _open_alchemy_pavilion(self, name):
        """打开炼丹阁。"""
        from ui.alchemy_dialog import AlchemyDialog
        dialog = AlchemyDialog(self.engine, parent=self)
        dialog.exec()

    def _refresh_event_banner(self):
        """根据当前城池是否有活跃事件刷新提示条。"""
        event = self.engine.get_active_city_event()
        if event:
            self.event_banner.setText(f"⚠ {event['name']}：{event['description']}")
            self.event_banner.setVisible(True)
        else:
            self.event_banner.setVisible(False)

    def _open_city_defense(self):
        """打开城池守城战弹窗。"""
        from ui.city_defense_dialog import CityDefenseDialog
        dialog = CityDefenseDialog(self.engine, parent=self)
        dialog.exec()
        self._refresh_event_banner()

    def _open_building_upgrade(self):
        """打开城池发展与建筑升级弹窗。"""
        from ui.building_upgrade_dialog import BuildingUpgradeDialog
        dialog = BuildingUpgradeDialog(self.engine, parent=self)
        dialog.exec()

    def _on_visit_npcs(self):
        """打开 NPC 交互弹窗。"""
        from ui.npc_dialog import NPCDialog
        dialog = NPCDialog(self.engine, parent=self)
        dialog.exec()
