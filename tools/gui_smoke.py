# -*- coding: utf-8 -*-
"""真窗口冒烟:启动真实 App(GUI),核对 HANDOFF 第 8 节那 8 条手工验证里可自动化的部分。

用法:
    .\\.venv\\Scripts\\python.exe tools\\gui_smoke.py
    .\\.venv\\Scripts\\python.exe tools\\gui_smoke.py --json report.json

覆盖(都是历史上真实复发过的缺陷):
    1. 三个模式窗口都能加载出来(page ready)
    2. 模式互切后「只有当前模式窗口可见」(按 Qt 的 isVisible 判定)
    3. 洞口区域真的被挖掉(SetWindowRgn 生效 → _hole_active)
    4. 洞口暂停后能恢复(弹窗/教程期间不被裁掉,结束后穿透回来)
    5. 迷你条上方提示浮层:打开 → 向上扩展;关闭 → 精确还原
    6. 迷你条高度由内容锁定,宽度不小于下限
    7. 退出链路:悬浮窗/翻译发 confirmQuit(带 mode),迷你条发 quitHint
    8. 按需窗口:设置/框选用完即销毁;框选几何按缩放比换算
    9. 桥接在多窗口里都活着(每个窗口 evaluate_js 调 get_state)

注意:会短暂弹出真实窗口(结束后全部关闭),并且**不读写仓库里的 config.json**:
配置/历史/请求日志全部重定向到临时目录。
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import threading
import time
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

os.environ.setdefault(
    "QTWEBENGINE_CHROMIUM_FLAGS",
    "--disable-gpu --disable-gpu-compositing --disable-software-rasterizer "
    "--disable-dev-shm-usage --disable-background-networking --disable-sync "
    "--renderer-process-limit=2 --process-per-site --js-flags=--max-old-space-size=96",
)


class Check:
    def __init__(self, name, ok, detail=""):
        self.name = name
        self.ok = bool(ok)
        self.detail = detail

    def as_dict(self):
        return {"name": self.name, "ok": self.ok, "detail": self.detail}


class Smoke:
    def __init__(self, tmp: Path, report_path: Path | None, timeout: float):
        self.tmp = tmp
        self.report_path = report_path
        self.timeout = timeout
        self.checks: list[Check] = []
        self.events: list[dict] = []
        self.app = None

    # ---------- 工具 ----------
    def check(self, name, ok, detail=""):
        self.checks.append(Check(name, ok, detail))
        mark = "PASS" if ok else "FAIL"
        print(f"[{mark}] {name}" + (f" —— {detail}" if detail else ""), flush=True)

    def wait_for(self, pred, timeout=8.0, interval=0.15):
        end = time.time() + timeout
        while time.time() < end:
            try:
                if pred():
                    return True
            except Exception:
                pass
            time.sleep(interval)
        return False

    @staticmethod
    def visible(win) -> bool:
        if win is None:
            return False
        try:
            return bool(win.native.isVisible())
        except Exception:
            return False

    def ready(self, win, timeout=15.0) -> bool:
        return self.wait_for(lambda: win is not None and win.events._pywebviewready.is_set(),
                             timeout=timeout)

    def push_recorder(self):
        original = self.app.push

        def spy(payload):
            try:
                self.events.append(payload)
            except Exception:
                pass
            return original(payload)

        self.app.push = spy

    def events_of(self, etype):
        return [e for e in self.events if e.get("type") == etype]

    # ---------- 主流程 ----------
    def run_checks(self):
        from app import config as cfgmod

        app = self.app
        overlay, mini, translate = app.overlay, app.mini, app.translate

        # 1. 三个模式窗口都要能加载出来(历史上出现过多窗口整片空白)
        ok = self.ready(overlay) and self.ready(mini) and self.ready(translate)
        self.check("三个模式窗口页面加载完成", ok,
                   f"overlay={self.ready(overlay,0.1)} mini={self.ready(mini,0.1)} "
                   f"translate={self.ready(translate,0.1)}")
        if not ok:
            return

        # 9. 桥接在每个窗口里都可用。
        #    注意:pywebview 的 api 方法在 JS 侧返回 Promise,evaluate_js 不会等待,
        #    所以这里改查「暴露出来的方法数与关键方法是否存在」——这也正是
        #    Api.__dir__ 精简桥接面那条优化的验收点。
        bridge = {}
        for name, win in (("overlay", overlay), ("mini", mini), ("translate", translate)):
            try:
                info = win.evaluate_js(
                    "(function(){"
                    "  var api = (window.pywebview && window.pywebview.api) || {};"
                    "  var keys = Object.keys(api);"
                    "  return {n: keys.length,"
                    "          has: keys.indexOf('get_state') >= 0"
                    "               && keys.indexOf('set_mode') >= 0"
                    "               && keys.indexOf('finish_snip') >= 0};"
                    "})()")
                bridge[name] = info or {}
            except Exception as exc:  # noqa: BLE001
                bridge[name] = {"error": str(exc)}
        ok_bridge = all(v.get("has") for v in bridge.values())
        counts = {k: v.get("n") for k, v in bridge.items()}
        # 桥接面必须保持精简(__dir__ 只返回公开方法):暴露过多会拖慢每个窗口的注入
        lean = all(isinstance(v.get("n"), int) and 40 <= v["n"] <= 120 for v in bridge.values())
        self.check("桥接在三个窗口都可用且方法面保持精简", ok_bridge and lean,
                   f"方法数={counts}(期望 40~120)" + (
                       "" if ok_bridge else f" 详情={bridge}"))

        # 2. 模式互切:只有当前模式的窗口可见
        mismatches = []
        for mode in ("overlay", "mini", "translate"):
            app.set_mode(mode)
            time.sleep(1.2)
            seen = {n: self.visible(w) for n, w in
                    (("overlay", overlay), ("mini", mini), ("translate", translate))}
            if seen != {m: (m == mode) for m in ("overlay", "mini", "translate")}:
                mismatches.append(f"{mode}:{seen}")
        self.check("模式切换后只有当前模式窗口可见", not mismatches,
                   ";".join(mismatches) if mismatches else "三种模式逐个切换均正确")

        # 3. 洞口穿透:切回悬浮窗,等前端上报洞口 → SetWindowRgn 生效
        app.set_mode("overlay")
        time.sleep(1.6)
        got = self.wait_for(lambda: app._hole_active, timeout=10)
        self.check("洞口区域已挖掉(鼠标穿透生效)", got,
                   f"_hole_key={app._hole_key} active={app._hole_active}")

        # 4. 洞口暂停/恢复(弹窗、教程共用这条链路)
        app.pause_hole(True)
        time.sleep(0.6)
        paused = not app._hole_active
        app.pause_hole(False)
        resumed = self.wait_for(lambda: app._hole_active, timeout=6)
        self.check("洞口暂停后能恢复", paused and resumed,
                   f"暂停时清空区域={paused} 恢复后重新挖洞={resumed}")

        # 5. 迷你条上方浮层:精确还原
        app.set_mode("mini")
        time.sleep(1.5)
        before = (int(mini.x), int(mini.y), int(mini.width), int(mini.height))
        app.set_modal_room(True)
        time.sleep(1.0)
        during = (int(mini.x), int(mini.y), int(mini.width), int(mini.height))
        grew_up = during[1] < before[1] and during[3] > before[3] and during[0] == before[0]
        app.set_modal_room(False)
        time.sleep(1.0)
        after = (int(mini.x), int(mini.y), int(mini.width), int(mini.height))
        self.check("迷你条提示浮层向上扩展且精确还原",
                   grew_up and after == before,
                   f"before={before} during={during} after={after}")

        # 6. 迷你条尺寸约束
        cfg_win = app.cfg.get("window") or {}
        min_ok = int(mini.width) >= 640 and int(mini.height) >= 56
        height_ok = abs(int(mini.height) - int(cfg_win.get("miniHeight") or 0)) <= 2
        self.check("迷你条高度贴合内容、宽度不低于下限", min_ok and height_ok,
                   f"实测 {int(mini.width)}x{int(mini.height)} "
                   f"配置 miniWidth={cfg_win.get('miniWidth')} miniHeight={cfg_win.get('miniHeight')}")

        # 7. 退出链路:各模式的待处理目标与事件类型
        self.events.clear()
        app.set_mode("overlay")
        time.sleep(1.2)
        app.request_quit()
        time.sleep(0.4)
        quit_evts = self.events_of("confirmQuit")
        ok_overlay = bool(quit_evts) and quit_evts[0].get("mode") == "overlay" \
            and app.quit_pending() == "overlay"
        app.clear_quit_pending_for("overlay")

        app.set_mode("mini")
        time.sleep(1.2)
        self.events.clear()
        app.request_quit()
        time.sleep(0.4)
        hint = self.events_of("quitHint")
        ok_mini = bool(hint) and hint[0].get("where") == "mini" and app.quit_pending() == "mini"
        # 后端兜底还原:离开迷你条时必须把浮层空间收回去(历史上被永久撑大)
        app.set_mode("overlay")
        time.sleep(1.4)
        restored = abs(int(mini.height) - int(cfg_win.get("miniHeight") or 0)) <= 2
        self.check("退出链路:悬浮窗发 confirmQuit(带 mode)、迷你条发 quitHint",
                   ok_overlay and ok_mini,
                   f"confirmQuit={quit_evts[:1]} quitHint={hint[:1]}")
        self.check("离开迷你条后浮层空间被后端兜底还原", restored and not app._mini_modal_open,
                   f"mini.height={int(mini.height)} 期望≈{cfg_win.get('miniHeight')}")

        # 8. 按需窗口:设置窗口创建与销毁
        app.open_settings()
        created = self.wait_for(lambda: app.settings is not None, timeout=8)
        ready_settings = created and self.ready(app.settings, timeout=20)
        blocked = bool(getattr(app, "_modal_block", False))
        app.close_settings()
        destroyed = self.wait_for(lambda: app.settings is None, timeout=8)
        unblocked = not bool(getattr(app, "_modal_block", False))
        self.check("设置窗口按需创建、打开时禁用主界面、关闭即销毁",
                   created and ready_settings and blocked and destroyed and unblocked,
                   f"created={created} ready={ready_settings} modal_block={blocked} "
                   f"destroyed={destroyed} unblocked={unblocked}")

        # 8b. 框选窗口几何:物理像素 → 逻辑像素(高 DPI 下窗口不能比屏幕大一倍)
        from app.capturer import virtual_screen
        from app.winutil import screen_scale
        vs = virtual_screen()
        k = screen_scale() or 1.0
        want = (int(round(vs["width"] / k)), int(round(vs["height"] / k)))
        app.start_snip()
        snip_ready = self.wait_for(lambda: app.snip is not None, timeout=8)
        time.sleep(1.0)
        got_size = (int(app.snip.width), int(app.snip.height)) if app.snip else (0, 0)
        near = abs(got_size[0] - want[0]) <= 4 and abs(got_size[1] - want[1]) <= 4
        self.check("框选窗口按缩放比换算(不会比屏幕大一倍)",
                   snip_ready and near,
                   f"物理 {vs['width']}x{vs['height']} 缩放 {k} → 逻辑 {got_size}(期望 {want})")

        # 收尾:退出框选,回到悬浮窗
        app.cancel_snip()
        time.sleep(1.0)

    # ---------- 入口 ----------
    def sandbox_config(self):
        """把配置/历史/请求日志重定向到临时目录,绝不碰仓库里的真实文件。"""
        from app import config as cfgmod
        from app import history, request_log

        self.tmp.mkdir(parents=True, exist_ok=True)
        cfgmod.CONFIG_PATH = self.tmp / "config.json"
        cfgmod.BACKUP_PATH = self.tmp / "config.json.bak"
        history.PATH = self.tmp / "history.json"
        request_log.LOG_PATH = self.tmp / "request_log.json"

        cfg = cfgmod.load_config()
        cfg["storage"]["cache_dir"] = str(self.tmp / "cache")
        cfg["storage"]["questions_dir"] = str(self.tmp / "questions")
        cfg["storage"]["add_to_knowledge"] = False
        cfg["ui"]["guideDone"] = {m: True for m in
                                  ("overlay", "mini", "translate", "settings", "snip")}
        cfg["behavior"]["quit_action"] = "ask"
        cfg["window"]["mini_x"] = None      # 让迷你条走"默认位置"分支
        cfg["window"]["mini_y"] = None
        cfg["window"]["translate_x"] = None
        cfg["window"]["translate_y"] = None
        cfgmod.save_config(cfg)

    def start(self):
        import webview

        from app.manager import App

        webview.settings["ALLOW_DOWNLOADS"] = False
        self.app = App()
        self.push_recorder()
        self.notice_before = len(self.events)

        def worker():
            try:
                if not self.wait_for(lambda: self.app.overlay is not None, timeout=self.timeout):
                    self.check("应用启动(窗口创建)", False, "超时未创建窗口")
                else:
                    self.check("应用启动(窗口创建)", True)
                    self.run_checks()
            except Exception as exc:  # noqa: BLE001
                self.checks.append(Check("冒烟脚本自身异常", False,
                                         f"{exc}\n{traceback.format_exc()}"))
                print("[FAIL] 冒烟脚本自身异常:", exc, flush=True)
                traceback.print_exc()
            finally:
                self.finish()

        threading.Thread(target=worker, daemon=True, name="smoke").start()
        self.app.start()          # 阻塞到窗口全部关闭
        return self.summary()

    def finish(self):
        print("\n收尾:关闭窗口…", flush=True)
        try:
            for name in ("overlay", "mini", "translate", "settings", "snip"):
                win = getattr(self.app, name, None)
                if win is not None:
                    try:
                        win.destroy()
                    except Exception:
                        pass
        except Exception:
            pass
        self.write_report()
        time.sleep(0.5)
        failed = [c for c in self.checks if not c.ok]
        print(f"\n结果:{len(self.checks) - len(failed)}/{len(self.checks)} 项通过", flush=True)
        sys.stdout.flush()
        os._exit(1 if failed else 0)

    def summary(self):
        return {"checks": [c.as_dict() for c in self.checks],
                "failed": [c.name for c in self.checks if not c.ok]}

    def write_report(self):
        if not self.report_path:
            return
        try:
            data = self.summary()
            data["events"] = [e.get("type") for e in self.events]
            self.report_path.write_text(json.dumps(data, ensure_ascii=False, indent=2),
                                        encoding="utf-8")
        except Exception:
            pass


def main() -> int:
    ap = argparse.ArgumentParser(description="真窗口冒烟(不碰真实配置)")
    ap.add_argument("--json", dest="report", default="", help="结果写到该 JSON 文件")
    ap.add_argument("--timeout", type=float, default=30.0, help="等待窗口就绪的上限(秒)")
    ap.add_argument("--tmp", default="", help="沙箱目录(默认用系统临时目录)")
    args = ap.parse_args()

    import tempfile

    tmp = Path(args.tmp) if args.tmp else Path(tempfile.mkdtemp(prefix="dscode-smoke-"))
    report = Path(args.report) if args.report else None
    print(f"沙箱目录:{tmp}", flush=True)

    smoke = Smoke(tmp, report, args.timeout)
    smoke.sandbox_config()
    smoke.start()
    return 0


if __name__ == "__main__":
    sys.exit(main())
