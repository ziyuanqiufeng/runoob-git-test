# -*- coding: utf-8 -*-
"""社交管理器：论道、双修、收徒、恩怨链。

本模块将 NPC 好感度、关系网与玩家社交属性整合，
提供一套可扩展的社交行为接口与月度推进逻辑。
"""

import random


class SocialManager:
    """管理玩家与 NPC 之间的论道、双修、收徒与恩怨链。

    参数:
        player: 玩家对象。
        npc_library: NPC 库，用于查询 NPC 信息与关系网。
        world: 世界对象，用于获取当前时间。
        config_dir: 配置目录，默认 "config"。
    """

    def __init__(self, player, npc_library, world, config_dir="config"):
        # 保存依赖对象
        self.player = player
        self.npc_library = npc_library
        self.world = world

    # ==================== 论道 ====================

    def can_debate(self, npc_id):
        """检查是否可与指定 NPC 论道。

        返回 (bool, message)。
        """
        npc = self.npc_library.get(npc_id)
        if not npc:
            return False, "NPC 不存在。"
        # 与仇敌或复仇目标无法论道
        if self.player.has_grudge(npc_id):
            return False, "你与对方有恩怨，无法心平气和地论道。"
        if npc_id in getattr(self.player, "revenge_targets", []):
            return False, "对方正欲找你寻仇，此时论道不合时宜。"
        # 好感度过低（-5 以下）无法进行理性交流
        if self.player.get_npc_relationship(npc_id) <= -5:
            return False, "对方对你颇为反感，拒绝与你论道。"
        return True, ""

    def debate(self, npc_id, rng=None):
        """与 NPC 论道。

        返回 (success, message, win)。
        success 表示是否成功发起论道；win 表示论道胜负。
        """
        rng = rng or random
        ok, msg = self.can_debate(npc_id)
        if not ok:
            return False, msg, None

        npc = self.npc_library.get(npc_id)
        # 计算双方论道得分：悟性 + 随机波动 + 好感度修正
        player_score = (
            getattr(self.player, "wisdom", 5)
            + rng.randint(-3, 3)
            + max(0, self.player.get_npc_relationship(npc_id) // 2)
        )
        npc_score = (
            getattr(npc, "wisdom", 5)
            + rng.randint(-2, 2)
        )

        win = player_score >= npc_score
        if win:
            # 胜利：好感度 +1，悟性概率 +1，论道记录胜利 +1
            self.player.increase_npc_relationship(npc_id, 1)
            if rng.random() < 0.3:
                self.player.wisdom += 1
                wisdom_gain = "，悟性略有提升"
            else:
                wisdom_gain = ""
            self.player.debate_record["wins"] += 1
            return (
                True,
                f"你在论道中辩赢了 {npc.name}，双方对大道理解更进一步{wisdom_gain}。",
                True,
            )
        else:
            # 失败：好感度 -1，悟性仍有小概率提升（从失败中领悟）
            self.player.decrease_npc_relationship(npc_id, 1)
            if rng.random() < 0.1:
                self.player.wisdom += 1
                wisdom_gain = "，虽败但亦有所悟，悟性微增"
            else:
                wisdom_gain = ""
            self.player.debate_record["losses"] += 1
            return (
                True,
                f"你在论道中被 {npc.name} 指出破绽，略有所失{wisdom_gain}。",
                False,
            )

    # ==================== 双修 ====================

    def can_dual_cultivate(self, npc_id):
        """检查是否可与指定 NPC 双修。

        返回 (bool, message)。
        """
        npc = self.npc_library.get(npc_id)
        if not npc:
            return False, "NPC 不存在。"
        if not getattr(npc, "can_dual_cultivate", True):
            return False, "对方不接受双修。"
        # 同性不可双修（可随世界观调整）
        if getattr(self.player, "gender", "male") == getattr(npc, "gender", "male"):
            return False, "同性之间无法进行双修。"
        # 年龄限制：避免过大年龄差
        player_age = getattr(self.player, "age", 16)
        npc_age = getattr(npc, "age", 30)
        if abs(player_age - npc_age) > 200:
            return False, "双方年龄相差过大，无法双修。"
        # 好感度要求
        if self.player.get_npc_relationship(npc_id) < 5:
            return False, "双方好感度不足，需达到 5 以上方可双修。"
        # 师徒、血缘关系不可双修
        if self.player.master_id == npc_id:
            return False, "不可与师父双修。"
        if npc_id in self.player.disciples:
            return False, "不可与徒弟双修。"
        if npc_id in getattr(self.player, "sworn_brothers", []):
            return False, "结拜兄弟之间不宜双修。"
        # 仇敌不可双修
        if self.player.has_grudge(npc_id):
            return False, "你与对方有恩怨，无法双修。"
        return True, ""

    def dual_cultivate(self, npc_id, rng=None):
        """与 NPC 双修，双方获得修为与好感度。

        返回 (success, message)。
        """
        rng = rng or random
        ok, msg = self.can_dual_cultivate(npc_id)
        if not ok:
            return False, msg

        npc = self.npc_library.get(npc_id)
        # 双修修为收益：基于玩家当前修为上限的一定比例
        base_qi_gain = int(getattr(self.player, "max_qi", 100) * 0.05)
        # 悟性加成
        wisdom_bonus = getattr(self.player, "wisdom", 5) * 0.01
        qi_gain = int(base_qi_gain * (1 + wisdom_bonus + rng.uniform(-0.1, 0.1)))
        qi_gain = max(1, qi_gain)

        # 收益上限为 max_qi 的 30%，防止溢出
        max_gain = int(getattr(self.player, "max_qi", 100) * 0.3)
        qi_gain = min(qi_gain, max_gain)

        self.player.qi = min(
            getattr(self.player, "max_qi", 999999),
            self.player.qi + qi_gain
        )
        # 好感度进一步提升
        self.player.increase_npc_relationship(npc_id, 1)
        # 双修耗费 15 日
        if self.world:
            self.world.advance(15)
            self.player.add_age_months(15)
        return (
            True,
            f"你与 {npc.name} 阴阳调和，修为增加 {qi_gain} 点，彼此关系更进一步。"
        )

    # ==================== 收徒 ====================

    def can_accept_disciple(self, npc_id):
        """检查是否可收指定 NPC 为徒。

        返回 (bool, message)。
        """
        npc = self.npc_library.get(npc_id)
        if not npc:
            return False, "NPC 不存在。"
        # 玩家境界必须高于 NPC
        player_order = self.player.REALM_ORDER.get(self.player.realm_id, 0)
        npc_order = self.player.REALM_ORDER.get(
            getattr(npc, "realm_id", "qi_refining_1"), 0
        )
        if player_order <= npc_order:
            return False, "你的境界需高于对方才能收徒。"
        # 好感度要求
        if self.player.get_npc_relationship(npc_id) < 4:
            return False, "双方好感度不足，需达到 4 以上方可收徒。"
        # 对方不能是玩家师父或已有师父
        if self.player.master_id == npc_id:
            return False, "你不能收自己的师父为徒。"
        if npc_id in self.player.disciples:
            return False, "对方已是你的徒弟。"
        # 徒弟数量上限（暂定 5 人）
        if len(self.player.disciples) >= 5:
            return False, "你门下的徒弟已满，无法再收徒。"
        return True, ""

    def accept_disciple(self, npc_id):
        """收 NPC 为徒。"""
        ok, msg = self.can_accept_disciple(npc_id)
        if not ok:
            return False, msg

        npc = self.npc_library.get(npc_id)
        disciple = {
            "npc_id": npc_id,
            "name": npc.name,
            "realm_id": getattr(npc, "realm_id", "qi_refining_1"),
            "progress": 0,  # 徒弟成长进度 0-100
            "loyalty": 50,  # 忠诚度 0-100
        }
        self.player.disciples.append(disciple)
        self.player.increase_npc_relationship(npc_id, 2)
        return (
            True,
            f"你收下 {npc.name} 为徒，日后可传授技艺、助其修行。"
        )

    def teach_disciple(self, npc_id, rng=None):
        """传授徒弟技艺，提升其成长进度与忠诚度。"""
        rng = rng or random
        disciple = next(
            (d for d in self.player.disciples if d["npc_id"] == npc_id),
            None
        )
        if not disciple:
            return False, "对方不是你的徒弟。"

        # 每次传授增加进度与忠诚
        progress_gain = 10 + getattr(self.player, "wisdom", 5) // 2
        disciple["progress"] = min(100, disciple["progress"] + progress_gain)
        disciple["loyalty"] = min(100, disciple["loyalty"] + 5)

        # 徒弟突破逻辑：进度满 100 时提升境界
        if disciple["progress"] >= 100:
            old_realm = disciple["realm_id"]
            realms = list(self.player.REALM_ORDER.keys())
            old_index = realms.index(old_realm) if old_realm in realms else 0
            if old_index + 1 < len(realms):
                disciple["realm_id"] = realms[old_index + 1]
                disciple["progress"] = 0
                return (
                    True,
                    f"你对 {disciple['name']} 悉心教导，其修为突破至新境界！"
                )
            else:
                disciple["progress"] = 100
                return (
                    True,
                    f"{disciple['name']} 在你的教导下大有精进，已接近瓶颈。"
                )
        return (
            True,
            f"你指导 {disciple['name']} 修行，徒弟进度 +{progress_gain}。"
        )

    # ==================== 恩怨链 ====================

    def add_grudge(self, npc_id, reason=""):
        """添加恩怨，并将 NPC 加入复仇目标列表（若等级较高）。"""
        npc = self.npc_library.get(npc_id)
        if not npc:
            return False, "NPC 不存在。"
        level = self.player.add_grudge(npc_id, 1, reason)
        if level >= 3 and npc_id not in self.player.revenge_targets:
            self.player.revenge_targets.append(npc_id)
        return (
            True,
            f"你与 {npc.name} 结下恩怨，当前恩怨等级：{level}。"
        )

    def resolve_grudge(self, npc_id):
        """通过和解化解恩怨（需要好感度 >= 0）。"""
        if not self.player.has_grudge(npc_id):
            return False, "你们之间并无恩怨。"
        if self.player.get_npc_relationship(npc_id) < 0:
            return False, "对方余怒未消，暂时无法和解。"
        self.player.remove_grudge(npc_id)
        if npc_id in self.player.revenge_targets:
            self.player.revenge_targets.remove(npc_id)
        npc = self.npc_library.get(npc_id)
        return True, f"你与 {npc.name} 冰释前嫌，恩怨已了。"

    def can_revenge(self, npc_id):
        """检查是否可对某 NPC 发起复仇。"""
        if not self.player.has_grudge(npc_id):
            return False, "你们之间并无恩怨。"
        npc = self.npc_library.get(npc_id)
        if not npc:
            return False, "NPC 不存在。"
        return True, ""

    def tick_grudges(self):
        """月度推进恩怨链：低等级恩怨自然衰减，高等级触发复仇事件。

        返回当月发生的事件列表，每项为 {"type": str, "npc_id": str, "message": str}。
        """
        events = []
        if not self.player.grudges:
            return events

        current_month = getattr(self.world, "month", 0) if self.world else 0
        to_remove = []
        for npc_id, grudge in list(self.player.grudges.items()):
            level = grudge.get("level", 1)
            # 低等级恩怨随时间衰减
            if level <= 1 and current_month - grudge.get("start_month", 0) >= 6:
                to_remove.append(npc_id)
                events.append({
                    "type": "grudge_decay",
                    "npc_id": npc_id,
                    "message": "随着时间流逝，一段小恩怨逐渐淡去。"
                })
                continue
            # 高等级恩怨有概率触发 NPC 寻仇
            if level >= 3 and random.random() < 0.05 * level:
                npc = self.npc_library.get(npc_id)
                if npc and npc_id not in self.player.revenge_targets:
                    self.player.revenge_targets.append(npc_id)
                events.append({
                    "type": "revenge_encounter",
                    "npc_id": npc_id,
                    "message": f"{npc.name if npc else npc_id} 因旧怨找上门来！"
                })
        for npc_id in to_remove:
            self.player.remove_grudge(npc_id)
        return events

    def on_npc_killed(self, npc_id):
        """击杀 NPC 后清理相关恩怨与关系。"""
        if npc_id in self.player.revenge_targets:
            self.player.revenge_targets.remove(npc_id)
        if npc_id in self.player.grudges:
            del self.player.grudges[npc_id]
        # 击杀会严重影响该 NPC 亲友的好感度
        npc = self.npc_library.get(npc_id)
        if not npc:
            return []
        events = []
        for friend_id in getattr(npc, "npc_relationships", {}).get("friends", []):
            self.player.decrease_npc_relationship(friend_id, 5)
            self.player.add_grudge(friend_id, 1, f"杀害 {npc.name} 之仇")
            events.append({
                "type": "friend_grudge",
                "npc_id": friend_id,
                "message": f"{npc.name} 的友人得知其死讯，对你恨之入骨。"
            })
        return events
