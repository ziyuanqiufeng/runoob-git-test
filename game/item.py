class Item:
    """物品对象，包含类型、价值、效果等属性；新增可堆叠属性。"""

    # 默认可堆叠的类型与堆叠上限
    DEFAULT_STACKABLE_TYPES = {"material", "pill", "herb", "consumable"}
    DEFAULT_MAX_STACK = 99

    def __init__(
        self,
        item_id,
        name,
        item_type,
        value,
        description,
        effects=None,
        stackable=None,
        max_stack=None,
        count=1,
        enhancement_level=0,
        affixes=None,
        quality=None,
    ):
        self.id = item_id          # 物品唯一标识
        self.name = name           # 显示名称
        self.type = item_type      # 类型：pill/manual/material/weapon 等
        self.value = value         # 物品价值，用于商店买卖
        self.description = description  # 物品描述
        self.effects = effects or {}    # 使用效果
        # 未显式指定时，根据类型推断是否可堆叠
        if stackable is None:
            stackable = item_type in self.DEFAULT_STACKABLE_TYPES
        self.stackable = stackable
        self.max_stack = max_stack if max_stack is not None else (self.DEFAULT_MAX_STACK if self.stackable else 1)
        self.count = max(1, count) if self.stackable else 1
        # 炼器附魔系统字段
        self.enhancement_level = enhancement_level  # 强化等级
        self.affixes = affixes or []                # 词缀列表
        # 炼丹品质：普通/上品/极品，None 表示无品质区分
        self.quality = quality

    @classmethod
    def from_dict(cls, data):
        """从 JSON 数据或存档创建 Item 对象。"""
        return cls(
            item_id=data["id"],
            name=data["name"],
            item_type=data["type"],
            value=data.get("value", 1),
            description=data.get("description", ""),
            effects=data.get("effects", {}),
            stackable=data.get("stackable"),
            max_stack=data.get("max_stack"),
            count=data.get("count", 1),
            enhancement_level=data.get("enhancement_level", 0),
            affixes=data.get("affixes", []),
            quality=data.get("quality"),
        )

    def to_dict(self):
        """序列化为字典，用于存档。"""
        data = {
            "id": self.id,
            "name": self.name,
            "type": self.type,
            "value": self.value,
            "description": self.description,
            "effects": self.effects,
            "count": self.count,
        }
        # 只有与默认值不同才写入，减少存档体积
        if self.stackable != (self.type in self.DEFAULT_STACKABLE_TYPES):
            data["stackable"] = self.stackable
        if self.max_stack != (self.DEFAULT_MAX_STACK if self.stackable else 1):
            data["max_stack"] = self.max_stack
        if self.enhancement_level:
            data["enhancement_level"] = self.enhancement_level
        if self.affixes:
            data["affixes"] = self.affixes
        if self.quality:
            data["quality"] = self.quality
        return data


class ItemLibrary:
    """物品库，从 JSON 加载所有物品模板。"""

    def __init__(self, config_dir="config"):
        import json
        import os

        items_path = os.path.join(config_dir, "items.json")
        with open(items_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        # 用物品 ID 做索引
        self.items = {d["id"]: Item.from_dict(d) for d in data}

    def get(self, item_id):
        """根据 ID 获取物品模板。"""
        return self.items.get(item_id)

    def create(self, item_id):
        """根据模板创建一个新的物品实例。"""
        template = self.get(item_id)
        if not template:
            return None
        # 返回副本，避免修改模板；复制堆叠属性
        return Item(
            item_id=template.id,
            name=template.name,
            item_type=template.type,
            value=template.value,
            description=template.description,
            effects=dict(template.effects),
            stackable=template.stackable,
            max_stack=template.max_stack,
            count=1,
        )

    def create_custom_item(self, item_id, name, item_type, value, description, effects):
        """根据传入参数创建一个自定义物品实例（用于炼制等动态生成）。"""
        return Item(
            item_id=item_id,
            name=name,
            item_type=item_type,
            value=value,
            description=description,
            effects=dict(effects),
        )
