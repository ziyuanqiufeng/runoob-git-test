# -*- coding: utf-8 -*-
"""AI 服务诊断：检查 API key 配置、网络连通与模型可用性。

诊断项：
1. key 是否已配置（环境变量 / config/ai_config.json）；
2. GET {api_root}/models 是否可达（验证网络与 key 有效性）；
3. 文生图模型是否在模型列表中（确认捏脸/立绘可用）。

纯逻辑实现（urllib，无 Qt），可离线单测（mock urlopen）。
"""
import json
import os
import urllib.request
import urllib.error

from game.portrait_generator import _load_ai_api_key, _load_image_config

# 兜底根地址（config 缺失时用）
_FALLBACK_ROOT = "https://apihub.agnes-ai.com/v1"


def _api_root(config_dir="config"):
    """从 config 的 image_base_url（或 base_url）推导 /v1 根地址。"""
    try:
        with open(os.path.join(config_dir, "ai_config.json"), encoding="utf-8") as f:
            cfg = json.load(f)
        url = cfg.get("image_base_url") or cfg.get("base_url")
        if url:
            return url.rsplit("/v1/", 1)[0] + "/v1"
    except (OSError, json.JSONDecodeError):
        pass
    return _FALLBACK_ROOT


def diagnose_ai(config_dir="config", timeout=15):
    """执行 AI 服务诊断，返回结果 dict。

    返回：{
        "key_present": bool,      # 是否配置了 API key
        "reachable": bool,        # /models 端点是否可达
        "image_model_ok": bool,   # 文生图模型是否在列（reachable 时才有意义）
        "detail": str,            # 人类可读的诊断说明
    }
    任何异常都被捕获并写入 detail，不抛出。
    """
    result = {
        "key_present": False,
        "reachable": False,
        "image_model_ok": False,
        "llm_model_ok": False,
        "detail": "",
    }

    api_key = _load_ai_api_key(config_dir)
    if not api_key:
        result["detail"] = "未配置 API key（环境变量 AGNES_API_KEY 或 config/ai_config.json）。"
        return result
    result["key_present"] = True

    image_model = _load_image_config(config_dir)[1]
    llm_model = "agnes-3.0-flash"
    try:
        with open(os.path.join(config_dir, "ai_config.json"), encoding="utf-8") as f:
            llm_model = json.load(f).get("model") or llm_model
    except (OSError, json.JSONDecodeError):
        pass

    url = _api_root(config_dir) + "/models"
    req = urllib.request.Request(
        url, headers={"Authorization": "Bearer " + api_key}
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = json.loads(resp.read().decode("utf-8"))
        result["reachable"] = True
    except urllib.error.HTTPError as e:
        if e.code == 401:
            result["detail"] = "key 无效或已过期（HTTP 401），请检查 API key。"
        else:
            result["detail"] = f"服务返回 HTTP {e.code}，请稍后重试。"
        return result
    except Exception as e:
        result["detail"] = f"网络不可达：{e}"
        return result

    model_ids = {
        m.get("id") for m in (body.get("data") or []) if isinstance(m, dict)
    }
    result["image_model_ok"] = image_model in model_ids
    result["llm_model_ok"] = llm_model in model_ids

    parts = []
    if result["image_model_ok"]:
        parts.append(f"文生图模型 {image_model} 可用")
    else:
        parts.append(f"未找到文生图模型 {image_model}（生图可能不可用）")
    if result["llm_model_ok"]:
        parts.append(f"LLM {llm_model} 可用")
    else:
        parts.append(f"未找到 LLM {llm_model}（剧情增强可能不可用）")
    result["detail"] = "连接正常，key 有效；" + "，".join(parts) + "。"
    return result
