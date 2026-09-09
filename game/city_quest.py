# -*- coding: utf-8 -*-
"""
城池动态任务生成器：根据当前城池与模板随机生成日常/周常任务。
"""

import json
import os
import random
import time


class CityQuestGenerator:
    """从 JSON 模板生成城池任务。"""

    def __init__(self, config_dir="config"):
        path = os.path.join(config_dir, "city_quests.json")
        with open(path, "r", encoding="utf-8") as f:
            self.templates = json.load(f)

    def generate(self, city_id, city_name, item_library, count=3):
        """
        为指定城池生成 count 条动态任务。
        返回任务 dict 列表，每个任务包含完整字段与唯一 quest_id。
        """
        quests = []
        # 随机选取不重复的模板
        chosen = random.sample(
            self.templates, min(count, len(self.templates))
        )
        for template in chosen:
            target_id = random.choice(template["target_pool"])
            target_name = self._get_target_name(target_id, item_library)
            quest_count = random.randint(*template["count_range"])
            qi_reward = random.randint(*template["reward_qi_range"])
            stone_reward = random.randint(*template["reward_stone_range"])

            # 生成唯一任务 ID：city_<城池ID>_<模板ID>_<时间戳>
            quest_id = f"city_{city_id}_{template['template_id']}_{int(time.time()*1000)}_{random.randint(1000,9999)}"

            description = template["description"].format(
                count=quest_count, target_name=target_name
            )

            quests.append({
                "id": quest_id,
                "name": template["name"],
                "description": description,
                "target_type": template["target_type"],
                "target_id": target_id,
                "target_name": target_name,
                "count": quest_count,
                "reward": {
                    "qi": qi_reward,
                    "spirit_stone": stone_reward,
                },
                "city_id": city_id,
                "city_name": city_name,
            })
        return quests

    def _get_target_name(self, target_id, item_library):
        """获取目标显示名称：物品优先从 item_library，否则直接返回 ID。"""
        item = item_library.get(target_id)
        if item:
            return item.name
        # 若目标是敌人，可用 enemy_library；这里简化处理
        return target_id
