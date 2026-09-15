# -*- coding: utf-8 -*-
"""RealmNodeManager 单元测试（F-03 节点图生成）。"""
import random
import unittest

from game.realm_node import RealmNodeManager


class TestRealmNode(unittest.TestCase):
    def test_map_structure(self):
        rng = random.Random(42)
        mgr = RealmNodeManager("config", rng=rng)
        layers = mgr.generate_map(total_floors=8, rng=rng)
        self.assertEqual(len(layers), 8)
        # 最后一层固定单个 Boss
        self.assertEqual(len(layers[-1]), 1)
        self.assertEqual(layers[-1][0]["type"], "boss")
        # 非最后层每个节点都有前向连线
        for li in range(len(layers) - 1):
            for n in layers[li]:
                self.assertGreaterEqual(len(n["edges"]), 1)

    def test_map_reachable_to_boss(self):
        rng = random.Random(7)
        mgr = RealmNodeManager("config", rng=rng)
        layers = mgr.generate_map(total_floors=6, rng=rng)
        by_id = {n["id"]: n for layer in layers for n in layer}
        reachable = set(n["id"] for n in layers[0])
        frontier = list(layers[0])
        while frontier:
            cur = frontier.pop()
            for tid in cur["edges"]:
                if tid not in reachable:
                    reachable.add(tid)
                    frontier.append(by_id[tid])
        self.assertIn(layers[-1][0]["id"], reachable)

    def test_node_ids_unique(self):
        rng = random.Random(99)
        mgr = RealmNodeManager("config", rng=rng)
        layers = mgr.generate_map(total_floors=5, rng=rng)
        ids = [n["id"] for layer in layers for n in layer]
        self.assertEqual(len(ids), len(set(ids)))


if __name__ == "__main__":
    unittest.main()
