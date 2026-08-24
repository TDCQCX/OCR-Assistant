# -*- coding: utf-8 -*-
"""后台流程线程:OCR -> 题目解析 -> 本地知识库/模型回答,避免网络等待卡住界面。

结果以结构化字典通过 finished_ok 发出:
{ocr_text, qtype, answer, detail, source, ocr_time, answer_time}
"""
import time

from PySide6.QtCore import QThread, Signal

from app import request_log
from app.agent import AgentClient, AgentError
from app.question_parser import parse as parse_question

DEFAULT_QUESTION = "请给出该题目的答案"

TYPE_NAMES = {
    "choice": "选择题",
    "true_false": "判断题",
    "fill_blank": "填空题",
    "open_ended": "问答题",
}


class PipelineWorker(QThread):
    status = Signal(str, str)  # (文本, 状态: working / ok / error)
    finished_ok = Signal(dict)  # 结构化结果
    failed = Signal(str)       # 错误信息

    def __init__(self, client: AgentClient, image: bytes, ocr_prompt: str,
                 answer_prompt: str, question: str, knowledge: list = None,
                 ocr_mode: str = "cloud", parent=None):
        super().__init__(parent)
        self._client = client
        self._image = image
        self._ocr_prompt = ocr_prompt
        self._answer_prompt = answer_prompt
        self._question = (question or "").strip() or DEFAULT_QUESTION
        self._knowledge = knowledge or []
        self._ocr_mode = ocr_mode or "cloud"

    def _match_knowledge(self, ocr_text: str, parsed) -> dict:
        """本地知识库匹配:关键词命中即返回,免 API 调用。"""
        haystack = f"{ocr_text}\n{parsed.question}\n{parsed.options_text}"
        for item in self._knowledge:
            keys = item.get("keys") or []
            if any(k and k in haystack for k in keys):
                return {
                    "answer": item.get("answer", "?"),
                    "detail": item.get("detail", ""),
                    "source": "本地知识库",
                }
        return None

    def _result(self, ocr_text: str, parsed, answer: str, detail: str,
                source: str, ocr_time: float, answer_time: float) -> dict:
        return {
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
        }

    def run(self):
        try:
            self.status.emit("正在OCR识别…", "working")
            t_ocr0 = time.time()
            if self._ocr_mode == "local":
                from app.local_ocr import recognize as local_recognize
                ocr_text = local_recognize(self._image).strip()
            else:
                ocr_text = self._client.ocr(self._image, self._ocr_prompt).strip()
            ocr_time = time.time() - t_ocr0

            parsed = parse_question(ocr_text)

            # 本地知识库优先(毫秒级,免 API)
            hit = self._match_knowledge(ocr_text, parsed)
            if hit:
                request_log.append(True, ocr_time * 1000.0, "本地知识库")
                self.status.emit("本地知识库命中", "ok")
                self.finished_ok.emit(self._result(
                    ocr_text, parsed, hit["answer"], hit["detail"],
                    hit["source"], ocr_time, 0.0,
                ))
                return

            self.status.emit("OCR完成,正在获取回答…", "working")
            # 用 replace 而非 format,避免文本中的花括号导致崩溃
            prompt = (
                self._answer_prompt
                .replace("{qtype}", parsed.question_type or "未知")
                .replace("{qtitle}", parsed.question or ocr_text[:200])
                .replace("{options}", parsed.options_text)
                .replace("{question}", self._question)
                .replace("{ocr_text}", ocr_text)
            )
            t_ans0 = time.time()
            answer = self._client.answer(self._image, prompt).strip()
            answer_time = time.time() - t_ans0

            request_log.append(True, (ocr_time + answer_time) * 1000.0, "模型")
            self.status.emit("完成", "ok")
            self.finished_ok.emit(self._result(
                ocr_text, parsed, answer, "", "模型", ocr_time, answer_time,
            ))
        except AgentError as exc:
            request_log.append(False, 0.0, "错误")
            self.status.emit("失败", "error")
            self.failed.emit(str(exc))
        except Exception as exc:  # noqa: BLE001
            request_log.append(False, 0.0, "错误")
            self.status.emit("失败", "error")
            self.failed.emit(f"发生未知错误:{exc}")
