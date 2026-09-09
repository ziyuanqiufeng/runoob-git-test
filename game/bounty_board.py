# -*- coding: utf-8 -*-
"""委托与悬赏板系统。"""
import random


class BountyBoardManager:
    """管理悬赏委托的接取与结算。"""

    def __init__(self, player, item_library, world):
        self.player = player
        self.item_library = item_library
        self.world = world
        # 当前可接取的悬赏列表
        self._available_bounties = []
        self._last_refresh_month = -1

    def refresh(self):
        """每月刷新悬赏列表。"""
        current = self.world.year * 12 + self.world.month
        if current == self._last_refresh_month:
            return
        self._last_refresh_month = current
        templates = [
            {"enemy_id": "wolf", "count": 5, "reward_stones": 20},
            {"enemy_id": "tiger", "count": 2, "reward_stones": 50},
            {"enemy_id": "bandit", "count": 3, "reward_stones": 40},
        ]
        self._available_bounties = []
        for t in random.sample(templates, min(2, len(templates))):
            self._available_bounties.append({
                "bounty_id": f"{t['enemy_id']}_{current}",
                "enemy_id": t["enemy_id"],
                "count": t["count"],
                "reward_stones": t["reward_stones"],
                "progress": 0,
            })

    def get_available(self):
        return self._available_bounties

    def accept(self, bounty_id):
        if any(b["bounty_id"] == bounty_id for b in self.player.active_bounties or []):
            return False, "已接取该悬赏。"
        bounty = next((b for b in self._available_bounties if b["bounty_id"] == bounty_id), None)
        if not bounty:
            return False, "悬赏不存在。"
        if not hasattr(self.player, "active_bounties"):
            self.player.active_bounties = []
        self.player.active_bounties.append(dict(bounty))
        return True, f"接取悬赏：击杀 {bounty['count']} 只 {bounty['enemy_id']}。"

    def update_kill(self, enemy_id):
        """击杀敌人时推进悬赏进度。"""
        completed = []
        if not hasattr(self.player, "active_bounties"):
            return completed
        for bounty in self.player.active_bounties:
            if bounty["enemy_id"] == enemy_id:
                bounty["progress"] += 1
                if bounty["progress"] >= bounty["count"]:
                    completed.append(bounty)
        for bounty in completed:
            self.complete(bounty["bounty_id"])
        return completed

    def complete(self, bounty_id):
        for bounty in self.player.active_bounties:
            if bounty["bounty_id"] == bounty_id:
                stones = bounty["reward_stones"]
                for _ in range(stones):
                    item = self.item_library.create("spirit_stone")
                    if item:
                        self.player.add_item(item)
                self.player.active_bounties.remove(bounty)
                return True, f"完成悬赏，获得 {stones} 灵石。"
        return False, "未找到该悬赏。"
