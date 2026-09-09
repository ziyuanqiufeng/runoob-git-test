# -*- coding: utf-8 -*-
"""坊市 NPC 配置管理器。

加载 config/market_npcs.json，为 engine 提供标准化的坊市商人、
拍卖师、摆摊散修等 NPC 数据，避免在代码中硬编码商品与对话。
"""
import json
import os


class MarketNPCManager:
    """管理坊市 NPC 配置。"""

    def __init__(self, config_dir="config"):
        self.config_dir = config_dir
        self._npcs = []
        self._npc_map = {}
        self._load()

    def _load(self):
        """加载坊市 NPC 配置。"""
        path = os.path.join(self.config_dir, "market_npcs.json")
        if not os.path.exists(path):
            return
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        self._npcs = data.get("npcs", [])
        self._npc_map = {n["id"]: n for n in self._npcs}

    def get_npc(self, npc_id):
        """根据 ID 获取 NPC 配置。"""
        return self._npc_map.get(npc_id)

    def get_all_npcs(self):
        """获取所有坊市 NPC 配置。"""
        return list(self._npcs)

    def get_npcs_by_service(self, service):
        """根据提供的服务筛选 NPC。"""
        return [n for n in self._npcs if service in n.get("services", [])]
