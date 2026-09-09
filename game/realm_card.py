# -*- coding: utf-8 -*-
"""秘境增益卡系统（F-03 Roguelike 秘境）。

增益卡在每次通关节点后三选一获得，可叠加形成 Build。
卡的 effect 支持：
  - "attack": "+30%"      → 攻击力百分比增益（流派限定卡带 apply_to）
  - "defense": "+20%"     → 防御力百分比增益
  - "hp": "+50"           → 生命上限固定增益
  - "skill_damage": "+30%" + "apply_to": <path>  → 等同攻击增益（流派限定）
所有百分比增益按堆叠层数（stacks）累加。
"""
import json
import os
import random

# 稀有度抽取权重：越高越难出
RARITY_WEIGHTS = {
    "common": 1.0,
    "uncommon": 0.55,
    "rare": 0.3,
    "immortal_gold": 0.1,
}


def parse_mod_value(value):
    """'+30%' -> ('pct', 0.3)；'+50' -> ('flat', 50)；'-10%' -> ('pct', -0.1)。"""
    v = str(value).strip()
    if v.endswith("%"):
        return ("pct", float(v[:-1]) / 100.0)
    return ("flat", float(v))


class RealmCardManager:
    def __init__(self, config_dir="config"):
        self.config_dir = config_dir
        self.cards = {}
        path = os.path.join(config_dir, "secret_realm", "realm_cards.json")
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                for c in json.load(f):
                    self.cards[c["id"]] = c

    def get(self, card_id):
        return self.cards.get(card_id)

    def all(self):
        return list(self.cards.values())

    def draw(self, count=3, rng=None, rarity_bonus=0.0):
        """抽取 count 张互不相同的卡（按稀有度权重，rarity_bonus 提升稀有度出现率）。"""
        rng = rng or random
        if not self.cards:
            return []
        pool = []
        for c in self.cards.values():
            w = RARITY_WEIGHTS.get(c.get("rarity", "common"), 1.0)
            if c.get("rarity") in ("uncommon", "rare", "immortal_gold"):
                w *= (1.0 + max(0.0, rarity_bonus))
            expanded = max(1, int(w * 100))
            pool.extend([c["id"]] * expanded)
        chosen_ids = set()
        attempts = 0
        limit = min(count, len(self.cards))
        while len(chosen_ids) < limit and attempts < 300:
            chosen_ids.add(rng.choice(pool))
            attempts += 1
        return [dict(self.cards[cid]) for cid in chosen_ids]

    def aggregate(self, owned, player_path=None):
        """owned: list of {"card_id": str, "stacks": int}
        返回战斗增益 mods: {"attack_pct", "defense_pct", "max_hp_flat"}。
        仅当卡无 apply_to 限制，或 apply_to == player_path 时生效。"""
        mods = {"attack_pct": 0.0, "defense_pct": 0.0, "max_hp_flat": 0}
        for entry in owned:
            card = self.cards.get(entry.get("card_id"))
            if not card:
                continue
            stacks = max(1, int(entry.get("stacks", 1)))
            effect = card.get("effect", {})
            apply_to = effect.get("apply_to")
            if apply_to and player_path and apply_to != player_path:
                continue  # 流派限定卡对当前流派不生效
            for key, val in effect.items():
                if key == "apply_to":
                    continue
                kind, num = parse_mod_value(val)
                if key in ("attack", "skill_damage"):
                    if kind == "pct":
                        mods["attack_pct"] += num * stacks
                elif key == "defense":
                    if kind == "pct":
                        mods["defense_pct"] += num * stacks
                elif key == "hp":
                    if kind == "flat":
                        mods["max_hp_flat"] += int(num) * stacks
        return mods
