# -*- coding: utf-8 -*-
"""识别历史:保存最近若干条识别结果,供「识别历史」页展示。"""
import json
import time
from pathlib import Path

from app.config import ROOT

PATH = ROOT / "history.json"
MAX_ITEMS = 100


def load() -> list:
    try:
        data = json.loads(PATH.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except Exception:
        return []


def save(items: list) -> None:
    try:
        PATH.write_text(json.dumps(items[-MAX_ITEMS:], ensure_ascii=False, indent=2),
                        encoding="utf-8")
    except Exception:
        pass


def append(entry: dict) -> None:
    entry = dict(entry)
    entry["time"] = time.strftime("%Y-%m-%d %H:%M:%S")
    items = load()
    items.append(entry)
    save(items)


def clear() -> None:
    save([])
