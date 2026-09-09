# -*- coding: utf-8 -*-
"""洞府系统。

玩家可购买、升级洞府及其中建筑，每月获得资源产出，同时可能遭遇袭击。
本模块同时支持：
- 城中洞府的直接购买
- 野外灵脉的占领（击败守卫后获得所有权）
- 洞府建筑的升级与维护
- 护山大阵能量管理
"""

import json
import os
import random


class ResidenceConfig:
    """洞府配置加载器。"""

    def __init__(self, config_dir="config"):
        path = os.path.join(config_dir, "residences.json")
        with open(path, "r", encoding="utf-8") as f:
            self.data = json.load(f)

    def get_residences(self):
        return self.data.get("residences", [])

    def get_residence(self, residence_id):
        for r in self.get_residences():
            if r["id"] == residence_id:
                return r
        return None

    def get_residences_by_location(self, location_id):
        """获取指定地点关联的所有洞府配置。"""
        return [r for r in self.get_residences() if r.get("location_id") == location_id]

    def get_residences_by_type(self, residence_type):
        """按类型（city/wild）筛选洞府配置。"""
        return [r for r in self.get_residences() if r.get("type") == residence_type]

    def get_building(self, residence_id, building_id):
        residence = self.get_residence(residence_id)
        if not residence:
            return None
        for b in residence.get("buildings", []):
            if b["id"] == building_id:
                return b
        return None

    def get_raid_config(self):
        return self.data.get("raid", {})


class ResidenceManager:
    """洞府管理器。

    负责洞府购买/占领、建筑升级、月度维护、产出与袭击判定。
    """

    # 维护费欠费达到该月数后设施停摆
    MAX_MAINTENANCE_DEBT = 3

    def __init__(self, player, item_library=None, config=None):
        self.player = player
        self.item_library = item_library
        self.config = config or ResidenceConfig()
        self._ensure_residence_state()

    def _get_residence_data(self):
        return self.player.residence

    def _get_player_money(self):
        """获取玩家当前灵石数量。"""
        return getattr(self.player, "count_item", lambda x: 0)("spirit_stone")

    def _add_money(self, amount):
        """向背包添加指定数量灵石。"""
        if not self.item_library or amount <= 0:
            return
        for _ in range(amount):
            stone = self.item_library.create("spirit_stone")
            if stone:
                self.player.inventory.append(stone)

    def _consume_money(self, amount):
        """扣除灵石，返回是否成功。"""
        consume = getattr(self.player, "consume_items", None)
        if not consume:
            return False
        return consume("spirit_stone", amount)

    def _ensure_residence_state(self):
        """确保玩家洞府数据结构包含新增字段（旧存档兼容）。"""
        if not self.player.residence:
            return
        residence = self.player.residence
        # 护山大阵当前能量
        residence.setdefault("energy", self.get_max_formation_energy())
        # 维护费欠费月数
        residence.setdefault("maintenance_debt", 0)
        # 灵脉品质倍率，影响修炼加成
        residence.setdefault("spirit_vein_quality", 1.0)
        # 建筑等级字典
        residence.setdefault("buildings", {})

    # ==================== 购买洞府 ====================

    def can_buy_residence(self, residence_id):
        """检查是否可以购买指定洞府。"""
        if self.player.residence is not None:
            return False, "你已拥有一处洞府。"
        residence = self.config.get_residence(residence_id)
        if not residence:
            return False, "洞府不存在。"
        # 仅城中洞府可直接购买
        if residence.get("type") != "city":
            return False, "该洞府无法直接购买，需通过占领获得。"
        cost = residence.get("cost", {})
        spirit_stone = cost.get("spirit_stone", 0)
        contribution = cost.get("contribution", 0)
        if self._get_player_money() < spirit_stone:
            return False, f"灵石不足，需要 {spirit_stone} 灵石。"
        if getattr(self.player, "sect_contribution", 0) < contribution:
            return False, f"宗门贡献不足，需要 {contribution} 贡献。"
        return True, ""

    def buy_residence(self, residence_id):
        """购买洞府。"""
        ok, msg = self.can_buy_residence(residence_id)
        if not ok:
            return False, msg
        residence = self.config.get_residence(residence_id)
        cost = residence.get("cost", {})
        spirit_stone = cost.get("spirit_stone", 0)
        contribution = cost.get("contribution", 0)
        self._consume_money(spirit_stone)
        self.player.sect_contribution -= contribution
        self.player.residence = {
            "id": residence_id,
            "buildings": {},
            "energy": 0,
            "maintenance_debt": 0,
            "spirit_vein_quality": 1.0,
        }
        # 城中洞府默认无护阵能量；野外洞府占领后由 finish_occupation 填充
        self._ensure_residence_state()
        return True, f"你购买了【{residence['name']}】。"

    # ==================== 野外洞府占领 ====================

    def can_occupy(self, location_id):
        """检查是否可以在指定地点占领野外洞府。"""
        if self.player.residence is not None:
            return False, "你已拥有一处洞府。"
        candidates = self.config.get_residences_by_location(location_id)
        wild = [r for r in candidates if r.get("type") == "wild"]
        if not wild:
            return False, "该地点没有可占领的灵脉洞府。"
        residence = wild[0]
        occupation = residence.get("occupation")
        if not occupation:
            return False, "洞府配置缺少占领信息。"
        required_order = occupation.get("required_realm_order", 1)
        player_order = self.player.REALM_ORDER.get(self.player.realm_id, 0)
        if player_order < required_order:
            return False, f"境界不足，需要境界顺序 {required_order} 以上。"
        return True, residence["id"]

    def occupy(self, location_id):
        """发起占领，返回 (success, message, guard_enemy_data)。

        调用方需使用返回的 enemy_data 创建敌人并进入战斗；
        战斗胜利后调用 finish_occupation 完成所有权转移。
        """
        ok, result = self.can_occupy(location_id)
        if not ok:
            return False, result, None
        residence_id = result
        residence = self.config.get_residence(residence_id)
        occupation = residence.get("occupation", {})
        guard_enemy_id = occupation.get("guard_enemy_id")
        return True, occupation.get("intro_text", ""), guard_enemy_id

    def finish_occupation(self, location_id, win):
        """完成占领战斗。"""
        if not win:
            return False, "占领失败，你被迫退走。"
        ok, result = self.can_occupy(location_id)
        if not ok:
            return False, result
        residence_id = result
        residence = self.config.get_residence(residence_id)
        max_energy = self._get_residence_max_energy(residence_id)
        self.player.residence = {
            "id": residence_id,
            "buildings": {},
            "energy": max_energy,
            "maintenance_debt": 0,
            "spirit_vein_quality": residence.get("spirit_vein_quality", 1.0),
        }
        self._ensure_residence_state()
        return True, f"你成功占领【{residence['name']}】，私人洞府已建立。"

    # ==================== 建筑升级 ====================

    def _get_building_level(self, building_id):
        """获取指定建筑当前等级。"""
        if not self.player.residence:
            return 0
        return self.player.residence.get("buildings", {}).get(building_id, 0)

    def _get_upgrade_cost(self, building_cfg, current_level):
        """计算建筑从 current_level 升到下一级所需的灵石。"""
        base_cost = building_cfg.get("base_cost", {}).get("spirit_stone", 0)
        multiplier = building_cfg.get("cost_multiplier", 1.5)
        return int(base_cost * (multiplier ** current_level))

    def can_upgrade_building(self, building_id):
        """检查是否可以升级指定建筑。"""
        if not self.player.residence:
            return False, "你尚未拥有洞府。"
        residence_id = self.player.residence["id"]
        building = self.config.get_building(residence_id, building_id)
        if not building:
            return False, "建筑不存在。"
        current_level = self._get_building_level(building_id)
        if current_level >= building.get("max_level", 0):
            return False, "建筑已达最高等级。"
        cost = self._get_upgrade_cost(building, current_level)
        if self._get_player_money() < cost:
            return False, f"灵石不足，升级需要 {cost} 灵石。"
        return True, ""

    def upgrade_building(self, building_id):
        """升级指定建筑。"""
        ok, msg = self.can_upgrade_building(building_id)
        if not ok:
            return False, msg
        residence_id = self.player.residence["id"]
        building = self.config.get_building(residence_id, building_id)
        current_level = self._get_building_level(building_id)
        cost = self._get_upgrade_cost(building, current_level)
        self._consume_money(cost)
        self.player.residence["buildings"][building_id] = current_level + 1
        # 升级护山大阵时补充能量上限
        if building_id == "defense_formation":
            new_max = self.get_max_formation_energy()
            self.player.residence["energy"] = new_max
        return True, f"【{building['name']}】升至 {current_level + 1} 级。"

    # ==================== 建筑效果 ====================

    def get_building_effect(self, effect_key):
        """累加所有建筑对指定效果 key 的贡献。"""
        total = 0.0
        if not self.player.residence:
            return total
        residence_id = self.player.residence["id"]
        for building_id, level in self.player.residence.get("buildings", {}).items():
            building = self.config.get_building(residence_id, building_id)
            if not building:
                continue
            per_level = building.get("effect_per_level", {})
            if effect_key in per_level:
                value = per_level[effect_key]
                # herb_id 等字符串配置不参与累加
                if isinstance(value, (int, float)):
                    total += value * level
        return total

    def get_cultivation_speed_bonus(self):
        """洞府提供的修炼速度加成（含灵脉品质倍率）。"""
        base = self.get_building_effect("cultivation_speed")
        quality = self.get_spirit_vein_quality()
        return base * quality

    def get_water_damage_bonus(self):
        """洞府提供的水属性伤害加成。"""
        return self.get_building_effect("water_damage")

    def get_refine_bonus(self):
        """炼器室提供的祭炼效果加成。"""
        return self.get_building_effect("refine_bonus")

    def get_raid_defense(self):
        """护府阵法提供的袭击防御率。"""
        return min(0.9, self.get_building_effect("raid_defense"))

    def get_alchemy_success_bonus(self):
        """炼丹室提供的炼丹成功率加成。"""
        return self.get_building_effect("alchemy_success")

    def get_alchemy_quality_bonus(self):
        """炼丹室提供的炼丹品质加成。"""
        return self.get_building_effect("alchemy_quality")

    def get_smith_success_bonus(self):
        """炼器台提供的炼器成功率加成。"""
        return self.get_building_effect("smith_success")

    def get_herb_production(self):
        """获取药园可产出的灵草配置。"""
        result = []
        if not self.player.residence:
            return result
        residence_id = self.player.residence["id"]
        for building_id, level in self.player.residence.get("buildings", {}).items():
            building = self.config.get_building(residence_id, building_id)
            if not building:
                continue
            per_level = building.get("effect_per_level", {})
            herb_id = per_level.get("herb_id")
            herb_chance = per_level.get("herb_chance", 0) * level
            if herb_id and herb_chance > 0:
                result.append({"herb_id": herb_id, "chance": herb_chance})
        return result

    # ==================== 维护费与护阵能量 ====================

    def get_maintenance_cost(self):
        """计算本月总维护费。"""
        if not self.player.residence:
            return 0
        residence_id = self.player.residence["id"]
        total = 0
        for building_id, level in self.player.residence.get("buildings", {}).items():
            building = self.config.get_building(residence_id, building_id)
            if not building:
                continue
            total += building.get("maintenance_per_level", 0) * level
        return total

    def can_pay_maintenance(self):
        """检查是否可以缴纳本月维护费。"""
        cost = self.get_maintenance_cost()
        if cost <= 0:
            return True, ""
        if self._get_player_money() < cost:
            return False, f"灵石不足，需要 {cost} 灵石支付维护费。"
        return True, ""

    def pay_maintenance(self):
        """缴纳本月维护费，清零欠费。"""
        cost = self.get_maintenance_cost()
        if cost > 0:
            ok, msg = self.can_pay_maintenance()
            if not ok:
                return False, msg
            self._consume_money(cost)
        if self.player.residence:
            self.player.residence["maintenance_debt"] = 0
        return True, f"缴纳维护费 {cost} 灵石，洞府设施运转正常。"

    def _get_residence_max_energy(self, residence_id):
        """计算指定洞府护山大阵的能量上限。"""
        total = 0
        residence = self.config.get_residence(residence_id)
        if not residence:
            return total
        for building in residence.get("buildings", []):
            if building["id"] == "defense_formation":
                max_energy = building.get("effect_per_level", {}).get("max_energy", 0)
                # 未建造时返回每级上限，作为初始容量
                total += max_energy
        return total

    def get_max_formation_energy(self):
        """获取当前洞府护山大阵能量上限（按防御阵等级）。

        未建造护山大阵时，仍保留配置中每级上限作为基础容量，
        保证野外洞府占领后初始能量有对应上限。
        """
        if not self.player.residence:
            return 0
        residence_id = self.player.residence["id"]
        level = self.player.residence.get("buildings", {}).get("defense_formation", 0)
        building = self.config.get_building(residence_id, "defense_formation")
        if not building:
            return 0
        per_level = building.get("effect_per_level", {})
        max_energy = per_level.get("max_energy", 0)
        # level 为 0 时按 1 档计算基础容量，建造后每升一级增加一档
        return max_energy * max(level, 1)

    def get_formation_energy(self):
        """获取当前护山大阵能量。"""
        if not self.player.residence:
            return 0
        return self.player.residence.get("energy", 0)

    def consume_formation_energy(self, amount):
        """消耗护山大阵能量，返回实际消耗值。"""
        if not self.player.residence or amount <= 0:
            return 0
        current = self.player.residence.get("energy", 0)
        actual = min(current, amount)
        self.player.residence["energy"] = current - actual
        return actual

    def get_defense_rate(self):
        """获取当前洞府综合防御率（含护阵能量加成）。"""
        base = self.get_raid_defense()
        max_energy = self.get_max_formation_energy()
        if max_energy <= 0:
            return base
        current = self.get_formation_energy()
        # 能量越满，防御率越高；能量为 0 时仅保留建筑基础防御
        energy_factor = current / max_energy
        return min(0.95, base + (1 - base) * energy_factor * 0.5)

    def get_spirit_vein_quality(self):
        """获取当前洞府灵脉品质倍率。"""
        if not self.player.residence:
            return 1.0
        return self.player.residence.get("spirit_vein_quality", 1.0)

    # ==================== 月度结算 ====================

    def tick_monthly(self, rng=None):
        """洞府每月结算：维护费、产出、可能遭遇袭击。

        返回 {
            "production": [...],
            "raid": raid_result 或 None,
            "logs": [...],
            "maintenance_paid": bool,
            "maintenance_cost": int,
            "energy_decay": int
        }。
        """
        rng = rng or random
        production = []
        logs = []
        if not self.player.residence:
            return {
                "production": production,
                "raid": None,
                "logs": logs,
                "maintenance_paid": False,
                "maintenance_cost": 0,
                "energy_decay": 0,
            }

        # 维护费处理：有灵石则自动缴纳，否则累加欠费
        maintenance_cost = self.get_maintenance_cost()
        maintenance_paid = False
        if maintenance_cost > 0:
            if self._get_player_money() >= maintenance_cost:
                self._consume_money(maintenance_cost)
                self.player.residence["maintenance_debt"] = 0
                maintenance_paid = True
                logs.append(f"自动缴纳维护费 {maintenance_cost} 灵石。")
            else:
                self.player.residence["maintenance_debt"] += 1
                logs.append(f"灵石不足，维护费欠费 {self.player.residence['maintenance_debt']} 个月。")

        # 欠费超过阈值时设施停摆，本月不再产出
        debt = self.player.residence.get("maintenance_debt", 0)
        facilities_down = debt >= self.MAX_MAINTENANCE_DEBT
        if facilities_down:
            logs.append("洞府设施因长期欠费停摆，本月无产出。")

        # 护阵能量自然衰减（维护正常时衰减少，欠费时衰减多）
        max_energy = self.get_max_formation_energy()
        energy_decay = 0
        if max_energy > 0:
            if facilities_down:
                energy_decay = int(max_energy * 0.2)
            else:
                energy_decay = int(max_energy * 0.05)
            if energy_decay > 0:
                self.consume_formation_energy(energy_decay)
                logs.append(f"护山大阵消耗能量 {energy_decay} 点。")

        # 药园产出（仅设施未停摆时）
        if not facilities_down:
            for entry in self.get_herb_production():
                if rng.random() < entry["chance"]:
                    production.append(entry["herb_id"])
                    if self.item_library:
                        herb = self.item_library.create(entry["herb_id"])
                        if herb:
                            self.player.add_item(herb)

        # 袭击判定
        raid = None
        raid_cfg = self.config.get_raid_config()
        base_chance = raid_cfg.get("base_chance", 0.0)
        defense = self.get_defense_rate()
        actual_chance = max(0.0, base_chance * (1 - defense))
        if rng.random() < actual_chance:
            enemy_pool = raid_cfg.get("enemy_pool", [])
            if enemy_pool:
                enemy_id = rng.choice(enemy_pool)
                min_bonus = raid_cfg.get("min_strength_bonus", 0.0)
                max_bonus = raid_cfg.get("max_strength_bonus", 0.0)
                strength_bonus = rng.uniform(min_bonus, max_bonus)
                raid = {
                    "enemy_id": enemy_id,
                    "strength_bonus": strength_bonus,
                    "resolved": False,
                }
                logs.append(f"洞府遭到 {enemy_id} 袭击！")

        return {
            "production": production,
            "raid": raid,
            "logs": logs,
            "maintenance_paid": maintenance_paid,
            "maintenance_cost": maintenance_cost,
            "energy_decay": energy_decay,
        }

    def resolve_raid(self, win):
        """处理入侵战斗结果。"""
        if not self.player.residence:
            return False, "你没有洞府。"
        if win:
            # 胜利后恢复少量能量并获得材料奖励
            max_energy = self.get_max_formation_energy()
            if max_energy > 0:
                self.player.residence["energy"] = min(
                    max_energy, self.player.residence.get("energy", 0) + int(max_energy * 0.1)
                )
            return True, "你成功击退入侵者，护山大阵能量略有恢复。"
        # 失败：随机降级一级建筑或扣除能量
        buildings = self.player.residence.get("buildings", {})
        upgradable = [bid for bid, lv in buildings.items() if lv > 0]
        if upgradable:
            bid = random.choice(upgradable)
            buildings[bid] -= 1
            if buildings[bid] <= 0:
                del buildings[bid]
            return False, f"洞府被攻破，【{bid}】受损降级。"
        # 无建筑可降时扣除剩余能量
        self.consume_formation_energy(self.get_formation_energy())
        return False, "洞府被攻破，护山大阵能量耗尽。"
