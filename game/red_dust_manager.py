# -*- coding: utf-8 -*-
"""
维度② 红尘炼心 / 入世（F-08 体验深化）。

修仙不止闭关苦修。暂别清修、投身凡尘，于市井烟火、情缘恩怨中淬炼心境：
- 入世历练（red_dust_active）开启后，月度结算自动经历红尘事件、结下羁绊；
- 羁绊分情缘/知己/挚友/红颜/恩怨五类，各对道心/心魔有不同牵引；
- 情劫（qingjie）随机降临，抉择永久改变道心与心魔；
- 归隐出尘时，红尘羁绊沉淀为心境（道心+，心魔+）。

本系统复用 player 既有的 mental_state（道心 0-100）/ heart_demon（心魔 0-100）
作为唯一真相源，所有新增状态持久化在 player 上：
- player.red_dust_active / red_dust_bonds / red_dust_months / red_dust_pending_qingjie
纯加法式接入，未入世时 tick 为 no-op，不影响任何旧系统行为。
"""

import json
import os
import random


class RedDustConfig:
    """加载维度②配置。"""

    def __init__(self, config_dir="config"):
        path = os.path.join(config_dir, "red_dust.json")
        with open(path, "r", encoding="utf-8") as f:
            self.data = json.load(f)

    def get_enter(self):
        return self.data.get("enter", {})

    def get_exit(self):
        return self.data.get("exit", {})

    def get_bond_types(self):
        return self.data.get("bond_types", {})

    def get_monthly_decay(self):
        return self.data.get("monthly_decay", {})

    def get_events(self):
        return self.data.get("red_dust_events", [])

    def get_qingjie(self):
        return self.data.get("qingjie_scenarios", [])

    def get_resonance(self):
        return self.data.get("bond_resonance", {})

    def get_warmth(self):
        return self.data.get("warmth", {})


class RedDustManager:
    """红尘炼心 / 入世管理器。"""

    def __init__(self, player, config_dir="config", notify_callback=None):
        self.player = player
        self.config = RedDustConfig(config_dir)
        self.notify = notify_callback or (lambda x: None)

    # ---------------- 状态读取 ----------------
    def is_active(self):
        return bool(getattr(self.player, "red_dust_active", False))

    # ---------------- 入世 / 出尘 ----------------
    def enter_red_dust(self):
        """入世历练：开启红尘淬心。"""
        if self.is_active():
            return False, "你已在红尘中历练。"
        self.player.red_dust_active = True
        if not isinstance(getattr(self.player, "red_dust_bonds", None), list):
            self.player.red_dust_bonds = []
        self.notify("[yellow]你暂别清修，入世历练，于凡尘烟火中淬炼心境。")
        return True, "已入世历练。"

    def exit_red_dust(self):
        """归隐出尘：结束历练，红尘羁绊沉淀为心境。"""
        if not self.is_active():
            return False, "你并未入世历练。"
        exit_cfg = self.config.get_exit()
        dao_per = exit_cfg.get("dao_heart_per_bond", 3)
        hd_per = exit_cfg.get("heart_demon_per_bond", 2)
        bonds = self.player.red_dust_bonds or []
        dao = dao_per * len(bonds)
        hd = hd_per * len(bonds)
        self._adjust_mental(dao)
        self._adjust_heart(hd)
        self.notify(
            f"[cyan]你归隐出尘：{len(bonds)} 段红尘羁绊沉淀为心境"
            f"（道心+{dao}，心魔+{hd}）。"
        )
        self.player.red_dust_active = False
        self.player.red_dust_bonds = []
        return True, "已归隐出尘，心境有所沉淀。"

    # ---------------- 主动历红尘 ----------------
    def experience(self):
        """主动历红尘：触发一次红尘事件（仅入世时可用）。"""
        if not self.is_active():
            return False, "你并未入世历练，无法历红尘。"
        evs = self.config.get_events()
        if not evs:
            return False, "红尘平静，无所经历。"
        ev = random.choice(evs)
        self._adjust_mental(ev.get("mental_delta", 0))
        self._adjust_heart(ev.get("heart_delta", 0))
        if random.random() < ev.get("bond_chance", 0.2):
            self._form_bond(ev.get("bond_type"))
        self.notify(
            f"[yellow]【红尘】{ev.get('name', '')}：{ev.get('description', '')}"
        )
        return True, ev.get("name", "历红尘")

    # ---------------- 月度结算 ----------------
    def tick_monthly(self):
        """月度推进：羁绊衰减 + 随机事件 + 情劫。未入世则为 no-op。"""
        if not self.is_active():
            return
        self.player.red_dust_months = getattr(self.player, "red_dust_months", 0) + 1
        # 羁绊亲密度自然衰减
        decay = self.config.get_monthly_decay().get("intimacy_decay_per_month", 4)
        for b in (self.player.red_dust_bonds or []):
            b["intimacy"] = max(0, b.get("intimacy", 0) - decay)
        # 随机事件（含可能结缘）
        enter = self.config.get_enter()
        if random.random() < enter.get("event_chance", 0.55):
            self._maybe_event()
        elif random.random() < enter.get("bond_gain_chance", 0.45):
            self._form_bond()
        # 情劫
        self._maybe_qingjie()
        # 羁绊共鸣：高亲密度羁绊稳定滋养道心 / 抑制心魔
        self._apply_resonance_tick()

    def _maybe_event(self):
        evs = self.config.get_events()
        if not evs:
            return
        ev = random.choice(evs)
        self._adjust_mental(ev.get("mental_delta", 0))
        self._adjust_heart(ev.get("heart_delta", 0))
        if random.random() < ev.get("bond_chance", 0.2):
            self._form_bond(ev.get("bond_type"))
        self.notify(
            f"[yellow]【红尘】{ev.get('name', '')}：{ev.get('description', '')}"
        )

    def _form_bond(self, bond_type=None):
        types = self.config.get_bond_types()
        if not types:
            return
        if bond_type is None or bond_type not in types:
            bond_type = random.choice(list(types.keys()))
        spec = types[bond_type]
        bonds = self.player.red_dust_bonds or []
        # 已存在同类羁绊则提升亲密度
        for b in bonds:
            if b.get("type") == bond_type:
                b["intimacy"] = min(
                    spec.get("intimacy_max", 100), b.get("intimacy", 0) + 10
                )
                self.player.red_dust_bonds = bonds
                return
        bonds.append({
            "type": bond_type,
            "name": spec.get("name", bond_type),
            "intimacy": 10,
        })
        self.player.red_dust_bonds = bonds
        self._adjust_mental(spec.get("mental_gain", 0))
        self._adjust_heart(spec.get("heart_gain", 0))
        self.notify(
            f"[magenta]你于红尘中结下「{spec.get('name', bond_type)}」之缘。"
        )

    def _maybe_qingjie(self):
        if getattr(self.player, "red_dust_pending_qingjie", None):
            return
        enter = self.config.get_enter()
        if random.random() >= enter.get("qingjie_chance", 0.08):
            return
        qjs = self.config.get_qingjie()
        if not qjs:
            return
        self.player.red_dust_pending_qingjie = random.choice(qjs)
        self.notify(
            f"[red]情劫将至：{self.player.red_dust_pending_qingjie.get('name', '')}！"
        )

    # ---------------- 情劫抉择 ----------------
    def apply_qingjie_choice(self, choice_id):
        """应用情劫抉择。返回 (ok, message)。"""
        scenario = getattr(self.player, "red_dust_pending_qingjie", None)
        if not scenario:
            return False, "当前无情劫待了断。"
        choice = next(
            (c for c in scenario.get("choices", []) if c.get("id") == choice_id),
            None,
        )
        if not choice:
            return False, "无效的抉择。"
        eff = choice.get("effects", {})
        self._adjust_mental(eff.get("mental_delta", 0))
        self._adjust_heart(eff.get("heart_delta", 0))
        text = choice.get("result_text", "")
        self.notify(f"[purple]你于情劫中抉择：{text}")
        self.player.red_dust_pending_qingjie = None
        return True, text

    # ---------------- 羁绊共鸣 ----------------
    def _resonance_for(self, bond):
        """返回该羁绊当前生效的最高共鸣档（intimacy >= min_intimacy 的最高档）。"""
        bt = bond.get("type")
        tiers = self.config.get_resonance().get(bt)
        if not tiers:
            return None
        intimacy = bond.get("intimacy", 0)
        chosen = None
        for tier in tiers:
            if intimacy >= tier.get("min_intimacy", 999):
                chosen = tier
        return chosen

    def get_resonances(self):
        """返回每条羁绊的共鸣状态，供 UI。resonance 为当前生效档，next 为下一档（含所需阈值）。"""
        out = []
        tiers_map = self.config.get_resonance()
        for b in (self.player.red_dust_bonds or []):
            bt = b.get("type")
            tiers = tiers_map.get(bt, [])
            cur = self._resonance_for(b)
            nxt = None
            for t in tiers:
                if b.get("intimacy", 0) < t.get("min_intimacy", 999):
                    nxt = t
                    break
            out.append({
                "type": bt,
                "name": b.get("name", bt),
                "intimacy": b.get("intimacy", 0),
                "resonance": cur,
                "next": nxt,
            })
        return out

    def _apply_resonance_tick(self):
        """月度共鸣结算：对每条已解锁共鸣的羁绊，稳定滋养道心 / 抑制心魔。

        独立于随机事件/情劫，便于确定性测试；在 tick_monthly 末尾调用。
        """
        for b in (self.player.red_dust_bonds or []):
            res = self._resonance_for(b)
            if not res:
                continue
            self._adjust_mental(res.get("monthly_mental", 0))
            self._adjust_heart(res.get("monthly_heart", 0))

    # ---------------- 温养羁绊 ----------------
    def warm_bond(self, bond_type):
        """以灵石温养某段羁绊，提升其亲密度（不超过 intimacy_max）。返回 (ok, message)。"""
        if not self.is_active():
            return False, "你并未入世历练，无法温养羁绊。"
        bonds = self.player.red_dust_bonds or []
        bond = next((b for b in bonds if b.get("type") == bond_type), None)
        if not bond:
            return False, "你与此人并无羁绊可温养。"
        spec = self.config.get_bond_types().get(bond_type, {})
        cap = spec.get("intimacy_max", 100)
        if bond.get("intimacy", 0) >= cap:
            return False, "此段羁绊已至情深义重，无需再温养。"
        warmth = self.config.get_warmth()
        cost_item = warmth.get("cost_item")
        cost_count = int(warmth.get("cost_count", 0) or 0)
        gain = int(warmth.get("intimacy_gain", 0) or 0)
        if cost_item and cost_count > 0:
            counter = getattr(self.player, "count_item", None)
            if counter is None or counter(cost_item) < cost_count:
                return False, f"温养需消耗 {cost_count} 枚{cost_item}，你灵石不足。"
            self.player.consume_items(cost_item, cost_count)
        bond["intimacy"] = min(cap, bond.get("intimacy", 0) + gain)
        self.player.red_dust_bonds = bonds
        self.notify(
            f"[magenta]你以灵石温养与「{spec.get('name', bond_type)}」之情，亲密度升至 {bond['intimacy']}。"
        )
        return True, "羁绊温养成功。"

    # ---------------- 工具 ----------------
    def _adjust_mental(self, delta):
        if not delta:
            return
        v = max(0, min(100, int(getattr(self.player, "mental_state", 50)) + int(delta)))
        self.player.mental_state = v

    def _adjust_heart(self, delta):
        if not delta:
            return
        v = max(0, min(100, int(getattr(self.player, "heart_demon", 0)) + int(delta)))
        self.player.heart_demon = v

    # ---------------- 供 UI ----------------
    def get_status(self):
        warmth = self.config.get_warmth()
        return {
            "active": self.is_active(),
            "months": getattr(self.player, "red_dust_months", 0),
            "bonds": [dict(b) for b in (self.player.red_dust_bonds or [])],
            "resonances": self.get_resonances(),
            "mental_state": getattr(self.player, "mental_state", 50),
            "heart_demon": getattr(self.player, "heart_demon", 0),
            "pending_qingjie": getattr(self.player, "red_dust_pending_qingjie", None),
            "bond_types": self.config.get_bond_types(),
            "enter": self.config.get_enter(),
            "exit": self.config.get_exit(),
            "warmth": {
                "cost_item": warmth.get("cost_item"),
                "cost_count": warmth.get("cost_count", 0),
                "intimacy_gain": warmth.get("intimacy_gain", 0),
                "desc": warmth.get("desc", ""),
            },
        }
