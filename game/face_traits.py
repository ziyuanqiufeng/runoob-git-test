# -*- coding: utf-8 -*-
"""捏脸系统（路线 B）：AI 提示词捏脸的特征表加载与 prompt 拼接。

特征表 config/face_traits.json 定义若干维度（脸型/眼神/气质/发型/服饰），
玩家每个维度选一项，程序把对应英文片段按序拼进提示词，交给
portrait_generator._generate_via_agnes 生成专属立绘。
"""
import json
import os

_GENDER_DESC = {"male": "handsome young man", "female": "beautiful young woman"}


def load_traits_config(config_dir="config"):
    """加载特征表 config/face_traits.json；缺失或格式错误返回 None。"""
    path = os.path.join(config_dir, "face_traits.json")
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict) or not data.get("dimensions"):
            return None
        return data
    except (json.JSONDecodeError, OSError):
        return None


def resolve_trait_prompts(traits, config=None):
    """把 {维度id: 选项id} 解析为按维度顺序排列的英文 prompt 片段列表。

    缺失或无效的维度回退为该维度第一个选项（保证 prompt 始终完整）。
    """
    config = config or load_traits_config()
    if not config:
        return []
    traits = traits or {}
    prompts = []
    for dim in config.get("dimensions", []):
        options = dim.get("options", [])
        if not options:
            continue
        choice = traits.get(dim.get("id"))
        option = next((o for o in options if o.get("id") == choice), options[0])
        if option.get("prompt"):
            prompts.append(option["prompt"])
    return prompts


def build_trait_prompt(traits, gender="male", config_dir="config", player=None):
    """按特征选择拼完整提示词，返回 (positive, negative)；配置缺失返回 (None, None)。

    player 可选：提供时把流派与境界描述一并拼入（复用 portrait_generator 模板）。
    """
    config = load_traits_config(config_dir)
    if not config:
        return None, None
    parts = [config.get("style_prefix", "").format(
        gender_desc=_GENDER_DESC.get(gender, _GENDER_DESC["male"]))]
    parts.extend(resolve_trait_prompts(traits, config))
    if player is not None:
        from game import portrait_generator as pg
        template = pg.load_prompt_template(config_dir)
        path_id = getattr(player, "cultivation_path", "fa")
        parts.append(template["path_desc"].get(path_id, "cultivator"))
        realm_prefix = pg._get_realm_prefix(getattr(player, "realm_id", "qi_refining_1"))
        parts.append(template["realm_desc"].get(realm_prefix, "Qi Refining"))
    suffix = config.get("style_suffix", "")
    if suffix:
        parts.append(suffix)
    # 清理片段首尾空白与多余逗号，避免出现 "portrait,," 双逗号
    cleaned = [p.strip().rstrip(",") for p in parts if p and p.strip()]
    positive = ", ".join(cleaned)
    negative = config.get("negative", "")
    return positive, negative
