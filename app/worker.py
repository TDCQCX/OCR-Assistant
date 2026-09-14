# -*- coding: utf-8 -*-
"""识别流程线程(纯 Python 线程 + 回调):OCR -> 题目解析 -> 本地知识库/模型回答/翻译。"""
import threading
import time

from app import history, request_log
from app.agent import AgentClient, AgentError
from app.question_parser import parse as parse_question

DEFAULT_QUESTION = "请回答识别到的内容"

TYPE_NAMES = {
    "choice": "选择题",
    "true_false": "判断题",
    "fill_blank": "填空题",
    "open_ended": "问答题",
}


class PipelineWorker(threading.Thread):
    """后台流程线程,结果通过回调返回。"""

    def __init__(self, client: AgentClient, image: bytes, ocr_prompt: str,
                 answer_prompt: str, question: str, knowledge: list = None,
                 ocr_mode: str = "cloud", on_status=None, on_result=None,
                 on_error=None, task: str = "answer", translate: dict = None):
        super().__init__(daemon=True)
        self._client = client
        self._image = image
        self._ocr_prompt = ocr_prompt
        self._answer_prompt = answer_prompt
        self._question = (question or "").strip() or DEFAULT_QUESTION
        self._knowledge = knowledge or []
        self._ocr_mode = ocr_mode or "cloud"
        self._on_status = on_status or (lambda text, tone: None)
        self._on_result = on_result or (lambda data: None)
        self._on_error = on_error or (lambda text: None)
        self._task = (task or "answer").lower()
        self._tr = dict(translate or {})

    # ---------- 本地知识库 ----------
    def _match_knowledge(self, ocr_text: str, parsed) -> dict:
        haystack = f"{ocr_text}\n{parsed.question}\n{parsed.options_text}"
        for item in self._knowledge:
            keys = item.get("keys") or []
            if any(k and k in haystack for k in keys):
                return {"answer": item.get("answer", "?"),
                        "detail": item.get("detail", ""),
                        "source": "本地知识库"}
        return None

    def _result(self, ocr_text, parsed, answer, detail, source, ocr_time, answer_time,
                extra: dict = None) -> dict:
        data = {
            "ocr_text": ocr_text,
            "qtype": parsed.question_type or "unknown",
            "qtype_name": TYPE_NAMES.get(parsed.question_type, "未知题型"),
            "question": parsed.question,
            "options": parsed.options_text,
            "answer": answer,
            "detail": detail,
            "source": source,
            "ocr_time": ocr_time,
            "answer_time": answer_time,
            "task": self._task,
        }
        data.update(extra or {})
        return data

    # ---------- 翻译任务 ----------
    def _run_translate(self):
        src_lang = self._tr.get("source_lang", "自动检测")
        dst_lang = self._tr.get("target_lang", "中文")
        engine_mode = (self._tr.get("mode") or "cloud").lower()
        local_engine = self._tr.get("engine", "auto")
        display = self._tr.get("display", "bilingual")

        self._on_status("正在识别内容…", "working")
        t0 = time.time()
        if self._ocr_mode == "local":
            from app.local_ocr import recognize as local_recognize
            ocr_text = local_recognize(self._image).strip()
        else:
            ocr_text = self._client.ocr(self._image, self._ocr_prompt).strip()
        ocr_time = time.time() - t0

        if not ocr_text or ocr_text.startswith("(未识别到文字"):
            request_log.append(True, ocr_time * 1000.0, "翻译(无文字)")
            self._on_status("未识别到文字", "warn")
            self._on_result(self._result(ocr_text, parse_question(ocr_text), "", "", "翻译",
                                         ocr_time, 0.0,
                                         {"pairs": [], "src_lang": src_lang, "dst_lang": dst_lang,
                                          "display": display, "engine": "—"}))
            return

        parsed = parse_question(ocr_text)
        self._on_status("正在翻译…", "working")
        t1 = time.time()
        from app import local_translate
        segments = local_translate.segment_text(ocr_text)

        if engine_mode == "local":
            info = local_translate.translate_lines(
                ocr_text, src_lang, dst_lang, local_engine,
                ollama_url=self._tr.get("ollama_url", ""),
                ollama_model=self._tr.get("ollama_model", ""),
                timeout=min(int(self._client.timeout), 180))
            pairs = info["pairs"]
            engine_name = info["engine"]
        else:
            prompt = (self._answer_prompt
                      .replace("{source_lang}", src_lang)
                      .replace("{target_lang}", dst_lang)
                      .replace("{count}", str(len(segments)))
                      .replace("{ocr_text}", "\n---\n".join(segments))
                      .replace("{question}", self._question))
            if (self._question or "").strip():
                prompt += f"\n\n附加要求:{self._question.strip()}"
            raw = self._client.answer(self._image, prompt).strip()
            pairs = local_translate.parse_translation_output(raw, segments)
            engine_name = "云端模型"

        answer_time = time.time() - t1
        text = "\n".join(p["dst"] for p in pairs if p.get("dst"))
        request_log.append(True, (ocr_time + answer_time) * 1000.0, "翻译")
        self._on_status("翻译完成", "ok")
        data = self._result(ocr_text, parsed, text, "", "翻译" if engine_mode == "cloud" else engine_name,
                            ocr_time, answer_time,
                            {"pairs": pairs, "src_lang": src_lang, "dst_lang": dst_lang,
                             "display": display, "engine": engine_name,
                             "mode": engine_mode})
        history.append(data)
        self._on_result(data)

    # ---------- 主流程 ----------
    def run(self):
        try:
            if self._task == "translate":
                self._run_translate()
                return
            self._on_status("正在OCR识别…", "working")
            t0 = time.time()
            if self._ocr_mode == "local":
                from app.local_ocr import recognize as local_recognize
                ocr_text = local_recognize(self._image).strip()
            else:
                ocr_text = self._client.ocr(self._image, self._ocr_prompt).strip()
            ocr_time = time.time() - t0

            parsed = parse_question(ocr_text)

            hit = self._match_knowledge(ocr_text, parsed)
            if hit:
                request_log.append(True, ocr_time * 1000.0, "本地知识库")
                self._on_status("本地知识库命中", "ok")
                self._on_result(self._result(ocr_text, parsed, hit["answer"], hit["detail"],
                                             hit["source"], ocr_time, 0.0))
                return

            self._on_status("OCR完成,正在获取回答…", "working")
            prompt = (self._answer_prompt
                      .replace("{qtype}", parsed.question_type or "未知")
                      .replace("{qtitle}", parsed.question or ocr_text[:200])
                      .replace("{options}", parsed.options_text)
                      .replace("{question}", self._question)
                      .replace("{ocr_text}", ocr_text))
            t1 = time.time()
            answer = self._client.answer(self._image, prompt).strip()
            answer_time = time.time() - t1

            request_log.append(True, (ocr_time + answer_time) * 1000.0, "模型")
            self._on_status("完成", "ok")
            data = self._result(ocr_text, parsed, answer, "", "模型", ocr_time, answer_time)
            history.append(data)
            self._on_result(data)
        except AgentError as exc:
            request_log.append(False, 0.0, "错误")
            self._on_status("失败", "danger")
            self._on_error(str(exc))
        except Exception as exc:  # noqa: BLE001
            request_log.append(False, 0.0, "错误")
            self._on_status("失败", "danger")
            self._on_error(f"发生未知错误:{exc}")
