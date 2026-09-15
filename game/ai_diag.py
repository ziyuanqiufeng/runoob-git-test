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

from game.portrait_generator import _AGNES_IMAGE_MODEL, _load_ai_api_key

# 模型服务根地址（与 portrait_generator 的生成端点同源）
_API_ROOT = "https://apihub.agnes-ai.com/v1"


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
        "detail": "",
    }

    api_key = _load_ai_api_key(config_dir)
    if not api_key:
        result["detail"] = "未配置 API key（环境变量 AGNES_API_KEY 或 config/ai_config.json）。"
        return result
    result["key_present"] = True

    url = _API_ROOT + "/models"
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
    if _AGNES_IMAGE_MODEL in model_ids:
        result["image_model_ok"] = True
        result["detail"] = (
            f"连接正常，key 有效；文生图模型 {_AGNES_IMAGE_MODEL} 可用。"
        )
    else:
        result["detail"] = (
            f"连接正常，但模型列表中未找到 {_AGNES_IMAGE_MODEL}，"
            "生图功能可能暂不可用。"
        )
    return result
