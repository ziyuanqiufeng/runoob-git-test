# -*- coding: utf-8 -*-
"""修仙家族/宗族系统（F-01）。

包含四个协作的管理器：
- FamilyManager        家族创建/解散、成员增删、等级、月度结算总调度
- FamilyTaskManager    成员任务分配与月度产出结算
- FamilyEventManager   家族事件触发、选项处理、结果应用
- FamilyDiplomacyManager 与其他家族的外交关系

设计要点：
- 家族状态持久化在 player.family（dict），随存档自然保存；from_save 用
  data.get 默认，旧存档无该字段时自动为 None（未建家族）。
- 所有按月结算通过 engine.register_monthly_tick 接入，未建家族时纯 no-op。
- 受 feature flag "family" 门控。
"""
import json
import os
import random

# 创建家族所需最低境界：金丹初期（order 14）
FAMILY_MIN_REALM_ORDER = 14
CREATE_COST_STONE = 5000      # 创建消耗灵石
CREATE_COST_REPUTATION = 200  # 创建所需（作为门槛，不消耗）总声望

TASKS = ("cultivate", "manage", "explore", "diplomacy")
TASK_NAMES = {
    "cultivate": "修炼",
    "manage": "经营",
    "explore": "探索",
    "diplomacy": "外交",
    None: "待命",
}


class FamilyConfig:
    """加载家族相关配置。"""

    def __init__(self, config_dir="config"):
        self.config_dir = config_dir
        self._members = {}
        self._buildings = {}
        self._events = []
        self._names = {}
        self._others = []
        self._load()

    def _load(self):
        base = os.path.join(self.config_dir, "family")
        if not os.path.isdir(base):
            return
        # 成员模板
        data = self._read(os.path.join(base, "family_members.json"))
        for t in data.get("member_templates", []):
            self._members[t["id"]] = t
        # 建筑
        data = self._read(os.path.join(base, "family_buildings.json"))
        for b in data.get("buildings", []):
            self._buildings[b["id"]] = b
        # 事件
        data = self._read(os.path.join(base, "family_events.json"))
        self._events = data.get("events", [])
        # 名称/家训/阵营
        self._names = self._read(os.path.join(base, "family_names.json"))
        # 其他家族（外交目标）
        data = self._read(os.path.join(base, "other_families.json"))
        self._others = data.get("other_families", [])

    @staticmethod
    def _read(path):
        if not os.path.exists(path):
            return {}
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    def member_templates(self):
        return list(self._members.values())

    def get_member_template(self, tid):
        return self._members.get(tid)

    def buildings(self):
        return list(self._buildings.values())

    def get_building(self, bid):
        return self._buildings.get(bid)

    def events(self):
        return list(self._events)

    def names(self):
        return self._names

    def other_families(self):
        return list(self._others)


class FamilyTaskManager:
    """成员任务分配与月度产出结算。"""

    def assign_task(self, family, member_id, task):
        member = self._find(family, member_id)
        if not member:
            return False
        if task not in TASKS:
            task = None
        member["task"] = task
        member["task_since"] = family.get("month", 0)
        return True

    @staticmethod
    def _find(family, member_id):
        for m in family.get("members", []):
            if m["id"] == member_id:
                return m
        return None

    def settle_monthly(self, family, rng=None):
        """对家族成员按月结算产出，返回日志列表。"""
        rng = rng or random
        logs = []
        cfg = family.get("_cfg")  # 由 FamilyManager 注入的 FamilyConfig
        buildings = family.get("buildings", {})

        # 建筑加成
        scripture_bonus = 0.0
        ancestral_loyalty = 0
        if cfg:
            for bid, lvl in buildings.items():
                b = cfg.get_building(bid)
                if not b or lvl <= 0:
                    continue
                eff = b.get("effect", {})
                scripture_bonus += eff.get("member_growth", 0.0) * lvl
                ancestral_loyalty += eff.get("loyalty_bonus", 0) * lvl

        for m in family.get("members", []):
            task = m.get("task")
            apt = m.get("aptitude", 50)
            gr = m.get("growth_rate", 1.0)
            if task == "cultivate":
                gain = apt * gr * 0.1 * (1 + scripture_bonus)
                m["cultivation"] = m.get("cultivation", 0) + gain
                logs.append(f"{m['name']} 闭关修炼，修为 +{gain:.1f}。")
            elif task == "manage":
                inc = int(apt * 0.5 + 10)
                family["treasury"] += inc
                herb = rng.randint(0, 3)
                family["resources"]["herb"] = family["resources"].get("herb", 0) + herb
                logs.append(f"{m['name']} 经营族务，灵石 +{inc}、灵植 +{herb}。")
            elif task == "explore":
                if rng.random() < 0.6:
                    ore = rng.randint(1, 4)
                    family["resources"]["ore"] = family["resources"].get("ore", 0) + ore
                    logs.append(f"{m['name']} 外出游历，寻得矿材 +{ore}。")
                else:
                    logs.append(f"{m['name']} 外出游历，无功而返。")
            elif task == "diplomacy":
                rep_gain = int(apt * 0.3 + 3)
                family["reputation"] += rep_gain
                logs.append(f"{m['name']} 奔走外交，家族声望 +{rep_gain}。")
            else:
                # 待命：忠诚缓慢流失
                m["loyalty"] = max(0, m.get("loyalty", 50) - 1)
            # 忠诚自然回复（有任务且祠堂加成）
            if task is not None:
                m["loyalty"] = min(100, m.get("loyalty", 50) + 1 + ancestral_loyalty * 0.2)

        return logs


class FamilyEventManager:
    """家族事件触发与选项处理。"""

    def __init__(self, config_dir="config"):
        self.config = FamilyConfig(config_dir)

    def maybe_trigger(self, family, rng=None):
        """按触发条件与权重挑选一个可触发事件，返回事件实例或 None。"""
        rng = rng or random
        month = family.get("month", 0)
        age = month - family.get("created_month", 0)
        members = family.get("members", [])
        min_loyalty = min((m.get("loyalty", 100) for m in members), default=100)

        candidates = []
        for ev in self.config.events():
            cond = ev.get("trigger_condition", {})
            if "month_min" in cond and age < cond["month_min"]:
                continue
            if "loyalty_below" in cond and min_loyalty >= cond["loyalty_below"]:
                continue
            if "members_min" in cond and len(members) < cond["members_min"]:
                continue
            candidates.append(ev)
        if not candidates:
            return None
        weights = [max(1, ev.get("weight", 10)) for ev in candidates]
        ev = rng.choices(candidates, weights=weights, k=1)[0]
        return {
            "event_id": ev["id"],
            "name": ev.get("name", ev["id"]),
            "desc": ev.get("desc", ""),
            "choices": ev.get("choices", []),
            "resolved": False,
        }

    def resolve_event(self, family, event_instance, choice_index,
                      rng=None, family_manager=None):
        """处理玩家对事件的选择，应用效果，返回日志。"""
        rng = rng or random
        choices = event_instance.get("choices", [])
        if choice_index < 0 or choice_index >= len(choices):
            return "无效的选项。"
        eff = choices[choice_index].get("effect", {})
        logs = []

        if "reputation" in eff:
            family["reputation"] = max(0, family["reputation"] + eff["reputation"])
            logs.append(f"家族声望 {'+' if eff['reputation'] >= 0 else ''}{eff['reputation']}。")
        if "karma" in eff and family_manager and family_manager.player:
            p = family_manager.player
            p.karma = getattr(p, "karma", 0) + eff["karma"]
            logs.append(f"业力 {'+' if eff['karma'] >= 0 else ''}{eff['karma']}。")
        if "morale" in eff:
            for m in family["members"]:
                m["loyalty"] = max(0, min(100, m["loyalty"] + eff["morale"]))
            logs.append(f"全族士气 {'+' if eff['morale'] >= 0 else ''}{eff['morale']}。")
        if "loyalty_all" in eff:
            for m in family["members"]:
                m["loyalty"] = max(0, min(100, m["loyalty"] + eff["loyalty_all"]))
            logs.append(f"全族忠诚 {'+' if eff['loyalty_all'] >= 0 else ''}{eff['loyalty_all']}。")
        if "member_growth" in eff:
            members = family["members"]
            if members:
                m = rng.choice(members)
                m["cultivation"] = m.get("cultivation", 0) + eff["member_growth"] * 20
                logs.append(f"{m['name']} 修为大涨！")
        if "recruit" in eff and family_manager:
            for _ in range(int(eff["recruit"])):
                mem = family_manager.recruit_member(quality="high", rng=rng)
                if mem:
                    logs.append(f"新成员 {mem['name']} 因联姻加入家族。")
        if "resources" in eff:
            res = eff["resources"]
            stone = res.get("spirit_stone")
            if stone == "partial_recovery":
                rec = int(family.get("stolen_stone", 0) * 0.5)
                family["treasury"] += rec
                family["stolen_stone"] = 0
                logs.append(f"追回灵石 {rec}。")
            elif isinstance(stone, (int, float)):
                family["treasury"] = max(0, family["treasury"] + int(stone))
                if int(stone) < 0:
                    family["stolen_stone"] = family.get("stolen_stone", 0) + (-int(stone))

        event_instance["resolved"] = True
        return "；".join(logs) if logs else "事件已了结。"


class FamilyDiplomacyManager:
    """与其他家族的外交关系。"""

    def __init__(self, config_dir="config"):
        self.config = FamilyConfig(config_dir)

    def list_targets(self):
        return self.config.other_families()

    def get_relation(self, family, target_id):
        return family.get("diplomacy", {}).get(target_id, "neutral")

    def set_relation(self, family, target_id, relation):
        if relation not in ("ally", "rival", "neutral"):
            return False
        family.setdefault("diplomacy", {})[target_id] = relation
        return True

    def is_ally(self, family, target_id):
        return self.get_relation(family, target_id) == "ally"

    def settle_monthly(self, family, rng=None):
        """关系缓慢向中立衰减（维持戏剧张力）。"""
        rng = rng or random
        dip = family.get("diplomacy", {})
        changed = []
        for tid, rel in list(dip.items()):
            if rel != "neutral" and rng.random() < 0.05:
                dip[tid] = "neutral"
                changed.append(tid)
        return changed


class FamilyManager:
    """家族核心管理器，编排任务/事件/外交的月度结算。"""

    def __init__(self, player, npc_library=None, social_manager=None,
                 item_library=None, config_dir="config",
                 is_feature_enabled=None, notify_callback=None,
                 get_month_callback=None):
        self.player = player
        self.npc_library = npc_library
        self.social_manager = social_manager
        self.item_library = item_library
        self.config_dir = config_dir
        self.config = FamilyConfig(config_dir)
        self._feature_enabled = is_feature_enabled
        self.notify = notify_callback or (lambda x: None)
        self._get_month = get_month_callback
        self.task_mgr = FamilyTaskManager()
        self.event_mgr = FamilyEventManager(config_dir)
        self.diplo_mgr = FamilyDiplomacyManager(config_dir)

    def _current_month(self):
        """返回当前世界月份（0 基）。无回调时回退 0。"""
        if callable(self._get_month):
            try:
                return int(self._get_month())
            except Exception:
                return 0
        return 0

    # ---------------- 开关与状态 ----------------
    def is_enabled(self):
        if callable(self._feature_enabled):
            return self._feature_enabled("family")
        return True

    def is_created(self):
        return bool(getattr(self.player, "family", None))

    def get_family(self):
        return getattr(self.player, "family", None)

    # ---------------- 创建 / 解散 ----------------
    def can_create(self):
        if not self.is_enabled():
            return False, "家族功能未开启。"
        if self.is_created():
            return False, "你已创立家族。"
        order = self.player.REALM_ORDER.get(self.player.realm_id, 0)
        if order < FAMILY_MIN_REALM_ORDER:
            return False, "需达到金丹期方可创立家族。"
        if self.player.count_item("spirit_stone") < CREATE_COST_STONE:
            return False, f"灵石不足，需 {CREATE_COST_STONE} 灵石。"
        total_rep = sum(self.player.reputation.values()) if hasattr(self.player, "reputation") else 0
        if total_rep < CREATE_COST_REPUTATION:
            return False, f"声望不足，需累计 {CREATE_COST_REPUTATION} 点。"
        return True, ""

    def create(self, name, motto, faction):
        ok, msg = self.can_create()
        if not ok:
            return False, msg
        if not self.player.consume_items("spirit_stone", CREATE_COST_STONE):
            return False, "扣除灵石失败。"
        family = {
            "name": name,
            "motto": motto,
            "faction": faction,
            "reputation": 0,
            "level": 1,
            "created_month": self._current_month(),
            "month": self._current_month(),
            "members": [],
            "buildings": {},
            "treasury": 0,
            "resources": {"herb": 0, "ore": 0},
            "diplomacy": {},
            "pending_events": [],
            "history": [],
            "next_member_id": 1,
            "stolen_stone": 0,
            "total_income": 0,
            "total_upkeep": 0,
            "_cfg": None,
        }
        family["_cfg"] = self.config
        # 家主作为首位成员
        founder = self._make_member({
            "id": "founder_template", "name_pool": [self.player.name],
            "spirit_root": "none", "aptitude_range": [90, 90],
            "personality": ["家主"], "loyalty_base": 100,
            "growth_rate": 1.0, "special_trait": "族长",
        }, rng=random)
        founder["task"] = "cultivate"
        family["members"].append(founder)
        self.player.family = family
        self.notify(f"[green]你创立了家族【{name}】！")
        return True, f"家族【{name}】创立成功。"

    def disband(self):
        if not self.is_created():
            return False, "尚未创立家族。"
        name = self.player.family.get("name", "")
        self.player.family = None
        self.notify(f"[red]家族【{name}】已解散。")
        return True, f"家族【{name}】已解散。"

    # ---------------- 成员 ----------------
    def _make_member(self, template, rng=None):
        rng = rng or random
        name = rng.choice(template.get("name_pool", ["无名"]))
        apt_lo, apt_hi = template.get("aptitude_range", [40, 70])
        return {
            "id": f"m_{self.player.family['next_member_id']}" if self.player.family else "m_tmp",
            "name": name,
            "spirit_root": template.get("spirit_root", "none"),
            "aptitude": rng.randint(int(apt_lo), int(apt_hi)),
            "personality": list(template.get("personality", ["朴实"])),
            "loyalty": template.get("loyalty_base", 60),
            "cultivation": 0.0,
            "growth_rate": template.get("growth_rate", 1.0),
            "special_trait": template.get("special_trait", ""),
            "task": None,
            "task_since": 0,
        }

    def recruit_member(self, quality="normal", rng=None):
        """招募一名成员；quality 影响模板权重（高声望可招揽天才）。"""
        rng = rng or random
        family = self.get_family()
        if not family:
            return None
        templates = self.config.member_templates()
        if not templates:
            return None
        rep = family.get("reputation", 0)
        # 高声望提升高品质模板权重
        weights = []
        for t in templates:
            w = 1.0
            high = t.get("aptitude_range", [0, 0])[1] >= 85
            if quality == "high" and high:
                w = 3.0 + rep / 100.0
            elif quality != "high" and not high:
                w = 2.0
            weights.append(w)
        tpl = rng.choices(templates, weights=weights, k=1)[0]
        member = self._make_member(tpl, rng=rng)
        member["id"] = f"m_{family['next_member_id']}"
        family["next_member_id"] += 1
        family["members"].append(member)
        return member

    def add_member_by_template(self, template_id, rng=None):
        tpl = self.config.get_member_template(template_id)
        if not tpl:
            return None
        family = self.get_family()
        if not family:
            return None
        member = self._make_member(tpl, rng=rng)
        member["id"] = f"m_{family['next_member_id']}"
        family["next_member_id"] += 1
        family["members"].append(member)
        return member

    def remove_member(self, member_id):
        family = self.get_family()
        if not family:
            return False
        for i, m in enumerate(family["members"]):
            if m["id"] == member_id:
                family["members"].pop(i)
                return True
        return False

    def get_member(self, member_id):
        family = self.get_family()
        if not family:
            return None
        for m in family["members"]:
            if m["id"] == member_id:
                return m
        return None

    def assign_task(self, member_id, task):
        family = self.get_family()
        if not family:
            return False
        return self.task_mgr.assign_task(family, member_id, task)

    # ---------------- 建筑 ----------------
    def build_cost(self, building_id, current_level):
        b = self.config.get_building(building_id)
        if not b:
            return None
        mult = current_level + 1
        return {k: v * mult for k, v in b.get("base_cost", {}).items()}

    def build_or_upgrade(self, building_id):
        family = self.get_family()
        if not family:
            return False, "尚未创立家族。"
        b = self.config.get_building(building_id)
        if not b:
            return False, "未知建筑。"
        cur = family["buildings"].get(building_id, 0)
        if cur >= b.get("max_level", 5):
            return False, "已达最高等级。"
        cost = self.build_cost(building_id, cur)
        stone = cost.get("spirit_stone", 0)
        if family["treasury"] < stone:
            return False, f"家族金库灵石不足，需 {stone}。"
        family["treasury"] -= stone
        family["buildings"][building_id] = cur + 1
        return True, f"{b['name']} 升至 {cur + 1} 级。"

    # ---------------- 月度结算 ----------------
    def tick_monthly(self):
        """注册到 engine 的月度插座；未建家族或功能关闭时为纯 no-op。"""
        if not self.is_enabled() or not self.is_created():
            return
        self.monthly_settle()

    def monthly_settle(self):
        family = self.get_family()
        if not family:
            return
        family["_cfg"] = self.config
        month = self._current_month()
        family["month"] = month

        # 1) 成员产出
        task_logs = self.task_mgr.settle_monthly(family, rng=random)
        # 2) 建筑收入与维护
        income, upkeep = self._building_economy(family)
        family["treasury"] = family["treasury"] + income - upkeep
        family["total_income"] += income
        family["total_upkeep"] += upkeep
        if family["treasury"] < 0:
            deficit = -family["treasury"]
            family["treasury"] = 0
            # 金库亏空：全族忠诚受损
            for m in family["members"]:
                m["loyalty"] = max(0, m["loyalty"] - 5)
            task_logs.append(f"金库亏空 {deficit} 灵石，族众离心（-5 忠诚）。")
        # 3) 外交衰减
        self.diplo_mgr.settle_monthly(family, rng=random)
        # 4) 家族等级重算
        self._recompute_level(family)
        # 5) 事件触发（最多 1 个/月）
        ev = self.event_mgr.maybe_trigger(family, rng=random)
        if ev:
            family["pending_events"].append(ev)
            self.notify(f"[yellow]家族事件：{ev['name']} —— {ev['desc']}")
        # 6) 历史记录
        for line in task_logs:
            family["history"].append({"month": month, "text": line})
        family["history"] = family["history"][-50:]

    def _building_economy(self, family):
        cfg = self.config
        income = 0
        upkeep = 0
        for bid, lvl in family.get("buildings", {}).items():
            b = cfg.get_building(bid)
            if not b or lvl <= 0:
                continue
            upkeep += b.get("maintenance", 0) * lvl
            eff = b.get("effect", {})
            income += eff.get("income", 0) * lvl
            income += eff.get("reputation_monthly", 0) * lvl  # 声望转部分灵石等价
        return income, upkeep

    def _recompute_level(self, family):
        members = len(family.get("members", []))
        rep = family.get("reputation", 0)
        lvl = 1 + max(0, (members - 1) // 3) + max(0, rep // 200)
        family["level"] = lvl

    # ---------------- 转世联动 ----------------
    def can_inherit_as_heir(self):
        """玩家死亡转世时，若存在家族可选择以继承人身份继续。"""
        return self.is_created() and len(self.get_family().get("members", [])) > 1

    def inherit_as_heir(self):
        """转世为家族继承人：保留家族资产，原家主退位，次位成员继任。"""
        family = self.get_family()
        if not family:
            return False
        members = family.get("members", [])
        if len(members) <= 1:
            return False
        # 移除原家主（首位），其余成员继承
        members.pop(0)
        family["members"] = members
        family["history"].append({
            "month": family.get("month", 0),
            "text": "家主仙逝，族人推举新家主，家族传承不息。",
        })
        return True
