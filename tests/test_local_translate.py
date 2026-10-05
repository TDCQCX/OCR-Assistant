# -*- coding: utf-8 -*-
"""端侧翻译的纯逻辑:分段、译文解析、提示词回显清洗、语言码映射。"""
from app import local_translate as lt


def test_segment_merges_unfinished_lines():
    text = "第一行没有句号\n第二行也没有\n第三行结束了。\n\n新段落结束。"
    segs = lt.segment_text(text)
    assert segs == ["第一行没有句号 第二行也没有 第三行结束了。", "新段落结束。"]


def test_segment_long_line_is_not_split():
    """现状记录:单行超长文本不会被再切分(函数 docstring 说会按 max_len 拆开,实际只 flush)。

    影响:一行超过 max_len 的文本会整段送进端侧模型,而 local_hf 侧
    ``truncation=True, max_length=400`` 会静默截断 → 丢内容。
    已在审计中登记为待确认项;若将来真的实现切分,请同步更新本用例。
    """
    long_line = "啊" * 500
    segs = lt.segment_text(long_line, max_len=100)
    assert len(segs) == 1
    assert len(segs[0]) == 500


def test_segment_empty_text():
    assert lt.segment_text("") == []
    assert lt.segment_text("\n\n   \n") == []


def test_parse_translation_output_json_array():
    segs = ["Hello", "World"]
    out = lt.parse_translation_output('["你好","世界"]', segs)
    assert [p["dst"] for p in out] == ["你好", "世界"]
    assert [p["src"] for p in out] == segs


def test_parse_translation_output_strips_json_fence():
    segs = ["Hello"]
    out = lt.parse_translation_output('```json\n["你好"]\n```', segs)
    assert out[0]["dst"] == "你好"


def test_parse_translation_output_short_array_is_padded_by_frontend_contract():
    """译文条数**少于**原文时只返回已有条数(不补空),由前端按 src 对齐展示。

    这是现状契约:补空逻辑在消费侧。若后端将来改为补空,请同步修改本用例。
    """
    out = lt.parse_translation_output('["一"]', ["a", "b"])
    assert len(out) == 1
    assert out[0] == {"src": "a", "dst": "一"}


def test_parse_translation_output_extra_items_keep_empty_src():
    """现状记录:译文比原文多时,多出来的条目 src 为空(前端左栏会出现空行)。

    属于轻微展示瑕疵(不影响功能),已在审计里登记为待确认项。
    若后端改为按原文条数截断,请同步修改本用例。
    """
    out = lt.parse_translation_output('["一","二","三"]', ["a"])
    assert len(out) == 3
    assert out[0] == {"src": "a", "dst": "一"}
    assert out[1]["src"] == "" and out[1]["dst"] == "二"


def test_parse_translation_output_filters_prompt_leak_and_numbering():
    """模型把提示词/编号抄进译文时,应回退为逐行对齐而不是原样展示。"""
    segs = ["苹果", "香蕉"]
    raw = "1. 苹果\n2. 香蕉"
    out = lt.parse_translation_output(raw, segs)
    assert len(out) == len(segs)
    # 编号行被识别为残留行 → 清洗后仍保留对应译文内容
    assert all(p["dst"] for p in out)


def test_lang_code_mapping():
    from app.config import LANG_CODES

    for name, code in LANG_CODES.items():
        assert lt._lang_code(name) == code
    assert lt._lang_code("自动检测") == ""
    assert lt._lang_code("不存在的语言") == ""


def test_translate_lines_rejects_empty_text():
    try:
        lt.translate_lines("   ", "英语", "中文")
    except lt.LocalTranslateError as exc:
        assert "没有可翻译的内容" in str(exc)
    else:
        raise AssertionError("空文本必须报错")


def test_translate_lines_rejects_unsupported_target():
    try:
        lt.translate_lines("hello", "英语", "克林贡语")
    except lt.LocalTranslateError as exc:
        assert "不支持的目标语言" in str(exc)
    else:
        raise AssertionError("不支持的语言必须报错")


def test_translate_lines_rejects_unsupported_source():
    try:
        lt.translate_lines("hello", "克林贡语", "中文")
    except lt.LocalTranslateError as exc:
        assert "不支持的来源语言" in str(exc)
    else:
        raise AssertionError("不支持的来源语言必须报错")


def test_translate_lines_collects_engine_errors(monkeypatch):
    """所有引擎都不可用时,错误信息里要能看出原因(没有模型/连接失败都算)。

    这里把两个外部依赖都"假死":端侧小模型判为不可用、本机没有 argostranslate,
    避免真的去联网下载语言包(会让用例卡到超时)。
    """
    from app import local_mt

    monkeypatch.setattr(local_mt, "available", lambda *a, **k: False)
    monkeypatch.setattr(lt, "argos_installed", lambda: False)
    monkeypatch.setattr(lt, "argos_languages", lambda: [])

    try:
        lt.translate_lines("hello world", "英语", "中文", engine="argos")
    except lt.LocalTranslateError as exc:
        assert "端侧翻译模型" in str(exc) or "未安装" in str(exc)
    else:
        raise AssertionError("本地引擎不可用时必须抛 LocalTranslateError")


def test_translate_lines_auto_reports_missing_model(monkeypatch):
    """auto 模式下没有可用引擎:提示应指向"去设置里下载模型"。"""
    from app import local_mt

    monkeypatch.setattr(local_mt, "available", lambda *a, **k: False)
    monkeypatch.setattr(lt, "argos_languages", lambda: [])

    try:
        lt.translate_lines("hello world", "英语", "中文", engine="auto")
    except lt.LocalTranslateError as exc:
        assert "尚未下载" in str(exc)
    else:
        raise AssertionError("无可用引擎时必须抛 LocalTranslateError")


def test_prompt_leak_helpers():
    assert lt.is_prompt_leak("请只输出一个 JSON 数组")
    assert not lt.is_prompt_leak("这是一句正常译文")
    assert lt.is_artifact_line("=====")
