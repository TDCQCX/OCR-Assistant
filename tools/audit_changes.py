# -*- coding: utf-8 -*-
"""改动审计:每次改完代码跑一遍,按历史踩坑清单逐条核对。

用法:
    .\\.venv\\Scripts\\python.exe tools\\audit_changes.py              # 审计工作区改动(默认 vs HEAD)
    .\\.venv\\Scripts\\python.exe tools\\audit_changes.py --base HEAD~1  # 审计最近一次提交
    .\\.venv\\Scripts\\python.exe tools\\audit_changes.py --all          # 忽略改动范围,全量体检
    .\\.venv\\Scripts\\python.exe tools\\audit_changes.py --json         # 机器可读输出

为什么要这个工具:本项目历史上"改 A 坏 B"的回归集中在少数几处 —— DPI 换算、洞口穿透、
迷你条高度还原、退出判定、构建产物未同步、静默吞异常。它们都能用静态规则提前发现,
不必等到手工点一遍界面。

结论分级:
    BLOCK  必须处理,否则大概率出缺陷(退出码 1)
    WARN   需要人工确认的有风险改动
    INFO   提示性信息,不影响退出码
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "frontend" / "src"
WEBUI = ROOT / "app" / "webui"

BLOCK, WARN, INFO = "BLOCK", "WARN", "INFO"
_RANK = {BLOCK: 1, WARN: 2, INFO: 3}


@dataclass
class Finding:
    rule: str
    level: str
    title: str
    detail: str = ""
    location: str = ""
    fix: str = ""

    def as_dict(self) -> dict:
        return {"rule": self.rule, "level": self.level, "title": self.title,
                "detail": self.detail, "location": self.location, "fix": self.fix}


@dataclass
class Report:
    findings: list = field(default_factory=list)
    checked: list = field(default_factory=list)

    def add(self, *a, **kw):
        self.findings.append(Finding(*a, **kw))

    def ok(self, rule: str):
        self.checked.append(rule)

    @property
    def worst(self) -> str:
        if not self.findings:
            return "OK"
        return min(self.findings, key=lambda f: _RANK[f.level]).level

    def by_level(self, level: str):
        return [f for f in self.findings if f.level == level]


# --------------------------- git 辅助 ---------------------------
def _git(*args: str) -> str:
    try:
        out = subprocess.run(["git", *args], cwd=str(ROOT), capture_output=True,
                             text=True, encoding="utf-8", errors="replace")
        return out.stdout or ""
    except Exception:
        return ""


def changed_files(base: str) -> set:
    """工作区相对 base 的改动文件(含未跟踪)。"""
    files = set()
    for line in _git("diff", "--name-only", base).splitlines():
        if line.strip():
            files.add(line.strip().replace("\\", "/"))
    for line in _git("status", "--porcelain").splitlines():
        if len(line) > 3:
            files.add(line[3:].strip().strip('"').replace("\\", "/"))
    return files


def diff_text(base: str, paths: list) -> str:
    if not paths:
        return ""
    return _git("diff", base, "--", *paths)


def added_lines(base: str, path: str) -> list:
    """返回该文件新增/修改的行(带行号),用于只审"这次改了什么"。"""
    out = []
    text = _git("diff", "-U0", base, "--", path)
    line_no = 0
    for line in text.splitlines():
        m = re.match(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,\d+)? @@", line)
        if m:
            line_no = int(m.group(1))
            continue
        if line.startswith("+") and not line.startswith("+++"):
            out.append((line_no, line[1:]))
            line_no += 1
        elif not line.startswith("-"):
            line_no += 1
    return out


def read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return ""


# --------------------------- 规则:构建产物同步 ---------------------------
def rule_build_in_sync(rep: Report, files: set):
    webui_refs_changed = any(f.startswith("app/webui/") for f in files)
    src_changed = any(f.startswith("frontend/src/") for f in files)
    if src_changed and not webui_refs_changed:
        rep.add("build.sync", BLOCK, "改了前端源码但没有重新构建",
                detail="frontend/src 有改动,app/webui 构建产物没有任何变化;"
                       "程序加载的是 app/webui,界面不会生效。",
                fix="cd frontend && npm run build")

    if not WEBUI.exists():
        rep.add("build.exists", BLOCK, "找不到 app/webui 构建产物")
        return

    assets = [p for p in (WEBUI / "assets").glob("*") if p.suffix in (".js", ".css")]
    if not assets:
        rep.add("build.assets", BLOCK, "app/webui/assets 是空的")
        return

    html = "".join(read(WEBUI / n) for n in ("index.html", "selector.html"))
    stale = sorted(p.name for p in assets if p.name not in html)
    if stale:
        rep.add("build.stale", BLOCK, "构建产物里有未被引用的旧文件",
                detail=f"这些文件不在 html 引用里:{stale}",
                fix="重新 npm run build(emptyOutDir 会清干净),或手工删除残留")

    newest_build = max(p.stat().st_mtime for p in assets)
    newest_src = max((p.stat().st_mtime for p in SRC.rglob("*") if p.is_file()), default=0)
    if newest_build < newest_src:
        rep.add("build.mtime", BLOCK, "构建产物早于前端源码",
                fix="cd frontend && npm run build")
    rep.ok("build.sync")


# --------------------------- 规则:版本号同步 ---------------------------
def rule_version_sync(rep: Report, files: set, base: str):
    cfg_path = ROOT / "app" / "config.py"
    if "app/config.py" not in files:
        rep.ok("version.sync")
        return
    m = re.search(r'APP_VERSION\s*=\s*"([0-9.]+)"', read(cfg_path))
    if not m:
        rep.add("version.source", BLOCK, "找不到 APP_VERSION(版本单一来源被破坏)")
        return
    ver = m.group(1)
    # 版本号是否在这次改动里变了
    old = re.search(r'APP_VERSION\s*=\s*"([0-9.]+)"', _git("show", f"{base}:app/config.py"))
    bumped = old and old.group(1) != ver

    problems = []
    pkg = read(ROOT / "frontend" / "package.json")
    if f'"version": "{ver}"' not in pkg:
        problems.append("frontend/package.json")
    vi = read(ROOT / "version_info.txt")
    nums = tuple(int(x) for x in ver.split("."))
    if f"filevers=({nums[0]}, {nums[1]}, {nums[2]}" not in vi.replace(" ", " "):
        if re.search(r"filevers=\(\s*%d,\s*%d,\s*%d" % nums, vi) is None:
            problems.append("version_info.txt filevers")
    specs = list(ROOT.glob("OCR助手-v*.spec"))
    if not any(ver in s.name for s in specs):
        problems.append(f"spec 文件名(当前:{[s.name for s in specs]})")
    for doc in ("README.md", "README.en.md"):
        t = read(ROOT / doc)
        if t and f"badge/Version-{ver}-" not in t:
            problems.append(f"{doc} 徽章")
    if f"## [{ver}]" not in read(ROOT / "CHANGELOG.md"):
        problems.append("CHANGELOG 当前版本条目")
    if f"OCR助手-v{ver}.exe" not in read(ROOT / "TUTORIAL.md"):
        problems.append("TUTORIAL.md 里的 exe 名")

    if problems:
        rep.add("version.sync", BLOCK if bumped else WARN,
                f"版本号 {ver} 未在所有位置同步",
                detail="待同步:" + "、".join(problems),
                fix="按 HANDOFF 第 5.1 节的三处 + 文档 + 教程一起改")
    else:
        rep.ok("version.sync")
    if bumped:
        rep.add("version.bumped", INFO, f"检测到版本号变更:{old.group(1)} → {ver}",
                detail="发版流程:同步 spec/version_info/package.json/README/CHANGELOG/"
                       "RELEASE_NOTES/TUTORIAL,然后重新打包 exe。")


# --------------------------- 规则:DPI 与洞口 ---------------------------
_WINDOW_OPS = re.compile(
    r"\b(win|overlay|mini|translate|snip|settings|w)\.(move|resize|show|hide|destroy|minimize|restore)\s*\(")
_WIN_COORD = re.compile(r"\b(win|overlay|mini|translate|snip)\.(x|y|width|height)\b")
_GRAB = re.compile(r"\b(grab_region|virtual_screen|apply_hole_region|set_hole_region)\b")


def rule_dpi_and_hole(rep: Report, files: set, base: str):
    touched = [f for f in files if f.startswith("app/") and f.endswith(".py")]
    hits = []
    for path in touched:
        for line_no, text in added_lines(base, path):
            if _WIN_COORD.search(text) and _GRAB.search(text) is False and "*" in text:
                hits.append((path, line_no, text.strip()))
    if hits:
        rep.add("ui.dpi", WARN, "新增了窗口坐标算术,确认已走 winutil 换算",
                detail=";".join(f"{p}:{n} {t}" for p, n, t in hits[:6]),
                fix="坐标/尺寸换算一律用 app/winutil.py 的 physical_origin()/screen_scale(),"
                    "不要自己乘 devicePixelRatio")

    # 洞口穿透:每个 pause_hole(True) 都要有配对的 False
    mgr = read(ROOT / "app" / "manager.py")
    trues = len(re.findall(r"pause_hole\(\s*True\s*\)", mgr))
    falses = len(re.findall(r"pause_hole\(\s*False\s*\)", mgr)) + \
        len(re.findall(r"pause_hole\(\s*on\s*=\s*False\s*\)", mgr))
    if trues != falses:
        rep.add("hole.pause_pair", WARN, "pause_hole(True/False) 配对数量不一致",
                detail=f"manager.py 里 True={trues} 次,False={falses} 次",
                fix="弹窗/教程期间暂停穿透后必须能恢复,否则洞口永久失效或弹窗被裁掉")
    else:
        rep.ok("hole.pause_pair")

    if "app/manager.py" in files:
        for line_no, text in added_lines(base, "app/manager.py"):
            if '"type": "status"' in text and re.search(
                    r"已切换|已置顶|已最小化|已取消|已恢复|已设为", text):
                rep.add("event.semantics", BLOCK,
                        "把界面操作文案写进了 status 事件",
                        location=f"app/manager.py:{line_no}",
                        detail=text.strip(),
                        fix="界面反馈要用 notice(2.2s 轻提示);status 专用于 AI 运行状态,"
                            "否则文案会一直挂在状态灯旁")
            if _WINDOW_OPS.search(text) and "run_in_main" not in text and "def " not in text:
                rep.add("ui.thread", WARN, "新增窗口操作可能没排队到 Qt 主线程",
                        location=f"app/manager.py:{line_no}", detail=text.strip(),
                        fix="所有窗口/WebView 操作必须经 run_in_main()")


# --------------------------- 规则:静默吞异常 ---------------------------
# 已人工确认过、代码里有注释说明"刻意静默"的位置,按「文件::所在函数」记录
# (用函数名而不是行号,这样改动上下移动行不会误报)。清单只允许缩小:
# 位置被挪走或函数改名时审计会重新提示,提醒你确认它仍是有意为之。
KNOWN_SILENT = {
    ("app/manager.py", "resize_mini_width"),      # resize 失败不回滚配置,下轮上报会纠正
    ("app/manager.py", "_register_hotkeys"),      # 热键被占用/注销失败:跳过它,其余照常注册
    ("app/manager.py", "toggle_topmost"),         # 设置 on_top 失败:外观问题,不打断用户操作
}


def _enclosing_def(path: Path, line_no: int) -> str:
    """找出该行所属的函数名(用于跨行漂移地识别白名单位置)。"""
    name = ""
    try:
        for i, line in enumerate(read(path).splitlines(), start=1):
            if i > line_no:
                break
            m = re.match(r"\s*def\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*\(", line)
            if m:
                name = m.group(1)
    except Exception:
        pass
    return name


def rule_silent_except(rep: Report, files: set, base: str):
    """新增的 except Exception: pass 要人工确认(它们会吞掉真实缺陷)。"""
    allow = {
        "app/winutil.py",     # 平台 API 失败必须降级:宁可偏移也不能崩
        "app/mainthread.py",  # 主线程回调异常无法回传(已登记为待办)
        "app/capturer.py",
        "app/clipboard.py",
        "app/history.py",
        "app/local_models.py",
        "app/local_mt.py",
        "app/local_hf.py",
    }
    new_silent = []
    for path in sorted(f for f in files if f.endswith(".py")):
        if path in allow:
            continue
        lines = added_lines(base, path)
        for i, (line_no, text) in enumerate(lines):
            if re.match(r"\s*except\s+(Exception|BaseException|OSError)\b", text):
                nxt = lines[i + 1][1] if i + 1 < len(lines) else ""
                if re.match(r"\s*(pass|return|continue)\s*$", nxt or "") or "pass" in text:
                    if (path, _enclosing_def(ROOT / path, line_no)) in KNOWN_SILENT:
                        continue          # 已人工确认过,有注释说明
                    new_silent.append(f"{path}:{line_no}")
    if new_silent:
        rep.add("py.silent_except", WARN, "新增了未经确认的静默吞异常",
                detail="、".join(new_silent[:10]),
                fix="确认失败可接受后,在代码里写清理由,并把「文件::函数名」加入 "
                    "tools/audit_changes.py 的 KNOWN_SILENT(或改成 push 一条 notice/status 告知用户)")
    else:
        rep.ok("py.silent_except")


# --------------------------- 规则:前端契约 ---------------------------
def rule_frontend_contract(rep: Report, files: set):
    text_all = "\n".join(read(p) for p in list(SRC.rglob("*.js")) + list(SRC.rglob("*.jsx")))

    sys.path.insert(0, str(ROOT))
    try:
        from app.api import Api
        methods = set()
        for klass in Api.__mro__:
            for name, value in vars(klass).items():
                if not name.startswith("_") and callable(value):
                    methods.add(name)
    except Exception as exc:  # noqa: BLE001
        rep.add("bridge.import", WARN, f"无法加载 app.api 做桥接核对:{exc}")
        return

    called = set(re.findall(r"call\(\s*'([a-z_][a-z0-9_]*)'", text_all))
    missing = sorted(c for c in called if c not in methods)
    if missing:
        rep.add("bridge.methods", BLOCK, "前端调用了后端不存在的方法",
                detail="、".join(missing),
                fix="改名/删接口时同步改前端;否则是一次静默失败(点下去没反应)")
    else:
        rep.ok("bridge.methods")

    # 事件:后端 push 的类型必须有人处理
    pushed = set()
    for path in (ROOT / "app").glob("*.py"):
        pushed |= set(re.findall(r'"type"\s*:\s*"([a-zA-Z]+)"', read(path)))
    pushed.discard("text")     # 请求模板里的字段,不是事件
    handled = set()
    for path in list(SRC.rglob("*.js")) + list(SRC.rglob("*.jsx")):
        t = read(path)
        handled |= set(re.findall(r"type\s*[!=]==?\s*'([a-zA-Z]+)'", t))
        handled |= set(re.findall(r'type\s*[!=]==?\s*"([a-zA-Z]+)"', t))
    unhandled = sorted(pushed - handled)
    if unhandled:
        rep.add("bridge.events", BLOCK, "后端推送了前端没处理的事件",
                detail="、".join(unhandled),
                fix="在 window.__ocrEvent 或组件的 ocr-event 监听里处理")
    else:
        rep.ok("bridge.events")


# --------------------------- 规则:CSS / 前端样式 ---------------------------
_CUSTOM_PREFIX = ("anim-", "view-", "result-", "mini-", "doc-", "guide-", "hole-", "tier-",
                  "qbox", "window-", "app-", "status-", "modal", "model-", "history-",
                  "translate-", "stat-", "settings-", "engine-", "nav-", "scroll-",
                  "hotkey", "toolbar-", "divider-", "drag-", "card", "inset", "panel")


# 这些类名不是"样式",是 JS 用的语义钩子,故意没有 CSS 规则(别误报):
#   mini-body   —— MiniBar 用它 querySelector + scrollHeight 量内容高度,再回传 set_mini_height
#   view-mini   —— 仅作模式语义标记(圆角由 .window-shell 统一负责)
CSS_HOOK_ALLOW = {"mini-body", "view-mini"}


def rule_css_classes(rep: Report):
    css = read(SRC / "index.css")
    tw = read(ROOT / "frontend" / "tailwind.config.js")
    defined = set(re.findall(r"\.([a-zA-Z][a-zA-Z0-9_-]*)", css))
    used = {}
    for path in list(SRC.glob("*.jsx")) + list(SRC.glob("*.js")):
        for m in re.finditer(r'className=(?:"([^"]*)"|\{`([^`]*)`\})', read(path)):
            raw = m.group(1) or m.group(2) or ""
            for cls in re.split(r"[\s${}()?:,'\"]+", raw):
                if cls and cls.startswith(_CUSTOM_PREFIX):
                    used.setdefault(cls, set()).add(path.name)
    missing = {c: sorted(v) for c, v in used.items()
               if c not in defined and c not in tw
               and c not in CSS_HOOK_ALLOW and not c.startswith("inset")}
    if missing:
        rep.add("css.classes", WARN, "用到了没有定义的 CSS 类(动画/样式不会生效)",
                detail="、".join(f"{c}({','.join(f)})" for c, f in sorted(missing.items())),
                fix="补回 index.css 的定义,或从 JSX 里删掉类名 —— 别让界面静默少一段效果")
    else:
        rep.ok("css.classes")


# --------------------------- 规则:仓库卫生 ---------------------------
_TEMP_PATTERNS = [
    (re.compile(r"^_[a-zA-Z0-9_-]+\.py$"), "临时脚本"),
    (re.compile(r"^_[a-zA-Z0-9_-]+\.(log|err|json|txt)$"), "临时输出"),
    (re.compile(r"^_bundle\.(js|css)$"), "临时构建产物"),
    (re.compile(r"^(dump\.rdb|test_capture\.png|test_window_grab\.png)$"), "临时文件"),
]


def rule_repo_hygiene(rep: Report):
    tracked = set(_git("ls-files").split())
    junk = []
    for path in ROOT.iterdir():
        if path.is_dir():
            continue
        for pat, kind in _TEMP_PATTERNS:
            if pat.match(path.name):
                junk.append(f"{path.name}({kind}{',已跟踪' if path.name in tracked else ''})")
    for path in (ROOT / "frontend").iterdir():
        if path.is_file() and path.name.startswith("_"):
            junk.append(f"frontend/{path.name}(临时构建产物)")
    if junk:
        rep.add("repo.hygiene", WARN, "根目录/前端目录有临时文件残留",
                detail="、".join(junk),
                fix="确认不再需要后删除;提交时不要 git add -A")
    else:
        rep.ok("repo.hygiene")


def rule_status_baseline(rep: Report):
    """未提交的改动集中在核心文件时给出提醒(避免下次接手的人误判基线)。"""
    status = _git("status", "--porcelain")
    if not status.strip():
        rep.ok("repo.clean")
        return
    n = len([l for l in status.splitlines() if l.strip()])
    rep.add("repo.dirty", INFO, f"工作区有 {n} 项未提交改动",
            detail="审计基于工作区当前内容;提交前请只 add 自己改过的文件(不要 git add -A)")


# --------------------------- 主流程 ---------------------------
ALL_RULES = (
    # 构建与发版
    "build.sync", "build.exists", "build.assets", "build.stale", "build.mtime",
    "version.sync", "version.source", "version.bumped",
    # 平台层与事件语义
    "ui.dpi", "ui.thread", "hole.pause_pair", "event.semantics",
    # 代码质量与契约
    "py.silent_except", "bridge.methods", "bridge.events", "bridge.import",
    "css.classes",
    # 仓库卫生
    "repo.hygiene", "repo.clean", "repo.dirty",
)


def run_audit(base: str = "HEAD", everything: bool = False) -> Report:
    rep = Report()
    files = changed_files(base)
    if everything:
        files = {str(p.relative_to(ROOT)).replace("\\", "/")
                 for p in ROOT.rglob("*") if p.is_file()
                 and ".git" not in p.parts and ".venv" not in p.parts
                 and "node_modules" not in p.parts and "models" not in p.parts}

    rule_build_in_sync(rep, files)
    rule_version_sync(rep, files, base)
    rule_dpi_and_hole(rep, files, base)
    rule_silent_except(rep, files, base)
    rule_frontend_contract(rep, files)
    rule_css_classes(rep)
    rule_repo_hygiene(rep)
    rule_status_baseline(rep)
    return rep


def print_report(rep: Report, files: set):
    icons = {BLOCK: "✗", WARN: "!", INFO: "·"}
    print("=" * 78)
    print("改动审计报告")
    print("=" * 78)
    print(f"审计范围:{len(files)} 个文件")
    print()
    if not rep.findings:
        print("没有发现问题。")
        return
    for level in (BLOCK, WARN, INFO):
        items = rep.by_level(level)
        if not items:
            continue
        print(f"--- {level} ({len(items)}) ---")
        for f in items:
            print(f"  {icons[level]} [{f.rule}] {f.title}")
            if f.location:
                print(f"      位置:{f.location}")
            if f.detail:
                for line in f.detail.split(";"):
                    if line.strip():
                        print(f"      细节:{line.strip()}")
            if f.fix:
                print(f"      处理:{f.fix}")
        print()
    passed = [r for r in rep.checked if r not in {x.rule for x in rep.findings}]
    if passed:
        print("已通过:" + "、".join(passed))


def main() -> int:
    ap = argparse.ArgumentParser(description="改动审计(对照历史踩坑清单)")
    ap.add_argument("--base", default="HEAD", help="对照基准(默认 HEAD,即工作区改动)")
    ap.add_argument("--all", action="store_true", help="忽略改动范围,全量体检")
    ap.add_argument("--json", action="store_true", help="输出 JSON")
    args = ap.parse_args()

    files = changed_files(args.base)
    rep = run_audit(args.base, args.all)
    if args.json:
        print(json.dumps({"worst": rep.worst, "files": sorted(files),
                          "findings": [f.as_dict() for f in rep.findings],
                          "passed": rep.checked}, ensure_ascii=False, indent=2))
    else:
        print_report(rep, files if not args.all else files)
    return 1 if rep.by_level(BLOCK) else 0


if __name__ == "__main__":
    sys.exit(main())
