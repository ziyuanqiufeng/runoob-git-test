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
