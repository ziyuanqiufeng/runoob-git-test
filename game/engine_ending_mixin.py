# -*- coding: utf-8 -*-
"""引擎结局/飞升域与主线剧情域 Mixin。

GameEngine 继承本文件中的两个 Mixin。方法通过鸭子类型访问引擎成员
（player/notify/chronicle_manager/_auto_save/config_dir 等）。
"""
import json
import os
import random


class EndingMixin:
    """多结局系统：结局加载、条件判定、触发与飞升尝试。"""

    # ==================== 多结局系统 ====================

    def _load_endings(self):
        """读取多结局定义 config/endings.json；失败返回空映射。"""
        path = os.path.join(self.config_dir, "endings.json")
        if not os.path.exists(path):
            return {"endings": [], "fallback": None}
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError):
            return {"endings": [], "fallback": None}
        if not isinstance(data, dict):
            return {"endings": [], "fallback": None}
        return {
            "endings": [e for e in data.get("endings", []) if isinstance(e, dict)],
            "fallback": data.get("fallback"),
        }

    def _check_ending_conditions(self, ending):
        """检查玩家是否满足某个结局的全部条件。"""
        cond = ending.get("conditions", {}) or {}
        p = self.player
        karma = getattr(p, "karma", 0)
        heart_demon = getattr(p, "heart_demon", 0)
        heaven_gaze = getattr(p, "heaven_gaze", 0)
        bonds = len(getattr(p, "red_dust_bonds", []) or [])
        if "karma_min" in cond and karma < cond["karma_min"]:
            return False
        if "karma_max" in cond and karma > cond["karma_max"]:
            return False
        if "heart_demon_min" in cond and heart_demon < cond["heart_demon_min"]:
            return False
        if "heart_demon_max" in cond and heart_demon > cond["heart_demon_max"]:
            return False
        if "heaven_gaze_min" in cond and heaven_gaze < cond["heaven_gaze_min"]:
            return False
        if "heaven_gaze_max" in cond and heaven_gaze > cond["heaven_gaze_max"]:
            return False
        if "red_dust_bonds_min" in cond and bonds < cond["red_dust_bonds_min"]:
            return False
        return True

    def _judge_ending(self, context):
        """根据触发场景与玩家状态判定结局，返回结局 dict；无匹配返回 None。"""
        endings = self._endings.get("endings", [])
        candidates = [e for e in endings if e.get("context") == context]
        candidates.sort(key=lambda e: e.get("priority", 999))
        for e in candidates:
            if self._check_ending_conditions(e):
                return e
        fallback_id = self._endings.get("fallback")
        for e in endings:
            if e.get("id") == fallback_id:
                return e
        return None

    def _trigger_ending(self, context):
        """判定并记录结局，返回结局 dict（已记录则返回 None）。"""
        if getattr(self.player, "ending_id", None):
            return None
        ending = self._judge_ending(context)
        if not ending:
            return None
        self.player.ending_id = ending["id"]
        if context == "ascend":
            self.player.has_won = True
        self.notify(f"[gold]【结局】{ending['name']}：{ending['desc']}")
        self.chronicle_manager.record(
            f"达成结局【{ending['name']}】", category="ending"
        )
        self.notify(f"__ENDING__:{ending['id']}")
        self._check_main_story()
        self._auto_save()
        return ending

    def _attempt_ascension(self):
        """元婴圆满尝试飞升：判定飞升劫与结局。"""
        p = self.player
        # 心魔过高：走火入魔
        if getattr(p, "heart_demon", 0) >= 80:
            self.notify("[red]飞升之际心魔大盛，你即将走火入魔！")
            return self._trigger_ending("ascend_fail")
        # 天道注视过高：天道降罚
        if getattr(p, "heaven_gaze", 0) >= 90:
            self.notify("[red]天道注视已久，飞升天劫化作灭世神雷！")
            return self._trigger_ending("ascend_fail")
        # 飞升成功率：受心魔与天道注视影响
        rate = 0.8 - (getattr(p, "heart_demon", 0) / 100.0) * 0.5 - (getattr(p, "heaven_gaze", 0) / 100.0) * 0.4
        rate = max(0.1, min(0.95, rate))
        success = random.random() < rate
        if success:
            self.notify("[gold]你渡过飞升天劫，白日飞升！")
            return self._trigger_ending("ascend")
        self.notify("[red]飞升天劫之下，你肉身兵解，唯余一丝真灵。")
        return self._trigger_ending("ascend_fail")


class MainStoryMixin:
    """主线剧情：章节加载、条件检查与推进。"""

    # ==================== 主线剧情 ====================

    def _load_main_story(self):
        """读取主线章节 config/main_story.json；失败返回空映射。"""
        path = os.path.join(self.config_dir, "main_story.json")
        if not os.path.exists(path):
            return {"chapters": []}
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError):
            return {"chapters": []}
        if not isinstance(data, dict):
            return {"chapters": []}
        return {"chapters": [c for c in data.get("chapters", []) if isinstance(c, dict)]}

    def _meet_story_condition(self, cond):
        """判断玩家是否满足主线章节的完成条件。"""
        cond = cond or {}
        t = cond.get("type")
        if t == "sect":
            return bool(getattr(self.player, "sect_id", None))
        if t == "realm":
            order = self.player.REALM_ORDER.get(self.player.realm_id, 0)
            return order >= cond.get("order", 0)
        if t == "ending":
            return getattr(self.player, "ending_id", None) is not None
        return False

    def _check_main_story(self):
        """检查当前主线章节是否完成，完成则推进到下一章。"""
        chapters = self._main_story.get("chapters", [])
        if not chapters:
            return
        step = getattr(self.player, "main_story_step", 0)
        if step >= len(chapters):
            return
        cur = chapters[step]
        if not self._meet_story_condition(cur.get("condition")):
            return
        self.player.main_story_step = step + 1
        self.notify(f"[gold]【主线】{cur.get('title', '')} 完成！")
        self.chronicle_manager.record(
            f"完成主线章节【{cur.get('title', '')}】", category="quest"
        )
        if step + 1 < len(chapters):
            nxt = chapters[step + 1]
            self.notify(f"[cyan]【主线】{nxt.get('title', '')}：{nxt.get('desc', '')}")
        else:
            self.notify("[gold]【主线】全部章节完成，你已走完问道长生之路！")
        self._auto_save()

    def get_main_story_progress(self):
        """返回当前主线章节 (title, desc, current, total)；已完成返回 None。"""
        chapters = self._main_story.get("chapters", [])
        if not chapters:
            return None
        step = getattr(self.player, "main_story_step", 0)
        if step >= len(chapters):
            return None
        cur = chapters[step]
        return (cur.get("title", ""), cur.get("desc", ""), step + 1, len(chapters))
