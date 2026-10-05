# -*- coding: utf-8 -*-
"""框选参数归一化:历史上"点翻译只做识别"就是参数错位造成的,这里锁死契约。"""
import pytest

from app.manager import SNIP_ACTIONS, normalize_snip_args


@pytest.mark.parametrize("action", SNIP_ACTIONS)
def test_new_signature_passes_through(action):
    sel = {"x": 1, "y": 2, "w": 3, "h": 4, "dpr": 1.25}
    out_sel, out_action, out_q = normalize_snip_args(sel, action, "提问")
    assert out_action == action
    assert out_q == "提问"
    assert out_sel == sel
    assert "action" not in out_sel


def test_legacy_signature_recovers_action_and_question():
    """旧版:finish_snip({...

    action:'region'}, '提问') —— 动作藏在 sel 里,提问落在第二个参数。"""
    sel = {"x": 0, "y": 0, "w": 10, "h": 10, "action": "region"}
    out_sel, action, question = normalize_snip_args(sel, "请翻译这段文字", "")
    assert action == "region", "动作不能再丢失"
    assert question == "请翻译这段文字", "旧调用里的提问要平移成 question"
    assert "action" not in out_sel


def test_legacy_signature_does_not_duplicate_question():
    sel = {"x": 0, "y": 0, "w": 10, "h": 10, "action": "translate"}
    _, action, question = normalize_snip_args(sel, "translate", "既有提问")
    assert action == "translate"
    assert question == "既有提问"


def test_unknown_action_falls_back_to_run():
    _, action, _ = normalize_snip_args({"x": 0, "y": 0, "w": 1, "h": 1}, "banana", "")
    assert action == "run"


def test_empty_selection_is_safe():
    sel, action, question = normalize_snip_args(None, None, None)
    assert sel == {}
    assert action == "run"
    assert question == ""
