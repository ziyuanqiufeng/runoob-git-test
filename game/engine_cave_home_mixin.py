# -*- coding: utf-8 -*-
"""GameEngine 洞府·居所·轮回域 Mixin（第九期纯净度修正，2026-09-22）。

洞府租用/闭关/信息、野居所占/维护/袭击、轮回转世。
方法原样迁出：第八期误并入 CityLifeMixin / 第六期误并入 SectMixin 的部分由本文件归位。
切出备份：tools/.purity_fix_backup_20260922.py。
"""


class CaveHomeMixin:
    """依赖宿主 GameEngine 的对应 Manager 实例属性与跨 Mixin 方法。"""

    def _tick_caves(self):
        """每月推进洞府租期与闭关修炼。"""
        # 若玩家处于闭关中，优先推进闭关收益
        if self.cave_manager.is_in_closed_door():
            qi_gain = self.cave_manager.tick_closed_door()
            if qi_gain > 0:
                self.notify(f"[cyan]闭关一月，获得修为 {qi_gain} 点。")
        # 推进所有洞府租期
        expired = self.cave_manager.tick_monthly()
        for name in expired:
            self.notify(f"【{name}】租期已到期。")

    def rent_cave(self, cave_id, months):
        """
        租赁城中洞府。

        返回 (success, message)。
        """
        ok, msg = self.cave_manager.rent_cave(cave_id, months)
        if ok:
            self._auto_save()
        return ok, msg

    def start_closed_door_cultivation(self, cave_id, months):
        """
        在租赁洞府中开始闭关修炼。

        返回 (success, message, expected_qi_gain)。
        """
        ok, msg, expected = self.cave_manager.start_closed_door(cave_id, months)
        if ok:
            self.notify(msg)
            self._auto_save()
        return ok, msg, expected

    def get_cave_info(self, location_id=None):
        """获取指定地点洞府信息，供 UI 展示。"""
        location_id = location_id or self.player.location_id
        caves = self.cave_manager.get_available_caves(location_id)
        result = []
        for cave in caves:
            cave_id = cave["id"]
            lease = self.cave_manager.get_current_lease(cave_id)
            result.append({
                "id": cave_id,
                "name": cave["name"],
                "description": cave["description"],
                "rent_per_month": cave.get("rent_per_month", 0),
                "max_lease_months": cave.get("max_lease_months", 12),
                "remaining_months": lease["remaining_months"] if lease else 0,
                "effects": cave.get("effects", {}),
            })
        return result

    # ==================== 私人洞府占领 ====================

    def can_occupy_wild_residence(self, location_id):
        """检查是否可以在指定地点占领野外洞府。"""
        return self.residence_manager.can_occupy(location_id)

    def start_residence_occupation(self, location_id):
        """发起野外洞府占领，返回 (success, message, guard_enemy_id)。

        占领成功发起后会在引擎中记录 pending_residence_occupation_location_id，
        便于 UI 层在战斗结束后调用 finish_residence_occupation 完成所有权转移。
        """
        # 调用 ResidenceManager 检查占领条件并返回守卫敌人 ID
        success, message, guard_enemy_id = self.residence_manager.occupy(location_id)
        if success:
            # 标记当前有待处理的占领战斗，记录目标地点 ID
            self.pending_residence_occupation_location_id = location_id
        return success, message, guard_enemy_id

    def finish_residence_occupation(self, location_id, win):
        """完成占领战斗，成功则获得洞府所有权。"""
        # 无论胜负，先清除占领战斗的待处理标记，避免重复结算
        if hasattr(self, "pending_residence_occupation_location_id"):
            del self.pending_residence_occupation_location_id
        ok, msg = self.residence_manager.finish_occupation(location_id, win)
        if ok:
            self.notify(msg)
            self._auto_save()
        return ok, msg

    def pay_residence_maintenance(self):
        """手动缴纳洞府维护费。"""
        ok, msg = self.residence_manager.pay_maintenance()
        if ok:
            self.notify(msg)
            self._auto_save()
        return ok, msg

    def resolve_residence_raid(self, win):
        """结算洞府袭击战斗结果。"""
        if not getattr(self, "pending_residence_raid", False):
            return
        self.pending_residence_raid = False
        ok, msg = self.residence_manager.resolve_raid(win)
        self.notify(msg)
        self._auto_save()

    def get_residence_info(self):
        """获取当前洞府状态摘要，供 UI 展示。"""
        if not self.player.residence:
            return None
        return {
            "id": self.player.residence["id"],
            "maintenance_cost": self.residence_manager.get_maintenance_cost(),
            "maintenance_debt": self.player.residence.get("maintenance_debt", 0),
            "energy": self.residence_manager.get_formation_energy(),
            "max_energy": self.residence_manager.get_max_formation_energy(),
            "defense_rate": self.residence_manager.get_defense_rate(),
            "spirit_vein_quality": self.residence_manager.get_spirit_vein_quality(),
        }

    # ==================== 社交系统接口 ====================

    def compute_reincarnation_options(self):
        """
        计算转世时可用的继承选项与点数。

        返回字典，包含 points、karma_category、options 等。
        """
        return self.reincarnation_manager.compute_available_options()

    def start_reincarnation(self, selected_option_ids):
        """转世重修：应用继承选择，生成新周目 Player 并注入前世羁绊。

        - new_player.past_bond 已由转世结算写入（道侣优先，其次好感最高 NPC）；
        - 向 NPC 库运行时注入"转世重逢"NPC（前世羁绊者转世现身于新周目）；
        - 输出宿慧叙事并记入年表。
        返回 (new_player, summary)。
        """
        from game.npc import NPC
        new_player, summary = self.apply_reincarnation(selected_option_ids)
        summary["past_bond"] = getattr(new_player, "past_bond", None)

        bond = getattr(new_player, "past_bond", None)
        if bond:
            bond_type_cn = "道侣" if bond["bond_type"] == "dao_lv" else "挚友"
            reborn_id = f"reborn_{bond['npc_id']}"
            if reborn_id not in self.npc_library.npcs:
                reborn_npc = NPC(
                    npc_id=reborn_id,
                    name=bond["name"],
                    location=new_player.location_id,
                    description=(
                        f"一位眉眼间似曾相识的修士。恍惚之间，你想起前世与"
                        f"{bond['name']}（{bond_type_cn}，情分 {bond['intimacy']}）"
                        f"的种种过往——如今TA转世重临，却已不记得你。"
                    ),
                    dialog=[
                        f"（{bond['name']}望着你，眼中闪过一丝迷惘）我们……是否在哪里见过？",
                        "总觉得你的气息莫名熟悉，像是很久很久以前的旧梦。",
                    ],
                    quests=[],
                    can_dual_cultivate=(bond["bond_type"] == "dao_lv"),
                )
                reborn_npc.past_life_bond = bond  # 供对话/AI 剧情引用前世信息
                self.npc_library.npcs[reborn_id] = reborn_npc
                # 前世羁绊写入新周目的 NPC 记忆（宿慧的具象化）
                new_player.record_npc_moment(
                    reborn_id,
                    f"前世：TA曾是我的{bond_type_cn}，情分深笃（亲密度 "
                    f"{bond['intimacy']}），一世纠葛未竟。",
                )
            self.notify(
                f"[purple]【宿慧】一缕前尘掠过心间：前世{bond_type_cn}"
                f"{bond['name']}的情分犹未了断——TA已转世重临人间，"
                f"或就在这方天地之间。"
            )
            self.chronicle_manager.record(
                f"第 {new_player.reincarnation_count} 世启程：前世{bond_type_cn}"
                f"{bond['name']}转世重逢的宿慧苏醒",
                category="reincarnation",
            )
        else:
            self.notify(
                f"[purple]【宿慧】前尘如烟，你于轮回中保住一缕真灵，"
                f"重踏修仙之路。"
            )
            self.chronicle_manager.record(
                f"第 {new_player.reincarnation_count} 世启程（无前世羁绊）",
                category="reincarnation",
            )
        return new_player, summary

    def apply_reincarnation(self, selected_option_ids):
        """
        应用玩家选择的继承项，生成新一世 Player。

        返回新 Player 实例与转世摘要信息。
        """
        from game.player import Player
        new_data = self.reincarnation_manager.apply_inheritance(selected_option_ids)
        new_player = self.reincarnation_manager.create_new_player(new_data, Player)
        summary = {
            "reincarnation_count": new_player.reincarnation_count,
            "karma": new_player.karma,
            "new_talents": new_data["new_talents"],
            "attribute_bonuses": new_data["attribute_bonuses"],
            "starting_items": new_data["starting_items"],
            "relationship_bonuses": new_data["relationship_bonuses"],
            "relic_chain_bonuses": new_data["relic_chain_bonuses"],
            "retain_roots": new_data.get("retain_roots", False),
            "past_bond": new_data.get("past_bond"),
            "negative_event": (
                new_data["negative_event"]["name"]
                if new_data["negative_event"]
                else None
            ),
        }
        return new_player, summary

