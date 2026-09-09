# -*- coding: utf-8 -*-
"""秘境节点图生成（F-03 Roguelike 秘境，杀戮尖塔风格 DAG）。

每层若干节点，节点类型按 floor_templates 权重随机；
除最后一层（固定单个 Boss）外，每个节点连向下一层 1~2 个邻近节点。
返回结构：layers = [ [node, ...], ... ]，node = {
    "id", "layer", "index", "type", "enemy_level"(可选), "edges": [next_node_id, ...]
}
"""
import json
import os
import random


class RealmNodeManager:
    def __init__(self, config_dir="config", rng=None):
        self.config_dir = config_dir
        self.rng = rng or random
        self.templates = []
        self.default_total_floors = 8
        self.qi_per_node = 12
        self.start_qi = 100
        path = os.path.join(config_dir, "secret_realm", "realm_floors.json")
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.templates = data.get("floor_templates", [])
            self.default_total_floors = data.get("default_total_floors", 8)
            self.qi_per_node = data.get("qi_per_node", 12)
            self.start_qi = data.get("start_qi", 100)

    def _template_for_floor(self, floor):
        for t in self.templates:
            lo, hi = t["floor_range"]
            if lo <= floor <= hi:
                return t
        return self.templates[-1] if self.templates else None

    @staticmethod
    def _weighted_type(weights, rng):
        items = list(weights.items())
        if not items:
            return "battle"
        total = sum(w for _, w in items)
        r = rng.random() * total
        acc = 0.0
        for name, w in items:
            acc += w
            if r <= acc:
                return name
        return items[0][0]

    def generate_map(self, total_floors=None, rng=None):
        rng = rng or self.rng
        total = total_floors or self.default_total_floors
        layers = []
        prev_nodes = None
        for f in range(1, total + 1):
            if f == total:
                boss = {
                    "id": f"n_{f}_0",
                    "layer": f,
                    "index": 0,
                    "type": "boss",
                    "enemy_level": None,
                    "edges": [],
                }
                if prev_nodes:
                    for pn in prev_nodes:
                        pn["edges"].append(boss["id"])
                layers.append([boss])
                prev_nodes = [boss]
                continue
            t = self._template_for_floor(f)
            cnt = rng.randint(*t["node_count"]) if t else 5
            weights = t["node_weights"] if t else {"battle": 70, "event": 20, "shop": 10}
            level_range = t["enemy_level_range"] if t else [1, 3]
            nodes = []
            for i in range(cnt):
                ntype = self._weighted_type(weights, rng)
                nodes.append({
                    "id": f"n_{f}_{i}",
                    "layer": f,
                    "index": i,
                    "type": ntype,
                    "enemy_level": rng.randint(*level_range)
                    if ntype in ("battle", "elite", "boss") else None,
                    "edges": [],
                })
            if prev_nodes:
                for pn in prev_nodes:
                    targets = self._connect_targets(pn, nodes, rng)
                    pn["edges"].extend(targets)
            layers.append(nodes)
            prev_nodes = nodes
        return layers

    @staticmethod
    def _connect_targets(pn, nodes, rng):
        """每个节点连向下一层 1~2 个邻近节点（按 index 接近度）。"""
        if not nodes:
            return []
        n = len(nodes)
        k = rng.choice([1, 2])
        # 以当前节点在上一层的相对位置映射到下一层相对位置
        start = rng.randint(0, max(0, n - 1))
        targets = []
        for j in range(k):
            idx = min(n - 1, start + j)
            tid = nodes[idx]["id"]
            if tid not in targets:
                targets.append(tid)
        return targets
