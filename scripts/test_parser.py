# -*- coding: utf-8 -*-
"""单元测试:题目结构化解析 + 本地知识库匹配(无需网络)。

运行: .venv\\Scripts\\python scripts\\test_parser.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.question_parser import parse  # noqa: E402
from app.worker import PipelineWorker  # noqa: E402


def test_choice():
    text = """1. 2025年联合国气候变化大会在哪举办？
A. 日内瓦
B. 纽约
C. 里约热内卢
D. 贝伦"""
    p = parse(text)
    assert p.question_type == "choice", p.question_type
    assert p.options.get("A") == "日内瓦", p.options
    assert p.options.get("D") == "贝伦"
    assert "气候变化" in p.question, p.question
    assert p.is_valid
    print("[choice] OK ->", p.question_type, "|", p.question[:24], "|", p.options_text.replace("\n", " "))


def test_true_false():
    text = "判断题:光速是宇宙中最快的速度。\n正确\n错误"
    p = parse(text)
    assert p.question_type == "true_false", p.question_type
    print("[true_false] OK ->", p.question_type)


def test_fill_blank():
    text = "12. 中国首都在____。"
    p = parse(text)
    assert p.question_type == "fill_blank", p.question_type
    print("[fill_blank] OK ->", p.question_type)


def test_circled_and_inline():
    text = "关于地球,下列说法正确的是 ①A. 自转一周约24小时 ②B. 是太阳系最大的行星 ③C. 没有卫星 ④D. 比太阳大"
    p = parse(text)
    assert p.question_type == "choice", p.question_type
    assert p.options.get("A") or p.options.get("1"), p.options
    print("[circled/inline] OK ->", p.options)


def test_knowledge():
    w = PipelineWorker.__new__(PipelineWorker)
    w._knowledge = [
        {"keys": ["联合国气候变化大会"], "answer": "D", "detail": "COP30 在巴西贝伦"},
    ]
    text = """1. 2025年联合国气候变化大会在哪举办？
A. 日内瓦 B. 纽约 C. 里约热内卢 D. 贝伦"""
    p = parse(text)
    hit = w._match_knowledge(text, p)
    assert hit and hit["answer"] == "D" and hit["source"] == "本地知识库", hit
    miss = w._match_knowledge("完全无关的文本", parse("完全无关的文本"))
    assert miss is None
    print("[knowledge] OK ->", hit["answer"], hit["source"])


if __name__ == "__main__":
    test_choice()
    test_true_false()
    test_fill_blank()
    test_circled_and_inline()
    test_knowledge()
    print("全部通过")
