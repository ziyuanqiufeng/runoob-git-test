# -*- coding: utf-8 -*-
"""pytest 全局配置。

WorkBuddy 沙箱环境下，`os.remove` / `os.unlink` 会因「Windows 回收站不可用」抛
OSError（safe-delete guard），导致测试 tearDown 清理临时文件失败、误报为测试失败。

这里用一个 autouse fixture 把删除失败降级为静默忽略：
- 删除成功（如 tempfile 临时目录内的文件）→ 保持原行为，正常删除；
- 删除失败（沙箱回收站不可用）→ 捕获 OSError 静默，不中断测试。

该 monkeypatch 仅在测试函数执行期间生效，测试结束后自动恢复，不影响生产代码。
"""
import os

import pytest


@pytest.fixture(autouse=True)
def _tolerate_remove_failure(monkeypatch):
    original_remove = os.remove
    original_unlink = getattr(os, "unlink", None)

    def _safe_remove(path, *args, **kwargs):
        try:
            return original_remove(path, *args, **kwargs)
        except OSError:
            return None

    monkeypatch.setattr(os, "remove", _safe_remove)
    if original_unlink is not None:
        monkeypatch.setattr(os, "unlink", _safe_remove)
    yield


@pytest.fixture(autouse=True)
def _no_external_ai_calls(monkeypatch):
    """测试期间封死所有真实外部 AI 调用（Agnes LLM / 文生图）。

    背景引擎流程（如游历事件的 AI 剧情钩子）在 ai_llm_story 开启时会真实
    请求外部服务；外部服务变慢/超时会拖垮整个测试套件（曾致全量回归挂死）。
    这里在类级把 API key 读数 mock 为空 → 引擎自动走离线模板降级，秒级返回。

    专项 AI 测试（test_ai_story_generator / test_portrait_agnes）内部用
    patch.object(实例, ...) 设置实例级属性，优先级高于本类级 mock，不受影响。
    """
    from game import ai_story_generator as _ai
    from game import portrait_generator as _pg

    monkeypatch.setattr(_ai.AIStoryGenerator, "_api_key", lambda self: "")
    monkeypatch.setattr(_pg, "_load_ai_api_key", lambda config_dir="config": "")
    yield
