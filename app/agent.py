# -*- coding: utf-8 -*-
"""百炼(DashScope)OpenAI 兼容接口客户端。

请求体由 config.json 中的 request_template 决定(JSON 模板),
支持占位符 {model} / {prompt} / {image_url}。
"""
import base64
import io
import json
import re
import time

import requests
from PIL import Image

from app.config import DEFAULT_REQUEST_TEMPLATE


class AgentError(Exception):
    """带用户友好信息的接口错误。"""


def chat_endpoint(base_url: str) -> str:
    """把用户填写的 Base URL 归一化成真正的聊天接口地址。

    各家官方文档给的 Base URL 形式不统一(有的带 /v1,有的带 /v4,有的直接给完整接口),
    这里统一处理,避免把请求发到 Base URL 本身而返回 404:
      https://api.deepseek.com          -> https://api.deepseek.com/v1/chat/completions
      https://api.deepseek.com/v1       -> https://api.deepseek.com/v1/chat/completions
      https://api.openai.com/v1         -> https://api.openai.com/v1/chat/completions
      https://open.bigmodel.cn/api/paas/v4 -> .../v4/chat/completions
      http://localhost:11434/v1         -> http://localhost:11434/v1/chat/completions
      https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions -> 原样使用
    若用户填的是自建网关/Ollama 原生接口(以 /api/chat 结尾)则原样使用。
    """
    url = (base_url or "").strip().rstrip("/")
    if not url:
        return url
    low = url.lower()
    for tail in ("/chat/completions", "/completions", "/api/chat", "/messages"):
        if low.endswith(tail):
            return url
    # 只有主机名(没有路径)时,按各家惯例补 /v1
    after_scheme = url.split("://", 1)[-1]
    has_path = "/" in after_scheme
    if not has_path:
        return url + "/v1/chat/completions"
    return url + "/chat/completions"


class AgentClient:
    def __init__(self, api_key: str, model: str, api_base: str,
                 request_template: str = "", timeout: int = 180,
                 max_side: int = 2048, max_retries: int = 3,
                 backoff: float = 0.8, enable_thinking: bool = False):
        self.api_key = (api_key or "").strip()
        self.model = (model or "").strip()
        self.api_base = chat_endpoint(api_base)
        self.request_template = request_template or DEFAULT_REQUEST_TEMPLATE
        self.timeout = timeout
        self.max_side = max_side
        self.max_retries = max(1, max_retries)
        self.backoff = backoff
        self.enable_thinking = enable_thinking

    def _encode_image(self, image: bytes) -> str:
        """PNG 字节 -> base64;长边超过 max_side 时等比压缩,防止接口拒绝。"""
        img = Image.open(io.BytesIO(image))
        w, h = img.size
        if max(w, h) > self.max_side:
            ratio = self.max_side / max(w, h)
            img = img.resize((int(w * ratio), int(h * ratio)), Image.LANCZOS)
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return base64.b64encode(buf.getvalue()).decode()

    def _build_payload(self, prompt: str, image: bytes) -> dict:
        """按模板生成请求体;占位符以 JSON 转义后的值替换,并注入思考开关。"""
        if not self.api_key:
            raise AgentError("未配置 API Key,请点击「配置」填写")
        image_url = "data:image/png;base64," + self._encode_image(image)
        body = (
            self.request_template
            .replace("{model}", json.dumps(self.model, ensure_ascii=False))
            .replace("{prompt}", json.dumps(prompt, ensure_ascii=False))
            .replace("{image_url}", json.dumps(image_url))
        )
        # 按平台的「是否开启思考」注入
        body = re.sub(
            r'"enable_thinking"\s*:\s*(true|false)',
            f'"enable_thinking": {str(bool(self.enable_thinking)).lower()}',
            body,
        )
        try:
            return json.loads(body)
        except Exception as exc:
            raise AgentError(f"请求JSON模板无效:{exc}") from exc

    def _chat(self, prompt: str, image: bytes) -> str:
        """发送请求;网络错误与 5xx/429 自动重试(指数退避)。"""
        payload = self._build_payload(prompt, image)
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        last_err = None
        for attempt in range(self.max_retries):
            try:
                resp = requests.post(self.api_base, headers=headers,
                                     json=payload, timeout=self.timeout)
            except requests.RequestException as exc:
                last_err = exc
            else:
                if resp.status_code in (429, 500, 502, 503, 504) and attempt < self.max_retries - 1:
                    last_err = f"接口返回 {resp.status_code}"
                elif resp.status_code != 200:
                    detail = ""
                    try:
                        detail = resp.json().get("error", {}).get("message", resp.text[:300])
                    except Exception:
                        detail = resp.text[:300]
                    if resp.status_code == 404:
                        raise AgentError(
                            f"接口返回 404(请求地址:{self.api_base})。"
                            f"通常是 Base URL 填错,或模型 ID 不存在:{detail}")
                    if resp.status_code in (401, 403):
                        raise AgentError(f"接口返回 {resp.status_code}:API Key 无效或无该模型权限:{detail}")
                    raise AgentError(f"接口返回 {resp.status_code}:{detail}")
                else:
                    try:
                        data = resp.json()
                        return data["choices"][0]["message"]["content"]
                    except (KeyError, IndexError, ValueError) as exc:
                        raise AgentError(f"接口响应解析失败:{resp.text[:300]}") from exc
            if attempt < self.max_retries - 1:
                time.sleep(self.backoff * (attempt + 1))
        raise AgentError(f"网络请求失败(已重试 {self.max_retries} 次):{last_err}")

    # ---------- 业务 ----------
    def ocr(self, image: bytes, prompt: str) -> str:
        """第一步:云端 OCR,只返回识别到的文字。"""
        return self._chat(prompt, image)

    def answer(self, image: bytes, prompt: str) -> str:
        """第二步:结合截图与 OCR 文字回答问题(prompt 已由调用方拼好)。"""
        return self._chat(prompt, image)

    def test_connection(self) -> str:
        """最小化连通性测试:发送纯文本 ping,返回结果说明。"""
        if not self.api_key:
            return "未配置 API Key"
        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": "ping"}],
            "max_tokens": 1,
        }
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        try:
            resp = requests.post(self.api_base, headers=headers,
                                 json=payload, timeout=min(self.timeout, 20))
        except requests.RequestException as exc:
            return f"连接失败:{exc}"
        if resp.status_code == 200:
            return "连接成功"
        detail = ""
        try:
            detail = resp.json().get("error", {}).get("message", resp.text[:200])
        except Exception:
            detail = resp.text[:200]
        if resp.status_code == 404:
            return (f"Base URL 或模型 ID 不正确(实际请求:{self.api_base})。"
                    f"Base URL 只填到 /v1 即可,程序会自动补 /chat/completions;{detail}")
        if resp.status_code in (401, 403):
            return f"API Key 无效或无权限({resp.status_code}):{detail}"
        if resp.status_code == 400:
            return f"请求被拒绝(通常是模型 ID 错误或参数不支持):{detail}"
        return f"失败({resp.status_code}):{detail}"
