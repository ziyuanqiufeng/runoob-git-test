# -*- coding: utf-8 -*-
"""历史年表系统：记录玩家修仙生涯的重要节点。"""


class ChronicleManager:
    """管理年表条目。"""

    def __init__(self, player, world):
        self.player = player
        self.world = world
        if not hasattr(player, "chronicle"):
            player.chronicle = []

    def record(self, event_text, category="event"):
        """记录一条年表事件。"""
        entry = {
            "year": self.world.year,
            "month": self.world.month,
            "age": self.player.age,
            "text": event_text,
            "category": category,
        }
        self.player.chronicle.append(entry)

    def get_entries(self, category=None, limit=50):
        """按类别或数量筛选年表条目。"""
        entries = self.player.chronicle
        if category:
            entries = [e for e in entries if e["category"] == category]
        return entries[-limit:]

    def get_summary(self):
        """生成生涯摘要。"""
        total = len(self.player.chronicle)
        categories = {}
        for e in self.player.chronicle:
            categories[e["category"]] = categories.get(e["category"], 0) + 1
        return {"total": total, "categories": categories}
