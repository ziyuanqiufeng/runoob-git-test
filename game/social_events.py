# -*- coding: utf-8 -*-
"""NPC 主动事件系统（AI 角色引擎二期）：NPC 根据关系状态主动发起交互。

挂载于月度结算插座，每月判定：
- 道侣赠礼：亲密度达标的道侣随机送来丹药
- 师父传功/弟子聆教：师徒关系定期触发修为互动
- 宿敌寻衅：恩怨未解的 NPC 随机上门寻衅（小额健康代价）

所有触发写入 player.npc_memory 的共同经历（moments），让角色"记得"这些往来。
冷却状态持久化于 player.social_event_state（跨存档）。
"""
import json
import os
import random

from game.constants import realm_qi_scale

DEFAULTS = {
    "dao_lv_gift": {"chance": 0.08, "cooldown_months": 12,
                    "min_intimacy": 40, "items": ["qi_pill", "healing_pill"]},
    "master_teaching": {"chance": 0.06, "cooldown_months": 24, "qi_base": 30},
    "rival_ambush": {"chance": 0.05, "cooldown_months": 18,
                     "min_grudge_level": 1, "hp_penalty_ratio": 0.10},
    "friend_visit": {"chance": 0.07, "cooldown_months": 12,
                     "min_favor": 50, "mental_gain": 5},
    "disciple_defect": {"chance": 0.03, "cooldown_months": 36,
                        "grudge_reason": "师门恩义已尽"},
    "rumor": {"chance": 0.06, "cooldown_months": 6},
}


class SocialEventConfig:
    """加载 NPC 主动事件配置。"""

    def __init__(self, config_dir="config"):
        path = os.path.join(config_dir, "social_events.json")
        merged = json.loads(json.dumps(DEFAULTS))  # 深拷贝默认值
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            for k, v in data.items():
                if k.startswith("_"):
                    continue
                if isinstance(v, dict) and k in merged:
                    merged[k].update(v)
                else:
                    merged[k] = v
        except (json.JSONDecodeError, OSError):
            pass
        self.data = merged

    def get(self, event_id):
        return self.data.get(event_id, {})


class SocialEventManager:
    """NPC 主动事件的月度判定与结算。"""

    def __init__(self, player, npc_library, item_library, world,
                 config_dir="config", notify_callback=None):
        self.player = player
        self.npc_library = npc_library
        self.item_library = item_library
        self.world = world
        self.config = SocialEventConfig(config_dir)
        self.notify_callback = notify_callback or (lambda msg: None)

    # ---------- 基础工具 ----------
    def _notify(self, msg):
        self.notify_callback(msg)

    def _month_index(self):
        return (self.world.year - 1) * 12 + self.world.month

    def _ready(self, key, cooldown_months):
        state = getattr(self.player, "social_event_state", {})
        last = state.get(key, -99999)
        return self._month_index() - last >= cooldown_months

    def _mark(self, key):
        state = getattr(self.player, "social_event_state", {})
        state[key] = self._month_index()
        self.player.social_event_state = state

    def _npc_name(self, npc_id):
        npc = self.npc_library.get(npc_id)
        return npc.name if npc else npc_id

    @staticmethod
    def _roll(chance):
        return random.random() < chance

    # ---------- 月度入口 ----------
    def tick_monthly(self):
        if not self.player.is_alive():
            return
        self._maybe_dao_lv_gift()
        self._maybe_master_teaching()
        self._maybe_rival_ambush()
        self._maybe_friend_visit()
        self._maybe_disciple_defect()
        self._maybe_rumor()

    # ---------- 事件：道侣赠礼 ----------
    def _maybe_dao_lv_gift(self):
        cfg = self.config.get("dao_lv_gift")
        companions = getattr(self.player, "companions", []) or []
        eligible = [c for c in companions
                    if c.get("intimacy", 0) >= cfg.get("min_intimacy", 40)]
        if not eligible or not self._roll(cfg.get("chance", 0.0)):
            return
        bond = random.choice(eligible)
        key = f"dao_lv_gift:{bond['npc_id']}"
        if not self._ready(key, cfg.get("cooldown_months", 12)):
            return
        pool = cfg.get("items", ["qi_pill"])
        item_id = random.choice(pool)
        item = self.item_library.create(item_id)
        if not item:
            return
        self.player.add_item(item)
        self._mark(key)
        self._notify(
            f"[cyan]【道侣】远方的{bond.get('name', bond['npc_id'])}"
            f"托人送来一枚【{item.name}】，附言：愿君道途顺遂。"
        )
        self.player.record_npc_moment(
            bond["npc_id"],
            f"第{self.world.year}年：TA送来一枚【{item.name}】，情意附于其上",
        )

    # ---------- 事件：师徒互动 ----------
    def _maybe_master_teaching(self):
        cfg = self.config.get("master_teaching")
        disciples = getattr(self.player, "disciples", []) or []
        if not disciples or not self._roll(cfg.get("chance", 0.0)):
            return
        disciple = random.choice(disciples)
        key = f"master_teaching:{disciple['npc_id']}"
        if not self._ready(key, cfg.get("cooldown_months", 24)):
            return
        realm = self.world.get_realm(self.player.realm_id)
        order = realm["order"] if realm else 1
        gain = int(cfg.get("qi_base", 30) * realm_qi_scale(order))
        self.player.qi += gain
        self._mark(key)
        d_name = disciple.get("name", disciple["npc_id"])
        self._notify(
            f"[cyan]【师徒】弟子{d_name}前来聆教，你倾囊相授，"
            f"教学相长（修为 +{gain}）。"
        )
        self.player.record_npc_moment(
            disciple["npc_id"],
            f"第{self.world.year}年：聆教论道，师徒俱有所得",
        )

    # ---------- 事件：宿敌寻衅 ----------
    def _maybe_rival_ambush(self):
        cfg = self.config.get("rival_ambush")
        grudges = getattr(self.player, "grudges", {}) or {}
        if not grudges or not self._roll(cfg.get("chance", 0.0)):
            return
        min_level = cfg.get("min_grudge_level", 1)
        candidates = [(nid, g) for nid, g in grudges.items()
                      if g.get("level", 0) >= min_level]
        if not candidates:
            return
        npc_id, grudge = max(candidates, key=lambda kv: kv[1].get("level", 0))
        key = f"rival_ambush:{npc_id}"
        if not self._ready(key, cfg.get("cooldown_months", 18)):
            return
        ratio = cfg.get("hp_penalty_ratio", 0.10)
        lost = max(1, int(self.player.health * ratio))
        self.player.health = max(1, self.player.health - lost)
        self._mark(key)
        name = self._npc_name(npc_id)
        self._notify(
            f"[red]【寻衅】{name}因旧怨拦路寻衅，一番缠斗后你击退对方，"
            f"但也负了轻伤（健康 -{lost}）。梁子怕是更深了。"
        )
        self.player.record_npc_moment(
            npc_id, f"第{self.world.year}年：因旧怨拦路寻衅，缠斗后负伤遁走",
        )

    # ---------- 事件：挚友来访 ----------
    def _maybe_friend_visit(self):
        cfg = self.config.get("friend_visit")
        rels = getattr(self.player, "npc_relationships", {}) or {}
        companions = {c.get("npc_id") for c in (getattr(self.player, "companions", []) or [])}
        min_favor = cfg.get("min_favor", 50)
        candidates = [nid for nid, v in rels.items()
                      if v >= min_favor and nid not in companions]
        if not candidates or not self._roll(cfg.get("chance", 0.0)):
            return
        npc_id = random.choice(candidates)
        key = f"friend_visit:{npc_id}"
        if not self._ready(key, cfg.get("cooldown_months", 12)):
            return
        gain = cfg.get("mental_gain", 5)
        self.player.mental_state = min(100, self.player.mental_state + gain)
        self._mark(key)
        name = self._npc_name(npc_id)
        self._notify(
            f"[cyan]【故人来访】{name}远道来访，与你煮茶论道、共忆往昔，"
            f"心境澄明（心境 +{gain}）。"
        )
        self.player.record_npc_moment(
            npc_id, f"第{self.world.year}年：远道来访，煮茶论道共忆往昔",
        )

    # ---------- 事件：弟子叛逃 ----------
    def _maybe_disciple_defect(self):
        cfg = self.config.get("disciple_defect")
        disciples = getattr(self.player, "disciples", []) or []
        if not disciples or not self._roll(cfg.get("chance", 0.0)):
            return
        disciple = random.choice(disciples)
        npc_id = disciple["npc_id"]
        key = f"disciple_defect:{npc_id}"
        if not self._ready(key, cfg.get("cooldown_months", 36)):
            return
        self.player.disciples = [
            d for d in disciples if d.get("npc_id") != npc_id
        ]
        reason = cfg.get("grudge_reason", "师门恩义已尽")
        self.player.add_grudge(npc_id, 1, reason)
        self._mark(key)
        d_name = disciple.get("name", npc_id)
        self._notify(
            f"[red]【叛离】弟子{d_name}不辞而别，只留下一封绝笔——"
            f"师徒缘尽，徒留一声叹息（恩怨 +1）。"
        )
        self.player.record_npc_moment(
            npc_id, f"第{self.world.year}年：不辞而别叛出师门，师徒缘尽",
        )

    # ---------- 事件：江湖传言 ----------
    def _maybe_rumor(self):
        cfg = self.config.get("rumor")
        if not self._roll(cfg.get("chance", 0.0)):
            return
        key = "rumor"
        if not self._ready(key, cfg.get("cooldown_months", 6)):
            return
        self._mark(key)
        if random.random() < 0.5:
            self.player.karma += 1
            self._notify(
                "[cyan]【江湖】茶馆里有人说起你的侠义事迹，"
                "善名渐播（业力 +1）。"
            )
        else:
            self.player.karma -= 1
            self._notify(
                "[red]【江湖】坊间流传你当年行事狠辣的传闻，"
                "纵是真真假假，也难免惹人侧目（业力 -1）。"
            )
