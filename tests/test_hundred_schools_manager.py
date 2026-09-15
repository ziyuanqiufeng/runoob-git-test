# -*- coding: utf-8 -*-
"""维度③ 百家争鸣 管理器测试。"""
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from game.hundred_schools_manager import HundredSchoolsManager
from game.skill import Skill
from game.player import Player


def _player(realm="golden_core_early", stones=200):
    """构造带灵石物品的测试玩家。"""
    p = Player("测试道友")
    p.realm_id = realm
    # 直接塞入灵石 item（与游戏内一致：spirit_stone 是物品）
    for _ in range(stones):
        p.add_item(_stone())
    return p


class _Stone:
    def __init__(self):
        self.id = "spirit_stone"
        self.name = "灵石"
        self.type = "currency"
        self.value = 1
        self.description = ""
        self.effects = {}
        self.stackable = True
        self.max_stack = 99
        self.count = 1


def _stone():
    return _Stone()


def test_found_sect_requires_golden_core():
    p = _player(realm="foundation_peak")
    mgr = HundredSchoolsManager(p)
    ok, msg = mgr.found_sect("青云宗")
    assert ok is False
    assert mgr.get_sect_status() is None


def test_found_sect_success_and_feedback():
    p = _player(realm="golden_core_early", stones=100)
    mgr = HundredSchoolsManager(p)
    ok, msg = mgr.found_sect("青云宗")
    assert ok is True
    assert mgr.get_sect_status()["name"] == "青云宗"
    assert p.count_item("spirit_stone") == 50  # 消耗 50 开派

    # 月度结算应增长弟子、气运，并产出灵石反哺
    before = p.count_item("spirit_stone")
    rewards = mgr.tick_monthly()
    assert rewards["spirit_stone"] >= 0
    assert mgr.get_sect_status()["disciples"] >= 1
    assert mgr.get_sect_status()["qi_yun"] > 0


def test_found_sect_no_duplicate():
    p = _player(realm="golden_core_early", stones=100)
    mgr = HundredSchoolsManager(p)
    mgr.found_sect("青云宗")
    ok, msg = mgr.found_sect("再立一宗")
    assert ok is False


def test_create_technique_limits_and_dao_heart():
    p = _player(realm="golden_core_early", stones=200)
    mgr = HundredSchoolsManager(p)
    ok, msg = mgr.create_technique("太上忘情诀", "剑修", "dao_heart")
    assert ok is True
    assert len(p.self_created_techniques) == 1
    # 月度结算自创功法应增益道心
    ms0 = p.mental_state
    mgr.tick_monthly()
    assert p.mental_state >= ms0


def test_create_technique_bad_attribute():
    p = _player(realm="golden_core_early", stones=200)
    mgr = HundredSchoolsManager(p)
    ok, msg = mgr.create_technique("邪功", "剑修", "illegal_attr")
    assert ok is False


def test_create_technique_max_reached():
    p = _player(realm="golden_core_early", stones=500)
    mgr = HundredSchoolsManager(p)
    for i in range(5):
        mgr.create_technique(f"功法{i}", "剑修", "dao_heart")
    ok, msg = mgr.create_technique("第六门", "剑修", "dao_heart")
    assert ok is False


def test_choose_life_path_and_mitigation():
    p = _player(realm="golden_core_early", stones=50)
    mgr = HundredSchoolsManager(p)
    ok, msg = mgr.choose_life_path("alchemy")
    assert ok is True
    assert p.life_path == "alchemy"
    # 精进度需达阈值才化解
    assert mgr.should_mitigate_heart_demon_tribulation() is False
    for _ in range(60):  # 远超 max_proficiency，达到上限
        mgr.tick_monthly()
    prof = mgr.get_life_path_proficiency()
    assert prof > 0
    # 达到阈值后，按概率返回 bool（多次调用至少一个结果类型正确）
    results = [mgr.should_mitigate_heart_demon_tribulation() for _ in range(20)]
    assert all(isinstance(r, bool) for r in results)


def test_enlightenment_consumes_qi_yun():
    p = _player(realm="golden_core_early", stones=100)
    mgr = HundredSchoolsManager(p)
    mgr.found_sect("青云宗")
    for _ in range(20):  # 累积气运
        mgr.tick_monthly()
    qi_before = mgr.get_sect_status()["qi_yun"]
    assert qi_before >= 10
    ms0 = p.mental_state
    ok, msg = mgr.spend_qi_yun_for_enlightenment()
    assert ok is True
    assert p.mental_state > ms0
    assert mgr.get_sect_status()["qi_yun"] < qi_before


def test_enlightenment_no_sect():
    p = _player(realm="golden_core_early", stones=100)
    mgr = HundredSchoolsManager(p)
    ok, msg = mgr.spend_qi_yun_for_enlightenment()
    assert ok is False


def test_get_status_structure():
    p = _player(realm="golden_core_early", stones=100)
    mgr = HundredSchoolsManager(p)
    status = mgr.get_status()
    assert set(status.keys()) >= {"sect", "techniques", "life_path", "life_path_proficiency", "mental_state"}


def test_create_technique_stores_skill_id():
    p = _player(realm="golden_core_early", stones=200)
    mgr = HundredSchoolsManager(p)
    ok, msg = mgr.create_technique("太上忘情诀", "剑修", "dao_heart")
    assert ok is True
    tech = p.self_created_techniques[-1]
    assert tech["skill_id"].startswith("self_tech_")
    # 第二门功法 id 递增、不冲突
    mgr.create_technique("青莲剑歌", "剑修", "attack")
    assert p.self_created_techniques[1]["skill_id"] == "self_tech_2"


def test_build_skill_kwargs_maps_template_and_element():
    p = _player(realm="golden_core_early", stones=200)
    mgr = HundredSchoolsManager(p)
    mgr.create_technique("太上忘情诀", "剑修", "dao_heart")
    tech = p.self_created_techniques[-1]
    kw = mgr.build_skill_kwargs(tech)
    assert kw is not None
    assert kw["skill_id"] == tech["skill_id"]
    assert kw["name"] == "太上忘情诀"
    # dao_heart → metal 元素（来自 attribute_element 配置）
    assert kw["element"] == "metal"
    # 剑修模板：高 base_damage，无 path_exclusive 限制
    assert kw["base_damage"] == 30
    assert kw["path_exclusive"] is None
    # 构造出的 Skill 可被引擎直接注册（字段与 Skill.__init__ 对齐）
    sk = Skill(**kw)
    assert sk.id == tech["skill_id"]
    assert sk.base_damage == 30


def test_build_skill_kwargs_unknown_school_returns_none():
    p = _player(realm="golden_core_early", stones=200)
    mgr = HundredSchoolsManager(p)
    assert mgr.build_skill_kwargs({"school": "不存在的流派", "attribute": "attack"}) is None


def test_tick_produces_life_path_item_when_due():
    p = _player(realm="golden_core_early", stones=50)
    mgr = HundredSchoolsManager(p)
    mgr.choose_life_path("talisman")
    # 推满精进度以越过 min_proficiency；并把 age_months 对齐到 2 的倍数（every_months=2）
    for _ in range(50):
        mgr.tick_monthly()
    p.age_months = 4  # 4 % 2 == 0 → 本应产出
    rewards = mgr.tick_monthly()
    assert "talisman_paper" in rewards["produced_items"]

    # 丹道流派产出 qi_pill
    p2 = _player(realm="golden_core_early", stones=50)
    mgr2 = HundredSchoolsManager(p2)
    mgr2.choose_life_path("alchemy")
    for _ in range(50):
        mgr2.tick_monthly()
    p2.age_months = 3  # 3 % 3 == 0
    rewards2 = mgr2.tick_monthly()
    assert "qi_pill" in rewards2["produced_items"]
