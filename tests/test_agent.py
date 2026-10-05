# -*- coding: utf-8 -*-
"""聊天接口地址归一化与请求体模板(平台配置写错时的第一道防线)。"""
import json

import pytest

from app.agent import AgentClient, AgentError, chat_endpoint
from app.config import DEFAULT_REQUEST_TEMPLATE


@pytest.mark.parametrize("given,expected", [
    # 只有主机名 → 补 /v1/chat/completions
    ("https://api.deepseek.com", "https://api.deepseek.com/v1/chat/completions"),
    # 已带 /v1 → 补 /chat/completions
    ("https://api.openai.com/v1", "https://api.openai.com/v1/chat/completions"),
    ("http://localhost:11434/v1", "http://localhost:11434/v1/chat/completions"),
    # 完整接口 → 原样
    ("https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions",
     "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions"),
    # 自建网关/Ollama 原生接口 → 原样
    ("http://127.0.0.1:8080/api/chat", "http://127.0.0.1:8080/api/chat"),
    ("https://x.y/v1/messages", "https://x.y/v1/messages"),
    # 带路径但没到接口 → 补 /chat/completions
    ("https://open.bigmodel.cn/api/paas/v4", "https://open.bigmodel.cn/api/paas/v4/chat/completions"),
    # 末尾斜杠要能容错
    ("https://api.openai.com/v1/", "https://api.openai.com/v1/chat/completions"),
])
def test_chat_endpoint_normalization(given, expected):
    assert chat_endpoint(given) == expected


def test_chat_endpoint_empty():
    assert chat_endpoint("") == ""
    assert chat_endpoint(None) == ""


def _client(**kw):
    opts = dict(api_key="sk-1", model="m1", api_base="https://api.openai.com/v1",
                request_template=DEFAULT_REQUEST_TEMPLATE)
    opts.update(kw)
    return AgentClient(**opts)


def test_payload_contains_model_and_prompt():
    client = _client()
    payload = client._build_payload("识别这段文字", _tiny_png())
    assert payload["model"] == "m1"
    text = payload["messages"][0]["content"][0]["text"]
    assert text == "识别这段文字"
    url = payload["messages"][0]["content"][1]["image_url"]["url"]
    assert url.startswith("data:image/png;base64,")
    assert payload["temperature"] == 0


def test_payload_rejects_missing_key():
    client = _client(api_key="")
    with pytest.raises(AgentError) as ei:
        client._build_payload("x", _tiny_png())
    assert "API Key" in str(ei.value)


def test_payload_removes_thinking_for_unsupported_platform():
    """不支持的平台必须把 enable_thinking 从请求体里删掉,否则部分网关返回 400。"""
    client = _client(supports_thinking=False, enable_thinking=True)
    payload = client._build_payload("x", _tiny_png())
    assert "enable_thinking" not in payload
    assert json.dumps(payload), "删除后仍是合法 JSON"


def test_payload_injects_thinking_for_supported_platform():
    client = _client(supports_thinking=True, enable_thinking=True)
    assert client._build_payload("x", _tiny_png())["enable_thinking"] is True
    client2 = _client(supports_thinking=True, enable_thinking=False)
    assert client2._build_payload("x", _tiny_png())["enable_thinking"] is False


def test_payload_bad_template_raises():
    client = _client(request_template="{ 这不是 json }")
    with pytest.raises(AgentError) as ei:
        client._build_payload("x", _tiny_png())
    assert "模板无效" in str(ei.value)


def test_payload_escapes_quotes_in_prompt():
    """提示词里带引号/换行时不能把 JSON 结构撑破。"""
    client = _client()
    tricky = '他说:"引号"\n换行\t制表符'
    payload = client._build_payload(tricky, _tiny_png())
    assert payload["messages"][0]["content"][0]["text"] == tricky


def test_image_is_downscaled_to_max_side():
    import io

    from PIL import Image

    big = Image.new("RGB", (4000, 2000), "white")
    buf = io.BytesIO()
    big.save(buf, format="PNG")
    client = _client(max_side=1000)
    import base64
    url = client._build_payload("x", buf.getvalue())["messages"][0]["content"][1]["image_url"]["url"]
    raw = base64.b64decode(url.split(",", 1)[1])
    assert max(Image.open(io.BytesIO(raw)).size) == 1000


@pytest.mark.parametrize("status,keyword", [
    (404, "Base URL"),
    (401, "API Key"),
    (403, "API Key"),
    (400, "接口返回 400"),
])
def test_error_messages_are_actionable(monkeypatch, status, keyword):
    """错误提示必须能直接指导用户改配置(历史上 404 提示帮了很多人)。"""
    import requests

    class Resp:
        status_code = status
        text = '{"error": {"message": "bad"}}'

        def json(self):
            return {"error": {"message": "bad"}}

    monkeypatch.setattr(requests, "post", lambda *a, **k: Resp())
    client = _client(max_retries=1, backoff=0)
    with pytest.raises(AgentError) as ei:
        client.answer(_tiny_png(), "x")
    assert keyword in str(ei.value)


def test_retry_then_success(monkeypatch):
    """前两次 500、第三次 200:必须重试到成功,而不是直接失败。"""
    import requests

    calls = {"n": 0}

    class Resp:
        def __init__(self, code):
            self.status_code = code
            self.text = ""

        def json(self):
            return {"choices": [{"message": {"content": "重试成功"}}]}

    def fake_post(*a, **k):
        calls["n"] += 1
        return Resp(500 if calls["n"] < 3 else 200)

    monkeypatch.setattr(requests, "post", fake_post)
    client = _client(max_retries=3, backoff=0)
    assert client.ocr(_tiny_png(), "x") == "重试成功"
    assert calls["n"] == 3


def test_parse_failure_is_reported(monkeypatch):
    import requests

    class Resp:
        status_code = 200
        text = "not json at all"

        def json(self):
            return {"unexpected": True}

    monkeypatch.setattr(requests, "post", lambda *a, **k: Resp())
    client = _client(max_retries=1)
    with pytest.raises(AgentError) as ei:
        client.ocr(_tiny_png(), "x")
    assert "解析失败" in str(ei.value)


def test_list_models_requires_config():
    assert _client(api_key="").list_models()[0] == []
    assert _client(api_base="").list_models()[0] == []


def test_list_models_from_data_shape(monkeypatch):
    import requests

    class Resp:
        status_code = 200

        def json(self):
            return {"data": [{"id": "m-b"}, {"id": "m-a"}, "m-c"]}

    monkeypatch.setattr(requests, "get", lambda *a, **k: Resp())
    ids, err = _client().list_models()
    assert ids == ["m-a", "m-b", "m-c"]
    assert err == ""


def test_list_models_from_models_shape(monkeypatch):
    import requests

    class Resp:
        status_code = 200

        def json(self):
            return {"models": [{"name": "qwen-vl-max"}, {"id": "glm-4v"}]}

    monkeypatch.setattr(requests, "get", lambda *a, **k: Resp())
    ids, err = _client().list_models()
    assert ids == ["glm-4v", "qwen-vl-max"]


def _tiny_png() -> bytes:
    import io

    from PIL import Image

    buf = io.BytesIO()
    Image.new("RGB", (32, 16), "white").save(buf, format="PNG")
    return buf.getvalue()
