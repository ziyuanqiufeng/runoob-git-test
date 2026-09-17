import collections
import json
import os
import random


class EventPool:
    """事件池，根据条件和地点抽取随机事件。

    支持去重窗口：avoid_recent=True 时，最近抽中的事件在候选充足时
    会被跳过（候选不足则回退全候选），避免连续抽出同一事件。
    """

    # 去重窗口大小：最近 N 次抽中的事件不重复
    RECENT_WINDOW = 5

    def __init__(self, config_dir="config"):
        # 加载事件配置
        events_path = os.path.join(config_dir, "events.json")
        with open(events_path, "r", encoding="utf-8") as f:
            self.events = json.load(f)

        # 用事件 ID 做索引
        self.event_map = {e["id"]: e for e in self.events}

        # 去重窗口：记录最近抽中的事件 id（不持久化，跨会话重置可接受）
        self._recent = collections.deque(maxlen=self.RECENT_WINDOW)

    def _weighted_choice(self, candidates, location):
        """按权重（地点覆盖优先）随机选择一个事件。"""
        weights = []
        for event in candidates:
            event_id = event["id"]
            if location and "event_weights" in location and event_id in location["event_weights"]:
                weights.append(location["event_weights"][event_id])
            else:
                weights.append(event["weight"])

        total_weight = sum(weights)
        roll = random.uniform(0, total_weight)
        current = 0
        for event, weight in zip(candidates, weights):
            current += weight
            if roll <= current:
                return event
        return candidates[-1]

    def draw(self, condition, location=None, avoid_recent=True):
        """根据条件和地点按权重随机抽取一个事件。

        avoid_recent=True 时启用去重窗口：最近 RECENT_WINDOW 次抽中的
        事件在还有其他候选时被跳过；候选不足（全部命中窗口）则回退
        全候选，保证总能抽出一个事件。
        """
        candidates = [e for e in self.events if e["condition"] == condition]
        if not candidates:
            return None

        if avoid_recent and len(candidates) > 1:
            recent = set(self._recent)
            fresh = [e for e in candidates if e["id"] not in recent]
            if fresh:
                candidates = fresh

        event = self._weighted_choice(candidates, location)
        self._recent.append(event["id"])
        return event

    def get_event(self, event_id):
        """根据 ID 直接获取事件。"""
        return self.event_map.get(event_id)
