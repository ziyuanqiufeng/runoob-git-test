# -*- coding: utf-8 -*-
"""战斗扩展系统：BUFF/DEBUFF、连携、地形、统计。"""
import random


class CombatBuff:
    """战斗中的 BUFF/DEBUFF。"""

    def __init__(self, buff_id, name, turns, effects):
        self.buff_id = buff_id
        self.name = name
        self.turns = turns
        self.effects = effects  # {"attack_mult": 0.2, "dot": 5, ...}


class CombatExtensionManager:
    """管理战斗中额外的状态、连携和统计。"""

    # 地形对元素伤害的加成
    TERRAIN_BONUSES = {
        "volcano": {"fire": 0.2, "water": -0.1},
        "lake": {"water": 0.2, "fire": -0.1},
        "forest": {"wood": 0.2, "metal": -0.1},
        "mine": {"metal": 0.2, "wood": -0.1},
        "plains": {"earth": 0.1},
        "thunder_cloud": {"metal": 0.15},
    }

    # 简单连携：前置技能 -> 触发奖励
    COMBO_SKILLS = {
        "fireball": {"next": "flame_burst", "bonus": 0.3},
        "ice_blade": {"next": "water_shield", "bonus": 0.2},
    }

    def __init__(self, player, world):
        self.player = player
        self.world = world
        self.buffs = []  # 当前战斗中的 buff 列表
        self.last_skill_id = None
        self.last_damage = 0

    def get_terrain(self):
        """根据玩家所在地点获取地形。"""
        location = self.world.get_location(self.player.location_id)
        return location.get("terrain", "plains") if location else "plains"

    def get_terrain_element_bonus(self, element):
        terrain = self.get_terrain()
        bonuses = self.TERRAIN_BONUSES.get(terrain, {})
        return bonuses.get(element, 0.0)

    def get_terrain_name(self):
        names = {
            "volcano": "火山", "lake": "湖泊", "forest": "森林",
            "mine": "矿脉", "plains": "平原", "thunder_cloud": "雷云"
        }
        return names.get(self.get_terrain(), "平原")

    def apply_buff(self, buff_id, name, turns, effects):
        self.buffs.append(CombatBuff(buff_id, name, turns, effects))

    def tick_buffs(self):
        """每回合推进 buff 持续时间。"""
        for buff in self.buffs:
            buff.turns -= 1
            # 处理 dot
            if "dot" in buff.effects and buff.turns >= 0:
                self.player.health -= buff.effects["dot"]
        self.buffs = [b for b in self.buffs if b.turns > 0]

    def get_buff_effects(self):
        """汇总当前生效的 buff 效果。"""
        merged = {}
        for buff in self.buffs:
            for key, value in buff.effects.items():
                if key in ("dot",):
                    continue
                merged[key] = merged.get(key, 0) + value
        return merged

    def check_combo(self, skill_id):
        """检查是否触发连携，返回加成倍率。"""
        if not self.last_skill_id:
            return 0.0
        combo = self.COMBO_SKILLS.get(self.last_skill_id)
        if combo and combo["next"] == skill_id:
            return combo["bonus"]
        return 0.0

    def record_skill_used(self, skill_id):
        self.last_skill_id = skill_id

    def record_damage(self, damage, is_player=True):
        """记录伤害统计。"""
        if is_player:
            self.player.combat_stats["total_damage_dealt"] += damage
            self.player.combat_stats["highest_damage"] = max(
                self.player.combat_stats["highest_damage"], damage
            )
        else:
            self.player.combat_stats["total_damage_taken"] += damage

    def start_battle(self):
        """每场战斗开始时重置临时状态并统计参战次数。"""
        self.buffs = []
        self.last_skill_id = None
        self.last_damage = 0
        self.player.combat_stats["total_battles"] += 1

    def end_battle(self, won):
        if won:
            self.player.combat_stats["wins"] += 1
        else:
            self.player.combat_stats["losses"] += 1

    def get_battle_report(self):
        return dict(self.player.combat_stats)
