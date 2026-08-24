# -*- coding: utf-8 -*-
"""题目文本结构化解析(借鉴 AutoAnswer 的 OCREngine 解析逻辑,精简版)。

把 OCR 识别出的文本解析为 {题型, 题目, 选项},供本地知识库匹配与答题提示词使用。
"""
import re
from dataclasses import dataclass, field
from typing import Dict, List, Tuple

CIRCLED_NUM_MAP = {
    '①': '1', '②': '2', '③': '3', '④': '4', '⑤': '5',
    '⑥': '6', '⑦': '7', '⑧': '8', '⑨': '9', '⑩': '10',
}
CN_NUM_MAP = {
    '一': '1', '二': '2', '三': '3', '四': '4', '五': '5',
    '六': '6', '七': '7', '八': '8', '九': '9', '十': '10',
}

# 注意:不匹配纯数字标签,避免把编号题目行("1. 题目")误判为选项
OPTION_LINE_RE = re.compile(
    r'^\s*(?P<label>[A-Za-z]|[①②③④⑤⑥⑦⑧⑨⑩]|'
    r'[一二三四五六七八九十])\s*[\.\、．:：\)）]\s*(?P<content>.+?)\s*$'
)
INLINE_LETTER_OPTION_RE = re.compile(
    r'(?<![A-Za-z0-9])(?P<label>[A-Z])\s*[\.\、．:：\)）]\s*'
)
FILL_BLANK_PATTERNS = [
    r'_{2,}', r'（\s*）', r'\(\s*\)', r'【\s*】', r'\[\s*\]',
]
TRUE_FALSE_HINTS = (
    '判断题', '判断下列', '对错', '是否正确', '是否错误', '是非题'
)


@dataclass
class ParsedQuestion:
    question: str = ""
    options: Dict[str, str] = field(default_factory=dict)
    question_type: str = "unknown"
    raw_text: str = ""

    @property
    def options_text(self) -> str:
        if not self.options:
            return "无选项"
        return "\n".join(f"{k}. {v}" for k, v in sorted(self.options.items()))

    @property
    def is_valid(self) -> bool:
        return len(self.question.replace("\n", "").strip()) >= 4 or len(self.options) >= 2


def _normalize_label(label: str) -> str:
    label = label.strip()
    if label in CIRCLED_NUM_MAP:
        return CIRCLED_NUM_MAP[label]
    if label in CN_NUM_MAP:
        return CN_NUM_MAP[label]
    if label.isalpha():
        return label.upper()
    return label


def _normalize_lines(text: str) -> List[str]:
    lines = []
    for line in text.split("\n"):
        cleaned = re.sub(r"[^\S\n]+", " ", line).strip()
        if cleaned:
            lines.append(cleaned)
    return lines


def _extract_options_from_lines(lines: List[str]) -> Tuple[Dict[str, str], int]:
    options: Dict[str, str] = {}
    current_label = None
    option_start = len(lines)
    for idx, line in enumerate(lines):
        m = OPTION_LINE_RE.match(line)
        if m:
            label = _normalize_label(m.group("label"))
            content = m.group("content").strip()
            if option_start == len(lines):
                option_start = idx
            if content:
                options[label] = content[:200]
                current_label = label
            continue
        if current_label is not None and option_start < len(lines):
            options[current_label] = (options[current_label] + " " + line)[:200]
    return options, option_start


def _extract_inline_options(text: str) -> Dict[str, str]:
    options: Dict[str, str] = {}
    matches = list(INLINE_LETTER_OPTION_RE.finditer(text))
    if len(matches) < 2:
        return options
    for i, m in enumerate(matches):
        label = m.group("label").upper()
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        content = text[start:end].strip(" \n\t,，;；")
        if content:
            options[label] = content[:200]
    return options


def _clean_question(question: str) -> str:
    patterns = [
        (r"^\d+[\.\u3001\s]*", ""),
        (r"^[\u4e00\u4e8c\u4e09\u56db\u4e94\u516d\u4e03\u516b\u4e5d\u5341\u767e]+[\.\u3001\s]*", ""),
        (r"^(题目|问题|请回答)[\uff1a:]?\s*", ""),
    ]
    for pat, rep in patterns:
        question = re.sub(pat, rep, question, flags=re.IGNORECASE)
    return question.strip()


def _detect_type(question: str, options: Dict[str, str], raw_text: str) -> str:
    combined = f"{question}\n{raw_text}".strip()
    values = "".join(options.values()).replace(" ", "")
    if len(options) <= 2 and (
        any(h in combined for h in TRUE_FALSE_HINTS)
        or ("正确" in values and "错误" in values)
        or (not options and re.search(r"(正确|错误|对|错|是否)", question))
    ):
        return "true_false"
    if not options and ("填空" in combined or any(re.search(p, combined) for p in FILL_BLANK_PATTERNS)):
        return "fill_blank"
    if options:
        return "choice"
    return "open_ended"


def parse(text: str) -> ParsedQuestion:
    """解析 OCR 文本 -> ParsedQuestion。解析失败时返回仅含原文的结果。"""
    if not text or not text.strip():
        return ParsedQuestion(raw_text=text or "")
    lines = _normalize_lines(text)
    text = "\n".join(lines)

    options, option_start = _extract_options_from_lines(lines)
    if options:
        question = "\n".join(lines[:option_start]).strip() if option_start > 0 else text
    else:
        options = _extract_inline_options(text)
        question = text
        if options:
            first_pos = len(text)
            for label in options:
                m = re.search(
                    r"(?<![A-Za-z0-9])%s\s*[\.\、．:：\)）]" % re.escape(label),
                    text, re.IGNORECASE,
                )
                if m and m.start() < first_pos:
                    first_pos = m.start()
            question = text[:first_pos].strip()

    question = _clean_question(question)
    return ParsedQuestion(
        question=question[:300],
        options=options,
        question_type=_detect_type(question, options, text),
        raw_text=text,
    )
