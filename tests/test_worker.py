# -*- coding: utf-8 -*-
"""识别/翻译流水线(worker)的行为契约。

用假的模型客户端驱动,不发任何网络请求,验证:
  * 知识库命中不走模型;
  * 云端 OCR / 回答的拼接与结果字段;
  * 翻译任务的两种引擎模式;
  * 失败路径必须回调 on_error 并记一条失败日志(不能静默);
  * 应用了提示词里的占位符替换(历史上漏 import json 导致翻译必失败)。
"""
import json

from app.worker import DEFAULT_QUESTION, PipelineWorker


class FakeClient:
    """最小可用的模型客户端替身。"""

    def __init__(self, ocr_text="CPU 是中央处理器。", answer="这是回答", timeout=180,
                 ocr_error=None, answer_error=None):
        self.timeout = timeout
        self._ocr_text = ocr_text
        self._answer = answer
        self._ocr_error = ocr_error
        self._answer_error = answer_error
        self.prompts = []

    def ocr(self, image, prompt):
        if self._ocr_error:
            raise self._ocr_error
        return self._ocr_text

    def answer(self, image, prompt):
        self.prompts.append(prompt)
        if self._answer_error:
            raise self._answer_error
        return self._answer


def run_worker(**kwargs):
    """同步跑一遍 worker,收集回调。"""
    events = {"status": [], "result": [], "error": []}
    w = PipelineWorker(
        kwargs.pop("client"), kwargs.pop("image", b"png"), kwargs.pop("ocr_prompt", "OCR 提示"),
        kwargs.pop("answer_prompt", "问答提示 {question} {ocr_text} {qtype} {qtitle} {options} {mode}"),
        kwargs.pop("question", ""),
        kwargs.pop("knowledge", []),
        kwargs.pop("ocr_mode", "cloud"),
        on_status=lambda t, tone: events["status"].append((t, tone)),
        on_result=lambda d: events["result"].append(d),
        on_error=lambda t: events["error"].append(t),
        **kwargs,
    )
    w.run()
    return events


def test_cloud_answer_flow(sandbox):
    events = run_worker(client=FakeClient(), question="这是什么")
    assert events["error"] == []
    assert len(events["result"]) == 1
    data = events["result"][0]
    assert data["ocr_text"] == "CPU 是中央处理器。"
    assert data["answer"] == "这是回答"
    assert data["source"] == "模型"
    assert data["task"] == "answer"
    assert data["ocr_time"] >= 0 and data["answer_time"] >= 0
    assert ("完成", "ok") in events["status"]


def test_empty_question_falls_back_to_default(sandbox):
    client = FakeClient()
    run_worker(client=client, question="   ")
    assert DEFAULT_QUESTION in client.prompts[0]


def test_prompt_placeholders_are_filled(sandbox):
    """真实答案提示词里的占位符必须全部被替换,不留花括号。"""
    from app.config import DEFAULT_ANSWER_PROMPT

    client = FakeClient(ocr_text="1. 中国的首都是?\nA. 上海\nB. 北京")
    events = run_worker(client=client, question="请作答", answer_prompt=DEFAULT_ANSWER_PROMPT)
    prompt = client.prompts[0]
    assert "请作答" in prompt
    assert "中国的首都" in prompt
    assert "B. 北京" in prompt
    tail = prompt.split("OCR识别结果")[-1]
    assert "{" not in tail and "}" not in tail, "占位符没有被替换干净"
    assert events["result"][0]["qtype"] == "choice"


def test_knowledge_hit_skips_model(sandbox):
    client = FakeClient()
    kb = [{"keys": ["中央处理器"], "answer": "CPU", "detail": "本地答案"}]
    events = run_worker(client=client, knowledge=kb, question="这是什么")
    data = events["result"][0]
    assert data["answer"] == "CPU"
    assert data["source"] == "本地知识库"
    assert client.prompts == [], "命中知识库时不应该请求模型"
    # 知识库命中必须计入请求日志(否则统计里会凭空少掉一批请求)
    from app import request_log
    recs = request_log.load()
    assert len(recs) == 1 and recs[0]["ok"] is True
    assert recs[0]["source"] == "本地知识库"


def test_local_ocr_mode_uses_local_engine(sandbox, monkeypatch):
    """ocr.mode=local 时不走云端 OCR(用替身验证调用点)。"""
    calls = []

    import app.local_ocr as local_ocr
    monkeypatch.setattr(local_ocr, "recognize", lambda png: calls.append(png) or "本地识别结果")

    client = FakeClient(ocr_text="不该被用到")
    events = run_worker(client=client, ocr_mode="local")
    assert calls, "没有调用端侧 OCR"
    assert events["result"][0]["ocr_text"] == "本地识别结果"


def test_translate_cloud_uses_json_array_prompt(sandbox):
    client = FakeClient(ocr_text="Hello world.\nGood bye.", answer='["你好,世界。","再见。"]')
    events = run_worker(
        client=client, task="translate",
        translate={"source_lang": "英语", "target_lang": "中文", "mode": "cloud",
                   "engine": "auto", "display": "bilingual"},
        answer_prompt=("把 {count} 项从 {source_lang} 翻译为 {target_lang}:{ocr_text}"),
        question="",
    )
    data = events["result"][0]
    assert data["task"] == "translate"
    assert data["engine"] == "云端模型"
    assert [p["dst"] for p in data["pairs"]] == ["你好,世界。", "再见。"]
    assert data["answer"] == "你好,世界。\n再见。"
    # 输入必须是 JSON 数组(分隔符回显问题的根治手段)
    payload = client.prompts[0]
    assert '["Hello world.", "Good bye."]' in payload
    assert "2 项" in payload


def test_translate_appends_extra_requirement_only_when_user_typed(sandbox):
    """附加要求:用户写了才追加。

    现状记录(已知缺陷,已在审计报告登记):
    用户没写提问时 ``question`` 会先被兜底成 DEFAULT_QUESTION("请回答识别到的内容"),
    于是**翻译请求里被判了一段"请回答识别到的内容"的附加要求** —— 这与翻译指令语义相反,
    可能让云端模型去"回答"而不是"翻译"。
    修复方向:兜底只用于答题任务(``task == "answer"``)时,翻译任务空提问就保持空。
    修复后请把下面第一段断言改为 ``not in``。
    """
    client = FakeClient(ocr_text="Hello world.", answer='["你好。"]')
    run_worker(client=client, task="translate",
               translate={"mode": "cloud"}, question="",
               answer_prompt="翻译:{ocr_text}")
    assert "附加要求:请回答识别到的内容" in client.prompts[0], "现状:空提问被兜底成了默认提问"

    client2 = FakeClient(ocr_text="Hello world.", answer='["你好。"]')
    run_worker(client=client2, task="translate",
               translate={"mode": "cloud"}, question="用书面语",
               answer_prompt="翻译:{ocr_text}")
    assert "附加要求:用书面语" in client2.prompts[0]


def test_translate_no_text_short_circuits(sandbox):
    client = FakeClient(ocr_text="(未识别到文字)")
    events = run_worker(client=client, task="translate", translate={"mode": "cloud"})
    data = events["result"][0]
    assert data["pairs"] == []
    assert data["engine"] == "—"
    assert client.prompts == [], "没有文字时不应再请求翻译"


def test_translate_local_engine_path(sandbox, monkeypatch):
    """端侧翻译:走到 local_translate,并把引擎名回传前端。"""
    import app.local_translate as lt
    monkeypatch.setattr(lt, "translate_lines", lambda *a, **k: {
        "pairs": [{"src": "Hello", "dst": "你好"}], "engine": "端侧翻译模型",
        "src_code": "en", "dst_code": "zh"})

    events = run_worker(client=FakeClient(ocr_text="Hello"), task="translate",
                        translate={"mode": "local", "source_lang": "英语", "target_lang": "中文"})
    data = events["result"][0]
    assert data["source"] == "端侧翻译模型"
    assert data["engine"] == "端侧翻译模型"


def test_agent_error_is_reported(sandbox):
    from app.agent import AgentError

    events = run_worker(client=FakeClient(ocr_error=AgentError("API Key 无效")))
    assert events["result"] == []
    assert events["error"] == ["API Key 无效"]
    assert ("失败", "danger") in events["status"]
    from app import request_log
    recs = request_log.load()
    assert len(recs) == 1 and recs[0]["ok"] is False


def test_unexpected_error_is_wrapped(sandbox):
    events = run_worker(client=FakeClient(answer_error=RuntimeError("boom")))
    assert events["error"] and "发生未知错误" in events["error"][0]
    assert "boom" in events["error"][0]


def test_result_is_written_to_history(sandbox):
    run_worker(client=FakeClient())
    from app import history
    items = history.load()
    assert len(items) == 1 and items[0]["answer"] == "这是回答"
