# -*- coding: utf-8 -*-
"""洞府租赁与闭关修炼系统。

玩家可在城中租赁洞府，获得修炼加成；支付租金后可在洞府中闭关，
按月获得额外修为，但跳过正常历练事件。
"""
import json
import os


class CaveConfig:
    """加载 caves.json 配置。"""

    def __init__(self, config_dir="config"):
        path = os.path.join(config_dir, "caves.json")
        with open(path, "r", encoding="utf-8") as f:
            self.data = json.load(f)
        self.caves = self.data.get("caves", [])
        self.cave_map = {c["id"]: c for c in self.caves}
        self.closed_door = self.data.get("closed_door", {})

    def get_cave(self, cave_id):
        return self.cave_map.get(cave_id)

    def get_caves_by_location(self, location_id):
        return [c for c in self.caves if c.get("location_id") == location_id]

    def get_closed_door_config(self):
        return self.closed_door


class CaveManager:
    """管理洞府租赁、租期与闭关修炼。"""

    def __init__(self, player, config=None):
        self.player = player
        self.config = config or CaveConfig()
        self._ensure_state()

    def _ensure_state(self):
        """确保玩家数据中存在洞府租赁字段。"""
        if not hasattr(self.player, "cave_leases"):
            self.player.cave_leases = {}
        if not hasattr(self.player, "closed_door_remaining"):
            self.player.closed_door_remaining = 0

    def get_available_caves(self, location_id):
        """获取指定地点可租赁的洞府列表。"""
        return self.config.get_caves_by_location(location_id)

    def get_current_lease(self, cave_id):
        """获取玩家对指定洞府的当前租约，无租约返回 None。"""
        return self.player.cave_leases.get(cave_id)

    def can_rent(self, cave_id, months):
        """判断是否可以租赁指定洞府指定月数。"""
        cave = self.config.get_cave(cave_id)
        if not cave:
            return False, "洞府不存在。"
        if months <= 0:
            return False, "租赁月数必须大于 0。"
        max_months = cave.get("max_lease_months", 12)
        current = self.player.cave_leases.get(cave_id, {}).get("remaining_months", 0)
        if current + months > max_months:
            return False, f"租期不能超过 {max_months} 个月。"
        total_cost = cave.get("rent_per_month", 0) * months
        if self.player.count_item("spirit_stone") < total_cost:
            return False, f"灵石不足，租赁 {months} 个月需要 {total_cost} 灵石。"
        return True, ""

    def rent_cave(self, cave_id, months):
        """
        租赁洞府指定月数。

        返回 (success, message)。
        """
        ok, msg = self.can_rent(cave_id, months)
        if not ok:
            return False, msg

        cave = self.config.get_cave(cave_id)
        total_cost = cave.get("rent_per_month", 0) * months
        self.player.consume_items("spirit_stone", total_cost)

        lease = self.player.cave_leases.get(cave_id)
        if lease is None:
            lease = {"cave_id": cave_id, "remaining_months": 0}
            self.player.cave_leases[cave_id] = lease
        lease["remaining_months"] += months
        return True, (
            f"租赁【{cave['name']}】{months} 个月，花费 {total_cost} 灵石。"
        )

    def can_start_closed_door(self, cave_id, months):
        """判断是否可以在指定洞府开始闭关。"""
        cave = self.config.get_cave(cave_id)
        if not cave:
            return False, "洞府不存在。"
        lease = self.player.cave_leases.get(cave_id)
        if not lease or lease.get("remaining_months", 0) <= 0:
            return False, "你尚未租赁该洞府或租期已到期。"
        if lease["remaining_months"] < months:
            return False, "洞府剩余租期不足，无法闭关这么久。"
        cfg = self.config.get_closed_door_config()
        min_months = cfg.get("min_months", 1)
        max_months = cfg.get("max_months", 12)
        if months < min_months or months > max_months:
            return False, f"闭关月数需在 {min_months}~{max_months} 之间。"
        if self.player.closed_door_remaining > 0:
            return False, "你已在闭关中。"
        return True, ""

    def start_closed_door(self, cave_id, months):
        """
        在指定洞府开始闭关修炼。

        返回 (success, message, expected_qi_gain)。
        """
        ok, msg = self.can_start_closed_door(cave_id, months)
        if not ok:
            return False, msg, 0

        cave = self.config.get_cave(cave_id)
        # 计算预期修为收益（简化：每月基础收益 × 洞府加成 × 闭关月数加成）
        base_qi_per_month = getattr(self.player, "base_qi_per_month", 50)
        cave_bonus = cave.get("effects", {}).get("closed_door_qi_bonus", 0)
        cfg = self.config.get_closed_door_config()
        month_mult = cfg.get("qi_multiplier_base", 1.0) + (
            months - 1
        ) * cfg.get("qi_multiplier_per_month", 0.05)
        expected_qi = int(base_qi_per_month * (1 + cave_bonus) * month_mult * months)

        self.player.closed_door_remaining = months
        self.player.closed_door_cave_id = cave_id
        return True, (
            f"开始在【{cave['name']}】闭关 {months} 个月，"
            f"预计获得修为 {expected_qi} 点。"
        ), expected_qi

    def tick_closed_door(self):
        """
        推进闭关一个月，返回本月获得的修为；未闭关返回 0。
        """
        if self.player.closed_door_remaining <= 0:
            return 0

        cave_id = getattr(self.player, "closed_door_cave_id", None)
        cave = self.config.get_cave(cave_id) if cave_id else None
        cave_bonus = cave.get("effects", {}).get("closed_door_qi_bonus", 0) if cave else 0
        base_qi_per_month = getattr(self.player, "base_qi_per_month", 50)
        # 闭关月数越深，收益越高（按剩余月数动态计算）
        months = self.player.closed_door_remaining
        cfg = self.config.get_closed_door_config()
        month_mult = cfg.get("qi_multiplier_base", 1.0) + (
            months - 1
        ) * cfg.get("qi_multiplier_per_month", 0.05)
        qi_gain = int(base_qi_per_month * (1 + cave_bonus) * month_mult)

        self.player.qi += qi_gain
        self.player.closed_door_remaining -= 1

        # 闭关期间同时消耗洞府租期
        if cave_id and cave_id in self.player.cave_leases:
            lease = self.player.cave_leases[cave_id]
            lease["remaining_months"] = max(0, lease["remaining_months"] - 1)

        return qi_gain

    def is_in_closed_door(self):
        """判断玩家是否处于闭关中。"""
        return getattr(self.player, "closed_door_remaining", 0) > 0

    def tick_monthly(self):
        """
        每月推进：减少所有洞府租期，返回到期洞府名称列表。
        注意：闭关期间的租期消耗在 tick_closed_door 中处理，
        此处不再重复扣除。
        """
        expired = []
        to_remove = []
        for cave_id, lease in list(self.player.cave_leases.items()):
            if self.is_in_closed_door() and cave_id == getattr(
                self.player, "closed_door_cave_id", None
            ):
                # 闭关期间租期已在 tick_closed_door 中扣除
                if lease["remaining_months"] <= 0:
                    cave = self.config.get_cave(cave_id)
                    expired.append(cave["name"] if cave else cave_id)
                    to_remove.append(cave_id)
                continue
            lease["remaining_months"] -= 1
            if lease["remaining_months"] <= 0:
                cave = self.config.get_cave(cave_id)
                expired.append(cave["name"] if cave else cave_id)
                to_remove.append(cave_id)
        for cave_id in to_remove:
            self.player.cave_leases.pop(cave_id, None)
        # 如果闭关结束，清理状态
        if self.player.closed_door_remaining <= 0:
            self.player.closed_door_cave_id = None
        return expired

    def get_cultivation_bonus(self):
        """获取当前租赁洞府提供的修炼速度加成总和。"""
        total = 0.0
        for cave_id, lease in self.player.cave_leases.items():
            if lease.get("remaining_months", 0) <= 0:
                continue
            cave = self.config.get_cave(cave_id)
            if cave:
                bonus = cave.get("effects", {}).get("cultivation_speed_bonus", 0)
                if isinstance(bonus, (int, float)):
                    total += bonus
        return total
