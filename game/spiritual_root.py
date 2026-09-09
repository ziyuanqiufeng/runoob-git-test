import json
import os
import random


class SpiritualRootConfig:
    """
    灵根配置管理器，从 spiritual_roots.json 加载五行灵根配置。
    负责灵根类型判定、修炼倍率查询、随机灵根生成等。
    """

    def __init__(self, config_dir="config"):
        config_path = os.path.join(config_dir, "spiritual_roots.json")
        with open(config_path, "r", encoding="utf-8") as f:
            self.data = json.load(f)

        # 元素列表（含基础五行与变异灵根）
        self.elements = self.data["elements"]
        # 变异灵根子集
        self.variant_elements = self.data.get("variant_elements", [])
        # 融合灵根配置：id -> {name, elements, description}
        self.fusion_roots = self.data.get("fusion_roots", {})
        # 属性中文名映射（含基础、变异、融合灵根名称）
        self.element_names = dict(self.data["element_names"])
        for fid, fcfg in self.fusion_roots.items():
            self.element_names[fid] = fcfg.get("name", fid)
        # 属性颜色（用于 UI 显示）
        self.element_colors = self.data.get("element_colors", {})
        # 灵根数量 → 修炼倍率
        self.multiplier_by_count = {
            int(k): v for k, v in self.data["multiplier_by_count"].items()
        }
        # 灵根数量 → 称谓
        self.root_names = {
            int(k): v for k, v in self.data["root_names"].items()
        }
        # 随机分配权重
        self.random_weights = {
            int(k): v for k, v in self.data["random_weights"].items()
        }
        # 灵根数量 → 纯度范围 [min, max]
        self.purity_ranges_by_count = {
            int(k): v for k, v in self.data.get("purity_ranges_by_count", {}).items()
        }
        # 纯度标签（纯/空/杂）
        self.purity_labels = self.data.get("purity_labels", {
            "pure": "纯", "normal": "", "mixed": "杂"
        })
        # 纯度阈值
        self.purity_thresholds = self.data.get("purity_thresholds", {
            "pure": 1.2, "mixed": 0.9
        })

    def get_multiplier(self, root_count):
        """根据灵根数量获取修炼倍率（倍率越高修炼越慢）。"""
        return self.multiplier_by_count.get(root_count, 4.0)

    def get_root_name(self, root_count):
        """根据灵根数量获取称谓（天灵根/真灵根等）。"""
        return self.root_names.get(root_count, "杂灵根")

    def get_element_name(self, element):
        """获取属性中文名（支持融合灵根 id）。"""
        return self.element_names.get(element, element)

    def is_fusion_root(self, root_id):
        """判断是否为融合灵根 id。"""
        return root_id in self.fusion_roots

    def expand_root(self, root_id):
        """
        展开单个灵根 id 为包含的基础/变异元素列表。
        普通元素返回 [element]，融合灵根返回其包含的元素列表。
        """
        if root_id in self.fusion_roots:
            return list(self.fusion_roots[root_id]["elements"])
        return [root_id]

    def expand_roots(self, roots):
        """展开灵根列表为所有基础/变异元素（去重并保持顺序）。"""
        result = []
        seen = set()
        for root_id in roots:
            for elem in self.expand_root(root_id):
                if elem not in seen:
                    seen.add(elem)
                    result.append(elem)
        return result

    def get_element_color(self, element):
        """获取属性对应的 UI 颜色。"""
        return self.element_colors.get(element, "#ecf0f1")

    def random_roots(self):
        """
        按权重随机生成灵根。
        返回灵根属性列表，如 ["fire"] 或 ["metal", "water", "wood"]。
        """
        # 按权重抽取灵根数量
        counts = list(self.random_weights.keys())
        weights = list(self.random_weights.values())
        root_count = random.choices(counts, weights=weights, k=1)[0]

        # 从五行中随机抽取指定数量的属性（不重复）
        roots = random.sample(self.elements, root_count)
        return roots

    def random_purities(self, root_count):
        """
        根据灵根数量生成各灵根的纯度值。
        灵根越少，纯度范围越高（专精路线）；灵根越多，纯度越低（全面路线）。
        返回字典：{"fire": 1.3, "metal": 0.8, ...}
        """
        # 获取该灵根数量对应的纯度范围，默认 [0.8, 1.0]
        purity_range = self.purity_ranges_by_count.get(root_count, [0.8, 1.0])
        min_p, max_p = purity_range[0], purity_range[1]
        # 从五行中随机抽取指定数量的属性（不重复）
        roots = random.sample(self.elements, root_count)
        # 为每个灵根生成纯度值
        return {e: round(random.uniform(min_p, max_p), 2) for e in roots}

    def get_purity_label(self, purity):
        """
        根据纯度值返回标签：纯/空/杂。
        purity >= 1.2 → "纯"
        purity < 0.9 → "杂"
        其他 → ""
        """
        pure_threshold = self.purity_thresholds.get("pure", 1.2)
        mixed_threshold = self.purity_thresholds.get("mixed", 0.9)
        if purity >= pure_threshold:
            return self.purity_labels.get("pure", "纯")
        if purity < mixed_threshold:
            return self.purity_labels.get("mixed", "杂")
        return self.purity_labels.get("normal", "")

    def format_roots_text(self, roots):
        """
        格式化灵根显示文本。
        例：["fire"] → "火（天灵根）"
        例：["metal", "water"] → "金、水（真灵根）"
        融合灵根按一个根计数，但显示其融合名称。
        """
        names = "、".join(self.get_element_name(e) for e in roots)
        root_name = self.get_root_name(len(roots))
        # 若存在融合灵根，在括号内补充说明
        fusion_desc = ""
        for root_id in roots:
            if self.is_fusion_root(root_id):
                elems = "、".join(self.get_element_name(e) for e in self.expand_root(root_id))
                fusion_desc += f"[{self.get_element_name(root_id)}：{elems}]"
        if fusion_desc:
            return f"{names}（{root_name} {fusion_desc}）"
        return f"{names}（{root_name}）"
