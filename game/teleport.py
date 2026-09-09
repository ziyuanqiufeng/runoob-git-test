# -*- coding: utf-8 -*-
"""传送阵网络系统。"""


class TeleportManager:
    """管理已解锁的传送阵与快速旅行。"""

    def __init__(self, player, world):
        self.player = player
        self.world = world
        if not hasattr(player, "unlocked_teleports"):
            player.unlocked_teleports = []

    def can_unlock(self, location_id):
        if location_id in self.player.unlocked_teleports:
            return False, "该地点传送阵已解锁。"
        location = self.world.get_location(location_id)
        if not location:
            return False, "地点不存在。"
        return True, ""

    def unlock(self, location_id):
        ok, msg = self.can_unlock(location_id)
        if not ok:
            return False, msg
        self.player.unlocked_teleports.append(location_id)
        location = self.world.get_location(location_id)
        return True, f"解锁【{location['name']}】的传送阵。"

    def can_teleport(self, location_id):
        if location_id not in self.player.unlocked_teleports:
            return False, "该地点传送阵未解锁。"
        if location_id == self.player.location_id:
            return False, "你已经在该地点。"
        stones = self.player.count_item("spirit_stone")
        if stones < 5:
            return False, "灵石不足（需要 5 块）。"
        return True, ""

    def teleport(self, location_id):
        ok, msg = self.can_teleport(location_id)
        if not ok:
            return False, msg
        self.player.consume_items("spirit_stone", 5)
        self.player.location_id = location_id
        location = self.world.get_location(location_id)
        return True, f"传送至【{location['name']}】。"
