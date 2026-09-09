"""追随者（弟子/仆从）系统。"""
import json
import os


class FollowerLibrary:
    """追随者模板库，从 JSON 加载可招募对象。"""

    def __init__(self, config_dir="config"):
        path = os.path.join(config_dir, "followers.json")
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        # 以 ID 为键建立索引
        self._followers = {entry["id"]: entry for entry in data}

    def get(self, follower_id):
        """获取指定追随者模板（深拷贝，避免运行时修改模板）。"""
        data = self._followers.get(follower_id)
        return dict(data) if data else None

    def get_by_sect(self, sect_id):
        """获取属于某宗门的所有可招募追随者模板。"""
        return [dict(entry) for entry in self._followers.values()
                if entry.get("sect_id") == sect_id]

    def all_ids(self):
        """返回所有追随者模板 ID。"""
        return list(self._followers.keys())
