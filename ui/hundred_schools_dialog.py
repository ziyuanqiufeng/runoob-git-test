# -*- coding: utf-8 -*-
"""百家争鸣 / 非传统修仙路线弹窗（维度③）。

展示立派传道（宗门/弟子/气运）、自创功法、生活流派精进度与道心；
提供「开宗立派」「道韵灌顶」「自创功法」「择生活流派」四项动作。
"""
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QLabel, QPushButton, QFrame, QTextEdit,
    QHBoxLayout, QMessageBox, QScrollArea, QWidget, QCheckBox,
)
from PySide6.QtCore import Qt


class HundredSchoolsDialog(QDialog):
    """百家争鸣交互弹窗。"""

    def __init__(self, engine, parent=None):
        super().__init__(parent)
        self.engine = engine
        self.player = engine.player
        self.mgr = engine.hundred_schools_manager
        self.setWindowTitle("百家争鸣")
        self.resize(560, 600)
        self._build()

    def _build(self):
        outer = QVBoxLayout(self)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        inner = QWidget()
        self._layout = QVBoxLayout(inner)
        scroll.setWidget(inner)
        outer.addWidget(scroll)

        status = self.mgr.get_status()

        # 道心
        self._layout.addWidget(self._bar(
            "道心", status["mental_state"], 100, "#27ae60"
        ))

        # 立派传道
        self._layout.addWidget(self._section_label("立派传道 · 气运反哺"))
        sect = status["sect"]
        if sect:
            self._layout.addWidget(QLabel(
                f"⛩ 宗门：{sect['name']}　弟子 {sect['disciples']}　气运 {sect['qi_yun']}"
            ))
            enl_btn = QPushButton("道韵灌顶（耗气运增益道心）")
            enl_btn.clicked.connect(self._on_enlightenment)
            self._layout.addWidget(enl_btn)
        else:
            found_btn = QPushButton("开宗立派（金丹期后）")
            found_btn.clicked.connect(self._on_found_sect)
            self._layout.addWidget(found_btn)

        # 自创功法
        self._layout.addWidget(self._section_label("自创功法 · 明心见性 · 可施展"))
        techs = status["techniques"]
        learned_ids = set(getattr(self.player, "skills", []))
        if techs:
            for t in techs:
                sid = t.get("skill_id")
                mark = "✓已可施展" if sid in learned_ids else "（待激活）"
                self._layout.addWidget(QLabel(
                    f"· 《{t.get('name', '无名功法')}》（{t.get('school', '')}·{t.get('attribute', '')}）{mark}"
                ))
        else:
            self._layout.addWidget(QLabel("（尚无自创功法）"))
        create_btn = QPushButton("推演自创功法（一次性）")
        create_btn.clicked.connect(self._on_create_technique)
        self._layout.addWidget(create_btn)

        # 维度③·M19：功法推演（养成式自创功法，逐节点参悟累积品质）
        deduce_btn = QPushButton("功法推演（养成式·参悟节点）")
        deduce_btn.clicked.connect(self._on_deduction)
        self._layout.addWidget(deduce_btn)

        # 生活流派
        self._layout.addWidget(self._section_label("生活流派 · 御心魔之劫 · 产异物"))
        lp = status["life_path"]
        lp_cfg = self.mgr.config.get_life_path()
        if lp:
            lp_name = lp_cfg.get("types", {}).get(lp, lp)
            prod = lp_cfg.get("produce", {}).get(lp)
            prod_text = ""
            if prod:
                item_name = prod.get("item_id")
                try:
                    item_name = self.engine.item_library.get(item_name).name if hasattr(self.engine, "item_library") and self.engine.item_library.get(item_name) else item_name
                except Exception:
                    pass
                prod_text = f"　每 {prod.get('every_months')} 月制得【{item_name}】"
            self._layout.addWidget(QLabel(
                f"🛠 当前流派：{lp_name}　精进度 {status['life_path_proficiency']}{prod_text}"
            ))
            # 维度③·M16：符箓/阵法流派产出可战斗部署法宝，给玩家开关控制权
            if lp in ("talisman", "array"):
                cb = QCheckBox("⚔ 战斗开始时自动部署法宝（消耗库存）")
                cb.setChecked(bool(getattr(self.engine.player, "lifepath_auto_deploy", False)))
                cb.toggled.connect(self._on_toggle_auto_deploy)
                self._layout.addWidget(cb)
        else:
            for key, name in lp_cfg.get("types", {}).items():
                btn = QPushButton(f"择『{name}』精进")
                btn.clicked.connect(lambda _checked, p=key: self._on_choose_life_path(p))
                self._layout.addWidget(btn)

        close = QPushButton("合卷")
        close.clicked.connect(self.accept)
        self._layout.addWidget(close)

    def _on_found_sect(self):
        name, ok = self._ask_text("开宗立派", "为你的道统命名：")
        if ok:
            res = self.engine.found_sect(name)
            QMessageBox.information(self, "立派", res[1])
            if res[0]:
                self._refresh()

    def _on_enlightenment(self):
        res = self.engine.spend_qi_yun_for_enlightenment()
        QMessageBox.information(self, "道韵灌顶", res[1])
        if res[0]:
            self._refresh()

    def _on_create_technique(self):
        name, ok = self._ask_text("自创功法", "命名你的独门功法：")
        if not ok:
            return
        schools = self.mgr.config.get_technique().get("schools", [])
        attrs = self.mgr.config.get_technique().get("allowed_attributes", [])
        # 简化交互：取首个流派与属性，UI 不强求复杂选择
        if schools and attrs:
            res = self.engine.create_technique(name, schools[0], attrs[0])
            QMessageBox.information(self, "自创功法", res[1])
            if res[0]:
                self._refresh()

    def _on_choose_life_path(self, path):
        res = self.engine.choose_life_path(path)
        QMessageBox.information(self, "生活流派", res[1])
        if res[0]:
            self._refresh()

    def _on_deduction(self):
        """维度③·M19：功法推演小游戏——开推演→逐节点参悟（随机机缘）→大成。

        简化为：命名后取首个流派/属性开推演，逐节点随机参悟累积品质，
        最后大成落定为带品质阶的自创功法（更强 Skill）。
        """
        name, ok = self._ask_text("功法推演", "命名你欲推演的独门功法：")
        if not ok or not name.strip():
            return
        tech_cfg = self.mgr.config.get_technique()
        schools = tech_cfg.get("schools", [])
        attrs = tech_cfg.get("allowed_attributes", [])
        if not schools or not attrs:
            QMessageBox.information(self, "功法推演", "推演配置缺失，无法进行。")
            return
        res = self.engine.start_technique_deduction(name.strip(), schools[0], attrs[0])
        if not res[0]:
            QMessageBox.information(self, "功法推演", res[1])
            return
        max_nodes = tech_cfg.get("deduction", {}).get("max_nodes", 4)
        lines = []
        for i in range(max_nodes):
            ok2, msg2, detail = self.engine.resolve_technique_deduction_node()
            if not ok2:
                lines.append(f"第{i + 1}节点：{msg2}")
                break
            lines.append(f"第{i + 1}节点【{detail['node']}】：{detail['outcome']}（品质+{detail['gain']}）")
        ok3, msg3, tech = self.engine.commit_technique_deduction()
        lines.append("")
        lines.append(msg3)
        QMessageBox.information(self, "功法推演·大成", "\n".join(lines))
        if ok3:
            self._refresh()

    def _on_toggle_auto_deploy(self, checked):
        """维度③·M16：玩家自主控制战斗自动部署法宝开关。"""
        self.engine.player.lifepath_auto_deploy = bool(checked)

    def _ask_text(self, title, prompt):
        from PySide6.QtWidgets import QInputDialog
        return QInputDialog.getText(self, title, prompt)

    def _refresh(self):
        while self._layout.count():
            item = self._layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()
        self._build()

    def _bar(self, name, value, max_v, color):
        pct = max(0, min(100, int(100 * value / max_v))) if max_v else 0
        filled = pct // 10
        bar = "█" * filled + "░" * (10 - filled)
        label = QLabel(f"{name}：[{bar}] {value}/{max_v}")
        label.setStyleSheet(f"color:{color}; font-family:monospace; font-size:13px;")
        return label

    def _section_label(self, text):
        lbl = QLabel(text)
        lbl.setStyleSheet("font-weight:bold; margin-top:8px;")
        return lbl
