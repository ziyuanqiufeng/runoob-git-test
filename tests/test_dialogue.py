# -*- coding: utf-8 -*-
"""对话系统单元测试。

覆盖：对话配置加载、条件判断、效果执行、选项推进、NPC dialogue_id 关联。
"""
import os
import unittest

from PySide6.QtWidgets import QApplication

from game.player import Player
from game.world import World
from game.events import EventPool
from game.item import ItemLibrary
from game.enemy import EnemyLibrary
from game.skill import SkillLibrary
from game.npc import NPCLibrary
from game.quest import QuestLibrary
from game.engine import GameEngine
from game.save_manager import SaveManager
from game.dialogue import Dialogue, DialogueLibrary, DialogueManager


class TestDialogueConfig(unittest.TestCase):
    """对话配置加载测试。"""

    def test_load_example_dialogues(self):
        """应能加载示例对话配置。"""
        lib = DialogueLibrary(config_dir="config")
        self.assertIn("fufeng_lord_greeting", lib.all_ids())
        self.assertIn("wandering_merchant_encounter", lib.all_ids())

    def test_get_node(self):
        """应能按节点 ID 获取节点。"""
        lib = DialogueLibrary(config_dir="config")
        dialogue = lib.get("fufeng_lord_greeting")
        self.assertIsNotNone(dialogue)
        node = dialogue.get_node("greeting")
        self.assertIsNotNone(node)
        self.assertIn("options", node)


class TestDialogueManager(unittest.TestCase):
    """对话管理器逻辑测试。"""

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.item_lib = ItemLibrary(config_dir="config")
        self.enemy_lib = EnemyLibrary(config_dir="config")
        self.skill_lib = SkillLibrary(config_dir="config")
        self.npc_lib = NPCLibrary(config_dir="config")
        self.quest_lib = QuestLibrary(config_dir="config")

        self.player = Player(name="测试修士")
        self.world = World(config_dir="config")
        self.event_pool = EventPool(config_dir="config")
        self.engine = GameEngine(
            self.player,
            self.world,
            self.event_pool,
            self.item_lib,
            self.enemy_lib,
            self.skill_lib,
            self.npc_lib,
            self.quest_lib,
            save_manager=SaveManager(save_path="test_dialogue_save.json"),
        )
        self.save_path = "test_dialogue_save.json"

    def tearDown(self):
        if os.path.exists(self.save_path):
            os.remove(self.save_path)

    def test_start_dialogue_returns_state(self):
        """开始对话应返回当前节点状态。"""
        state = self.engine.start_dialogue("fufeng_lord_greeting", npc_id="fufeng_lord")
        self.assertIsNotNone(state)
        self.assertIn("来者何人", state["text"])
        self.assertEqual(len(state["options"]), 2)

    def test_choose_option_advances_node(self):
        """选择选项应推进到下一节点。"""
        self.engine.start_dialogue("fufeng_lord_greeting", npc_id="fufeng_lord")
        # 选择第一个选项：晚辈前来拜会城主
        next_state, logs = self.engine.choose_dialogue_option(0)
        self.assertIsNotNone(next_state)
        self.assertIn("风妖作乱", next_state["text"])

    def test_option_effects_start_quest_and_set_flag(self):
        """选择接任务选项应触发任务接取与标志位设置。"""
        self.engine.start_dialogue("fufeng_lord_greeting", npc_id="fufeng_lord")
        # 先进入 ask_reason 节点
        self.engine.choose_dialogue_option(0)
        # 选择接取任务
        next_state, logs = self.engine.choose_dialogue_option(0)
        self.assertIn("fufeng_wind_trial", self.player.quest_progress)
        self.assertTrue(self.player.dialogue_flags.get("accepted_wind_demon_quest"))
        self.assertTrue(any("接取任务" in log for log in logs), logs)

    def test_condition_filters_options(self):
        """条件不满足时选项应被过滤。"""
        # 未见过云游商人，"你这里可有什么消息？"选项应被隐藏
        state = self.engine.start_dialogue("wandering_merchant_encounter")
        texts = [opt["text"] for opt in state["options"]]
        self.assertNotIn("你这里可有什么消息？", texts)

    def test_condition_shows_option_when_flag_set(self):
        """条件满足时选项应显示。"""
        self.player.dialogue_flags["met_wandering_merchant"] = True
        state = self.engine.start_dialogue("wandering_merchant_encounter")
        texts = [opt["text"] for opt in state["options"]]
        self.assertIn("你这里可有什么消息？", texts)

    def test_has_item_condition(self):
        """has_item 条件应正确判断背包物品。"""
        # 给玩家 5 颗灵石
        for _ in range(5):
            item = self.item_lib.create("spirit_stone")
            self.player.add_item(item)
        state = self.engine.start_dialogue("fufeng_innkeeper_rumor")
        texts = [opt["text"] for opt in state["options"]]
        self.assertIn("来一壶好酒。", texts)

    def test_give_item_effect(self):
        """give_item 效果应添加物品到背包。"""
        self.player.dialogue_flags["met_wandering_merchant"] = True
        self.engine.start_dialogue("wandering_merchant_encounter")
        # 选择"你这里可有什么消息？"（索引 1）
        _, logs = self.engine.choose_dialogue_option(1)
        self.assertTrue(self.player.count_item("ancient_scroll") >= 1)
        self.assertTrue(any("获得" in log for log in logs), logs)

    def test_take_item_effect(self):
        """take_item 效果应消耗背包物品。"""
        for _ in range(5):
            item = self.item_lib.create("spirit_stone")
            self.player.add_item(item)
        self.engine.start_dialogue("fufeng_innkeeper_rumor")
        # 选择"来一壶好酒"（索引 1）
        before = self.player.count_item("spirit_stone")
        self.engine.choose_dialogue_option(1)
        after = self.player.count_item("spirit_stone")
        self.assertEqual(before - after, 5)

    def test_modify_reputation_effect(self):
        """modify_reputation 效果应改变 NPC 好感度。"""
        self.engine.start_dialogue("fufeng_innkeeper_rumor")
        before = self.player.get_npc_relationship("fufeng_innkeeper")
        self.engine.choose_dialogue_option(0)
        after = self.player.get_npc_relationship("fufeng_innkeeper")
        self.assertGreater(after, before)

    def test_realm_min_condition(self):
        """realm_min 条件应按境界过滤。"""
        dialogue = Dialogue.from_dict({
            "id": "test_realm",
            "npc_id": None,
            "entry_node": "start",
            "nodes": {
                "start": {
                    "text": "测试",
                    "options": [
                        {
                            "text": "高境界选项",
                            "conditions": [{"type": "realm_min", "realm_id": "foundation_early"}],
                            "next_node": "end"
                        },
                        {"text": "普通选项", "next_node": "end"}
                    ]
                },
                "end": {"text": "结束", "options": []}
            }
        })
        manager = DialogueManager(self.engine)
        manager.start_dialogue("test_realm")
        # 注入测试对话（绕过 library）
        self.engine.dialogue_library.dialogues["test_realm"] = dialogue
        state = self.engine.start_dialogue("test_realm")
        texts = [opt["text"] for opt in state["options"]]
        self.assertNotIn("高境界选项", texts)

        self.player.realm_id = "foundation_early"
        state = self.engine.start_dialogue("test_realm")
        texts = [opt["text"] for opt in state["options"]]
        self.assertIn("高境界选项", texts)

    def test_npc_choice_condition(self):
        """npc_choice 条件应按 NPC 记忆选择过滤。"""
        self.player.record_npc_choice("fufeng_innkeeper", "bought_inn_wine", True)
        dialogue = Dialogue.from_dict({
            "id": "test_choice",
            "npc_id": "fufeng_innkeeper",
            "entry_node": "start",
            "nodes": {
                "start": {
                    "text": "测试",
                    "options": [
                        {
                            "text": "买过酒选项",
                            "conditions": [
                                {"type": "npc_choice", "key": "bought_inn_wine", "value": True}
                            ],
                            "next_node": "end"
                        },
                        {"text": "普通选项", "next_node": "end"}
                    ]
                },
                "end": {"text": "结束", "options": []}
            }
        })
        self.engine.dialogue_library.dialogues["test_choice"] = dialogue
        state = self.engine.start_dialogue("test_choice")
        texts = [opt["text"] for opt in state["options"]]
        self.assertIn("买过酒选项", texts)

    def test_end_dialogue_clears_state(self):
        """结束对话后状态应清空。"""
        self.engine.start_dialogue("fufeng_lord_greeting")
        self.assertTrue(self.engine.dialogue_manager.is_active())
        self.engine.end_dialogue()
        self.assertFalse(self.engine.dialogue_manager.is_active())


class TestNPCDialogueID(unittest.TestCase):
    """NPC dialogue_id 关联测试。"""

    def test_npc_has_dialogue_id(self):
        """配置了 dialogue_id 的 NPC 应能正确读取。"""
        lib = NPCLibrary(config_dir="config")
        lord = lib.get("fufeng_lord")
        self.assertEqual(getattr(lord, "dialogue_id", None), "fufeng_lord_greeting")


if __name__ == "__main__":
    unittest.main()
