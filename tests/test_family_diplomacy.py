# -*- coding: utf-8 -*-
"""FamilyDiplomacyManager 单元测试（F-01 外交）。"""
import unittest

from game.family import FamilyManager, FamilyDiplomacyManager


class TestFamilyDiplomacy(unittest.TestCase):
    def _mgr(self):
        fam = {"diplomacy": {}}
        mgr = FamilyDiplomacyManager(config_dir="config")
        return mgr, fam

    def test_list_targets(self):
        mgr, _ = self._mgr()
        targets = mgr.list_targets()
        self.assertGreaterEqual(len(targets), 1)
        self.assertIn("id", targets[0])

    def test_set_and_get_relation(self):
        mgr, fam = self._mgr()
        self.assertEqual(mgr.get_relation(fam, "su_family"), "neutral")
        self.assertTrue(mgr.set_relation(fam, "su_family", "ally"))
        self.assertEqual(mgr.get_relation(fam, "su_family"), "ally")
        self.assertTrue(mgr.is_ally(fam, "su_family"))
        # 非法关系被拒
        self.assertFalse(mgr.set_relation(fam, "su_family", "bogus"))

    def test_decay_to_neutral(self):
        mgr, fam = self._mgr()
        mgr.set_relation(fam, "su_family", "rival")
        # 用确定性 rng 强制不衰减（random() 返回 >0.05）
        class _R:
            def random(self):
                return 0.5
        changed = mgr.settle_monthly(fam, rng=_R())
        self.assertEqual(changed, [])


if __name__ == "__main__":
    unittest.main()
