# -*- coding: utf-8 -*-
"""配置层:默认值完整性、深合并、自动备份、平台回落、提示词迁移。"""
import json

from app import config as cfgmod


def test_default_config_shape():
    """默认配置必须覆盖各模块读取的键(少一个键就会在运行时 KeyError)。"""
    cfg = cfgmod.DEFAULT_CONFIG
    for key in ("active_provider", "providers", "prompts", "request_template", "mode",
                "ui", "window", "capture", "timeout", "retry", "ocr", "translate",
                "local", "knowledge", "hotkeys", "behavior", "storage", "app"):
        assert key in cfg, f"默认配置缺少分组:{key}"

    # 各分组内的关键键
    assert {"ocr", "answer", "translate"} <= set(cfg["prompts"])
    for k in ("width", "height", "miniWidth", "miniHeight", "translateWidth", "translateHeight",
              "defaultMiniHeight", "holeWidth", "holeHeight", "chromeHeight"):
        assert k in cfg["window"], f"window 缺少:{k}"
    for k in ("capture", "snip", "exit", "modeOverlay", "modeMini", "modeSnip",
              "modeTranslate", "topmost"):
        assert k in cfg["hotkeys"], f"hotkeys 缺少:{k}"
    assert cfg["mode"] in ("overlay", "mini", "translate", "snip")


def test_window_size_defaults_are_consistent():
    """窗口默认值必须落在各处硬编码的下限之内,否则切模式时会被后端强行改尺寸。"""
    from app.manager import MINI_MIN_WIDTH

    w = cfgmod.DEFAULT_CONFIG["window"]
    # 迷你条:宽度下限保证右上角那组控件不被挤出窗口
    assert w["miniWidth"] >= MINI_MIN_WIDTH
    assert w["defaultMiniWidth"] >= MINI_MIN_WIDTH
    # 高度由前端实测内容后回写(miniHeight),两处兜底值都要在 set_mini_height 的夹取范围内
    for key in ("miniHeight", "defaultMiniHeight"):
        assert 56 <= w[key] <= 240, f"{key} 超出 set_mini_height 的夹取范围"

    assert w["translateWidth"] == w["defaultTranslateWidth"]
    assert w["translateHeight"] == w["defaultTranslateHeight"]
    assert w["width"] == w["defaultWidth"]
    assert w["height"] == w["defaultHeight"]


def test_provider_presets_have_models():
    """每个预置平台都要有 Base URL 与候选模型,否则界面下拉是空的。"""
    for p in cfgmod.PROVIDER_PRESETS:
        assert p["id"] and p["name"]
        assert isinstance(p.get("models"), list) and p["models"], f"{p['id']} 没有候选模型"


def test_models_for_unknown_provider():
    assert cfgmod.models_for("not-exist") == []
    assert cfgmod.models_for("bailian")


def test_deep_merge_keeps_untouched_groups():
    out = cfgmod._deep_merge({"a": {"b": 1, "c": 2}}, {"a": {"b": 9}})
    assert out == {"a": {"b": 9, "c": 2}}


def test_save_config_writes_backup_once(sandbox):
    """写盘前留存上一份:第一次写留默认内容,内容相同则不覆盖备份。"""
    cfg = cfgmod.DEFAULT_CONFIG
    cfgmod.save_config(cfg)
    assert sandbox.cfg_path.exists()
    assert not cfgmod.BACKUP_PATH.exists(), "首次写入不该产生备份"

    cfg2 = json.loads(sandbox.cfg_path.read_text(encoding="utf-8"))
    cfg2["active_provider"] = "openai"
    cfgmod.save_config(cfg2)
    assert cfgmod.BACKUP_PATH.exists(), "第二次写入必须产生备份"
    bak = json.loads(cfgmod.BACKUP_PATH.read_text(encoding="utf-8"))
    assert bak["active_provider"] == cfgmod.DEFAULT_CONFIG["active_provider"]

    # 内容相同:备份不再被覆盖
    before = cfgmod.BACKUP_PATH.read_text(encoding="utf-8")
    cfgmod.save_config(cfg2)
    assert cfgmod.BACKUP_PATH.read_text(encoding="utf-8") == before


def test_load_config_fills_missing_keys(sandbox):
    """残缺配置必须被深合并补全,不能把缺键留给运行时。"""
    sandbox.cfg_path.write_text(json.dumps({"window": {"width": 700}}, ensure_ascii=False),
                                encoding="utf-8")
    cfg = cfgmod.load_config()
    assert cfg["window"]["width"] == 700          # 用户值保留
    assert cfg["window"]["height"] == cfgmod.DEFAULT_CONFIG["window"]["height"]
    assert cfg["prompts"]["ocr"]
    assert cfg["app"]["version"] == cfgmod.APP_VERSION, "app.version 必须同步为唯一版本来源"


def test_load_config_corrupt_file_falls_back(sandbox):
    sandbox.cfg_path.write_text("{ 这不是 json", encoding="utf-8")
    cfg = cfgmod.load_config()
    assert cfg["providers"], "配置损坏时应回落到默认值而不是抛错"


def test_translate_prompt_migration(sandbox):
    """旧版翻译提示词(TAB 逐行)必须自动升级为 JSON 数组版,并落盘。"""
    data = {"prompts": {"translate": "旧版:请用 TAB 分隔逐行输出译文"}}
    sandbox.cfg_path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    cfg = cfgmod.load_config()
    assert cfg["prompts"]["translate"] == cfgmod.DEFAULT_TRANSLATE_PROMPT
    saved = json.loads(sandbox.cfg_path.read_text(encoding="utf-8"))
    assert "JSON 数组" in saved["prompts"]["translate"], "迁移结果必须写回磁盘"


def test_ensure_active_provider_falls_back():
    """选中的平台被清空 Key 时,自动回落到已配置的平台。"""
    cfg = {
        "active_provider": "a",
        "providers": [{"id": "a", "api_key": ""}, {"id": "b", "api_key": "sk-b"}],
    }
    assert cfgmod.ensure_active_provider(cfg) == "b"
    assert cfg["active_provider"] == "b"

    # 没有可用平台时置空,不抛错
    cfg2 = {"active_provider": "a", "providers": [{"id": "a", "api_key": ""}]}
    assert cfgmod.ensure_active_provider(cfg2) == ""
    assert cfg2["active_provider"] == ""


def test_active_provider_falls_back_to_first():
    cfg = {"active_provider": "zzz", "providers": [{"id": "a"}, {"id": "b"}]}
    assert cfgmod.active_provider(cfg)["id"] == "a"


def test_provider_ready_ignores_whitespace_key():
    assert cfgmod.provider_ready({"api_key": "   "}) is False
    assert cfgmod.provider_ready({"api_key": "sk-1"}) is True
    assert cfgmod.provider_ready({}) is False


def test_thinking_only_for_supported_platforms():
    """开启思考只对支持它的平台注入,其它平台必须从请求体里移除(否则 400)。"""
    assert "bailian" in cfgmod.THINKING_PROVIDER_IDS
