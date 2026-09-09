"""宗门外交任务系统。"""
import json
import os


class DiplomaticMissionLibrary:
    """外交任务模板库，从 JSON 加载。"""

    def __init__(self, config_dir="config"):
        path = os.path.join(config_dir, "diplomatic_missions.json")
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        self._missions = {entry["id"]: entry for entry in data}

    def get(self, mission_id):
        """获取指定外交任务模板（深拷贝）。"""
        data = self._missions.get(mission_id)
        return dict(data) if data else None

    def get_by_relation(self, relation):
        """获取面向指定关系类型的外交任务模板列表。"""
        return [dict(entry) for entry in self._missions.values()
                if entry.get("target_relation") == relation]

    def all_missions(self):
        """返回所有外交任务模板。"""
        return [dict(entry) for entry in self._missions.values()]
