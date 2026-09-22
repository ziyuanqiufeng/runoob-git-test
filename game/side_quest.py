# -*- coding: utf-8 -*-
"""支线任务系统：NPC 发布的独立小任务。"""
import json
import os


class SideQuestConfig:
    """加载支线任务配置。"""

    def __init__(self, config_dir="config"):
        self.config_dir = config_dir
        self._quests = {}
        self._load()

    def _load(self):
        path = os.path.join(self.config_dir, "side_quests.json")
        if not os.path.exists(path):
            return
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        for entry in data:
            self._quests[entry["id"]] = entry

    def get(self, quest_id):
        return self._quests.get(quest_id)

    def get_all(self):
        return list(self._quests.values())


class SideQuestManager:
    """管理支线任务的接取、进度与结算。"""

    def __init__(self, player, item_library, config_dir="config", world=None):
        self.player = player
        self.item_library = item_library
        self.config = SideQuestConfig(config_dir)
        self.world = world
        if not hasattr(player, "active_side_quests"):
            player.active_side_quests = {}
        if not hasattr(player, "completed_side_quests"):
            player.completed_side_quests = []

    def _realm_qi_scale(self):
        """境界成长系数（与 GameEngine._realm_qi_scale 同斜率）。

        未注入 world 时返回 1.0（保持旧行为，兼容测试与旧调用方）。
        """
        if not self.world:
            return 1.0
        realm = self.world.realms.get(self.player.realm_id)
        order = realm["order"] if realm else 1
        return 1 + order * 0.8

    def get_available_quests(self, location_id):
        """获取当前地点可接取的支线任务。"""
        available = []
        for qid, quest in self.config._quests.items():
            if qid in self.player.active_side_quests or qid in self.player.completed_side_quests:
                continue
            if quest.get("location") == location_id:
                available.append(quest)
        return available

    def accept(self, quest_id):
        if quest_id in self.player.active_side_quests:
            return False, "任务已在进行中。"
        quest = self.config.get(quest_id)
        if not quest:
            return False, "任务不存在。"
        self.player.active_side_quests[quest_id] = {
            "objectives": [{**obj, "progress": 0} for obj in quest.get("objectives", [])],
        }
        return True, f"接受支线任务：【{quest['name']}】"

    def update_progress(self, objective_type, **kwargs):
        """
        推进所有活跃支线任务的对应目标。
        返回 {quest_id: rewards_dict} 的已完成任务奖励映射。
        """
        completed_quests = []
        for qid, state in self.player.active_side_quests.items():
            quest = self.config.get(qid)
            if not quest:
                continue
            all_done = True
            for obj in state["objectives"]:
                if obj["type"] != objective_type:
                    continue
                if obj.get("completed"):
                    continue
                # 击杀目标
                if objective_type == "kill" and obj.get("enemy_id") == kwargs.get("enemy_id"):
                    obj["progress"] = obj.get("progress", 0) + kwargs.get("count", 1)
                    if obj["progress"] >= obj.get("count", 1):
                        obj["completed"] = True
                # 收集目标
                elif objective_type == "collect_item" and obj.get("item_id") == kwargs.get("item_id"):
                    have = self.player.count_item(obj["item_id"])
                    obj["progress"] = min(have, obj.get("count", 1))
                    if obj["progress"] >= obj.get("count", 1):
                        obj["completed"] = True
                # 访问地点
                elif objective_type == "visit_location" and obj.get("location_id") == kwargs.get("location_id"):
                    obj["progress"] = 1
                    obj["completed"] = True
                if not obj.get("completed"):
                    all_done = False
            if all_done:
                completed_quests.append(qid)
        rewards_map = {}
        for qid in completed_quests:
            ok, msg, rewards = self.complete(qid)
            if ok:
                rewards_map[qid] = rewards
        return rewards_map

    def complete(self, quest_id):
        """完成任务并发放基础奖励，返回 (success, message, rewards_dict)。"""
        if quest_id not in self.player.active_side_quests:
            return False, "任务未激活。", {}
        quest = self.config.get(quest_id)
        rewards = quest.get("rewards", {})
        # 好感度
        rel = rewards.get("relationship", 0)
        if rel and quest.get("giver_npc_id"):
            self.player.increase_npc_relationship(quest["giver_npc_id"], rel)
        # 宗门贡献
        contrib = rewards.get("sect_contribution", 0)
        if contrib:
            self.player.sect_contribution += contrib
        # 修为奖励（乘境界成长系数，保持相对价值）
        qi_reward = int(rewards.get("qi", 0) * self._realm_qi_scale())
        if qi_reward:
            self.player.qi += qi_reward
        del self.player.active_side_quests[quest_id]
        self.player.completed_side_quests.append(quest_id)
        return True, f"完成支线任务【{quest['name']}】", rewards

    def get_rewards(self, quest_id):
        """获取任务奖励配置（供 engine 发放）。"""
        quest = self.config.get(quest_id)
        return quest.get("rewards", {}) if quest else {}
