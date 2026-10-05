# -*- coding: utf-8 -*-
"""识别历史的持久化契约(上限、时间戳、损坏文件容错)。"""
import json

from app import history


def test_load_missing_file_returns_empty(sandbox):
    assert history.load() == []


def test_append_adds_timestamp_and_persists(sandbox):
    history.append({"ocr_text": "A", "answer": "B"})
    items = history.load()
    assert len(items) == 1
    assert items[0]["ocr_text"] == "A"
    assert items[0]["time"], "每条历史必须带时间戳(历史页相对时间依赖它)"


def test_append_trims_to_max_items(sandbox):
    for i in range(history.MAX_ITEMS + 15):
        history.append({"ocr_text": str(i)})
    items = history.load()
    assert len(items) == history.MAX_ITEMS
    assert items[-1]["ocr_text"] == str(history.MAX_ITEMS + 14), "保留最新的 N 条"
    assert items[0]["ocr_text"] == "15"


def test_load_corrupt_file_returns_empty(sandbox):
    history.PATH.write_text("{ 不是 JSON", encoding="utf-8")
    assert history.load() == []


def test_load_non_list_file_returns_empty(sandbox):
    """历史文件被写成对象时不能把非列表交给前端渲染。"""
    history.PATH.write_text(json.dumps({"a": 1}), encoding="utf-8")
    assert history.load() == []


def test_clear(sandbox):
    history.append({"ocr_text": "x"})
    history.clear()
    assert history.load() == []
