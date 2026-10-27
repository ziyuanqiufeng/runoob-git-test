# -*- coding: utf-8 -*-
"""NPC 个人支线（v1 寻物型）：数据驱动确定性生成，覆盖全部 NPC。

设计：
- 按 npc_id 的 CRC32 确定性选择所需物品/数量/文案（同一 NPC 每次一致）；
- 状态存 player.npc_quests = {npc_id: {"accepted": bool, "done": bool}}（转世清零）；
- 交付：扣物品 → 发灵石 → 好感 +N → 写共同记忆 + 年表。
"""
import json
import os
import zlib


class NPCQuestManager:
    """NPC 寻物支线管理器。"""

    def __init__(self, player, npc_library, item_library,
                 chronicle_manager=None, config_dir="config"):
        self.player = player
        self.npc_library = npc_library
        self.item_library = item_library
        self.chronicle_manager = chronicle_manager
        self.config = self._load(config_dir)

    def _load(self, config_dir):
        path = os.path.join(config_dir, "npc_quests.json")
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (OSError, json.JSONDecodeError):
            return {"item_pool": ["healing_pill"], "count_range": [1, 1],
                    "favor_reward": 10, "stone_reward": 50,
                    "intro_templates": ["帮我带 {count} 份【{item}】来。"]}

    # ---------- 生成与状态 ----------
    def get_quest(self, npc_id):
        """确定性生成该 NPC 的支线（同一 npc_id 恒定）。

        类型分派：seed % 3 == 0 → 护法、== 1 → 复仇、否则寻物。
        """
        npc = self.npc_library.get(npc_id) if self.npc_library else None
        if npc is None:
            return None
        seed = zlib.crc32(str(npc_id).encode("utf-8"))
        qt = seed % 3
        if qt in (0, 1):
            section = self.config.get("guard" if qt == 0 else "revenge") or {}
            pool = section.get("enemy_pool") or ["wolf"]
            enemy_id = pool[(seed // 17) % len(pool)]
            favor = int(self.config.get("combat_favor_reward", 15))
            stone = int(self.config.get("combat_stone_reward", 120))
            return {
                "npc_id": npc_id,
                "npc_name": getattr(npc, "name", npc_id),
                "type": "guard" if qt == 0 else "revenge",
                "type_title": section.get("title", "护法"),
                "intro": section.get("intro", "可否助我一臂之力？"),
                "enemy_id": enemy_id,
                "favor_reward": favor,
                "stone_reward": stone,
                "count": 0,
                "text": section.get("intro", "可否助我一臂之力？"),
            }
        # 寻物型
        pool = self.config.get("item_pool") or ["healing_pill"]
        item_id = pool[seed % len(pool)]
        lo, hi = (self.config.get("count_range") or [1, 1])[:2]
        span = max(0, int(hi) - int(lo))
        count = int(lo) + (seed // 7 % (span + 1)) if span else int(lo)
        templates = self.config.get("intro_templates") or ["帮我带 {count} 份【{item}】来。"]
        template = templates[(seed // 13) % len(templates)]
        item_name = self._item_name(item_id) or item_id
        return {
            "npc_id": npc_id,
            "npc_name": getattr(npc, "name", npc_id),
            "type": "collect",
            "type_title": "寻物",
            "item_id": item_id,
            "item_name": item_name,
            "count": count,
            "favor_reward": int(self.config.get("favor_reward", 10)),
            "stone_reward": int(self.config.get("stone_reward", 50)),
            "text": template.format(item=item_name, count=count),
        }

    def get_state(self, npc_id):
        """"none" 未接 / "accepted" 进行中 / "ready" 可交付 / "done" 已完成。"""
        state = (getattr(self.player, "npc_quests", {}) or {}).get(npc_id)
        if not state:
            return "none"
        if state.get("done"):
            return "done"
        quest = self.get_quest(npc_id)
        if not quest:
            return "accepted"
        if quest.get("type") == "collect":
            if self.player.count_item(quest["item_id"]) >= quest["count"]:
                return "ready"
            return "accepted"
        # 战斗型：接取后即"可出发"
        return "ready"

    # ---------- 动作 ----------
    def accept(self, npc_id):
        quest = self.get_quest(npc_id)
        if not quest:
            return False, "此人身上没有任何委托。"
        if self.get_state(npc_id) != "none":
            return False, "这条支线已经接过了。"
        store = getattr(self.player, "npc_quests", None)
        if store is None:
            self.player.npc_quests = {}
            store = self.player.npc_quests
        store[npc_id] = {"accepted": True, "done": False,
                         "type": quest.get("type", "collect")}
        if quest.get("type") == "collect":
            moment = (f"承接了 TA 的委托：寻 {quest['count']} 份"
                      f"【{quest['item_name']}】")
            msg = f"已接下委托：{quest['count']} 份【{quest['item_name']}】"
        else:
            moment = f"承接了 TA 的{quest.get('type_title', '战斗')}委托"
            msg = f"已接下{quest.get('type_title', '战斗')}委托——随时可以出发。"
        self.player.record_npc_moment(npc_id, moment)
        return True, msg

    def turn_in(self, npc_id):
        quest = self.get_quest(npc_id)
        if not quest:
            return False, "此人身上没有任何委托。"
        if quest.get("type") != "collect":
            return False, "这是战斗委托，请直接出发。"
        state = self.get_state(npc_id)
        if state == "done":
            return False, "这条支线已经完成了。"
        if state != "ready":
            return False, f"材料不足：还需 {quest['count']} 份【{quest['item_name']}】。"
        self.player.consume_items(quest["item_id"], quest["count"])
        # 灵石奖励
        stone = self.item_library.create("spirit_stone")
        for _ in range(quest["stone_reward"]):
            self.player.add_item(stone)
        # 好感奖励
        current = self.player.npc_relationships.get(npc_id, 0)
        self.player.npc_relationships[npc_id] = min(
            100, current + quest["favor_reward"])
        # 状态与记忆
        self.player.npc_quests[npc_id] = {"accepted": True, "done": True}
        self.player.record_npc_moment(
            npc_id, f"完成了 TA 的委托（寻【{quest['item_name']}】），情分更深"
        )
        if self.chronicle_manager is not None:
            self.chronicle_manager.record(
                f"完成了【{quest['npc_name']}】的委托",
                category="quest",
            )
        return True, (
            f"委托完成：灵石 +{quest['stone_reward']}，"
            f"好感 +{quest['favor_reward']}。"
        )

    def get_combat_enemy_id(self, npc_id):
        """战斗型委托：返回敌人 id（engine 用其创建 Enemy）；非战斗型返回 None。"""
        quest = self.get_quest(npc_id)
        if not quest or quest.get("type") not in ("guard", "revenge"):
            return None
        return quest.get("enemy_id")

    def complete_combat_quest(self, npc_id):
        """战斗型委托胜利结算：发奖励 + 记忆 + 年表 + 状态置 done。"""
        quest = self.get_quest(npc_id)
        if not quest or quest.get("type") not in ("guard", "revenge"):
            return False, "这不是战斗委托。"
        if self.get_state(npc_id) == "done":
            return False, "委托已经完成。"
        stone = self.item_library.create("spirit_stone")
        for _ in range(quest["stone_reward"]):
            self.player.add_item(stone)
        current = self.player.npc_relationships.get(npc_id, 0)
        self.player.npc_relationships[npc_id] = min(
            100, current + quest["favor_reward"])
        store = getattr(self.player, "npc_quests", None)
        if store is None:
            self.player.npc_quests = {}
            store = self.player.npc_quests
        store[npc_id] = {"accepted": True, "done": True,
                         "type": quest["type"]}
        self.player.record_npc_moment(
            npc_id, f"为 TA 完成了一场{quest['type_title']}，情义更重"
        )
        if self.chronicle_manager is not None:
            self.chronicle_manager.record(
                f"完成了【{quest['npc_name']}】的{quest['type_title']}委托",
                category="quest",
            )
        return True, (
            f"{quest['type_title']}完成：灵石 +{quest['stone_reward']}，"
            f"好感 +{quest['favor_reward']}。"
        )

    def _item_name(self, item_id):
        try:
            item = self.item_library.create(item_id)
            return item.name if item else None
        except Exception:
            return None
