# -*- coding: utf-8 -*-
"""动态剧情生成器：为游历事件文案注入环境与心境描写，使剧情不再千篇一律。

纯离线、零成本、即时生成。通过 config/story_flavors.json 的描写池，
按地点类型与玩家状态（心魔/红尘羁绊/天道注视/正邪）动态组合文案。
"""
import json
import os
import random


class StoryGenerator:
    """根据事件 + 玩家状态 + 地点，渲染更生动的剧情文案。"""

    def __init__(self, config_dir="config"):
        path = os.path.join(config_dir, "story_flavors.json")
        try:
            with open(path, "r", encoding="utf-8") as f:
                self.data = json.load(f)
        except (json.JSONDecodeError, OSError):
            self.data = {}

    # ---- 内部工具 ----

    def _pick(self, items, rng=None):
        """从列表中随机取一条；空列表返回空串。"""
        if not items:
            return ""
        return (rng or random).choice(items)

    def _env_flavor(self, location, rng=None):
        """按地点类型取环境描写。"""
        loc_type = (location or {}).get("type", "wild")
        env_map = self.data.get("environments", {})
        return self._pick(env_map.get(loc_type, []), rng)

    def _state_flavors(self, player):
        """按玩家状态收集命中的心境描写（可能多条）。"""
        states = []
        state_map = self.data.get("states", {})
        if getattr(player, "heart_demon", 0) >= 60:
            states.extend(state_map.get("heart_demon_high", []))
        else:
            states.extend(state_map.get("heart_demon_low", []))
        if getattr(player, "heaven_gaze", 0) >= 60:
            states.extend(state_map.get("heaven_gaze_high", []))
        if getattr(player, "red_dust_bonds", None):
            states.extend(state_map.get("red_dust_bonded", []))
        karma = getattr(player, "karma", 0)
        if karma > 0:
            states.extend(state_map.get("righteous", []))
        elif karma < 0:
            states.extend(state_map.get("demonic", []))
        return states

    # ---- 对外接口 ----

    def pick_description(self, event, rng=None):
        """取事件正文：优先 descriptions 变体随机一条，回退旧 description。

        descriptions 为空/缺失的旧配置与旧存档仍走单条 description，
        保证向后兼容。非 explore 路径（城池事件等）也可复用本方法。
        """
        variants = event.get("descriptions") or []
        if variants:
            return (rng or random).choice(variants)
        return event.get("description", "")

    def render_event(self, event, player, location=None, rng=None):
        """渲染事件文案，返回一段融入环境与心境的剧情文字。

        格式：{开头}，{环境}。{事件描述} {心境}，{收尾}
        事件描述优先取 descriptions 随机变体，消除重复游历的复读感。
        """
        rng = rng or random
        description = self.pick_description(event, rng)
        # 开头只在七成场合拼接：opener 多含明确时间（晨钟/月上山岗/日头西斜），
        # 而事件正文自有时序（如「夜里靠着树干」），无条件拼接会撞车。
        opener = ""
        if rng.random() < 0.7:
            opener = self._pick(self.data.get("openers", []), rng)
        env = self._env_flavor(location, rng)
        state = self._pick(self._state_flavors(player), rng)
        closer = self._pick(self.data.get("closers", []), rng)

        head = "，".join(p for p in (opener, env) if p)
        tail = "，".join(p for p in (state, closer) if p)

        pieces = []
        if head:
            pieces.append(head + "。")
        if description:
            pieces.append(description)
        if tail:
            pieces.append(tail)
        return "".join(pieces)

    def render_event_name(self, event):
        """返回事件标题（保持原名）。"""
        return event.get("name", "")
