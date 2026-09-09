# -*- coding: utf-8 -*-
"""个人灵兽养殖系统。"""
import random


class PersonalBeastManager:
    """管理玩家个人驯养的灵兽：成长、忠诚、产出。"""

    def __init__(self, player, item_library):
        self.player = player
        self.item_library = item_library
        if not hasattr(player, "personal_beasts"):
            player.personal_beasts = []

    def capture(self, enemy_id, name, beast_type="combat"):
        """捕捉一只灵兽。"""
        beast = {
            "enemy_id": enemy_id,
            "name": name,
            "growth": 0,
            "loyalty": 30,
            "type": beast_type,  # combat / mount / resource
            "dispatch": None,    # 派遣状态：None 或 {"return_month": m, "return_day": d, "reward_preview": {...}}
        }
        self.player.personal_beasts.append(beast)
        return True, f"收服灵兽【{name}】。"

    def feed(self, index, food_item_id="spirit_herb"):
        """喂养灵兽，提升忠诚度。"""
        if index < 0 or index >= len(self.player.personal_beasts):
            return False, "灵兽不存在。"
        beast = self.player.personal_beasts[index]
        # 默认用灵草喂养，也可消耗灵石购买饲料
        cost = 1
        if self.player.count_item(food_item_id) < cost:
            item_name = self.item_library.get(food_item_id).name if self.item_library.get(food_item_id) else food_item_id
            return False, f"缺少喂养材料：{item_name}。"
        self.player.consume_items(food_item_id, cost)
        # 忠诚度越高提升越慢
        gain = max(1, 10 - beast["loyalty"] // 20)
        old = beast["loyalty"]
        beast["loyalty"] = min(100, beast["loyalty"] + gain)
        return True, f"喂养【{beast['name']}】，忠诚度 {old} → {beast['loyalty']}。"

    def train(self, index):
        """训练灵兽，消耗时间提升成长值。"""
        if index < 0 or index >= len(self.player.personal_beasts):
            return False, "灵兽不存在。"
        beast = self.player.personal_beasts[index]
        if beast["loyalty"] < 20:
            return False, f"【{beast['name']}】忠诚度太低，无法训练。"
        gain = 2 if beast["loyalty"] >= 80 else 1
        beast["growth"] += gain
        return True, f"训练【{beast['name']}】，成长 +{gain}（当前 {beast['growth']}）。"

    def dispatch(self, index, world, months=1):
        """派遣灵兽外出历练，经过指定月数后带回奖励。"""
        if index < 0 or index >= len(self.player.personal_beasts):
            return False, "灵兽不存在。"
        beast = self.player.personal_beasts[index]
        if beast.get("dispatch"):
            return False, f"【{beast['name']}】已在历练途中。"
        if beast["loyalty"] < 30:
            return False, f"【{beast['name']}】忠诚度不足，不愿远行。"

        # 计算回归日期
        return_month = world.month + months
        return_year = world.year
        return_day = world.day
        while return_month > 12:
            return_month -= 12
            return_year += 1

        # 根据灵兽类型与成长预生成奖励
        rewards = {"spirit_stone": months * (1 + beast["growth"] // 10)}
        if beast["type"] == "resource":
            rewards["spirit_stone"] += months
        if random.random() < 0.3:
            rewards["demon_core"] = 1

        beast["dispatch"] = {
            "return_year": return_year,
            "return_month": return_month,
            "return_day": return_day,
            "rewards": rewards,
        }
        return True, f"派遣【{beast['name']}】外出历练，预计 {return_year}年{return_month}月{return_day}日 归来。"

    def check_dispatch_return(self, world):
        """检查是否有灵兽历练归来，返回 (是否归来, 日志列表)。"""
        logs = []
        returned = False
        for beast in self.player.personal_beasts:
            dispatch = beast.get("dispatch")
            if not dispatch:
                continue
            # 比较当前日期是否达到或超过回归日期
            cur = (world.year, world.month, world.day)
            ret = (dispatch["return_year"], dispatch["return_month"], dispatch["return_day"])
            if cur >= ret:
                returned = True
                beast["dispatch"] = None
                # 发放奖励
                rewards = dispatch["rewards"]
                reward_texts = []
                for item_id, count in rewards.items():
                    for _ in range(count):
                        item = self.item_library.create(item_id)
                        if item:
                            self.player.add_item(item)
                    item_name = self.item_library.get(item_id).name if self.item_library.get(item_id) else item_id
                    reward_texts.append(f"{item_name} x{count}")
                logs.append(
                    f"灵兽【{beast['name']}】历练归来，带回：{', '.join(reward_texts)}。"
                )
        return returned, logs

    def tick_monthly(self):
        """每月推进灵兽成长与产出。"""
        logs = []
        for beast in self.player.personal_beasts:
            # 忠诚度影响成长
            growth_rate = 1 if beast["loyalty"] >= 50 else 0
            if growth_rate:
                beast["growth"] += growth_rate
            # 资源型灵兽产出
            if beast["type"] == "resource" and beast["growth"] >= 6 and random.random() < 0.3:
                item = self.item_library.create("spirit_stone")
                if item:
                    self.player.add_item(item)
                    logs.append(f"灵兽【{beast['name']}】产出【{item.name}】。")
        return logs

    def get_combat_bonus(self):
        """战斗型灵兽提供固定攻击加成。"""
        bonus = 0
        for beast in self.player.personal_beasts:
            if beast["type"] == "combat":
                bonus += 2 + beast["growth"] // 10
        return bonus
