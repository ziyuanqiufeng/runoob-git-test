# -*- coding: utf-8 -*-
"""试炼塔：连续波次挑战（层数越高敌人越强，奖励越丰）。

设计要点：
- 局（run）状态只存内存：当前层数、本局累计奖励；
- 每层胜利后可三选一补给（物品/灵石，复用 items.json，不做属性污染）；
- 胜利推进由战斗胜利钩子调用 on_combat_won；失败/撤退调用 on_combat_lost/retreat；
- 最高层纪录持久化于 player.trial_tower_best（跨世保留）。
"""
import json
import os
import random


class TrialTowerManager:
    """试炼塔管理器（引擎持有，UI 驱动）。"""

    def __init__(self, player, enemy_library, item_library, config_dir="config"):
        self.player = player
        self.enemy_library = enemy_library
        self.item_library = item_library
        self.config = self._load(config_dir)
        self.floor = 0           # 当前层（0=未开始）
        self.active = False
        self.pending_buffs = []  # 待选择的三选一

    # ---------- 配置 ----------
    def _load(self, config_dir):
        path = os.path.join(config_dir, "trial_tower.json")
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (OSError, json.JSONDecodeError):
            return {"max_floors": 15, "enemy_tiers": []}

    @property
    def max_floors(self):
        return int(self.config.get("max_floors", 15))

    @property
    def best(self):
        return int(getattr(self.player, "trial_tower_best", 0))

    # ---------- 局生命周期 ----------
    def start_run(self):
        """开始挑战。返回第 1 层敌人；若非空闲或未达条件返回 None。"""
        if self.active:
            return None
        if not self.player.is_alive():
            return None
        self.active = True
        self.floor = 1
        self.pending_buffs = []
        return self._spawn_floor_enemy()

    def _spawn_floor_enemy(self):
        tier = None
        for t in self.config.get("enemy_tiers", []):
            if t.get("min_floor", 1) <= self.floor <= t.get("max_floor", 999):
                tier = t
                break
        pool = (tier or {}).get("enemy_pool") or []
        if not pool:
            # 兜底：随意取一个低阶敌人
            pool = ["wolf"]
        enemy_id = random.choice(pool)
        data = self.enemy_library.get(enemy_id)
        if not data:
            return None
        from game.enemy import Enemy
        return Enemy.from_dict(data)

    def on_combat_won(self):
        """一层胜利：结算该层奖励 → 推进层数或通关。返回 dict 结果。"""
        if not self.active:
            return {"continue": False}
        result = {"floor_cleared": self.floor, "rewards": []}
        # 每层灵石
        stone = int(self.config.get("stone_reward_per_floor", 20)) * self.floor
        self._grant_stone(stone)
        result["rewards"].append(f"灵石 ×{stone}")
        # 每 N 层物品
        every = int(self.config.get("item_reward_every", 5))
        if every > 0 and self.floor % every == 0:
            pool = self.config.get("item_reward_pool", [])
            if pool:
                item_id = random.choice(pool)
                self._grant_item(item_id, 1)
                name = self._item_name(item_id)
                if name:
                    result["rewards"].append(f"{name} ×1")
        # 推进
        self.floor += 1
        if self.floor > self.max_floors:
            result["cleared"] = True
            result["clear_bonus"] = self._grant_clear_bonus()
            self._record_best(self.floor - 1)
            self.active = False
            self.floor = 0
            return result
        result["cleared"] = False
        self.pending_buffs = self._roll_buffs()
        result["buffs"] = list(self.pending_buffs)
        return result

    def on_combat_lost(self):
        """一层失败：按已通过层数 50% 结算后结束本局。"""
        reached = max(0, self.floor - 1)
        if reached > 0:
            stone = int(self.config.get("stone_reward_per_floor", 20)) * reached // 2
            self._grant_stone(stone)
        self._record_best(reached)
        self.active = False
        self.floor = 0
        self.pending_buffs = []
        return {"reached": reached}

    def retreat(self):
        """主动撤退：按已通过层数全额结算。"""
        reached = max(0, self.floor - 1)
        if reached > 0:
            stone = int(self.config.get("stone_reward_per_floor", 20)) * reached
            self._grant_stone(stone)
        self._record_best(reached)
        self.active = False
        self.floor = 0
        self.pending_buffs = []
        return {"reached": reached}

    def next_floor_enemy(self):
        """取当前层的敌人（三选一补给后进入下一层）。"""
        if not self.active or self.floor < 1:
            return None
        self.pending_buffs = []
        return self._spawn_floor_enemy()

    # ---------- 三选一补给 ----------
    def _roll_buffs(self):
        pool = list(self.config.get("buff_pool", []))
        random.shuffle(pool)
        return pool[:3]

    def choose_buff(self, buff_id):
        """选择一项补给并立即发放。返回 (ok, 描述)。"""
        target = None
        for b in self.pending_buffs:
            if b.get("id") == buff_id:
                target = b
                break
        if not target:
            return False, "该补给不可选。"
        if "item" in target:
            self._grant_item(target["item"], int(target.get("count", 1)))
        if "stone" in target:
            self._grant_stone(int(target["stone"]))
        self.pending_buffs = []
        return True, target.get("desc", target.get("name", "补给已获得"))

    # ---------- 内部 ----------
    def _grant_stone(self, count):
        item = self.item_library.create("spirit_stone")
        for _ in range(count):
            self.player.add_item(item)

    def _grant_item(self, item_id, count):
        base = self.item_library.create(item_id)
        if base is None:
            return
        for _ in range(count):
            item = self.item_library.create(item_id)
            if item is not None:
                self.player.add_item(item)

    def _item_name(self, item_id):
        item = self.item_library.create(item_id)
        return item.name if item else None

    def _grant_clear_bonus(self):
        bonus = self.config.get("clear_bonus", {})
        lines = []
        stone = int(bonus.get("spirit_stone", 0))
        if stone:
            self._grant_stone(stone)
            lines.append(f"灵石 ×{stone}")
        if bonus.get("item"):
            count = int(bonus.get("item_count", 1))
            self._grant_item(bonus["item"], count)
            name = self._item_name(bonus["item"])
            if name:
                lines.append(f"{name} ×{count}")
        return lines

    def _record_best(self, reached):
        best = self.best
        if reached > best:
            self.player.trial_tower_best = reached
