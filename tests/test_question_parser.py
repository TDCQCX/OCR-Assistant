# -*- coding: utf-8 -*-
"""题目解析:题型判定、选项抽取、题干清理(提示词与知识库匹配都依赖它)。"""
from app.question_parser import parse


def test_choice_question_with_line_options():
    text = "1. 中国的首都是哪个城市?\nA. 上海\nB. 北京\nC. 广州\nD. 深圳"
    q = parse(text)
    assert q.question_type == "choice"
    assert list(q.options) == ["A", "B", "C", "D"]
    assert q.options["B"] == "北京"
    assert "首都" in q.question
    assert q.is_valid


def test_choice_question_with_inline_options():
    text = "2. 下列哪个是编程语言? A. 香蕉 B. Python C. 桌子 D. 汽车"
    q = parse(text)
    assert q.question_type == "choice"
    assert q.options.get("B") == "Python"


def test_numeric_label_is_not_treated_as_option():
    """"1. 题目"是题号,不能被吃成选项(否则题干会空)。"""
    q = parse("1. 请计算 2+2 的值\n2. 请计算 3+3 的值")
    assert q.options == {}
    assert "2+2" in q.question


def test_true_false_by_hint():
    q = parse("3. 判断下列说法的对错:地球是平的\nA. 正确\nB. 错误")
    assert q.question_type == "true_false"


def test_true_false_without_options():
    q = parse("下列说法是否正确:水在常温下是液体")
    assert q.question_type == "true_false"


def test_fill_blank():
    q = parse("4. 中国的首都是____。")
    assert q.question_type == "fill_blank"


def test_open_ended():
    """纯问答题(无选项、无判断提示)→ 主观题。"""
    q = parse("请解释一下函数连续性的定义。")
    assert q.question_type == "open_ended"


def test_typing_hint_matching_is_too_loose_known_issue():
    """现状记录(已知缺陷):无选项时 ``对|错`` 单字参与判断题判定,会误伤常见词汇。

    "相对论"里的"对"、"不错"里的"错"都会让整题被判成判断题(true_false),
    进而影响知识库匹配键与答题提示词里的题型说明。
    修复方向:去掉单字 ``对|错`` 兜底,只保留 ``正确|错误|是否`` 等多字提示
    (带选项的判断题已由选项内容分支覆盖)。修复后请把本用例改为断言 open_ended。
    """
    q = parse("请解释一下相对论的基本思想,并说明其现实意义。")
    assert q.question_type == "true_false"


def test_true_false_still_detected_by_word_hint():
    """多字提示词仍能正确判为判断题(不能为了修上面的缺陷而把这条弄坏)。"""
    assert parse("下列说法是否正确:水在常温下是液体").question_type == "true_false"
    assert parse("判断下列说法的对错:1+1=3").question_type == "true_false"


def test_option_content_is_trimmed():
    q = parse("5. 题目内容是什么?\nA. " + "很长的选项内容" * 40)
    assert len(q.options["A"]) <= 200


def test_question_is_truncated():
    q = parse("题干" * 400 + "?")
    assert len(q.question) <= 300


def test_options_text_format():
    q = parse("6. 选一个\nA. 甲\nB. 乙")
    assert q.options_text == "A. 甲\nB. 乙"
    assert parse("没有选项的纯文本题目内容").options_text == "无选项"


def test_empty_text_is_safe():
    q = parse("")
    assert q.question == "" and q.options == {}
    assert not q.is_valid


def test_multi_line_option_continuation_is_merged():
    q = parse("7. 下面哪个正确?\nA. 第一行的内容\n第二行还是 A 的内容\nB. 另一个选项")
    assert "第二行还是 A 的内容" in q.options["A"]
