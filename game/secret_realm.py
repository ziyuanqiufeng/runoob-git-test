# -*- coding: utf-8 -*-
"""秘境副本系统。"""
import json
import os
import random

from game.enemy import Enemy
from game.realm_card import RealmCardManager
from game.realm_node import RealmNodeManager
from game.realm_reward import RealmRewardManager


class SecretRealmConfig:
    def __init__(self, config_dir="config"):
        self.config_dir = config_dir
        self._realms = {}
        self._load()

    def _load(self):
        path = os.path.join(self.config_dir, "secret_realms.json")
        if not os.path.exists(path):
            return
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        for entry in data:
            self._realms[entry["id"]] = entry

    def get(self, realm_id):
        return self._realms.get(realm_id)


class SecretRealmManager:
    """管理秘境解锁、进入、层数推进。"""

    def __init__(
        self,
        player,
        enemy_library,
        item_library,
        config_dir="config",
        rng=None,
        feature_enabled=None,
    ):
        self.player = player
        self.enemy_library = enemy_library
        self.item_library = item_library
        self.config = SecretRealmConfig(config_dir)
        self.config_dir = config_dir
        self._rng = rng or random
        self._feature_enabled = feature_enabled  # 可选可调用：flag -> bool
        self.card_mgr = RealmCardManager(config_dir)
        self.node_mgr = RealmNodeManager(config_dir, rng=self._rng)
        self.reward_mgr = RealmRewardManager(player, item_library, config_dir)
        self._difficulties = self._load_difficulties()
        self.active_run = None

    def is_unlocked(self, realm_id):
        return realm_id in self.player.unlocked_secret_realms

    def _check_unlock_requirement(self, realm):
        """检查秘境的前置解锁条件是否满足。"""
        req = realm.get("unlock_requirement", {})
        if not req:
            return True, ""
        # 前置秘境：需已解锁
        pre_realm = req.get("completed_realm")
        if pre_realm and pre_realm not in self.player.unlocked_secret_realms:
            pre_cfg = self.config.get(pre_realm)
            pre_name = pre_cfg["name"] if pre_cfg else pre_realm
            return False, f"需先通关秘境【{pre_name}】。"
        # 前置任务：需已完成
        pre_quest = req.get("completed_quest")
        if pre_quest and pre_quest not in self.player.completed_quests:
            return False, "前置任务尚未完成。"
        # 前置物品：需持有
        pre_item = req.get("item_id")
        if pre_item and not self.player.has_item(pre_item):
            return False, "缺少必要物品。"
        return True, ""

    def unlock(self, realm_id):
        if self.is_unlocked(realm_id):
            return False, "秘境已解锁。"
        realm = self.config.get(realm_id)
        if not realm:
            return False, "秘境不存在。"
        ok, msg = self._check_unlock_requirement(realm)
        if not ok:
            return False, msg
        self.player.unlocked_secret_realms.append(realm_id)
        return True, f"解锁秘境【{realm['name']}】。"

    def can_enter(self, realm_id):
        realm = self.config.get(realm_id)
        if not realm:
            return False, "秘境不存在。"
        if not self.is_unlocked(realm_id):
            return False, "秘境未解锁。"
        ok, msg = self._check_unlock_requirement(realm)
        if not ok:
            return False, msg
        order = self.player.REALM_ORDER.get(self.player.realm_id, 0)
        if order < realm.get("min_realm_order", 1):
            return False, "境界不足，无法进入该秘境。"
        return True, ""

    def generate_floor_enemies(self, realm_id, floor):
        """生成某层敌人列表。"""
        realm = self.config.get(realm_id)
        pool = realm.get("enemy_pool", [])
        counts = realm.get("enemies_per_floor", [])
        if floor >= len(counts):
            return []
        enemies = []
        for _ in range(counts[floor]):
            eid = random.choice(pool)
            data = self.enemy_library.get(eid)
            if data:
                enemies.append(Enemy.from_dict(data))
        return enemies

    def get_boss(self, realm_id):
        realm = self.config.get(realm_id)
        boss_id = realm.get("boss")
        data = self.enemy_library.get(boss_id)
        return Enemy.from_dict(data) if data else None

    def get_rewards(self, realm_id):
        """通关奖励物品。"""
        realm = self.config.get(realm_id)
        rewards = []
        for item_id in realm.get("rewards", []):
            item = self.item_library.create(item_id)
            if item:
                rewards.append(item)
        return rewards

    # ==================== Roguelike 秘境（F-03） ====================

    def _load_difficulties(self):
        path = os.path.join(self.config_dir, "secret_realm", "realm_difficulty.json")
        if not os.path.exists(path):
            return {}
        with open(path, "r", encoding="utf-8") as f:
            return {d["id"]: d for d in json.load(f)}

    def _difficulty(self, difficulty_id):
        return self._difficulties.get(difficulty_id)

    def is_roguelike_enabled(self):
        if callable(self._feature_enabled):
            return self._feature_enabled("roguelike_secret_realm")
        return True

    def can_start_roguelike(self, realm_id):
        if not self.is_roguelike_enabled():
            return False, "Roguelike 秘境功能未开启。"
        return self.can_enter(realm_id)

    def get_difficulties(self):
        return list(self._difficulties.values())

    def list_realms(self):
        out = []
        for rid, cfg in self.config._realms.items():
            out.append({
                "id": rid,
                "name": cfg.get("name", rid),
                "description": cfg.get("description", ""),
                "min_realm_order": cfg.get("min_realm_order", 1),
                "floors": cfg.get("floors", self.node_mgr.default_total_floors),
            })
        return out

    def mark_cleared(self, node_id):
        if self.active_run:
            self.active_run["cleared"].add(node_id)

    def start_run(self, realm_id, difficulty_id, party=None):
        """开启一次 Roguelike 秘境探索。party: list of {name, path}。"""
        ok, msg = self.can_start_roguelike(realm_id)
        if not ok:
            return False, msg
        diff = self._difficulty(difficulty_id)
        if diff is None:
            return False, "难度不存在。"
        total = self.node_mgr.default_total_floors
        layers = self.node_mgr.generate_map(total_floors=total, rng=self._rng)
        realm_cfg = self.config.get(realm_id) or {}
        if not party:
            party = [{"name": self.player.name, "path": self.player.cultivation_path}]
        self.active_run = {
            "realm_id": realm_id,
            "difficulty": difficulty_id,
            "difficulty_cfg": diff,
            "map": layers,
            "current_node_id": None,
            "qi": self.node_mgr.start_qi,
            "party": party,
            "cards": [],
            "coins": 0,
            "discovered": {"cards": [], "bosses": [], "events": []},
            "cleared": set(),
            "pending_event": None,
            "total_floors": total,
            "victory": False,
        }
        return True, f"进入秘境【{realm_cfg.get('name', realm_id)}】（{diff['name']}）"

    def is_run_active(self):
        return self.active_run is not None

    def current_run(self):
        return self.active_run

    def _find_node(self, node_id):
        if not self.active_run:
            return None
        for layer in self.active_run["map"]:
            for n in layer:
                if n["id"] == node_id:
                    return n
        return None

    def get_available_node_ids(self):
        run = self.active_run
        if run is None:
            return []
        if run["current_node_id"] is None:
            return [n["id"] for n in run["map"][0]] if run["map"] else []
        cur = self._find_node(run["current_node_id"])
        return list(cur["edges"]) if cur else []

    def get_available_nodes(self):
        return [self._find_node(nid) for nid in self.get_available_node_ids()]

    def enter_node(self, node_id):
        """进入一个可达节点，扣除灵气值并返回解析描述。"""
        run = self.active_run
        if run is None:
            return {"kind": "none"}
        node = self._find_node(node_id)
        if node is None or node_id not in self.get_available_node_ids():
            return {"kind": "invalid", "msg": "该节点当前不可达"}
        run["qi"] -= self.node_mgr.qi_per_node
        run["current_node_id"] = node_id
        kind = node["type"]
        if kind in ("battle", "elite", "boss"):
            enemy = self._generate_node_enemy(run["realm_id"], node, run["difficulty_cfg"])
            if kind == "boss":
                if run["realm_id"] not in run["discovered"]["bosses"]:
                    run["discovered"]["bosses"].append(run["realm_id"])
            return {"kind": kind, "node": node, "enemy": enemy}
        if kind == "event":
            ev = self._pick_event()
            run["pending_event"] = ev
            return {"kind": "event", "node": node, "event": ev}
        if kind == "shop":
            return {"kind": "shop", "node": node}
        return {"kind": "unknown", "node": node}

    def _generate_node_enemy(self, realm_id, node, difficulty_cfg):
        realm = self.config.get(realm_id) or {}
        if node["type"] == "boss":
            eid = realm.get("boss")
        else:
            pool = realm.get("enemy_pool", [])
            eid = self._rng.choice(pool) if pool else None
        data = self.enemy_library.get(eid) if (eid and self.enemy_library) else None
        if not data:
            return None
        enemy = Enemy.from_dict(data)
        strength = difficulty_cfg["modifiers"].get("enemy_strength", 1.0)
        level = node.get("enemy_level") or 1
        enemy.level = level
        enemy.attack = int(enemy.attack * strength)
        enemy.defense = int(enemy.defense * strength)
        enemy.max_hp = int(enemy.max_hp * strength)
        enemy.hp = enemy.max_hp
        return enemy

    def _pick_event(self):
        path = os.path.join(self.config_dir, "secret_realm", "realm_events.json")
        events = []
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                events = json.load(f).get("events", [])
        if not events:
            return {"id": "empty", "name": "空寂", "description": "此处别无他物。",
                    "choices": [{"text": "继续前行", "effect": {}}]}
        return dict(self._rng.choice(events))

    def on_battle_cleared(self, node_id, victory):
        """战斗结束后调用。胜利则发放秘境币并抽取三张增益卡。"""
        run = self.active_run
        node = self._find_node(node_id)
        if not victory:
            return {"defeated": True}
        kind = node["type"] if node else "battle"
        base = {"battle": 10, "elite": 20, "boss": 50}.get(kind, 8)
        reward_mult = run["difficulty_cfg"]["modifiers"].get("reward_mult", 1.0)
        coins = int(base * reward_mult)
        run["coins"] += coins
        run["cleared"].add(node_id)
        rarity_bonus = run["difficulty_cfg"]["modifiers"].get("card_rarity_bonus", 0.0)
        draws = self.card_mgr.draw(3, rng=self._rng, rarity_bonus=rarity_bonus)
        return {"coins": coins, "draws": draws, "is_boss": kind == "boss"}

    def add_card(self, card_id):
        run = self.active_run
        if run is None:
            return False
        card = self.card_mgr.get(card_id)
        if not card:
            return False
        if card_id not in run["discovered"]["cards"]:
            run["discovered"]["cards"].append(card_id)
        if not card.get("stackable", False):
            for e in run["cards"]:
                if e["card_id"] == card_id:
                    return False
            run["cards"].append({"card_id": card_id, "stacks": 1})
            return True
        max_stack = card.get("max_stack", 1)
        for e in run["cards"]:
            if e["card_id"] == card_id:
                if e["stacks"] < max_stack:
                    e["stacks"] += 1
                    return True
                return False
        run["cards"].append({"card_id": card_id, "stacks": 1})
        return True

    def choose_event(self, node_id, choice_index):
        run = self.active_run
        ev = run.get("pending_event") if run else None
        if not ev:
            return {"applied": {}}
        choices = ev.get("choices", [])
        if choice_index < 0 or choice_index >= len(choices):
            return {"applied": {}}
        choice = choices[choice_index]
        effect = choice.get("effect", {})
        applied = {}
        if "qi" in effect:
            run["qi"] = max(0, run["qi"] + int(effect["qi"]))
            applied["qi"] = int(effect["qi"])
        if "coins" in effect:
            run["coins"] = max(0, run["coins"] + int(effect["coins"]))
            applied["coins"] = int(effect["coins"])
        if "karma" in effect:
            applied["karma"] = int(effect["karma"])
        if effect.get("draw_card"):
            rarity_bonus = run["difficulty_cfg"]["modifiers"].get("card_rarity_bonus", 0.0)
            applied["draws"] = self.card_mgr.draw(3, rng=self._rng, rarity_bonus=rarity_bonus)
        run["cleared"].add(node_id)
        if ev["id"] not in run["discovered"]["events"]:
            run["discovered"]["events"].append(ev["id"])
        run["pending_event"] = None
        return {"applied": applied}

    def _party_synergy(self, party):
        paths = set(p.get("path") for p in (party or []))
        bonus = {"attack_pct": 0.0, "defense_pct": 0.0, "max_hp_flat": 0}
        if "jian" in paths and "dan" in paths:
            bonus["attack_pct"] += 0.10
        if "fa" in paths and "yu" in paths:
            bonus["attack_pct"] += 0.08
        if "ti" in paths:
            bonus["max_hp_flat"] += 30
        if "zhen" in paths:
            bonus["defense_pct"] += 0.10
        if len(party or []) >= 2:
            bonus["max_hp_flat"] += (len(party) - 1) * 15
        return bonus

    def get_combat_mods(self):
        run = self.active_run
        if run is None:
            return {"attack_pct": 0.0, "defense_pct": 0.0, "max_hp_flat": 0}
        card_mods = self.card_mgr.aggregate(run["cards"], self.player.cultivation_path)
        syn = self._party_synergy(run.get("party", []))
        return {
            "attack_pct": card_mods["attack_pct"] + syn["attack_pct"],
            "defense_pct": card_mods["defense_pct"] + syn["defense_pct"],
            "max_hp_flat": card_mods["max_hp_flat"] + syn["max_hp_flat"],
        }

    def buy_from_shop(self, item_id):
        return self.reward_mgr.exchange(item_id)

    def end_run(self, victory):
        run = self.active_run
        if run is None:
            return {"victory": False, "coins_earned": 0}
        run["victory"] = victory
        summary = self.reward_mgr.end_run_summary(run["realm_id"], victory, run)
        self.active_run = None
        return summary
