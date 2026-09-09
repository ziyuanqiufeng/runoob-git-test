import json
import os
import random


class EventPool:
    """事件池，根据条件和地点抽取随机事件。"""

    def __init__(self, config_dir="config"):
        # 加载事件配置
        events_path = os.path.join(config_dir, "events.json")
        with open(events_path, "r", encoding="utf-8") as f:
            self.events = json.load(f)

        # 用事件 ID 做索引
        self.event_map = {e["id"]: e for e in self.events}

    def draw(self, condition, location=None):
        """根据条件和地点按权重随机抽取一个事件。"""
        # 筛选符合当前条件的事件
        candidates = [e for e in self.events if e["condition"] == condition]
        if not candidates:
            return None

        # 如果提供了地点，使用地点覆盖的权重
        weights = []
        for event in candidates:
            event_id = event["id"]
            if location and "event_weights" in location and event_id in location["event_weights"]:
                weights.append(location["event_weights"][event_id])
            else:
                weights.append(event["weight"])

        # 按权重随机选择
        total_weight = sum(weights)
        roll = random.uniform(0, total_weight)
        current = 0
        for event, weight in zip(candidates, weights):
            current += weight
            if roll <= current:
                return event
        return candidates[-1]

    def get_event(self, event_id):
        """根据 ID 直接获取事件。"""
        return self.event_map.get(event_id)
