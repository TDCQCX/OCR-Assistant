# -*- coding: utf-8 -*-
"""请求记录:最近请求的成功/失败与耗时,供「关于应用」的 GitHub 风格绿块图展示。"""
import json
import sys
import time
from pathlib import Path

if getattr(sys, "frozen", False):
    ROOT = Path(sys.executable).resolve().parent
else:
    ROOT = Path(__file__).resolve().parent.parent
LOG_PATH = ROOT / "request_log.json"
MAX_RECORDS = 500


def load() -> list:
    try:
        return json.loads(LOG_PATH.read_text(encoding="utf-8"))
    except Exception:
        return []


def append(ok: bool, ms: float, source: str = "模型") -> None:
    records = load()
    records.append({"ts": time.time(), "ok": ok, "ms": int(ms), "source": source})
    save(records[-MAX_RECORDS:])


def save(records: list) -> None:
    LOG_PATH.write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")


def day_counts(days: int = 140) -> dict:
    """返回最近 days 天内每天请求次数:{'YYYY-MM-DD': count}。"""
    counts = {}
    for r in load():
        d = time.strftime("%Y-%m-%d", time.localtime(r["ts"]))
        counts[d] = counts.get(d, 0) + 1
    return counts


def stats(days: int = 140) -> dict:
    """统计:总请求次数、失败次数、成功率、平均耗时,以及最近 days 天的天数覆盖。"""
    records = load()
    total = len(records)
    failed = sum(1 for r in records if not r.get("ok", True))
    ok = total - failed
    durations = [int(r.get("ms") or 0) for r in records if (r.get("ms") or 0) > 0]
    return {
        "total": total,
        "ok": ok,
        "failed": failed,
        "success_rate": round(ok * 100.0 / total, 1) if total else 0.0,
        "avg_ms": int(sum(durations) / len(durations)) if durations else 0,
        "keep": MAX_RECORDS,
        "days": days,
        "first_ts": min((r.get("ts") or 0) for r in records) if records else 0,
        "last_ts": max((r.get("ts") or 0) for r in records) if records else 0,
    }
