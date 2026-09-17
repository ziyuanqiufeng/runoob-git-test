# -*- coding: utf-8 -*-
"""引擎拜师学技域 Mixin。

GameEngine 继承本 Mixin。方法通过鸭子类型访问引擎成员
（player/skill_library/notify/_auto_save 等）。
"""


class MentorMixin:

    # ==================== 拜师学技 ====================

    def can_learn_skill(self, npc, skill_id):
        """检查是否满足向该 NPC 学习指定技能的条件，返回 (ok: bool, reasons: list[str])。"""
        reasons = []
        skill = self.skill_library.get(skill_id)
        if not skill:
            return False, ["技能不存在"]

        if self.player.has_skill(skill_id):
            return False, ["已经习得该技能"]

        # 查找该 NPC 是否教授此技能
        teach_info = None
        for info in getattr(npc, "teach_skills", []):
            if info["skill_id"] == skill_id:
                teach_info = info
                break
        if not teach_info:
            return False, [f"{npc.name} 不传授这个技能"]

        # NPC 教授条件（任务/流派）
        requirement = teach_info.get("requirement")
        req_value = teach_info.get("requirement_value")
        if requirement == "completed_quest":
            if req_value not in self.player.completed_quests:
                quest = self.quest_library.get(req_value)
                reasons.append(f"需先完成任务：{quest.name if quest else req_value}")
        elif requirement and requirement.startswith("path_"):
            required_path = requirement[5:]
            if self.player.cultivation_path != required_path:
                path_names = {"fa": "法修", "ti": "体修", "jian": "剑修", "xie": "邪修",
                              "dan": "丹修", "qi": "器修", "shou": "御兽修", "hun": "魂修",
                              "zhen": "阵修", "fu": "符修"}
                reasons.append(f"需为{path_names.get(required_path, required_path)}")

        # 灵石费用
        cost = teach_info.get("cost_spirit_stone", 0)
        if cost > 0:
            if self.player.count_item("spirit_stone") < cost:
                reasons.append(f"需要 {cost} 灵石")

        # 灵根属性
        if not self.player.has_element(skill.element):
            elem_cn = ELEMENT_NAMES.get(skill.element, skill.element)
            reasons.append(f"需要{elem_cn}属性灵根")

        # 流派专属
        if skill.path_exclusive and self.player.cultivation_path != skill.path_exclusive:
            path_names = {"fa": "法修", "ti": "体修", "jian": "剑修", "xie": "邪修",
                          "dan": "丹修", "qi": "器修", "shou": "御兽修", "hun": "魂修",
                          "zhen": "阵修", "fu": "符修"}
            reasons.append(f"{path_names.get(skill.path_exclusive, skill.path_exclusive)}专属")

        # 境界要求
        if skill.realm_id:
            required_order = self.player.REALM_ORDER.get(skill.realm_id, 0)
            if self._get_realm_order() < required_order:
                realm_data = self.world.get_realm(skill.realm_id)
                realm_name = realm_data.get("name", skill.realm_id) if realm_data else skill.realm_id
                reasons.append(f"需要达到【{realm_name}】")

        return len(reasons) == 0, reasons

    def learn_from_npc(self, npc, skill_id):
        """向 NPC 学习技能。"""
        ok, reasons = self.can_learn_skill(npc, skill_id)
        if not ok:
            self.notify("\n".join(reasons))
            return False

        skill = self.skill_library.get(skill_id)
        teach_info = next(
            (info for info in getattr(npc, "teach_skills", []) if info["skill_id"] == skill_id),
            None,
        )
        cost = teach_info.get("cost_spirit_stone", 0) if teach_info else 0
        if cost > 0:
            self.player.consume_items("spirit_stone", cost)

        self.player.learn_skill(skill_id)
        self.notify(f"{npc.name} 传授你【{skill.name}】！")
        # 触发习得技能事件钩子
        self._on_learn_skill(skill_id)
        self._auto_save()
        return True

    def switch_cultivation_path(self, new_path_id):
        """
        流派转换（通过道师 NPC）。
        代价：遗忘旧流派的专属技能 + 资源清零。
        """
        if new_path_id == self.player.cultivation_path:
            self.notify("你已是该流派，无需转换。")
            return False

        # 获取旧流派专属技能 ID 列表，从玩家技能中移除
        old_path = self.player.cultivation_path
        old_exclusive = self.path_config.get_exclusive_skills(old_path)
        removed_skills = []
        for sid in old_exclusive:
            if sid in self.player.skills:
                # 找到技能名用于提示
                skill = self.skill_library.get(sid)
                skill_name = skill.name if skill else sid
                self.player.skills.remove(sid)
                removed_skills.append(skill_name)

        # 应用新流派修正（set_cultivation_path 会重置专属资源）
        modifiers = self.path_config.get_modifiers(new_path_id)
        self.player.set_cultivation_path(new_path_id, modifiers)

        # 提示
        new_name = self.path_config.get_path_name(new_path_id)
        old_name = self.path_config.get_path_name(old_path)
        self.notify(
            f"你从【{old_name}】转为【{new_name}】之道！"
        )
        if removed_skills:
            self.notify(f"旧流派的专属技能已遗忘：{'、'.join(removed_skills)}")
        self.notify("流派专属资源已清零，请重新积累。")
        # 记录年表
        self.chronicle_manager.record(
            f"从【{old_name}】转修【{new_name}】", category="cultivation"
        )
        self._auto_save()
        return True

