# -*- coding: utf-8 -*-
"""桥接面契约:前端调用的后端方法必须存在;后端推送的事件必须有人处理。

v2.6.10 的审计就是靠人工核对"前端全部 call('x') 均能在后端找到实现",
这一组用例把它变成自动化,防止改名后留下静默失败。
"""
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "frontend" / "src"


def _frontend_call_names() -> set:
    names = set()
    for path in list(SRC.rglob("*.js")) + list(SRC.rglob("*.jsx")):
        text = path.read_text(encoding="utf-8", errors="ignore")
        names |= set(re.findall(r"call\(\s*'([a-z_][a-z0-9_]*)'", text))
        names |= set(re.findall(r'call\(\s*"([a-z_][a-z0-9_]*)"', text))
    return names


def _api_methods() -> set:
    """桥接方法 = Api 沿 MRO 的所有公开可调用成员(与 Api.__dir__ 的语义一致)。"""
    from app.api import Api

    methods = set()
    for klass in Api.__mro__:
        for name, value in vars(klass).items():
            if not name.startswith("_") and callable(value):
                methods.add(name)
    return methods


def test_every_frontend_call_has_backend_method():
    missing = sorted(n for n in _frontend_call_names() if n not in _api_methods())
    assert not missing, f"前端调用了后端不存在的方法:{missing}"


def test_no_removed_bridge_methods_still_called():
    """显式盯着历史上被删掉的接口:再被调用就是静默失败。

    v2.6.9 审计发现 QuitDialog 仍在调用已删除的 ``confirm_quit_room``。
    """
    removed = {"confirm_quit_room", "run_capture_last", "run_mini_capture"}
    still_called = sorted(removed & _frontend_call_names())
    assert not still_called, f"前端仍在调用已删除的接口:{still_called}"


def test_api_dir_only_returns_public_callables():
    from app.api import Api

    class _FakeApp:
        """只为满足 Api.__init__ 的签名,__dir__ 不使用它。"""

    for name in Api.__dir__(Api(_FakeApp())):
        assert not name.startswith("_"), f"__dir__ 暴露了私有成员:{name}"
        assert callable(getattr(Api, name, None)), f"__dir__ 暴露了非可调用成员:{name}"


def _backend_event_types() -> set:
    types = set()
    for path in (ROOT / "app").glob("*.py"):
        text = path.read_text(encoding="utf-8", errors="ignore")
        types |= set(re.findall(r'"type"\s*:\s*"([a-zA-Z]+)"', text))
    # 请求模板里的 {"type": "text"} 是给模型的 JSON,不是前端事件
    types.discard("text")
    return types


def _frontend_handled_event_types() -> set:
    """收集前端比较过的事件名:``type === 'x'`` / ``type !== 'x'`` / ``case 'x'`` 都算。"""
    handled = set()
    for path in list(SRC.rglob("*.js")) + list(SRC.rglob("*.jsx")):
        text = path.read_text(encoding="utf-8", errors="ignore")
        handled |= set(re.findall(r"type\s*[!=]==?\s*'([a-zA-Z]+)'", text))
        handled |= set(re.findall(r'type\s*[!=]==?\s*"([a-zA-Z]+)"', text))
        handled |= set(re.findall(r"case\s*'([a-zA-Z]+)'", text))
    return handled


def test_event_entry_point_is_registered_in_bridge():
    """事件总入口必须在 bridge.js 里注册(框选页是独立入口,不经过 main.jsx)。"""
    text = (SRC / "bridge.js").read_text(encoding="utf-8", errors="ignore")
    assert "window.__ocrEvent" in text
    assert "ocr-event" in text


def test_every_backend_event_has_a_handler():
    unhandled = sorted(_backend_event_types() - _frontend_handled_event_types() - {"download"})
    # download 由 ui.jsx 用 download 事件名在别处分发,单独在下一个用例里核对
    assert not unhandled, f"后端推送了没人处理的事件:{unhandled}"


def test_download_event_is_handled():
    text = (SRC / "ui.jsx").read_text(encoding="utf-8", errors="ignore") \
        + (SRC / "Settings.jsx").read_text(encoding="utf-8", errors="ignore")
    assert "'download'" in text and "'pack'" in text


@pytest.mark.parametrize("event_type", ["confirmQuit", "quitHint", "modalBlock", "hotkeyCapture"])
def test_control_events_reach_their_components(event_type):
    """控制类事件必须有明确的接收方,否则界面会出现"点了没反应"。"""
    owners = {
        "confirmQuit": "QuitDialog.jsx",
        "quitHint": "MiniBar.jsx",
        "modalBlock": "main.jsx",
        "hotkeyCapture": "Overlay.jsx",
    }
    text = (SRC / owners[event_type]).read_text(encoding="utf-8", errors="ignore")
    assert event_type in text, f"{event_type} 在 {owners[event_type]} 里没有被处理"
