# -*- coding: utf-8 -*-
"""旅行成本模型：统一计算赶路时间、加速方式与消耗。"""

import math


class TravelCostModel:
    """负责把玩家从一个地点移动到另一个地点所需的成本计算。

    输入：出发地、目的地、玩家状态（境界、技能、灵兽、灵石）。
    输出：耗时（月）、消耗（灵石）、提示信息列表。
    """

    # 练气一层基础速度：每月 80 单位
    BASE_SPEED = 80.0
    # 每高一个境界，移动速度 +8%
    REALM_MULTIPLIER_STEP = 0.08
    # 地点类型对赶路速度的影响
    TYPE_FACTOR = {"sect": 0.75, "city": 0.85, "wild": 1.0}
    # 疾风步等技能减免比例
    SKILL_REDUCTION = 0.30
    # 每 10 块灵石可减少 1 个月赶路时间
    STONES_PER_MONTH = 10

    def __init__(self, player, world, sect_manager):
        """初始化旅行成本模型。

        Args:
            player: Player 实例。
            world: World 实例。
            sect_manager: SectManager 实例，用于查询坐骑型灵兽加成。
        """
        self.player = player
        self.world = world
        self.sect_manager = sect_manager

    def can_flight(self):
        """玩家是否已解锁御剑飞行（筑基后）。"""
        return self.player.has_feature("flight")

    def has_mount(self):
        """玩家是否拥有可全额免除赶路时间的坐骑型灵兽。"""
        return self.sect_manager.get_beast_mount_bonus() > 0

    def get_skill_reduction(self):
        """获取当前可提供的技能旅行减免比例。"""
        if "gale_step" in self.player.skills:
            return self.SKILL_REDUCTION
        return 0.0

    def calculate_base_time(self, to_location_id, from_location_id=None):
        """计算未应用任何加速方式的基础赶路月数。"""
        if from_location_id is None:
            from_location_id = self.player.location_id

        from_loc = self.world.get_location(from_location_id)
        to_loc = self.world.get_location(to_location_id)
        if not from_loc or not to_loc:
            return 1

        dx = from_loc.get("x", 0) - to_loc.get("x", 0)
        dy = from_loc.get("y", 0) - to_loc.get("y", 0)
        distance = math.sqrt(dx * dx + dy * dy)

        realm = self.world.get_realm(self.player.realm_id)
        order = realm.get("order", 1) if realm else 1
        realm_multiplier = 1.0 + (order - 1) * self.REALM_MULTIPLIER_STEP

        loc_type = to_loc.get("type", "wild")
        type_factor = self.TYPE_FACTOR.get(loc_type, 1.0)

        # 旅行难度系数优先读取配置，未配置时使用基于推荐境界的默认值
        difficulty_factor = to_loc.get("travel_difficulty")
        if difficulty_factor is None:
            rec_realm = self.world.get_realm(to_loc.get("recommended_realm", "qi_refining_1"))
            rec_order = rec_realm.get("order", 1) if rec_realm else 1
            difficulty_factor = 1.0 + (rec_order - 1) * 0.04
            beast_weight = to_loc.get("event_weights", {}).get("beast_attack", 20)
            if beast_weight >= 30:
                difficulty_factor += 0.15
            elif beast_weight <= 10:
                difficulty_factor -= 0.1

        effective_speed = (
            self.BASE_SPEED * realm_multiplier / (type_factor * difficulty_factor)
        )
        months = max(1, int(math.ceil(distance / effective_speed)))
        return months

    def apply_speedups(self, months, use_spirit_stones=0):
        """对基础耗时应用技能减免与灵石加速。

        Returns:
            tuple: (actual_months, consumed_stones, messages)
        """
        messages = []
        consumed_stones = 0

        # 技能减免
        reduction = self.get_skill_reduction()
        if reduction > 0 and months > 1:
            months = max(1, int(months * (1 - reduction)))
            messages.append("你施展身法，赶路时间大幅缩短。")

        # 灵石加速
        if use_spirit_stones > 0 and months > 1:
            available = self.player.count_item("spirit_stone")
            max_useful = (months - 1) * self.STONES_PER_MONTH
            consume = min(use_spirit_stones, available, max_useful)
            if consume > 0:
                self.player.consume_items("spirit_stone", consume)
                months = max(1, months - consume // self.STONES_PER_MONTH)
                consumed_stones = consume
                messages.append(f"你耗费 {consume} 块灵石加速赶路。")

        return months, consumed_stones, messages

    def get_cost_preview(self, to_location_id, from_location_id=None, use_spirit_stones=0):
        """获取旅行预览信息（用于 UI 提示）。

        Returns:
            dict: {
                "can_flight": bool,
                "has_mount": bool,
                "base_months": int,
                "actual_months": int,
                "consumed_stones": int,
                "free": bool,
            }
        """
        if self.can_flight() or self.has_mount():
            return {
                "can_flight": self.can_flight(),
                "has_mount": self.has_mount(),
                "base_months": 0,
                "actual_months": 0,
                "consumed_stones": 0,
                "free": True,
            }

        base_months = self.calculate_base_time(to_location_id, from_location_id)
        actual_months, consumed_stones, _ = self.apply_speedups(
            base_months, use_spirit_stones=use_spirit_stones
        )
        return {
            "can_flight": False,
            "has_mount": False,
            "base_months": base_months,
            "actual_months": actual_months,
            "consumed_stones": consumed_stones,
            "free": False,
        }
