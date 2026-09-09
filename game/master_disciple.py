# -*- coding: utf-8 -*-
"""师徒系统。"""


class MasterDiscipleManager:
    """管理拜师、收徒、师徒任务与出师。"""

    def __init__(self, player, npc_library):
        self.player = player
        self.npc_library = npc_library

    def can_take_master(self, npc_id):
        """判断是否能拜某 NPC 为师。"""
        npc = self.npc_library.get(npc_id)
        if not npc:
            return False, "NPC 不存在。"
        if not getattr(npc, "can_be_master", False):
            return False, "该 NPC 不愿收徒。"
        if self.player.master_id:
            return False, "你已有师父。"
        return True, ""

    def take_master(self, npc_id):
        ok, msg = self.can_take_master(npc_id)
        if not ok:
            return False, msg
        npc = self.npc_library.get(npc_id)
        self.player.master_id = npc_id
        self.player.increase_npc_relationship(npc_id, 3)
        return True, f"拜【{npc.name}】为师。"

    def can_accept_disciple(self, npc_id):
        """判断是否能收某 NPC 为徒。"""
        npc = self.npc_library.get(npc_id)
        if not npc:
            return False, "NPC 不存在。"
        if any(d["npc_id"] == npc_id for d in self.player.disciples):
            return False, "已收该 NPC 为徒。"
        return True, ""

    def accept_disciple(self, npc_id):
        ok, msg = self.can_accept_disciple(npc_id)
        if not ok:
            return False, msg
        npc = self.npc_library.get(npc_id)
        self.player.disciples.append({
            "npc_id": npc_id,
            "name": getattr(npc, "name", "未知"),
            "realm_id": "qi_refining_1",
            "progress": 0,
        })
        self.player.increase_npc_relationship(npc_id, 2)
        return True, f"收【{npc.name}】为徒。"

    def tick_disciples(self):
        """每月推进徒弟成长，返回成长日志。"""
        logs = []
        for disciple in self.player.disciples:
            disciple["progress"] += 1
            if disciple["progress"] >= 12:
                # 徒弟境界提升
                order = self.player.REALM_ORDER.get(disciple["realm_id"], 1)
                next_realm = None
                for rid, ord_val in self.player.REALM_ORDER.items():
                    if ord_val == order + 1:
                        next_realm = rid
                        break
                if next_realm:
                    disciple["realm_id"] = next_realm
                    disciple["progress"] = 0
                    logs.append(f"徒弟【{disciple['name']}】突破至{next_realm}。")
        return logs
