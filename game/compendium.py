# -*- coding: utf-8 -*-
"""图鉴系统：记录玩家见过的敌人、物品、技能。"""


class CompendiumManager:
    """管理图鉴收录。"""

    def __init__(self, player):
        self.player = player
        if not hasattr(player, "bestiary"):
            player.bestiary = {}
        if not hasattr(player, "item_compendium"):
            player.item_compendium = []
        if not hasattr(player, "skill_compendium"):
            player.skill_compendium = []

    def record_enemy(self, enemy_id):
        """记录击杀敌人。"""
        self.player.bestiary[enemy_id] = self.player.bestiary.get(enemy_id, 0) + 1

    def record_item(self, item_id):
        """记录获得物品。"""
        if item_id not in self.player.item_compendium:
            self.player.item_compendium.append(item_id)

    def record_skill(self, skill_id):
        """记录习得技能。"""
        if skill_id not in self.player.skill_compendium:
            self.player.skill_compendium.append(skill_id)

    def get_completion(self):
        return {
            "enemies": len(self.player.bestiary),
            "items": len(self.player.item_compendium),
            "skills": len(self.player.skill_compendium),
        }
