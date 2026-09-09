# -*- coding: utf-8 -*-
"""城池政策与城主竞选系统。

玩家可在满足条件的城池参与城主竞选，竞选成功后可在任期内
颁布城池政策，获得各类增益效果。
"""
import json
import os


class CityPolicyConfig:
    """加载 city_policies.json 配置。"""

    def __init__(self, config_dir="config"):
        path = os.path.join(config_dir, "city_policies.json")
        with open(path, "r", encoding="utf-8") as f:
            self.data = json.load(f)
        self.policies = self.data.get("policies", [])
        self.policy_map = {p["id"]: p for p in self.policies}
        self.election = self.data.get("election", {})

    def get_policy(self, policy_id):
        return self.policy_map.get(policy_id)

    def get_policies(self):
        return self.policies

    def get_election_config(self):
        return self.election


class CityPolicyManager:
    """管理单座城池的政策与城主状态。"""

    def __init__(self, player, city_id, config=None):
        self.player = player
        self.city_id = city_id
        self.config = config or CityPolicyConfig()
        self._ensure_state()

    def _ensure_state(self):
        """确保玩家数据中存在城池政策字段。"""
        if not hasattr(self.player, "city_policies"):
            self.player.city_policies = {}
        if self.city_id not in self.player.city_policies:
            self.player.city_policies[self.city_id] = {
                "active": [],          # 生效中的政策列表
                "mayor_until": 0,      # 城主任期结束的世界月份（0 表示非城主）
                "last_campaign_month": 0,  # 上次参选世界月份
            }

    def _city_state(self):
        return self.player.city_policies[self.city_id]

    def _current_world_month(self):
        """从玩家或世界对象获取当前世界月份；无世界对象时返回 0。"""
        world = getattr(self.player, "world", None)
        if world:
            return world.year * 12 + world.month
        return getattr(self.player, "world_month", 0)

    def is_mayor(self):
        """判断玩家当前是否为本城城主。"""
        return self._current_world_month() < self._city_state()["mayor_until"]

    def get_mayor_until_month(self):
        """返回城主任期结束的世界月份。"""
        return self._city_state()["mayor_until"]

    def can_campaign(self):
        """判断玩家当前是否可以参与城主竞选。"""
        current = self._current_world_month()
        state = self._city_state()
        cfg = self.config.get_election_config()
        cooldown = cfg.get("reelection_cooldown_months", 0)
        if current - state.get("last_campaign_month", 0) < cooldown:
            return False, "竞选冷却中。"
        if self.is_mayor():
            return False, "你当前仍在任期内。"
        rep = self.player.city_reputation.get(self.city_id, 0)
        min_rep = cfg.get("min_reputation", 0)
        if rep < min_rep:
            return False, f"城池声望不足，需要 {min_rep} 点。"
        stones = self.player.count_item("spirit_stone")
        cost_stone = cfg.get("campaign_cost_spirit_stone", 0)
        if stones < cost_stone:
            return False, f"灵石不足，竞选需要 {cost_stone} 灵石。"
        cost_rep = cfg.get("campaign_cost_reputation", 0)
        if rep < cost_rep:
            return False, f"城池声望不足，竞选需要 {cost_rep} 点。"
        return True, ""

    def campaign(self):
        """
        参与城主竞选。

        扣除资源后根据声望与机缘判定是否当选。
        返回 (success, message)。
        """
        ok, msg = self.can_campaign()
        if not ok:
            return False, msg

        cfg = self.config.get_election_config()
        cost_stone = cfg.get("campaign_cost_spirit_stone", 0)
        cost_rep = cfg.get("campaign_cost_reputation", 0)
        term = cfg.get("term_months", 24)

        # 扣除竞选费用
        self.player.consume_items("spirit_stone", cost_stone)
        self.player.city_reputation[self.city_id] = (
            self.player.city_reputation.get(self.city_id, 0) - cost_rep
        )

        state = self._city_state()
        state["last_campaign_month"] = self._current_world_month()

        # 竞选成功率：基础 40% + 声望/1000 + 机缘/20
        import random
        rep = self.player.city_reputation.get(self.city_id, 0)
        luck = getattr(self.player, "luck", 5)
        chance = 0.4 + min(0.4, rep / 1000.0) + min(0.2, luck / 100.0)
        if random.random() < chance:
            state["mayor_until"] = self._current_world_month() + term
            return True, f"竞选成功！你成为本城城主，任期 {term} 个月。"
        return False, "竞选失败，民心未向你倾斜。"

    def get_active_policies(self):
        """获取当前生效中的政策列表（含剩余月数）。"""
        return list(self._city_state()["active"])

    def can_enact_policy(self, policy_id):
        """判断是否可以颁布指定政策。"""
        if not self.is_mayor():
            return False, "只有城主可以颁布政策。"
        policy = self.config.get_policy(policy_id)
        if not policy:
            return False, "政策不存在。"
        state = self._city_state()
        cfg = self.config.get_election_config()
        max_active = cfg.get("max_active_policies", 3)
        if len(state["active"]) >= max_active:
            return False, f"同时生效的政策不能超过 {max_active} 个。"
        # 检查是否已激活同 ID 政策
        if any(p["id"] == policy_id for p in state["active"]):
            return False, "该政策已生效。"
        # 检查费用
        cost = policy.get("cost", {})
        stones = self.player.count_item("spirit_stone")
        need_stone = cost.get("spirit_stone", 0)
        if stones < need_stone:
            return False, f"灵石不足，需要 {need_stone} 灵石。"
        need_rep = cost.get("reputation", 0)
        rep = self.player.city_reputation.get(self.city_id, 0)
        if rep < need_rep:
            return False, f"城池声望不足，需要 {need_rep} 点。"
        return True, ""

    def enact_policy(self, policy_id):
        """
        颁布政策，扣除费用并加入生效列表。

        返回 (success, message)。
        """
        ok, msg = self.can_enact_policy(policy_id)
        if not ok:
            return False, msg

        policy = self.config.get_policy(policy_id)
        cost = policy.get("cost", {})
        need_stone = cost.get("spirit_stone", 0)
        need_rep = cost.get("reputation", 0)

        if need_stone > 0:
            self.player.consume_items("spirit_stone", need_stone)
        if need_rep > 0:
            self.player.city_reputation[self.city_id] = (
                self.player.city_reputation.get(self.city_id, 0) - need_rep
            )

        state = self._city_state()
        state["active"].append({
            "id": policy_id,
            "remaining_months": policy.get("duration_months", 1),
        })
        return True, f"颁布政策【{policy['name']}】，持续 {policy.get('duration_months', 1)} 个月。"

    def get_policy_effect(self, effect_key):
        """累加当前生效政策对指定效果 key 的加成。"""
        total = 0.0
        state = self._city_state()
        for entry in state["active"]:
            policy = self.config.get_policy(entry["id"])
            if not policy:
                continue
            effects = policy.get("effects", {})
            if effect_key in effects:
                value = effects[effect_key]
                if isinstance(value, (int, float)):
                    total += value
        return total

    def tick_monthly(self):
        """
        每月推进：减少政策剩余月数，到期自动移除。

        返回到期政策名称列表。
        """
        expired_names = []
        state = self._city_state()
        new_active = []
        for entry in state["active"]:
            entry["remaining_months"] -= 1
            if entry["remaining_months"] <= 0:
                policy = self.config.get_policy(entry["id"])
                if policy:
                    expired_names.append(policy["name"])
            else:
                new_active.append(entry)
        state["active"] = new_active
        return expired_names

    def get_active_policy_descriptions(self):
        """返回用于 UI 展示的生效政策信息列表。"""
        result = []
        for entry in self._city_state()["active"]:
            policy = self.config.get_policy(entry["id"])
            if policy:
                result.append({
                    "id": entry["id"],
                    "name": policy["name"],
                    "description": policy["description"],
                    "remaining_months": entry["remaining_months"],
                })
        return result
