# -*- coding: utf-8 -*-
"""
转世轮回与多周目继承管理器。

负责：
- 根据前世状态计算继承点与业力影响
- 生成可选择的继承项列表
- 应用玩家选择的继承，生成新一世初始数据
"""
import json
import os
import random

from game.lifespan_manager import compute_relic_chain_bonus


class ReincarnationConfig:
    """加载转世规则配置。"""

    def __init__(self, config_dir="config"):
        path = os.path.join(config_dir, "reincarnation.json")
        with open(path, "r", encoding="utf-8") as f:
            self.data = json.load(f)

    def get_rules(self):
        """获取转世规则。"""
        return self.data.get("inheritance_rules", {})

    def get_options(self):
        """获取所有继承选项。"""
        return self.data.get("inheritance_options", [])

    def get_option(self, option_id):
        """根据 ID 获取继承选项。"""
        for opt in self.get_options():
            if opt.get("id") == option_id:
                return opt
        return None

    def get_random_talents(self):
        """获取随机天赋池。"""
        return self.data.get("random_talents", [])

    def get_negative_events(self):
        """获取负面转世事件池。"""
        return self.data.get("negative_reincarnation_events", [])


class ReincarnationManager:
    """管理转世结算、继承选择与新世数据生成。"""

    def __init__(self, player, config=None):
        self.player = player
        self.config = config or ReincarnationConfig()

    def _get_realm_score(self):
        """
        根据前世境界计算分数。

        使用 Player.REALM_ORDER 作为境界顺序。
        """
        order = getattr(self.player, "REALM_ORDER", {})
        return order.get(self.player.realm_id, 1)

    def _get_fame_score(self):
        """根据名望/成就计算分数（当前用成就数与声望简单估算）。"""
        achievements = len(getattr(self.player, "achievements", []))
        reputation_total = sum(
            getattr(self.player, "reputation", {}).values()
        )
        city_rep_total = sum(
            getattr(self.player, "city_reputation", {}).values()
        )
        return achievements * 5 + reputation_total + city_rep_total

    def _karma_category(self):
        """根据业力值返回业力等级。"""
        karma = getattr(self.player, "karma", 0)
        thresholds = self.config.get_rules().get("karma_thresholds", {})
        if karma <= thresholds.get("benevolent", -50):
            return "benevolent"
        if karma >= thresholds.get("evil", 200):
            return "evil"
        return "neutral"

    def compute_inheritance_points(self):
        """
        计算本次转世可用的继承点。

        公式：境界分 × 倍率 + 转世次数 × 每次加成 + 名望分 × 倍率 + 业力修正。
        """
        rules = self.config.get_rules().get("base_points_formula", {})
        base = (
            self._get_realm_score() * rules.get("realm_score_multiplier", 0.5)
            + getattr(self.player, "reincarnation_count", 0)
            * rules.get("per_reincarnation_bonus", 2)
            + self._get_fame_score() * rules.get("fame_score_multiplier", 0.1)
        )
        karma_effect = (
            self.config.get_rules()
            .get("karma_effects", {})
            .get(self._karma_category(), {})
        )
        return max(0, int(base + karma_effect.get("bonus_points", 0)))

    def compute_available_options(self):
        """
        生成本次转世可选择的继承项列表。

        过滤不可重复选择超过上限的选项，并标注业力影响。
        """
        points = self.compute_inheritance_points()
        options = self.config.get_options()
        selected_count = getattr(self.player, "selected_inheritance_count", {})
        result = []
        for opt in options:
            opt_id = opt["id"]
            times = selected_count.get(opt_id, 0)
            max_times = opt.get("max_times_per_life", 1)
            available = times < max_times
            result.append(
                {
                    "id": opt_id,
                    "name": opt["name"],
                    "description": opt["description"],
                    "cost": opt["cost"],
                    "category": opt.get("category", "other"),
                    "effects": opt.get("effects", {}),
                    "available": available,
                    "remaining_times": max_times - times,
                }
            )
        return {
            "points": points,
            "karma_category": self._karma_category(),
            "karma": getattr(self.player, "karma", 0),
            "options": result,
        }

    def _pick_random_talent(self):
        """从随机天赋池中抽取一个天赋。"""
        talents = self.config.get_random_talents()
        if not talents:
            return None
        return random.choice(talents)

    def _pick_negative_event(self):
        """业力过高时抽取一个负面转世事件。"""
        events = self.config.get_negative_events()
        if not events:
            return None
        weights = [e.get("weight", 1) for e in events]
        return random.choices(events, weights=weights, k=1)[0]

    def apply_inheritance(self, selected_option_ids):
        """
        根据玩家选择的继承项，生成新一世的初始数据。

        返回新 Player 的初始化参数字典，供外部创建新存档使用。
        """
        available = self.compute_available_options()
        points = available["points"]
        total_cost = 0
        selected_options = []
        for opt_id in selected_option_ids:
            opt = self.config.get_option(opt_id)
            if not opt:
                continue
            total_cost += opt.get("cost", 0)
            selected_options.append(opt)

        # 如果超出点数，按顺序截断（理论上 UI 应限制）
        if total_cost > points:
            selected_options = []
            total_cost = 0
            for opt_id in selected_option_ids:
                opt = self.config.get_option(opt_id)
                cost = opt.get("cost", 0)
                if total_cost + cost > points:
                    break
                selected_options.append(opt)
                total_cost += cost

        # 构建新世初始数据
        new_data = {
            "name": self.player.name,
            "reincarnation_count": getattr(self.player, "reincarnation_count", 0) + 1,
            "karma": getattr(self.player, "karma", 0),
            "past_life_talents": list(getattr(self.player, "past_life_talents", [])),
            "new_talents": [],
            "attribute_bonuses": {"wisdom": 0, "luck": 0, "constitution": 0},
            "starting_items": [],
            "relationship_bonuses": {},
            "retain_roots": False,
            "root_purity_decay": 0,
            "negative_event": None,
            "relic_chain": list(getattr(self.player, "relic_chain", []) or []),
            "relic_chain_bonuses": compute_relic_chain_bonus(
                getattr(self.player, "relic_chain", []) or []
            ),
        }

        # 应用业力影响
        karma_effect = (
            self.config.get_rules()
            .get("karma_effects", {})
            .get(self._karma_category(), {})
        )
        if karma_effect.get("extra_talent_chance", 0) > random.random():
            talent = self._pick_random_talent()
            if talent:
                new_data["new_talents"].append(talent["id"])
                new_data["past_life_talents"].append(talent["id"])

        if self._karma_category() == "evil":
            new_data["attribute_bonuses"]["luck"] += karma_effect.get(
                "starting_luck_bonus", 0
            )
            if karma_effect.get("random_debuff_chance", 0) > random.random():
                new_data["negative_event"] = self._pick_negative_event()
        else:
            new_data["attribute_bonuses"]["luck"] += karma_effect.get(
                "starting_luck_bonus", 0
            )

        # 应用玩家选择的继承项
        for opt in selected_options:
            effects = opt.get("effects", {})
            category = opt.get("category", "other")
            if category == "talent" and effects.get("retain_roots"):
                new_data["retain_roots"] = True
                new_data["root_purity_decay"] = effects.get("purity_decay", 0)
            elif category == "talent" and effects.get("grant_random_talent"):
                talent = self._pick_random_talent()
                if talent:
                    new_data["new_talents"].append(talent["id"])
                    new_data["past_life_talents"].append(talent["id"])
            elif category == "attribute":
                for key in ["wisdom", "luck", "constitution"]:
                    bonus = effects.get(f"{key}_bonus", 0)
                    new_data["attribute_bonuses"][key] += bonus
            elif category == "item":
                # 默认携带价值最高的装备或物品（外部可覆盖）
                carry_count = effects.get("carry_item_count", 1)
                new_data["starting_items"] = self._select_carry_items(carry_count)
            elif category == "relationship":
                # 默认保留好感度最高的 NPC（外部可覆盖）
                count = effects.get("relationship_npc_count", 1)
                bonus = effects.get("intimacy_bonus", 0)
                new_data["relationship_bonuses"] = self._select_relationship_bonuses(
                    count, bonus
                )
            elif category == "karma":
                new_data["karma"] -= effects.get("karma_reduction", 0)

        return new_data

    def _select_carry_items(self, count):
        """选择价值最高的若干物品用于转世携带。"""
        items = getattr(self.player, "inventory", []) + [
            item for item in getattr(self.player, "equipment", {}).values() if item
        ]
        # 按价值排序，取前 count 个
        sorted_items = sorted(
            items, key=lambda x: getattr(x, "value", 0), reverse=True
        )
        return [
            {"item_id": item.id, "name": item.name}
            for item in sorted_items[:count]
        ]

    def _select_relationship_bonuses(self, count, bonus):
        """选择好感度最高的若干 NPC 保留关系。"""
        relationships = getattr(self.player, "npc_relationships", {})
        sorted_relationships = sorted(
            relationships.items(), key=lambda x: x[1], reverse=True
        )
        return {
            npc_id: bonus for npc_id, _ in sorted_relationships[:count]
        }

    def create_new_player(self, new_data, player_class):
        """
        根据继承数据创建新一世 Player。

        player_class 为 Player 类，用于实例化。
        """
        new_player = player_class(name=new_data["name"])
        new_player.reincarnation_count = new_data["reincarnation_count"]
        new_player.karma = new_data["karma"]
        new_player.past_life_talents = list(new_data["past_life_talents"])

        # 应用属性加成
        new_player.wisdom += new_data["attribute_bonuses"].get("wisdom", 0)
        new_player.luck += new_data["attribute_bonuses"].get("luck", 0)
        new_player.constitution += new_data["attribute_bonuses"].get(
            "constitution", 0
        )

        # 应用天赋效果（简单处理为属性修正，实际可由天赋管理器解析）
        for talent_id in new_data["new_talents"]:
            if talent_id == "talent_fast_cultivator":
                # 修炼速度加成可后续接入修炼系统
                new_player.reincarnation_cultivation_bonus = (
                    getattr(new_player, "reincarnation_cultivation_bonus", 0) + 0.1
                )
            elif talent_id == "talent_spirit_affinity":
                new_player.reincarnation_breakthrough_bonus = (
                    getattr(new_player, "reincarnation_breakthrough_bonus", 0) + 0.05
                )

        # 应用前世遗物链加成（跨世累积，转世保留 relic_chain 集合）
        chain_ids = new_data.get("relic_chain", []) or []
        new_player.relic_chain = list(chain_ids)
        chain_bonus = new_data.get("relic_chain_bonuses", {}) or {}
        new_player.wisdom += chain_bonus.get("wisdom", 0)
        new_player.luck += chain_bonus.get("luck", 0)
        new_player.constitution += chain_bonus.get("constitution", 0)
        mh = chain_bonus.get("max_health", 0)
        if mh:
            new_player.max_health += mh
            new_player.health = new_player.max_health
        new_player.reincarnation_cultivation_bonus = (
            getattr(new_player, "reincarnation_cultivation_bonus", 0)
            + chain_bonus.get("cultivation_speed", 0.0)
        )
        new_player.reincarnation_breakthrough_bonus = (
            getattr(new_player, "reincarnation_breakthrough_bonus", 0)
            + chain_bonus.get("breakthrough_bonus", 0.0)
        )

        # 保留灵根
        if new_data["retain_roots"]:
            decay = new_data["root_purity_decay"]
            old_roots = getattr(self.player, "spiritual_roots", ["fire"])
            old_purities = getattr(self.player, "root_purities", {})
            new_purities = {
                r: max(0.3, p - decay)
                for r, p in old_purities.items()
                if r in old_roots
            }
            new_player.set_spiritual_roots(old_roots, new_purities)

        # 应用负面事件
        if new_data["negative_event"]:
            event = new_data["negative_event"]
            effects = event.get("effects", {})
            if "max_health_penalty" in effects:
                new_player.max_health -= effects["max_health_penalty"]
                new_player.health = new_player.max_health
            if effects.get("starting_spirit_stone") == 0:
                new_player.inventory = [
                    item for item in new_player.inventory
                    if getattr(item, "id", None) != "spirit_stone"
                ]
            if "root_purity_reduction" in effects:
                reduction = effects["root_purity_reduction"]
                purities = getattr(new_player, "root_purities", {})
                new_purities = {
                    r: max(0.1, p * (1 - reduction))
                    for r, p in purities.items()
                }
                new_player.set_spiritual_roots(
                    getattr(new_player, "spiritual_roots", ["fire"]),
                    new_purities,
                )

        return new_player
