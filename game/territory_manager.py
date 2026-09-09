# -*- coding: utf-8 -*-
"""领地建设与扩张系统（F-02）。

包含四个协作的管理器：
- TerritoryManager          领地占领 / 品阶升级（灵脉→福地→洞天）/ 月度结算总调度
- TerritoryBuildManager     建筑放置 / 拆除 / 升级（N×M 网格校验）
- TerritoryDefenseManager   阵眼五行搭配、护阵能量、妖兽袭扰触发与结算
- TerritoryProductionManager 月度产出与维护（注册引擎月度 tick）

设计要点（与 M3 家族系统保持一致范式）：
- 领地状态持久化在 player.territory（dict），随存档自然保存；from_save 用
  data.get 默认，旧存档无该字段时自动为 None（未占领地）。
- 所有按月结算通过 engine.register_monthly_tick 接入，未占领地时纯 no-op。
- 受 feature flag "territory" 门控，解锁境界为元婴期（order 18）。
- 占领守卫战斗沿用 ResidenceManager 的"返回 enemy_id → 外部开战 → 回调结算"模式，
  本模块只负责产出待战敌情，不直接耦合战斗引擎，便于测试与 UI 接入。
"""

import json
import os
import random

# 解锁所需最低境界：元婴期（order 18）
TERRITORY_MIN_REALM_ORDER = 18

# 品阶升级顺序
TIER_ORDER = ["spirit_vein", "blessed_land", "cave_heaven"]
TIER_NAMES = {"spirit_vein": "灵脉", "blessed_land": "福地", "cave_heaven": "洞天"}

# 五行元素（用于阵眼协同）
FIVE_ELEMENTS = ("fire", "water", "wood", "metal", "earth")
# 每覆盖一种不同元素，额外防御加成
FORMATION_SYNERGY_PER_ELEMENT = 0.03


class TerritoryConfig:
    """加载领地相关配置（config/territory/）。"""

    def __init__(self, config_dir="config"):
        self.config_dir = config_dir
        self._tiers = {}
        self._maps = {}
        self._buildings = {}
        self._load()

    def _load(self):
        base = os.path.join(self.config_dir, "territory")
        if not os.path.isdir(base):
            return
        # 品阶与可占领地图
        data = self._read(os.path.join(base, "territory_maps.json"))
        for t in data.get("tiers", []):
            self._tiers[t["id"]] = t
        for m in data.get("maps", []):
            self._maps[m["id"]] = m
        # 建筑
        data = self._read(os.path.join(base, "buildings.json"))
        for b in data.get("buildings", []):
            self._buildings[b["id"]] = b

    @staticmethod
    def _read(path):
        if not os.path.exists(path):
            return {}
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    def tiers(self):
        return list(self._tiers.values())

    def tier(self, tid):
        return self._tiers.get(tid)

    def maps(self):
        return list(self._maps.values())

    def get_map(self, mid):
        return self._maps.get(mid)

    def buildings(self):
        return list(self._buildings.values())

    def get_building(self, bid):
        return self._buildings.get(bid)


class TerritoryBuildManager:
    """建筑放置 / 拆除 / 升级（N×M 网格）。"""

    def __init__(self, player, config):
        self.player = player
        self.config = config

    # ---------------- 网格工具 ----------------
    @staticmethod
    def _in_bounds(territory, r, c):
        grid = territory["grid"]
        return 0 <= r < grid["rows"] and 0 <= c < grid["cols"]

    def _cell(self, territory, r, c):
        return territory["grid"]["cells"][r][c]

    def placed(self, territory):
        """返回所有已放置建筑 [(r, c, building_id, level)]。"""
        result = []
        grid = territory["grid"]
        for r in range(grid["rows"]):
            for c in range(grid["cols"]):
                cell = grid["cells"][r][c]
                if cell:
                    result.append((r, c, cell["building_id"], cell["level"]))
        return result

    # ---------------- 费用 ----------------
    def place_cost(self, building_id, current_level):
        b = self.config.get_building(building_id)
        if not b:
            return None
        mult = (b.get("cost_multiplier", 1.5)) ** current_level
        return {k: int(v * mult) for k, v in b.get("base_cost", {}).items()}

    def upgrade_cost(self, building_id, current_level):
        return self.place_cost(building_id, current_level)

    # ---------------- 放置 ----------------
    def can_place(self, territory, r, c, building_id):
        if not self._in_bounds(territory, r, c):
            return False, "坐标超出领地范围。"
        if self._cell(territory, r, c):
            return False, "该格子已有建筑。"
        b = self.config.get_building(building_id)
        if not b:
            return False, "未知建筑。"
        cost = self.place_cost(building_id, 0)
        stone = cost.get("spirit_stone", 0) if cost else 0
        if self.player.count_item("spirit_stone") < stone:
            return False, f"灵石不足，放置需要 {stone} 灵石。"
        return True, ""

    def place(self, territory, r, c, building_id):
        ok, msg = self.can_place(territory, r, c, building_id)
        if not ok:
            return False, msg
        b = self.config.get_building(building_id)
        cost = self.place_cost(building_id, 0)
        stone = cost.get("spirit_stone", 0) if cost else 0
        if stone > 0 and not self.player.consume_items("spirit_stone", stone):
            return False, "扣除灵石失败。"
        territory["grid"]["cells"][r][c] = {"building_id": building_id, "level": 1}
        return True, f"【{b['name']}】已建于 ({r},{c})。"

    # ---------------- 拆除 ----------------
    def remove(self, territory, r, c):
        if not self._in_bounds(territory, r, c):
            return False, "坐标超出领地范围。"
        cell = self._cell(territory, r, c)
        if not cell:
            return False, "该格子没有建筑。"
        b = self.config.get_building(cell["building_id"])
        name = b["name"] if b else cell["building_id"]
        # 返还当前等级一半的灵石（向下取整）
        cost = self.place_cost(cell["building_id"], cell["level"] - 1)
        refund = (cost.get("spirit_stone", 0) // 2) if cost else 0
        territory["grid"]["cells"][r][c] = None
        if refund > 0:
            self._grant_stone(refund)
        return True, f"【{name}】已拆除，返还 {refund} 灵石。"

    # ---------------- 升级 ----------------
    def can_upgrade(self, territory, r, c):
        if not self._in_bounds(territory, r, c):
            return False, "坐标超出领地范围。"
        cell = self._cell(territory, r, c)
        if not cell:
            return False, "该格子没有建筑。"
        b = self.config.get_building(cell["building_id"])
        if not b:
            return False, "未知建筑。"
        if cell["level"] >= b.get("max_level", 1):
            return False, "建筑已达最高等级。"
        cost = self.upgrade_cost(cell["building_id"], cell["level"])
        stone = cost.get("spirit_stone", 0) if cost else 0
        if self.player.count_item("spirit_stone") < stone:
            return False, f"灵石不足，升级需要 {stone} 灵石。"
        return True, ""

    def upgrade(self, territory, r, c):
        ok, msg = self.can_upgrade(territory, r, c)
        if not ok:
            return False, msg
        cell = self._cell(territory, r, c)
        b = self.config.get_building(cell["building_id"])
        cost = self.upgrade_cost(cell["building_id"], cell["level"])
        stone = cost.get("spirit_stone", 0) if cost else 0
        if stone > 0 and not self.player.consume_items("spirit_stone", stone):
            return False, "扣除灵石失败。"
        cell["level"] += 1
        return True, f"【{b['name']}】升至 {cell['level']} 级。"

    # ---------------- 效果聚合 ----------------
    def get_effect(self, territory, key):
        """累加所有建筑对指定效果 key 的贡献（按 level）。"""
        total = 0.0
        for _r, _c, bid, lvl in self.placed(territory):
            b = self.config.get_building(bid)
            if not b:
                continue
            val = b.get("effect_per_level", {}).get(key)
            if isinstance(val, (int, float)):
                total += val * lvl
        return total

    def _grant_stone(self, amount):
        """将灵石返还到玩家背包。"""
        for _ in range(amount):
            stone = getattr(self.player, "item_library", None)
            if stone and hasattr(stone, "create"):
                item = stone.create("spirit_stone")
                if item:
                    self.player.add_item(item)
            else:
                # 退路：直接加计数（测试桩可能无 item_library）
                self.player.inventory.append({"id": "spirit_stone", "count": 1})


class TerritoryDefenseManager:
    """阵眼五行搭配、护阵能量、妖兽袭扰触发与结算。"""

    def __init__(self, player, config):
        self.player = player
        self.config = config

    def max_energy(self, territory):
        """护阵能量上限 = 品阶基础 + 守卫塔贡献。"""
        tier = self.config.tier(territory["tier"])
        base = tier.get("max_energy", 0) if tier else 0
        base += int(self._build_mgr_effect(territory, "max_energy"))
        return base

    def _build_mgr_effect(self, territory, key):
        """通过配置聚合某效果（不依赖外部 build_mgr 实例）。"""
        total = 0.0
        grid = territory["grid"]
        for r in range(grid["rows"]):
            for c in range(grid["cols"]):
                cell = grid["cells"][r][c]
                if not cell:
                    continue
                b = self.config.get_building(cell["building_id"])
                if not b:
                    continue
                val = b.get("effect_per_level", {}).get(key)
                if isinstance(val, (int, float)):
                    total += val * cell["level"]
        return total

    def formation_elements(self, territory):
        """返回已布置阵眼覆盖的五行元素集合。"""
        covered = set()
        grid = territory["grid"]
        for r in range(grid["rows"]):
            for c in range(grid["cols"]):
                cell = grid["cells"][r][c]
                if not cell:
                    continue
                b = self.config.get_building(cell["building_id"])
                if b and b.get("category") == "formation":
                    elem = b.get("element")
                    if elem in FIVE_ELEMENTS:
                        covered.add(elem)
        return covered

    def synergy_bonus(self, territory):
        return FORMATION_SYNERGY_PER_ELEMENT * len(self.formation_elements(territory))

    def energy_factor(self, territory):
        max_e = self.max_energy(territory)
        if max_e <= 0:
            return 0.0
        cur = territory.get("energy", 0)
        return min(1.0, cur / max_e)

    def defense_rate(self, territory):
        """综合防御率：品阶基础 + 守卫塔 + 阵眼协同 + 能量因子。"""
        tier = self.config.tier(territory["tier"])
        base = tier.get("defense_base", 0.0) if tier else 0.0
        guard = self._build_mgr_effect(territory, "defense")
        synergy = self.synergy_bonus(territory)
        energy = self.energy_factor(territory) * 0.3
        return min(0.95, base + guard + synergy + energy)

    # ---------------- 袭扰 ----------------
    def maybe_trigger_raid(self, territory, rng=None):
        """按基础袭扰概率与当前防御率，决定是否触发妖兽袭扰。

        返回 raid 字典或 None；命中时写入 territory['pending_raid']。
        """
        rng = rng or random
        raid_cfg = territory.get("raid_config", {})
        base_chance = raid_cfg.get("base_chance", 0.12)
        defense = self.defense_rate(territory)
        chance = max(0.0, base_chance * (1 - defense))
        if rng.random() < chance:
            enemy_pool = raid_cfg.get("enemy_pool", [])
            if not enemy_pool:
                return None
            enemy_id = rng.choice(enemy_pool)
            lo, hi = raid_cfg.get("strength_range", [0.0, 0.3])
            strength_bonus = rng.uniform(lo, hi)
            raid = {
                "enemy_id": enemy_id,
                "strength_bonus": strength_bonus,
                "resolved": False,
            }
            territory["pending_raid"] = raid
            return raid
        return None

    def resolve_raid(self, territory, win):
        """结算袭扰战斗结果。"""
        if not territory.get("pending_raid"):
            return False, "当前没有待结算的袭扰。"
        territory["pending_raid"]["resolved"] = True
        max_e = self.max_energy(territory)
        if win:
            territory["defended_count"] = territory.get("defended_count", 0) + 1
            if max_e > 0:
                territory["energy"] = min(
                    max_e, territory.get("energy", 0) + int(max_e * 0.15)
                )
            territory["pending_raid"] = None
            return True, "你成功击退来犯妖兽，护阵能量略有恢复。"
        # 失败：损毁一座建筑或损耗能量
        territory["raided_count"] = territory.get("raided_count", 0) + 1
        grid = territory["grid"]
        occupiable = []
        for r in range(grid["rows"]):
            for c in range(grid["cols"]):
                if grid["cells"][r][c]:
                    occupiable.append((r, c))
        if occupiable:
            r, c = random.choice(occupiable)
            cell = grid["cells"][r][c]
            b = self.config.get_building(cell["building_id"])
            name = b["name"] if b else cell["building_id"]
            if cell["level"] > 1:
                cell["level"] -= 1
                msg = f"领地遭劫，【{name}】受损降为 {cell['level']} 级。"
            else:
                grid["cells"][r][c] = None
                msg = f"领地遭劫，【{name}】被摧毁。"
        else:
            if max_e > 0:
                territory["energy"] = max(0, territory.get("energy", 0) - int(max_e * 0.3))
                msg = "领地遭劫，护阵能量大幅损耗。"
            else:
                msg = "领地遭劫，所幸并无损失。"
        territory["pending_raid"] = None
        return False, msg


class TerritoryProductionManager:
    """月度产出与维护（注册引擎月度 tick）。"""

    def __init__(self, player, config, item_library=None):
        self.player = player
        self.config = config
        self.item_library = item_library

    def total_maintenance(self, territory):
        """累加领地所有建筑的维护费（按等级）。"""
        total = 0
        grid = territory["grid"]
        for r in range(grid["rows"]):
            for c in range(grid["cols"]):
                cell = grid["cells"][r][c]
                if not cell:
                    continue
                b = self.config.get_building(cell["building_id"])
                if not b:
                    continue
                total += b.get("maintenance", 0) * cell["level"]
        return total

    def settle_monthly(self, territory, rng=None):
        """按月结算产出与维护，返回日志列表。

        维护费优先从领地金库扣除，金库不足部分从玩家私库（背包灵石）补足，
        使经济真实可感：净负领地会持续消耗玩家灵石，净正领地则累积金库盈余。
        """
        rng = rng or random
        logs = []
        # 灵石产出（含聚灵塔 + 坊市）进入领地金库
        stone = int(self._effect(territory, "spirit_stone"))
        # 维护费（建筑顶层 maintenance 字段，按等级累加）
        upkeep = self.total_maintenance(territory)
        # 声望积累（坊市）
        rep = int(self._effect(territory, "reputation"))

        # 维护费：优先从领地金库扣除，缺口从玩家私库补足
        if upkeep > 0:
            from_treasury = min(territory.get("treasury", 0), upkeep)
            territory["treasury"] = max(0, territory["treasury"] - from_treasury)
            remain = upkeep - from_treasury
            paid_private = 0
            if remain > 0:
                before = self.player.count_item("spirit_stone")
                self.player.consume_items("spirit_stone", remain)
                paid_private = before - self.player.count_item("spirit_stone")
                remain -= paid_private
            if remain > 0:
                logs.append(
                    f"建筑维护缺口 {remain} 灵石（金库 {from_treasury} + 私库 {paid_private}），领地运转吃紧。"
                )
            else:
                logs.append(
                    f"建筑维护消耗 {upkeep} 灵石（金库 {from_treasury} + 私库 {paid_private}）。"
                )

        if stone > 0:
            territory["treasury"] += stone
            logs.append(f"领地运转，金库灵石 +{stone}。")
        if rep > 0:
            rep_map = getattr(self.player, "reputation", None)
            if isinstance(rep_map, dict):
                rep_map["territory"] = rep_map.get("territory", 0) + rep
                logs.append(f"坊市往来，势力声望 +{rep}。")
        # 灵草 / 灵矿产出（按概率，转为背包物品）
        for key, item_id in (("herb", "spirit_herb"), ("ore", "spirit_ore")):
            amount = int(self._effect(territory, key))
            if amount <= 0:
                continue
            produced = 0
            for _ in range(amount):
                if rng.random() < 0.7:
                    produced += 1
            if produced > 0:
                self._grant_item(item_id, produced)
                logs.append(f"产出 {item_id} ×{produced}（已入背包）。")
        return logs

    def _effect(self, territory, key):
        total = 0.0
        grid = territory["grid"]
        for r in range(grid["rows"]):
            for c in range(grid["cols"]):
                cell = grid["cells"][r][c]
                if not cell:
                    continue
                b = self.config.get_building(cell["building_id"])
                if not b:
                    continue
                val = b.get("effect_per_level", {}).get(key)
                if isinstance(val, (int, float)):
                    total += val * cell["level"]
        return total

    def _grant_item(self, item_id, count):
        if self.item_library and hasattr(self.item_library, "create"):
            for _ in range(count):
                item = self.item_library.create(item_id)
                if item:
                    self.player.add_item(item)
        else:
            for _ in range(count):
                self.player.inventory.append({"id": item_id, "count": 1})


class TerritoryManager:
    """领地核心管理器，编排建造 / 防御 / 产出的月度结算。"""

    def __init__(self, player, config_dir="config",
                 is_feature_enabled=None, notify_callback=None,
                 get_month_callback=None, item_library=None):
        self.player = player
        self.config_dir = config_dir
        self.config = TerritoryConfig(config_dir)
        self._feature_enabled = is_feature_enabled
        self.notify = notify_callback or (lambda x: None)
        self._get_month = get_month_callback
        self.item_library = item_library
        self.build_mgr = TerritoryBuildManager(player, self.config)
        self.defense_mgr = TerritoryDefenseManager(player, self.config)
        self.prod_mgr = TerritoryProductionManager(player, self.config, item_library)

    def _current_month(self):
        if callable(self._get_month):
            try:
                return int(self._get_month())
            except Exception:
                return 0
        return 0

    # ---------------- 开关与状态 ----------------
    def is_enabled(self):
        if callable(self._feature_enabled):
            return self._feature_enabled("territory")
        return True

    def is_claimed(self):
        return bool(getattr(self.player, "territory", None))

    def get_territory(self):
        return getattr(self.player, "territory", None)

    def monthly_extraction(self, territory, key="spirit_stone"):
        """返回领地本月某类资源抽取量（供灵脉枯竭监测等外部系统使用）。"""
        if not isinstance(territory, dict):
            return 0
        return self.prod_mgr._effect(territory, key)

    # ---------------- 占领 ----------------
    def can_claim(self, territory_id):
        if not self.is_enabled():
            return False, "领地功能未开启。"
        if self.is_claimed():
            return False, "你已占据一处领地。"
        order = self.player.REALM_ORDER.get(self.player.realm_id, 0)
        if order < TERRITORY_MIN_REALM_ORDER:
            return False, "需达到元婴期方可占据领地。"
        m = self.config.get_map(territory_id)
        if not m:
            return False, "领地不存在。"
        if order < m.get("required_realm_order", TERRITORY_MIN_REALM_ORDER):
            return False, "境界不足以占据该领地。"
        cost = m.get("claim_cost", {})
        stone = cost.get("spirit_stone", 0)
        if self.player.count_item("spirit_stone") < stone:
            return False, f"灵石不足，占据需要 {stone} 灵石。"
        return True, ""

    def claim(self, territory_id):
        ok, msg = self.can_claim(territory_id)
        if not ok:
            return False, msg
        m = self.config.get_map(territory_id)
        cost = m.get("claim_cost", {})
        stone = cost.get("spirit_stone", 0)
        if stone > 0 and not self.player.consume_items("spirit_stone", stone):
            return False, "扣除灵石失败。"
        tier = m.get("tier", "spirit_vein")
        tier_cfg = self.config.tier(tier) or {"grid": [4, 4], "max_energy": 60}
        rows, cols = tier_cfg.get("grid", [4, 4])
        territory = {
            "territory_id": territory_id,
            "name": m.get("name", territory_id),
            "tier": tier,
            "claimed_month": self._current_month(),
            "month": self._current_month(),
            "grid": {
                "rows": rows,
                "cols": cols,
                "cells": [[None for _ in range(cols)] for _ in range(rows)],
            },
            "energy": tier_cfg.get("max_energy", 60),
            "max_energy": tier_cfg.get("max_energy", 60),
            "treasury": 0,
            "resources": {"herb": 0, "ore": 0},
            "pending_raid": None,
            "raid_config": {
                "base_chance": 0.12,
                "enemy_pool": ["beast_tiger", "snow_wolf", "demon_beast"],
                "strength_range": [0.0, 0.3],
            },
            "history": [],
            "raided_count": 0,
            "defended_count": 0,
        }
        self.player.territory = territory
        self.notify(f"[green]你占据了领地【{territory['name']}】！")
        return True, f"领地【{territory['name']}】占据成功。"

    def get_claim_guard(self, territory_id):
        """返回该领地守卫敌人 id（可选，供 UI 触发战斗 flavor）。"""
        m = self.config.get_map(territory_id)
        if not m:
            return None
        return m.get("guard_enemy_id")

    # ---------------- 品阶升级 ----------------
    def can_upgrade_tier(self):
        territory = self.get_territory()
        if not territory:
            return False, "尚未占据领地。"
        idx = TIER_ORDER.index(territory["tier"])
        if idx >= len(TIER_ORDER) - 1:
            return False, "领地已至最高品阶（洞天）。"
        next_tier = TIER_ORDER[idx + 1]
        tier_cfg = self.config.tier(next_tier)
        cost = tier_cfg.get("upgrade_cost", {})
        stone = cost.get("spirit_stone", 0)
        if self.player.count_item("spirit_stone") < stone:
            return False, f"灵石不足，升阶需要 {stone} 灵石。"
        order = self.player.REALM_ORDER.get(self.player.realm_id, 0)
        if order < tier_cfg.get("required_realm_order", TERRITORY_MIN_REALM_ORDER):
            return False, "境界不足以升阶。"
        return True, ""

    def upgrade_tier(self):
        ok, msg = self.can_upgrade_tier()
        if not ok:
            return False, msg
        territory = self.get_territory()
        idx = TIER_ORDER.index(territory["tier"])
        next_tier = TIER_ORDER[idx + 1]
        tier_cfg = self.config.tier(next_tier)
        cost = tier_cfg.get("upgrade_cost", {})
        stone = cost.get("spirit_stone", 0)
        if stone > 0 and not self.player.consume_items("spirit_stone", stone):
            return False, "扣除灵石失败。"
        # 网格扩大（仅增大，旧建筑坐标仍有效），保留既有建筑
        new_rows, new_cols = tier_cfg.get("grid", [6, 6])
        old = territory["grid"]
        new_cells = [[None for _ in range(new_cols)] for _ in range(new_rows)]
        for r in range(old["rows"]):
            for c in range(old["cols"]):
                new_cells[r][c] = old["cells"][r][c]
        territory["grid"] = {"rows": new_rows, "cols": new_cols, "cells": new_cells}
        territory["tier"] = next_tier
        territory["max_energy"] = tier_cfg.get("max_energy", territory.get("max_energy", 0))
        territory["energy"] = territory["max_energy"]
        self.notify(
            f"[green]领地升阶为【{TIER_NAMES.get(next_tier, next_tier)}】，"
            f"领地范围扩大至 {new_rows}×{new_cols}！"
        )
        return True, f"领地升阶为【{TIER_NAMES.get(next_tier, next_tier)}】。"

    # ---------------- 金库存取 ----------------
    def withdraw(self, amount):
        territory = self.get_territory()
        if not territory:
            return False, "尚未占据领地。"
        amount = min(amount, territory["treasury"])
        if amount <= 0:
            return False, "金库没有可收取的灵石。"
        territory["treasury"] -= amount
        for _ in range(amount):
            if self.item_library and hasattr(self.item_library, "create"):
                item = self.item_library.create("spirit_stone")
                if item:
                    self.player.add_item(item)
            else:
                self.player.inventory.append({"id": "spirit_stone", "count": 1})
        return True, f"从领地金库收取 {amount} 灵石。"

    # ---------------- 辅助查询 ----------------
    def get_cultivation_speed_bonus(self):
        territory = self.get_territory()
        if not territory:
            return 0.0
        return self.build_mgr.get_effect(territory, "cultivation_speed")

    def get_defense_rate(self):
        territory = self.get_territory()
        if not territory:
            return 0.0
        return self.defense_mgr.defense_rate(territory)

    # ---------------- 月度结算 ----------------
    def tick_monthly(self):
        """注册到 engine 的月度插座；未占领地或功能关闭时为纯 no-op。"""
        if not self.is_enabled() or not self.is_claimed():
            return
        self.monthly_settle()

    def monthly_settle(self):
        territory = self.get_territory()
        if not territory:
            return
        territory["month"] = self._current_month()
        month = territory["month"]

        # 1) 产出与维护
        logs = self.prod_mgr.settle_monthly(territory, rng=random)

        # 2) 护阵能量自然衰减
        max_e = territory.get("max_energy", 0)
        if max_e > 0:
            decay = int(max_e * 0.05)
            if decay > 0:
                territory["energy"] = max(0, territory.get("energy", 0) - decay)

        # 3) 妖兽袭扰
        raid = self.defense_mgr.maybe_trigger_raid(territory, rng=random)
        if raid:
            logs.append(f"妖兽袭扰！来犯之敌：{raid['enemy_id']}（请前往防御处置）。")
            self.notify(f"[yellow]领地遭妖兽袭扰：{raid['enemy_id']}")

        # 4) 历史记录
        for line in logs:
            territory["history"].append({"month": month, "text": line})
        territory["history"] = territory["history"][-50:]
