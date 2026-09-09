class Quest:
    """任务对象。"""

    def __init__(
        self,
        quest_id,
        name,
        description,
        target_type,
        target_id,
        count,
        reward,
        next_quest=None,
        unlocks=None,
    ):
        self.id = quest_id
        self.name = name
        self.description = description
        self.target_type = target_type  # kill / collect
        self.target_id = target_id
        self.count = count
        self.reward = reward
        self.next_quest = next_quest      # 后续任务 ID
        self.unlocks = unlocks or {}      # 解锁内容，如地点

    @classmethod
    def from_dict(cls, data):
        return cls(
            quest_id=data["id"],
            name=data["name"],
            description=data.get("description", ""),
            target_type=data["target_type"],
            target_id=data["target_id"],
            count=data["count"],
            reward=data.get("reward", {}),
            next_quest=data.get("next_quest"),
            unlocks=data.get("unlocks"),
        )


class QuestLibrary:
    """任务库，从 JSON 加载。"""

    def __init__(self, config_dir="config"):
        import json
        import os

        quests_path = os.path.join(config_dir, "quests.json")
        with open(quests_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        self.quests = {d["id"]: Quest.from_dict(d) for d in data}

    def get(self, quest_id):
        return self.quests.get(quest_id)
