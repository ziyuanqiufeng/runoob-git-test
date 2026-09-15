from PySide6.QtWidgets import QWidget, QVBoxLayout, QTextEdit


class LogPanel(QWidget):
    """底部日志面板，记录游戏中的重要事件。"""

    def __init__(self):
        super().__init__()

        # 垂直布局
        self.layout = QVBoxLayout(self)

        # 文本框只读，用于显示日志
        self.text_edit = QTextEdit()
        self.text_edit.setReadOnly(True)
        self.text_edit.setPlaceholderText("修仙日志将显示在这里...")
        self.layout.addWidget(self.text_edit)

    def append(self, message):
        """追加一条日志。"""
        if not message:
            return
        self.text_edit.append(message)

    def clear(self):
        """清空日志。"""
        self.text_edit.clear()
