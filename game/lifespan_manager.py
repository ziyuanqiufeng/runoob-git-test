# -*- coding: utf-8 -*-
"""
维度⑤ 寿元与轮回晚年（F-09）。

复用 player 的 age / max_lifespan 与既有 ReincarnationManager（转世 / 前世天赋）。
本模块补足三条新增链路：
- 坐化安排后事（继承人 / 留功法 / 引爆法宝）→ 转世时转化为前世遗产
- 残魂夺舍 / 器灵化身：肉身死亡但神魂强大者，化为残魂依附法宝 / 灵兽
- 前世遗迹回响：转世后探索时概率触发呼应往世因果的事件

全部加法式接入，状态持久化在 player 上：
- player.sit_pending / player.past_life_arrangements
- player.remnant_soul / player.is_remnant / player.remnant_months
- player.past_life_relics
"""

import json
import os
import random


class LifespanConfig:
    """加载维度⑤配置。"""

    def __init__(self, config_dir="config"):
        path = os.path.join(config_dir, "lifespan.json")
        with open(path, "r", encoding="utf-8") as f:
            self.data = json.load(f)

    def get_sit(self):
        return self.data.get("sit_and_dissolve", {})

    def get_remnant(self):
        return self.data.get("remnant_soul", {})

    def get_forms(self):
        return self.get_remnant().get("forms", [])

    def get_default_form(self):
        return self.get_remnant().get("default_form", "formless")

    def get_relics(self):
        return self.data.get("past_life_relics", {})

    def get_relic_chains(self):
        return self.data.get("relic_chains", {}).get("chains", [])


# 前世遗物链加成键：属性类为纯加法，速度类叠加既有的转世修炼/突破修正。
_RELIC_CHAIN_BONUS_KEYS = (
    "wisdom", "luck", "constitution", "max_health",
    "cultivation_speed", "breakthrough_bonus",
)


def compute_relic_chain_bonus(relic_chain_ids, config_dir="config"):
    """按玩家持久遗物链集合，聚合所有链的永久加成。

    relic_chain_ids：跨世累积的遗物 id 集合（player.relic_chain）。
    返回包含六个加成键的字典；任一链每收集到一个 link 计 per_link，集齐全部 link 额外计 set。
    为纯函数，便于测试与转世流程复用（reincarnation_manager 调用于新世生成）。
    """
    cfg = LifespanConfig(config_dir)
    chains = cfg.get_relic_chains()
    bonus = {k: 0 for k in _RELIC_CHAIN_BONUS_KEYS}
    if not chains:
        return bonus
    owned = set(relic_chain_ids or [])
    for ch in chains:
        links = ch.get("links", []) or []
        found = sum(1 for lid in links if lid in owned)
        per = ch.get("per_link", {}) or {}
        for k in bonus:
            if k in per:
                bonus[k] += per[k] * found
        if links and found >= len(links):
            s = ch.get("set", {}) or {}
            for k in bonus:
                if k in s:
                    bonus[k] += s[k]
    return bonus


class LifespanManager:
    """寿元与轮回晚年管理器。"""

    def __init__(self, player, config_dir="config", notify_callback=None):
        self.player = player
        self.config = LifespanConfig(config_dir)
        self.notify = notify_callback or (lambda x: None)

    # ---------------- 坐化 ----------------
    def is_near_end(self):
        """是否临近寿元尽头（可安排坐化）。"""
        near = self.config.get_sit().get("near_end_years", 10)
        return getattr(self.player, "age", 0) >= (
            getattr(self.player, "max_lifespan", 100) - near
        )

    def arrange_sit(self, arrangements):
        """安排坐化后事。arrangements 为 {heir/leave_manual/detonate_treasure: True}。"""
        if not self.is_near_end():
            return False, "寿元尚丰，无需安排坐化后事。"
        valid = set(self.config.get_sit().get("arrangements", {}).keys())
        chosen = {k: True for k in arrangements if k in valid}
        if not chosen:
            return False, "未选择任何有效的后事安排。"
        self.player.sit_pending = True
        self.player.past_life_arrangements = chosen
        self.notify("[cyan]你已在心中安排好后事，静待坐化之时。")
        return True, "后事已安排。"

    def on_death(self):
        """肉身死亡时由引擎调用，将坐化安排转化为前世遗产。返回摘要列表。"""
        summary = []
        arrangements = getattr(self.player, "past_life_arrangements", None) or {}
        if not arrangements:
            return summary
        for key in arrangements:
            spec = self.config.get_sit().get("arrangements", {}).get(key, {})
            effect = spec.get("past_life_effect")
            if effect == "manual_relic":
                is_new = self._record_relic("legacy_manual", "毕生功法残卷")
                if is_new:
                    self.notify("[magenta]前世遗物入链：毕生功法残卷")
                summary.append("坐化所留功法将化为前世遗泽，转世后有缘重得。")
            elif effect == "inheritance_boon":
                summary.append("衣钵传于继承人，转世后其势力对你天然亲近。")
            elif effect == "enemy_curse":
                summary.append("本命法宝自爆重创仇敌，转世后其势力气运受损。")
        self.player.sit_pending = False
        self.player.past_life_arrangements = {}
        return summary

    # ---------------- 残魂 / 器灵化身 ----------------
    def can_become_remnant(self):
        """是否具备化作残魂的资格（神魂强大：境界达标）。"""
        order = getattr(self.player, "REALM_ORDER", {}).get(
            getattr(self.player, "realm_id", ""), 1
        )
        return order >= self.config.get_remnant().get("min_realm_order", 18)

    def become_remnant_soul(self, host_type, host_id=None):
        """肉身陨落（或主动）后化为残魂，依附法宝 / 灵兽。"""
        if not self.can_become_remnant():
            return False, "神魂尚弱，不足以凝为残魂。"
        if host_type not in self.config.get_remnant().get("host_types", []):
            return False, "未知的残魂依附载体。"
        form = self._select_form(host_type)
        self.player.remnant_soul = {
            "host_type": host_type,
            "host_id": host_id,
            "form": form.get("id") if form else self.config.get_default_form(),
        }
        self.player.is_remnant = True
        self.player.remnant_months = 0
        form_name = form.get("name", "残魂") if form else "残魂"
        self.notify(
            f"[magenta]你神魂不灭，化为「{form_name}」依附于「{host_type}」，以器灵 / 兽灵之姿继续存续。"
        )
        return True, "已凝为残魂。"

    def tick_remnant_soul(self):
        """月度推进残魂：累计月份、应用形态月度被动，按概率重塑肉身。返回是否重塑成功。"""
        if not getattr(self.player, "is_remnant", False):
            return False
        self.player.remnant_months = getattr(self.player, "remnant_months", 0) + 1
        self._apply_form_passive()
        cfg = self.config.get_remnant()
        min_months = cfg.get("min_months_as_remnant", 3)
        if self.player.remnant_months < min_months:
            return False
        soul = getattr(self.player, "remnant_soul", None)
        form = self._get_form(soul.get("form")) if isinstance(soul, dict) else None
        bonus = 0.0
        if form:
            bonus = float(form.get("monthly_passive", {}).get("reshape_bonus", 0.0))
        if random.random() < cfg.get("reshape_chance_per_month", 0.03) + bonus:
            self.player.is_remnant = False
            self.player.remnant_soul = None
            self.player.health = max(1, self.player.health)
            self.notify("[green]残魂历经劫数，终得重塑肉身，重归世间！")
            return True
        return False

    # ---------------- 残魂形态 ----------------
    def _get_form(self, form_id):
        """按 id 取形态配置；缺失时回退到 default_form。"""
        forms = self.config.get_forms()
        for f in forms:
            if f.get("id") == form_id:
                return f
        for f in forms:
            if f.get("id") == self.config.get_default_form():
                return f
        return None

    def _select_form(self, host_type):
        """根据玩家神魂资质与依附载体，选择匹配的残魂形态（取满足条件中 min_mental_state 最高者）。"""
        ms = getattr(self.player, "mental_state", 50)
        hd = getattr(self.player, "heart_demon", 0)
        default_id = self.config.get_default_form()
        best = None
        best_min = -1
        for f in self.config.get_forms():
            if f.get("id") == default_id:
                continue
            if ms < int(f.get("min_mental_state", 0)):
                continue
            if hd > int(f.get("max_heart_demon", 99)):
                continue
            req = f.get("require_host")
            if req and req != host_type:
                continue
            fmin = int(f.get("min_mental_state", 0))
            if fmin > best_min:
                best = f
                best_min = fmin
        if best is None:
            return self._get_form(default_id)
        return best

    def _apply_form_passive(self):
        """应用当前残魂形态的月度被动（道心 / 心魔修正，钳制 0–100）。"""
        soul = getattr(self.player, "remnant_soul", None)
        if not isinstance(soul, dict):
            return
        form = self._get_form(soul.get("form"))
        if not form:
            return
        passive = form.get("monthly_passive", {}) or {}
        ms = getattr(self.player, "mental_state", 50)
        hd = getattr(self.player, "heart_demon", 0)
        ms = max(0, min(100, ms + int(passive.get("mental_delta", 0))))
        hd = max(0, min(100, hd + int(passive.get("heart_delta", 0))))
        self.player.mental_state = ms
        self.player.heart_demon = hd

    def _form_status(self):
        """供 UI 展示当前残魂形态。"""
        soul = getattr(self.player, "remnant_soul", None)
        if not isinstance(soul, dict) or not getattr(self.player, "is_remnant", False):
            return None
        form = self._get_form(soul.get("form"))
        if not form:
            return None
        return {
            "id": form.get("id"),
            "name": form.get("name"),
            "desc": form.get("desc"),
            "monthly_passive": form.get("monthly_passive", {}),
        }

    # ---------------- 前世遗迹回响 ----------------
    def _record_relic(self, relic_id, name):
        """记录一件前世遗物：写入本世 past_life_relics（叙事），并去重并入持久
        relic_chain（驱动跨世链之加持）。返回是否为首次入链（True 表示新 link）。"""
        relics = getattr(self.player, "past_life_relics", []) or []
        relics.append({"id": relic_id, "name": name})
        self.player.past_life_relics = relics
        chain = getattr(self.player, "relic_chain", None)
        if chain is None:
            chain = []
            self.player.relic_chain = chain
        if relic_id not in chain:
            chain.append(relic_id)
            return True
        return False

    def get_relic_chain_status(self):
        """供 UI 展示每条遗物链的收集进度与已/将获加成。"""
        chains = self.config.get_relic_chains()
        owned = set(getattr(self.player, "relic_chain", []) or [])
        result = []
        for ch in chains:
            links = ch.get("links", []) or []
            found = [lid for lid in links if lid in owned]
            done = bool(links) and len(found) == len(links)
            result.append({
                "id": ch.get("id"),
                "name": ch.get("name"),
                "desc": ch.get("desc"),
                "total": len(links),
                "found": len(found),
                "found_ids": found,
                "per_link": ch.get("per_link", {}),
                "set": ch.get("set", {}),
                "complete": done,
            })
        return result

    def roll_past_life_echo(self):
        """探索时按概率触发前世回响。返回事件文本或 None。"""
        if getattr(self.player, "reincarnation_count", 0) <= 0:
            return None
        chance = self.config.get_relics().get("echo_chance_on_explore", 0.15)
        if random.random() >= chance:
            return None
        pool = self.config.get_relics().get("echo_events", [])
        if not pool:
            return None
        echo = random.choice(pool)
        # 同时有概率拾得一件前世遗物（首次拾得即入链，转世后获链之加持）
        relics = self.config.get_relics().get("relic_pool", [])
        if relics and random.random() < 0.5:
            relic = random.choice(relics)
            is_new = self._record_relic(relic["id"], relic["name"])
            self.notify(f"[magenta]前世遗物：{relic['name']}（{relic['echo']}）")
            if is_new:
                self.notify("[magenta]此遗物首次入链，转世后将获链之加持。")
        self.notify(f"[magenta]{echo}")
        return echo

    def get_status(self):
        """供 UI 展示。"""
        return {
            "age": getattr(self.player, "age", 0),
            "max_lifespan": getattr(self.player, "max_lifespan", 100),
            "is_near_end": self.is_near_end(),
            "sit_pending": getattr(self.player, "sit_pending", False),
            "arrangements": getattr(self.player, "past_life_arrangements", None),
            "is_remnant": getattr(self.player, "is_remnant", False),
            "remnant_soul": getattr(self.player, "remnant_soul", None),
            "remnant_form": self._form_status(),
            "remnant_months": getattr(self.player, "remnant_months", 0),
            "past_life_relics": getattr(self.player, "past_life_relics", []),
            "relic_chain": getattr(self.player, "relic_chain", []),
            "relic_chains_status": self.get_relic_chain_status(),
            "reincarnation_count": getattr(self.player, "reincarnation_count", 0),
        }
