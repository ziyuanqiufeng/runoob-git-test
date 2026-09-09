# -*- coding: utf-8 -*-
"""秘境币结算与图鉴（F-03 Roguelike 秘境）。

- 秘境币（realm_coins）累计在 player 上，跨周目保留，可兑换稀有物品。
- 秘境图鉴记录已发现的卡 / Boss / 事件，鼓励全收集。
"""
import json
import os


class RealmRewardManager:
    def __init__(self, player, item_library, config_dir="config"):
        self.player = player
        self.item_library = item_library
        self._exchange_list = []
        path = os.path.join(config_dir, "secret_realm", "realm_exchange.json")
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                self._exchange_list = json.load(f).get("exchange", [])

    def add_realm_coins(self, n):
        self.player.realm_coins = max(0, self.player.realm_coins + int(n))

    def get_exchange_items(self, include_exclusive=True):
        if include_exclusive:
            return list(self._exchange_list)
        return [e for e in self._exchange_list if not e.get("exclusive")]

    def exchange(self, item_id):
        entry = next((e for e in self._exchange_list if e["id"] == item_id), None)
        if not entry:
            return False, "无此兑换物。"
        cost = entry["cost"]
        if self.player.realm_coins < cost:
            return False, "秘境币不足。"
        item = self.item_library.create(item_id) if self.item_library else None
        if item is None:
            return False, "物品库缺失该物品。"
        self.player.realm_coins -= cost
        self.player.add_item(item)
        return True, f"兑换【{entry.get('name', item_id)}】成功。"

    def record_discovery(self, kind, id_):
        lst = self.player.realm_compendium.get(kind)
        if lst is not None and id_ not in lst:
            lst.append(id_)

    def end_run_summary(self, realm_id, victory, run):
        coins = run.get("coins", 0)
        self.add_realm_coins(coins)
        for cid in run.get("discovered", {}).get("cards", []):
            self.record_discovery("cards", cid)
        for bid in run.get("discovered", {}).get("bosses", []):
            self.record_discovery("bosses", bid)
        for eid in run.get("discovered", {}).get("events", []):
            self.record_discovery("events", eid)
        return {
            "realm_id": realm_id,
            "victory": victory,
            "coins_earned": coins,
            "total_realm_coins": self.player.realm_coins,
            "cards_owned": run.get("cards", []),
            "compendium": dict(self.player.realm_compendium),
        }
