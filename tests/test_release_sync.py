# -*- coding: utf-8 -*-
"""发版一致性:版本号是单一来源,其它位置必须与它同步。

历史上出现过"关于页版本与 exe 版本不一致""README 徽章落后两个版本"这类问题,
这一组用例把它们变成可自动发现的错误。
"""
import json
import re

import pytest

from app import config as cfgmod

ROOT = cfgmod.ROOT if not getattr(__import__("sys"), "frozen", False) else cfgmod.ROOT
ROOT = cfgmod.CONFIG_PATH.parent


def _version_tuple(v: str):
    return tuple(int(x) for x in re.findall(r"\d+", v)[:3])


def test_frontend_package_version_matches():
    pkg = json.loads((ROOT / "frontend" / "package.json").read_text(encoding="utf-8"))
    assert pkg["version"] == cfgmod.APP_VERSION, "frontend/package.json 版本未同步"


def test_version_info_matches():
    text = (ROOT / "version_info.txt").read_text(encoding="utf-8", errors="ignore")
    m = re.search(r"filevers=\((\d+),\s*(\d+),\s*(\d+)", text)
    assert m, "version_info.txt 缺少 filevers"
    assert tuple(int(g) for g in m.groups()) == _version_tuple(cfgmod.APP_VERSION)
    assert f"StringFileInfo" in text


def test_pyinstaller_spec_matches():
    specs = list(ROOT.glob("OCR助手-v*.spec"))
    assert specs, "找不到 PyInstaller spec(发版必需)"
    latest = max(specs, key=lambda p: _version_tuple(p.name))
    assert cfgmod.APP_VERSION in latest.name, (
        f"spec 文件名版本落后(app={cfgmod.APP_VERSION}, spec={latest.name})")
    content = latest.read_text(encoding="utf-8")
    assert f"OCR助手-v{cfgmod.APP_VERSION}" in content, "spec 内 name 未同步版本"


@pytest.mark.parametrize("doc", ["README.md", "README.en.md"])
def test_readme_badge_matches(doc):
    path = ROOT / doc
    if not path.exists():
        pytest.skip(f"{doc} 不存在")
    text = path.read_text(encoding="utf-8", errors="ignore")
    m = re.search(r"badge/Version-([0-9.]+)-", text)
    assert m, f"{doc} 没有版本徽章"
    assert m.group(1) == cfgmod.APP_VERSION, f"{doc} 版本徽章未同步"


def test_tutorial_mentions_current_exe_name():
    path = ROOT / "TUTORIAL.md"
    if not path.exists():
        pytest.skip("TUTORIAL.md 不存在")
    text = path.read_text(encoding="utf-8", errors="ignore")
    exe_names = set(re.findall(r"OCR助手-v([0-9.]+)\.exe", text))
    if not exe_names:
        pytest.skip("教程未提及 exe 名")
    assert cfgmod.APP_VERSION in exe_names, (
        f"TUTORIAL.md 里的 exe 名版本落后:{sorted(exe_names)}")


def test_changelog_has_current_version():
    text = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8", errors="ignore")
    assert f"## [{cfgmod.APP_VERSION}]" in text, "CHANGELOG 没有当前版本的条目"


def test_built_webui_matches_source_mtime():
    """构建产物不能落后于前端源码:落后说明改了前端但忘了 npm run build。

    这是本项目最容易踩的坑之一(界面明明改了,程序里还是老样子)。
    """
    webui = ROOT / "app" / "webui" / "assets"
    if not webui.exists() or not list(webui.glob("*.js")):
        pytest.skip("尚无构建产物")
    newest_build = max(p.stat().st_mtime for p in webui.iterdir())
    newest_src = max(
        p.stat().st_mtime
        for p in (ROOT / "frontend" / "src").rglob("*")
        if p.is_file()
    )
    assert newest_build >= newest_src, (
        "app/webui 构建产物早于 frontend/src 的修改 —— 请运行 `npm run build`")


def test_built_html_references_existing_assets():
    """产物 HTML 里引用的资源必须真实存在(否则窗口会整片空白)。"""
    webui = ROOT / "app" / "webui"
    for name in ("index.html", "selector.html"):
        html = (webui / name).read_text(encoding="utf-8", errors="ignore")
        refs = re.findall(r'(?:src|href)="([^"]+)"', html)
        local = [r for r in refs if not r.startswith(("http://", "https://", "data:"))]
        assert local, f"{name} 没有任何本地资源引用"
        for ref in local:
            assert (webui / ref).exists(), f"{name} 引用了不存在的资源:{ref}"


def test_no_stale_assets_in_webui():
    """产物目录里不能残留上一次构建的 js/css(否则容易加载到旧界面)。"""
    webui = ROOT / "app" / "webui"
    html = "".join((webui / n).read_text(encoding="utf-8", errors="ignore")
                   for n in ("index.html", "selector.html"))
    stale = []
    for f in (webui / "assets").iterdir():
        if f.suffix in (".js", ".css") and f.name not in html:
            stale.append(f.name)
    assert not stale, f"app/webui/assets 有未被引用的旧产物:{stale}"
