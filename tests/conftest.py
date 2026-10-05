# -*- coding: utf-8 -*-
"""测试共用夹具。

两条原则:
1. **绝不碰真实数据**:config.json / history.json / request_log.json / questions/ 全部
   重定向到 pytest 的临时目录,跑测试不会污染用户配置与历史。
2. **不依赖 GUI**:默认用例只测纯逻辑与契约;需要真实窗口的验证放在
   ``tools/gui_smoke.py``,由 ``tools/check.py --gui`` 触发。
"""
import json
import sys
import types
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# 让"慢用例"(端侧推理/真实 OCR 模型)默认不跑
SLOW = bool(__import__("os").environ.get("DSCODE_SLOW"))


def pytest_configure(config):
    config.addinivalue_line("markers", "slow: 需要端侧模型或耗时较长的用例(DSCODE_SLOW=1 时才跑)")
    config.addinivalue_line("markers", "gui: 需要真实窗口,由 tools/gui_smoke.py 覆盖")


def pytest_collection_modifyitems(config, items):
    if SLOW:
        return
    skip = pytest.mark.skip(reason="慢用例:设置 DSCODE_SLOW=1 后运行")
    for item in items:
        if "slow" in item.keywords:
            item.add_marker(skip)


@pytest.fixture
def sandbox(tmp_path, monkeypatch):
    """把配置/历史/请求日志/缓存目录重定向到临时目录。

    这些模块的路径是导入期常量,这里直接改模块属性 —— 与运行时行为一致,
    且不会写坏仓库里的真实文件。
    """
    from app import config as cfgmod
    from app import history, request_log

    cfg_path = tmp_path / "config.json"
    monkeypatch.setattr(cfgmod, "CONFIG_PATH", cfg_path, raising=False)
    monkeypatch.setattr(cfgmod, "BACKUP_PATH", tmp_path / "config.json.bak", raising=False)
    monkeypatch.setattr(cfgmod, "ROOT", tmp_path, raising=False)
    monkeypatch.setattr(history, "PATH", tmp_path / "history.json", raising=False)
    monkeypatch.setattr(request_log, "LOG_PATH", tmp_path / "request_log.json", raising=False)

    box = types.SimpleNamespace(root=tmp_path, cfg_path=cfg_path)
    yield box


@pytest.fixture
def fake_cfg():
    """一份最小可用配置(不读真实 config.json,内容可预期)。"""
    from app import config as cfgmod

    cfg = json.loads(json.dumps(cfgmod.DEFAULT_CONFIG, ensure_ascii=False))
    # 默认平台填一份假的,避免"未配置 Key"分支把流程挡掉
    cfg["providers"][0]["api_key"] = "sk-test"
    cfg["providers"][0]["model"] = "test-model"
    cfg["active_provider"] = cfg["providers"][0]["id"]
    cfg["ui"]["guideDone"] = {m: True for m in ("overlay", "mini", "translate", "settings", "snip")}
    cfg["storage"]["questions_dir"] = ""
    cfg["storage"]["add_to_knowledge"] = False
    return cfg
