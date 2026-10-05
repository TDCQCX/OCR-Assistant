# -*- coding: utf-8 -*-
"""请求日志:记录上限、按天统计、统计口径与 days 参数一致。"""
import json
import time

from app import request_log


def test_load_missing_returns_empty(sandbox):
    assert request_log.load() == []


def test_append_record_fields(sandbox):
    request_log.append(True, 123.7, "模型")
    recs = request_log.load()
    assert len(recs) == 1
    r = recs[0]
    assert r["ok"] is True
    assert r["ms"] == 123
    assert r["source"] == "模型"
    assert abs(float(r["ts"]) - time.time()) < 5


def test_append_keeps_max_records(sandbox):
    for i in range(request_log.MAX_RECORDS + 10):
        request_log.append(True, 1, f"s{i}")
    recs = request_log.load()
    assert len(recs) == request_log.MAX_RECORDS
    assert recs[-1]["source"] == f"s{request_log.MAX_RECORDS + 9}"


def test_stats_counts_failures_and_rate(sandbox):
    request_log.append(True, 100)
    request_log.append(True, 300)
    request_log.append(False, 0)
    s = request_log.stats(140)
    assert s["total"] == 3
    assert s["failed"] == 1
    assert s["ok"] == 2
    assert s["success_rate"] == round(200 / 3, 1)
    # 平均耗时只统计成功且有耗时的记录,不把失败的 0ms 拉低平均值
    assert s["avg_ms"] == 200
    assert s["days"] == 140


def test_stats_window_matches_days_param(sandbox):
    """days 之外的记录不能计入统计(否则右侧数字与图上窗口对不上)。"""
    old = {"ts": time.time() - 40 * 86400, "ok": True, "ms": 10, "source": "旧"}
    request_log.save([old, {"ts": time.time(), "ok": True, "ms": 10, "source": "新"}])

    near = request_log.stats(7)
    assert near["total"] == 1, "统计必须遵守 days 参数"
    far = request_log.stats(140)
    assert far["total"] == 2


def test_day_counts_buckets_by_local_day(sandbox):
    now = time.time()
    request_log.save([
        {"ts": now, "ok": True, "ms": 1, "source": "a"},
        {"ts": now - 3, "ok": True, "ms": 1, "source": "b"},
        {"ts": now - 40 * 86400, "ok": True, "ms": 1, "source": "old"},
    ])
    counts = request_log.day_counts(7)
    today = time.strftime("%Y-%m-%d", time.localtime(now))
    assert counts.get(today) == 2
    assert sum(counts.values()) == 2, "超出 days 的记录不应出现"


def test_corrupt_log_is_tolerated(sandbox):
    request_log.LOG_PATH.write_text("不是 json", encoding="utf-8")
    assert request_log.load() == []
    s = request_log.stats(140)
    assert s["total"] == 0 and s["success_rate"] == 0.0


def test_json_is_readable_utf8(sandbox):
    request_log.append(True, 1, "本地知识库")
    raw = request_log.LOG_PATH.read_text(encoding="utf-8")
    assert "本地知识库" in raw
    assert json.loads(raw)
