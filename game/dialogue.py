# -*- coding: utf-8 -*-
"""对话（Dialogue）系统。

负责加载分支对话配置、检查选项/节点条件、执行对话效果，并维护当前对话状态。
对话配置位于 config/dialogues.json，可被 NPC、任务、世界事件引用。
"""
import json
import os


class Dialogue:
    """单条对话配置。"""

    def __init__(self, dialogue_id, npc_id, entry_node, nodes):
        self.id = dialogue_id
        self.npc_id = npc_id
        self.entry_node = entry_node
        self.nodes = nodes  # dict: node_id -> node dict

    def get_node(self, node_id):
        """获取指定节点，不存在返回 None。"""
        return self.nodes.get(node_id)

    @classmethod
    def from_dict(cls, data):
        return cls(
            dialogue_id=data["id"],
            npc_id=data.get("npc_id"),
            entry_node=data.get("entry_node", "start"),
            nodes=data.get("nodes", {}),
        )


class DialogueLibrary:
    """对话配置库。"""

    def __init__(self, config_dir="config"):
        self.config_dir = config_dir
        self.dialogues = {}
        self._load()

    def _load(self):
        path = os.path.join(self.config_dir, "dialogues.json")
        if not os.path.exists(path):
            return
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        for entry in data:
            dialogue = Dialogue.from_dict(entry)
            self.dialogues[dialogue.id] = dialogue

    def get(self, dialogue_id):
        return self.dialogues.get(dialogue_id)

    def all_ids(self):
        return set(self.dialogues.keys())


class DialogueManager:
    """对话状态管理器，绑定到游戏引擎。"""

    # 受支持的条件类型
    VALID_CONDITIONS = {
        "realm_min",
        "realm_max",
        "reputation_min",
        "quest_active",
        "quest_completed",
        "has_item",
        "cultivation_path",
        "dialogue_flag",
        "npc_choice",
    }

    # 受支持的效果类型
    VALID_EFFECTS = {
        "start_quest",
        "advance_quest",
        "complete_quest",
        "modify_reputation",
        "give_item",
        "take_item",
        "set_flag",
        "teach_skill",
        "change_npc_location",
        "notify",
        "record_choice",
    }

    def __init__(self, engine):
        self.engine = engine
        self.player = engine.player
        self.world = engine.world
        # 当前进行中的对话状态
        self.current_dialogue_id = None
        self.current_node_id = None
        self.current_npc_id = None

    # ------------------- 状态管理 -------------------

    def start_dialogue(self, dialogue_id, npc_id=None, node_id=None):
        """开始一段对话，返回当前节点或 None。"""
        dialogue = self.engine.dialogue_library.get(dialogue_id)
        if not dialogue:
            return None
        self.current_dialogue_id = dialogue_id
        self.current_npc_id = npc_id or dialogue.npc_id
        self.current_node_id = node_id or dialogue.entry_node
        return self._get_current_node()

    def is_active(self):
        """是否有进行中的对话。"""
        return self.current_dialogue_id is not None

    def end_dialogue(self):
        """结束当前对话。"""
        self.current_dialogue_id = None
        self.current_node_id = None
        self.current_npc_id = None

    def _get_current_node(self):
        dialogue = self.engine.dialogue_library.get(self.current_dialogue_id)
        if not dialogue:
            return None
        return dialogue.get_node(self.current_node_id)

    # ------------------- 节点与选项 -------------------

    def get_current_state(self):
        """获取当前对话节点及可用选项（已过滤条件）。"""
        node = self._get_current_node()
        if not node:
            return None
        # 节点级条件：若节点自身条件不满足，则 fallback 到默认分支或直接结束
        if not self._check_conditions(node.get("conditions", [])):
            fallback = node.get("fallback_node")
            if fallback:
                self.current_node_id = fallback
                return self.get_current_state()
            return None

        options = []
        for idx, opt in enumerate(node.get("options", [])):
            if self._check_conditions(opt.get("conditions", [])):
                options.append({"index": idx, "text": opt.get("text", "…")})
        return {
            "dialogue_id": self.current_dialogue_id,
            "node_id": self.current_node_id,
            "text": node.get("text", ""),
            "speaker": node.get("speaker", self.current_npc_id),
            "options": options,
            "is_end": len(options) == 0,
        }

    def choose_option(self, option_index):
        """玩家选择选项，执行效果并切换到下一节点。

        返回 (next_state, logs)。next_state 为 None 表示对话结束。
        """
        node = self._get_current_node()
        if not node:
            self.end_dialogue()
            return None, []

        options = node.get("options", [])
        if option_index < 0 or option_index >= len(options):
            self.end_dialogue()
            return None, []

        opt = options[option_index]
        logs = []

        # 执行选项效果
        effect_logs = self._apply_effects(opt.get("effects", []))
        logs.extend(effect_logs)

        # 记录玩家对该 NPC 的关键选择
        choice_key = opt.get("record_choice_key")
        if choice_key and self.current_npc_id:
            choice_value = opt.get("record_choice_value", option_index)
            self.player.record_npc_choice(self.current_npc_id, choice_key, choice_value)

        next_node_id = opt.get("next_node")
        if not next_node_id:
            self.end_dialogue()
            return None, logs

        self.current_node_id = next_node_id
        return self.get_current_state(), logs

    # ------------------- 条件判断 -------------------

    def _check_conditions(self, conditions):
        """判断一组条件是否全部满足。"""
        for cond in conditions:
            if not self._check_single_condition(cond):
                return False
        return True

    def _check_single_condition(self, cond):
        """判断单个条件。"""
        ctype = cond.get("type")
        if ctype not in self.VALID_CONDITIONS:
            # 未知条件视为满足，避免配置错误阻断流程
            return True

        if ctype == "realm_min":
            return self._realm_order(self.player.realm_id) >= self._realm_order(cond.get("realm_id"))
        if ctype == "realm_max":
            return self._realm_order(self.player.realm_id) <= self._realm_order(cond.get("realm_id"))
        if ctype == "reputation_min":
            npc_id = cond.get("npc_id", self.current_npc_id)
            return self.player.get_npc_relationship(npc_id) >= cond.get("value", 0)
        if ctype == "quest_active":
            return cond.get("quest_id") in self.player.quest_progress
        if ctype == "quest_completed":
            return cond.get("quest_id") in self.player.completed_quests
        if ctype == "has_item":
            item_id = cond.get("item_id")
            count = cond.get("count", 1)
            return self.player.count_item(item_id) >= count
        if ctype == "cultivation_path":
            return self.player.cultivation_path == cond.get("path_id")
        if ctype == "dialogue_flag":
            flag = cond.get("flag")
            expected = cond.get("value")
            actual = self.player.dialogue_flags.get(flag)
            if expected is None:
                return actual is not None
            return actual == expected
        if ctype == "npc_choice":
            npc_id = cond.get("npc_id", self.current_npc_id)
            key = cond.get("key")
            expected = cond.get("value")
            memory = self.player.get_npc_memory(npc_id).get("choices", {})
            actual = memory.get(key)
            if expected is None:
                return actual is not None
            return actual == expected
        return True

    def _realm_order(self, realm_id):
        """获取境界 order，未知境界返回 0。"""
        return getattr(self.player, "REALM_ORDER", {}).get(realm_id, 0)

    # ------------------- 效果执行 -------------------

    def _apply_effects(self, effects):
        """执行一组效果，返回日志列表。"""
        logs = []
        for effect in effects:
            log = self._apply_effect(effect)
            if log:
                logs.append(log)
        return logs

    def _apply_effect(self, effect):
        """执行单个效果，返回一条日志或 None。"""
        etype = effect.get("type")
        if etype not in self.VALID_EFFECTS:
            return None

        if etype == "start_quest":
            quest_id = effect.get("quest_id")
            self.engine.accept_quest(quest_id)
            quest = self.engine.quest_library.get(quest_id)
            name = quest.name if quest else quest_id
            return f"接取任务：{name}"

        if etype == "advance_quest":
            quest_id = effect.get("quest_id")
            step = effect.get("step", 1)
            # 使用引擎任务推进接口，若不存在则直接修改进度
            if quest_id in self.player.quest_progress:
                self.player.quest_progress[quest_id] += step
            return None

        if etype == "complete_quest":
            quest_id = effect.get("quest_id")
            self.engine.complete_quest(quest_id)
            return None

        if etype == "modify_reputation":
            npc_id = effect.get("npc_id", self.current_npc_id)
            value = effect.get("value", 0)
            if npc_id:
                new_val = self.player.increase_npc_relationship(npc_id, value)
                direction = "提升" if value >= 0 else "下降"
                return f"与 {npc_id} 的好感度{direction}至 {new_val}"
            return None

        if etype == "give_item":
            item_id = effect.get("item_id")
            count = effect.get("count", 1)
            item_name = item_id
            for _ in range(count):
                item = self.engine.item_library.create(item_id)
                if item:
                    self.player.add_item(item)
                    item_name = item.name
            return f"获得 {item_name} x{count}"

        if etype == "take_item":
            item_id = effect.get("item_id")
            count = effect.get("count", 1)
            removed = 0
            for _ in range(count):
                for item in self.player.inventory:
                    if item.id == item_id:
                        self.player.remove_item(item)
                        removed += 1
                        break
            item_obj = self.engine.item_library.get(item_id)
            name = item_obj.name if item_obj else item_id
            return f"失去 {name} x{removed}"

        if etype == "set_flag":
            flag = effect.get("flag")
            value = effect.get("value", True)
            self.player.dialogue_flags[flag] = value
            return None

        if etype == "teach_skill":
            skill_id = effect.get("skill_id")
            if skill_id and skill_id not in self.player.skills:
                self.player.skills.append(skill_id)
            skill = self.engine.skill_library.get(skill_id)
            name = skill.name if skill else skill_id
            return f"习得技能：{name}"

        if etype == "change_npc_location":
            npc_id = effect.get("npc_id")
            location = effect.get("location")
            npc = self.engine.npc_library.get(npc_id)
            if npc:
                npc.current_location = location
            return None

        if etype == "notify":
            text = effect.get("text", "")
            self.engine.notify(text)
            return text

        if etype == "record_choice":
            npc_id = effect.get("npc_id", self.current_npc_id)
            key = effect.get("key")
            value = effect.get("value")
            if npc_id and key is not None:
                self.player.record_npc_choice(npc_id, key, value)
            return None

        return None
