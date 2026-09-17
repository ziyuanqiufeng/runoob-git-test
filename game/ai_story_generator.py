# -*- coding: utf-8 -*-
"""Agnes AI 文本生成器：调用 Agnes LLM 生成动态剧情文案。

失败（网络/超时/额度/无 key）时返回 None，由调用方回退到离线模板。
"""
import json
import os
import urllib.error
import urllib.request


class AIStoryGenerator:
    """封装 Agnes LLM（chat/completions）生成游历剧情文案。"""

    def __init__(self, config_dir="config"):
        self.config = self._load_config(config_dir)

    def _load_config(self, config_dir):
        path = os.path.join(config_dir, "ai_config.json")
        try:
            with open(path, "r", encoding="utf-8") as f:
                cfg = json.load(f)
            return cfg if isinstance(cfg, dict) else {}
        except (json.JSONDecodeError, OSError):
            return {}

    def _api_key(self):
        return os.environ.get("AGNES_API_KEY") or self.config.get("api_key", "")

    def _state_desc(self, player):
        parts = []
        if getattr(player, "heart_demon", 0) >= 60:
            parts.append("心魔缠身，心神不宁")
        else:
            parts.append("道心澄澈，气机平和")
        if getattr(player, "heaven_gaze", 0) >= 60:
            parts.append("感到天道注视如芒在背")
        if getattr(player, "red_dust_bonds", None):
            parts.append("心系红尘牵挂")
        karma = getattr(player, "karma", 0)
        if karma > 0:
            parts.append("一身浩然正气")
        elif karma < 0:
            parts.append("行事随心，隐有煞气")
        return "；".join(parts) if parts else "心境平和"

    def _build_prompt(self, event, player, location, realm_name):
        loc_type = (location or {}).get("type", "wild")
        type_desc = {"city": "繁华城池", "sect": "仙门宗派", "wild": "荒野之地"}.get(
            loc_type, "荒野"
        )
        loc_name = (location or {}).get("name", "某处")
        return (
            "你是古典仙侠小说的写手。请根据以下信息，用古风笔法写一段修士游历奇遇的描写，"
            "融入环境氛围与修士心境，文笔典雅、不写对话、不要标题，约50字：\n\n"
            f"事件：{event.get('description', '')}\n"
            f"地点：{loc_name}（{type_desc}）\n"
            f"境界：{realm_name or '炼气期'}\n"
            f"心境：{self._state_desc(player)}\n\n"
            "只输出正文，不要解释。"
        )

    def generate_story(self, event, player, location=None, realm_name=None):
        """调 Agnes LLM 生成剧情文案；失败返回 None。"""
        base_url = self.config.get("base_url", "")
        api_key = self._api_key()
        if not base_url or not api_key:
            return None
        payload = {
            "model": self.config.get("model", "agnes-3.0-flash"),
            "messages": [{"role": "user", "content": self._build_prompt(event, player, location, realm_name)}],
            "max_tokens": self.config.get("max_tokens", 200),
        }
        req = urllib.request.Request(
            base_url,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": "Bearer " + api_key,
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(
                req, timeout=self.config.get("timeout_seconds", 60)
            ) as resp:
                body = resp.read().decode("utf-8")
            data = json.loads(body)
            content = data["choices"][0]["message"]["content"]
            content = (content or "").strip()
            return content or None
        except Exception:
            return None
