import json
import os


class CultivationPathConfig:
    """
    修炼流派配置管理器，从 cultivation_paths.json 加载流派配置。
    负责流派属性修正、专属资源、协同与克制关系查询。
    """

    def __init__(self, config_dir="config"):
        config_path = os.path.join(config_dir, "cultivation_paths.json")
        with open(config_path, "r", encoding="utf-8") as f:
            self.data = json.load(f)

        # 所有流派配置
        self.paths = self.data["paths"]
        # 流派 + 灵根协同倍率
        self.synergy = self.data.get("synergy", {})
        # 流派克制关系：A 克制 B
        self.counter = self.data.get("counter", {})
        # 克制时的伤害倍率
        self.counter_multiplier = self.data.get("counter_multiplier", 1.3)
        # 被克制时的伤害倍率
        self.counter_resist_multiplier = self.data.get("counter_resist_multiplier", 0.8)

    def get_path(self, path_id):
        """根据流派 ID 获取流派配置。"""
        return self.paths.get(path_id)

    def get_path_name(self, path_id):
        """获取流派中文名。"""
        path = self.get_path(path_id)
        return path["name"] if path else "未入门"

    def get_path_color(self, path_id):
        """获取流派 UI 颜色。"""
        path = self.get_path(path_id)
        return path.get("color", "#ecf0f1") if path else "#ecf0f1"

    def get_modifiers(self, path_id):
        """获取流派属性修正字典。"""
        path = self.get_path(path_id)
        if not path:
            return {}
        return path.get("modifiers", {})

    def get_resource_info(self, path_id):
        """
        获取流派专属资源信息。
        返回 (resource_key, resource_name, resource_max) 或 None。
        """
        path = self.get_path(path_id)
        if not path:
            return None
        return (
            path.get("resource"),
            path.get("resource_name", ""),
            path.get("resource_max", 100),
        )

    def get_exclusive_skills(self, path_id):
        """获取流派专属技能 ID 列表。"""
        path = self.get_path(path_id)
        if not path:
            return []
        return path.get("exclusive_skills", [])

    def get_synergy_multiplier(self, path_id, element):
        """
        获取流派与灵根的协同倍率。
        例：剑修+金灵根 → 1.2
        """
        key = f"{path_id},{element}"
        return self.synergy.get(key, 1.0)

    def get_counter_multiplier(self, attacker_path, defender_path):
        """
        计算流派克制伤害系数：
        - 攻击方克制防御方：×1.3
        - 攻击方被防御方克制：×0.8
        - 无克制关系：×1.0
        """
        if not attacker_path or not defender_path:
            return 1.0
        # 攻击方克制防御方
        if self.counter.get(attacker_path) == defender_path:
            return self.counter_multiplier
        # 防御方克制攻击方
        if self.counter.get(defender_path) == attacker_path:
            return self.counter_resist_multiplier
        return 1.0

    def get_all_path_ids(self):
        """获取所有流派 ID 列表。"""
        return list(self.paths.keys())
