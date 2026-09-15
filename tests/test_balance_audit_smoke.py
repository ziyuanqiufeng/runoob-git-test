# -*- coding: utf-8 -*-
"""balance_audit 冒烟测试（§9 ②：balance_audit 接入 CI + smoke 测试）。

守护 CI 新增的 balance_audit 步骤：确保维度③三支柱审计在小型受控模拟下
不抛异常、返回结构符合预期。只读模拟，不改游戏逻辑。
"""
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(HERE)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from tools import balance_audit as ba  # noqa: E402


class TestBalanceAuditSmoke(unittest.TestCase):
    def test_audit_sect_returns_expected_keys(self):
        res = ba.audit_sect(6)
        self.assertIsInstance(res, dict)
        if "error" not in res:
            for k in ("qi_cap_month", "final_disciples", "steady_feedback", "traj"):
                self.assertIn(k, res)

    def test_audit_techniques_returns_expected_keys(self):
        res = ba.audit_techniques(6)
        self.assertIsInstance(res, dict)
        for k in (
            "techniques", "dao_heart_start", "dao_heart_end",
            "dao_heart_per_month", "months_50_to_100",
        ):
            self.assertIn(k, res)

    def test_audit_lifepath_returns_produced_dict(self):
        res = ba.audit_lifepath("alchemy", 6)
        self.assertIsInstance(res, dict)
        self.assertIn("produced", res)
        self.assertIsInstance(res["produced"], dict)

    def test_audit_battle_buff_returns_rows(self):
        rows = ba.audit_battle_buff()
        self.assertIsInstance(rows, list)
        self.assertTrue(len(rows) > 0)
        for r in rows:
            self.assertIn("path", r)


if __name__ == "__main__":
    unittest.main()
