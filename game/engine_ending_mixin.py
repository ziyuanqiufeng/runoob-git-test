# -*- coding: utf-8 -*-
"""引擎结局/飞升域与主线剧情域 Mixin。

GameEngine 继承本文件中的两个 Mixin。方法通过鸭子类型访问引擎成员
（player/notify/chronicle_manager/_auto_save/config_dir 等）。
"""
import json
import os
import random


class EndingMixin:
    """多结局系统：结局加载、条件判定、触发与飞升尝试。"""

    # ==================== 多结局系统 ====================

    def _load_endings(self):
        """读取多结局定义 config/endings.json；失败返回空映射。"""
        path = os.path.join(self.config_dir, "endings.json")
        if not os.path.exists(path):
            return {"endings": [], "fallback": None}
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError):
            return {"endings": [], "fallback": None}
        if not isinstance(data, dict):
            return {"endings": [], "fallback": None}
        return {
            "endings": [e for e in data.get("endings", []) if isinstance(e, dict)],
            "fallback": data.get("fallback"),
        }

    def _check_ending_conditions(self, ending):
        """检查玩家是否满足某个结局的全部条件。"""
        cond = ending.get("conditions", {}) or {}
        p = self.player
        karma = getattr(p, "karma", 0)
        heart_demon = getattr(p, "heart_demon", 0)
        heaven_gaze = getattr(p, "heaven_gaze", 0)
        bonds = len(getattr(p, "red_dust_bonds", []) or [])
        if "karma_min" in cond and karma < cond["karma_min"]:
            return False
        if "karma_max" in cond and karma > cond["karma_max"]:
            return False
        if "heart_demon_min" in cond and heart_demon < cond["heart_demon_min"]:
            return False
        if "heart_demon_max" in cond and heart_demon > cond["heart_demon_max"]:
            return False
        if "heaven_gaze_min" in cond and heaven_gaze < cond["heaven_gaze_min"]:
            return False
        if "heaven_gaze_max" in cond and heaven_gaze > cond["heaven_gaze_max"]:
            return False
        if "red_dust_bonds_min" in cond and bonds < cond["red_dust_bonds_min"]:
            return False
        return True

    def _judge_ending(self, context):
        """根据触发场景与玩家状态判定结局，返回结局 dict；无匹配返回 None。"""
        endings = self._endings.get("endings", [])
        candidates = [e for e in endings if e.get("context") == context]
        candidates.sort(key=lambda e: e.get("priority", 999))
        for e in candidates:
            if self._check_ending_conditions(e):
                return e
        fallback_id = self._endings.get("fallback")
        for e in endings:
            if e.get("id") == fallback_id:
                return e
        return None

    def _trigger_ending(self, context):
        """判定并记录结局，返回结局 dict（已记录则返回 None）。"""
        if getattr(self.player, "ending_id", None):
            return None
        ending = self._judge_ending(context)
        if not ending:
            return None
        self.player.ending_id = ending["id"]
        if context == "ascend":
            self.player.has_won = True
        self.notify(f"[gold]【结局】{ending['name']}：{ending['desc']}")
        self.chronicle_manager.record(
            f"达成结局【{ending['name']}】", category="ending"
        )
        self.notify(f"__ENDING__:{ending['id']}")
        self._check_main_story()
        self._auto_save()
        return ending

    # 天门试炼默认参数（config/ascension.json 可覆盖）
    ASCENSION_DEFAULTS = {
        "heart_demon_fail": 80, "heart_demon_wound": 50,
        "heaven_gaze_fail": 90,
        "base_rate": 0.5, "pill_bonus": 0.30,
        "mental_gate": 80, "mental_bonus": 0.10, "wound_penalty": 0.10,
        "heart_demon_rate_drag": 200.0, "heaven_gaze_rate_drag": 250.0,
        "stone_burn_ratio": 0.5,
        "fail_qi_penalty": 0.7, "fail_hp_penalty": 0.5,
        "fail_lifespan_cost": 30, "fail_gaze_gain": 10,
    }

    def _load_ascension_config(self):
        """读取天门试炼参数 config/ascension.json；缺失字段用默认兜底。"""
        path = os.path.join(self.config_dir, "ascension.json")
        cfg = dict(self.ASCENSION_DEFAULTS)
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                for k, v in data.items():
                    if k in cfg and isinstance(v, (int, float)):
                        cfg[k] = v
        except (json.JSONDecodeError, OSError):
            pass
        return cfg

    def _attempt_ascension(self):
        """炼虚圆满冲击天门：三阶段试炼（问心 → 渡雷 → 天门一跃）。

        - 问心/渡雷各有红线（心魔 80+/天道注视 90+），触发即对应坏结局；
        - 天门一跃为概率判定（受心魔/天道注视/道心/飞升丹影响），
          **普通失败不再直接结局**：兵解重创（qi/hp/寿元折损、天道注视+10），
          玩家可重整旗鼓再次冲击（返回 None，游戏继续）。
        """
        p = self.player
        cfg = self._load_ascension_config()

        # 阶段一·问心（心魔大劫）：红线直接走火入魔
        if getattr(p, "heart_demon", 0) >= cfg["heart_demon_fail"]:
            self.notify("[red]天门之前心魔大盛，你道心崩碎，走火入魔！")
            return self._trigger_ending("ascend_fail")
        # 道基蒙尘：心魔 50+ 未过问心，天门一跃减益
        wounded = getattr(p, "heart_demon", 0) >= cfg["heart_demon_wound"]
        if wounded:
            self.notify("[purple]心魔未净，你强压杂念踏入天门，道基隐隐不稳……")

        # 阶段二·渡雷（天道神雷）：红线直接天道降罚
        if getattr(p, "heaven_gaze", 0) >= cfg["heaven_gaze_fail"]:
            self.notify("[red]天道注视已久，天门神雷化作灭世之罚！")
            return self._trigger_ending("ascend_fail")

        # 阶段三·天门一跃：资源豪赌 + 概率判定
        burn = int(getattr(p, "spirit_stones", 0) * cfg["stone_burn_ratio"])
        p.spirit_stones = getattr(p, "spirit_stones", 0) - burn
        pill_used = False
        for item in list(p.inventory):
            if item.id == "ascension_pill":
                p.remove_item(item)
                pill_used = True
                break

        rate = cfg["base_rate"]
        rate -= getattr(p, "heart_demon", 0) / cfg["heart_demon_rate_drag"]
        rate -= getattr(p, "heaven_gaze", 0) / cfg["heaven_gaze_rate_drag"]
        if pill_used:
            rate += cfg["pill_bonus"]
        if getattr(p, "mental_state", 50) >= cfg["mental_gate"]:
            rate += cfg["mental_bonus"]
        if wounded:
            rate -= cfg["wound_penalty"]
        rate = max(0.05, min(0.95, rate))

        extra = []
        if burn > 0:
            extra.append(f"燃灵石 {burn}")
        if pill_used:
            extra.append("服飞升丹")
        ctx = f"（{'、'.join(extra) or '孤注一掷'}，成功率 {int(rate * 100)}%）"

        if random.random() < rate:
            self.notify(f"[gold]天门轰然洞开！{ctx}——你跨过最后一道天堑，白日飞升！")
            return self._trigger_ending("ascend")

        # 折戟天门：兵解重创，可重整再战（不触发结局）
        p.qi = int(p.qi * (1 - cfg["fail_qi_penalty"]))
        p.health = max(1, int(p.health * (1 - cfg["fail_hp_penalty"])))
        p.max_lifespan = max(p.age + 1, p.max_lifespan - cfg["fail_lifespan_cost"])
        p.heaven_gaze = min(100, getattr(p, "heaven_gaze", 0) + cfg["fail_gaze_gain"])
        self.notify(
            f"[red]天门一跃失败！{ctx}——你兵解重创，修为折损七成，"
            f"寿元折损 {cfg['fail_lifespan_cost']} 载，天道注视愈深。"
            "整理道基之后，天门仍为你而开。"
        )
        self._check_death()
        return None


class MainStoryMixin:
    """主线剧情：章节加载、条件检查与推进。"""

    # ==================== 主线剧情 ====================

    def _load_main_story(self):
        """读取主线章节 config/main_story.json；失败返回空映射。"""
        path = os.path.join(self.config_dir, "main_story.json")
        if not os.path.exists(path):
            return {"chapters": []}
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError):
            return {"chapters": []}
        if not isinstance(data, dict):
            return {"chapters": []}
        return {"chapters": [c for c in data.get("chapters", []) if isinstance(c, dict)]}

    def _meet_story_condition(self, cond):
        """判断玩家是否满足主线章节的完成条件。"""
        cond = cond or {}
        t = cond.get("type")
        if t == "sect":
            return bool(getattr(self.player, "sect_id", None))
        if t == "realm":
            order = self.player.REALM_ORDER.get(self.player.realm_id, 0)
            return order >= cond.get("order", 0)
        if t == "ending":
            return getattr(self.player, "ending_id", None) is not None
        return False

    def _check_main_story(self):
        """检查当前主线章节是否完成，完成则推进到下一章。"""
        chapters = self._main_story.get("chapters", [])
        if not chapters:
            return
        step = getattr(self.player, "main_story_step", 0)
        if step >= len(chapters):
            return
        cur = chapters[step]
        if not self._meet_story_condition(cur.get("condition")):
            return
        self.player.main_story_step = step + 1
        self.notify(f"[gold]【主线】{cur.get('title', '')} 完成！")
        self.chronicle_manager.record(
            f"完成主线章节【{cur.get('title', '')}】", category="quest"
        )
        if step + 1 < len(chapters):
            nxt = chapters[step + 1]
            self.notify(f"[cyan]【主线】{nxt.get('title', '')}：{nxt.get('desc', '')}")
        else:
            self.notify("[gold]【主线】全部章节完成，你已走完问道长生之路！")
        self._auto_save()

    def get_main_story_progress(self):
        """返回当前主线章节 (title, desc, current, total)；已完成返回 None。"""
        chapters = self._main_story.get("chapters", [])
        if not chapters:
            return None
        step = getattr(self.player, "main_story_step", 0)
        if step >= len(chapters):
            return None
        cur = chapters[step]
        return (cur.get("title", ""), cur.get("desc", ""), step + 1, len(chapters))

    def _story_condition_hint(self, cond):
        """把主线完成条件翻译成玩家可读的行动提示。"""
        cond = cond or {}
        t = cond.get("type")
        if t == "sect":
            return "加入一方宗门"
        if t == "realm":
            order = cond.get("order", 0)
            realm_id = {v: k for k, v in self.player.REALM_ORDER.items()}.get(order)
            name = None
            if realm_id:
                realm = self.world.get_realm(realm_id)
                name = realm.get("name") if isinstance(realm, dict) else None
            return f"修为达到【{name or order}】"
        if t == "ending":
            return "达成任意结局"
        return "继续修行"

    def get_main_story_hint(self):
        """返回当前主线章节的行动提示（str）；无进行中章节返回 None。"""
        chapters = self._main_story.get("chapters", [])
        step = getattr(self.player, "main_story_step", 0)
        if not chapters or step >= len(chapters):
            return None
        return self._story_condition_hint(chapters[step].get("condition"))
