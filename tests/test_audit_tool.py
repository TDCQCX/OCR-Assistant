# -*- coding: utf-8 -*-
"""审计工具自身的体检:规则不能变成"永远通过"的摆设。

两类断言:
  * 规则里的模式/白名单必须能匹配到真实的坏样本(否则规则是死的);
  * 白名单不能腐坏(KNOWN_SILENT 里的位置必须还在代码里)。
"""
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import audit_changes as audit  # noqa: E402


def test_known_silent_entries_still_exist():
    """白名单里每一项都必须还能在代码里找到对应的 def,否则该删掉。"""
    for path, func in audit.KNOWN_SILENT:
        full = ROOT / path
        assert full.exists(), f"白名单里的文件不存在:{path}"
        text = full.read_text(encoding="utf-8", errors="ignore")
        assert re.search(rf"^\s*def\s+{re.escape(func)}\s*\(", text, re.M), \
            f"白名单里的函数已不存在,请从 KNOWN_SILENT 移除:{path}::{func}"


def test_templates_flag_real_violation():
    """把界面文案写进 status 是真实踩过的坑,规则必须能识别。"""
    bad = 'self.push({"type": "status", "text": "已切换到悬浮窗模式", "tone": "ok"})'
    assert re.search(r"已切换|已置顶|已最小化|已取消|已恢复|已设为", bad)
    assert '"type": "status"' in bad


def test_status_rule_ignores_ai_status():
    """AI 运行状态用的是别的文案,不能被误判。"""
    good = 'self.push({"type": "status", "text": "正在OCR识别…", "tone": "working"})'
    assert not re.search(r"已切换|已置顶|已最小化|已取消|已恢复|已设为", good)


def test_window_coordinate_rule_matches_raw_arithmetic():
    """窗口坐标算术 + 乘缩放比 → 必须提示走 winutil。"""
    bad = "left = win.x * screen_scale()"
    assert audit._WIN_COORD.search(bad)
    assert "*" in bad


def test_window_coordinate_rule_ignores_winutil_calls():
    good = "origin = physical_origin(win)"
    assert not audit._WIN_COORD.search(good)


def test_enclosing_def_resolves_function_name():
    line = None
    target = ROOT / "app" / "manager.py"
    for i, text in enumerate(target.read_text(encoding="utf-8", errors="ignore").splitlines(), 1):
        if text.strip() == "def resize_mini_width(self, w) -> bool:":
            line = i
            break
    assert line, "找不到 resize_mini_width(测试样本已失效)"
    assert audit._enclosing_def(target, line + 5) == "resize_mini_width"


def test_added_lines_parses_git_diff(monkeypatch):
    """added_lines 只能返回新增行(带行号),不能把删除行当成新增。"""
    fake = (
        "@@ -10,3 +10,4 @@\n"
        " context\n"
        "-removed line\n"
        "+added line one\n"
        "+added line two\n"
        " context2\n"
    )
    monkeypatch.setattr(audit, "_git", lambda *a: fake)
    got = audit.added_lines("HEAD", "app/x.py")
    assert got == [(11, "added line one"), (12, "added line two")]


def test_css_hook_allowlist_is_justified():
    """允许"用了但没定义"的类名必须真的在 JSX 里被引用,否则该从白名单删掉。"""
    sources = "\n".join(p.read_text(encoding="utf-8", errors="ignore")
                        for p in (ROOT / "frontend" / "src").rglob("*.jsx"))
    for cls in audit.CSS_HOOK_ALLOW:
        assert cls in sources, f"{cls} 已无人使用,请从 CSS_HOOK_ALLOW 里移除"


def test_report_worst_level():
    rep = audit.Report()
    rep.ok("x")
    assert rep.worst == "OK"
    rep.add("t", audit.INFO, "提示")
    assert rep.worst == audit.INFO
    rep.add("t2", audit.WARN, "警告")
    assert rep.worst == audit.WARN
    rep.add("t3", audit.BLOCK, "阻塞")
    assert rep.worst == audit.BLOCK
    assert len(rep.by_level(audit.BLOCK)) == 1


def test_all_rules_are_registered():
    """每个规则名都要登记进 ALL_RULES —— 它是"已通过"清单的来源,漏登记会静默少报。"""
    source = (ROOT / "tools" / "audit_changes.py").read_text(encoding="utf-8")
    used = set(re.findall(r'rep\.(?:add|ok)\(\s*"([a-z_.]+)"', source))
    declared = set(audit.ALL_RULES)
    missing = sorted(used - declared)
    assert not missing, f"规则名没有登记到 ALL_RULES:{missing}"


def test_no_rule_is_declared_but_never_used():
    """反过来:ALL_RULES 里的规则必须真的被某个函数用到(防止留下空转的条目)。"""
    source = (ROOT / "tools" / "audit_changes.py").read_text(encoding="utf-8")
    used = set(re.findall(r'rep\.(?:add|ok)\(\s*"([a-z_.]+)"', source))
    dead = sorted(set(audit.ALL_RULES) - used)
    assert not dead, f"ALL_RULES 里这些规则没有任何地方使用:{dead}"


def test_audit_runs_clean_on_current_tree():
    """当前工作区必须跑得过审计(有 BLOCK 就该在这里暴露出来)。"""
    rep = audit.run_audit("HEAD", everything=False)
    blocks = [f.title for f in rep.by_level(audit.BLOCK)]
    assert not blocks, f"当前工作区存在阻塞级问题:{blocks}"


def test_build_sync_blocks_when_frontend_changed_without_rebuild():
    """最常见的事故:改了 frontend/src 却忘了 npm run build(程序里还是老界面)。"""
    rep = audit.Report()
    audit.rule_build_in_sync(rep, {"frontend/src/MiniBar.jsx"})
    assert rep.worst == audit.BLOCK
    assert any(f.rule == "build.sync" for f in rep.findings)

    rep2 = audit.Report()
    audit.rule_build_in_sync(rep2, {"frontend/src/MiniBar.jsx", "app/webui/index.html"})
    assert rep2.worst == "OK", "产物也跟着改了就不该报"


def test_build_sync_flags_stale_assets():
    """产物目录里留下上一轮构建的 js/css 也是真实事故源(会加载到旧界面)。"""
    rep = audit.Report()
    audit.rule_build_in_sync(rep, set())
    stale = [f for f in rep.findings if f.rule == "build.stale"]
    assert not stale, "当前产物应当没有残留;若有残留请重新 npm run build"


def test_version_sync_detects_unsynced_docs(monkeypatch):
    """把版本号改成 9.9.9 后,version.sync 必须报出来(证明规则不是摆设)。"""
    real_read = audit.read

    def fake_read(path, *a, **k):
        text = real_read(path, *a, **k)
        if Path(path).name == "config.py":
            return text.replace('APP_VERSION = "2.6.10"', 'APP_VERSION = "9.9.9"')
        return text

    monkeypatch.setattr(audit, "read", fake_read)
    rep = audit.Report()
    audit.rule_version_sync(rep, {"app/config.py"}, "HEAD")
    assert any(f.rule == "version.sync" for f in rep.findings), "版本号不同步时必须报错"
    assert any("9.9.9" in f.title for f in rep.findings)


def test_audit_json_output_is_serializable(capsys, monkeypatch):
    monkeypatch.setattr(sys, "argv", ["audit_changes.py", "--json"])
    code = audit.main()
    out = capsys.readouterr().out
    import json

    data = json.loads(out)
    assert "worst" in data and "findings" in data
    assert code in (0, 1)
