# -*- coding: utf-8 -*-
"""应用控制器:多窗口(悬浮窗/迷你条/设置/选区)、模式切换、识别流程、全局快捷键。

注意:窗口与 WebView 操作统一通过 run_in_main 排队到 Qt 主线程执行。
"""
import json
import os
import queue
import subprocess
import threading
import time
import webbrowser
from pathlib import Path

import webview

from app import config as cfgmod
from app import history, request_log
from app.agent import AgentClient
from app.capturer import CaptureError, grab_region, virtual_screen
from app.mainthread import run_in_main

WEBUI = Path(__file__).resolve().parent / "webui"


def _url(view: str) -> str:
    return (WEBUI / "index.html").as_uri() + f"?view={view}"


def _snip_url() -> str:
    return (WEBUI / "selector.html").as_uri()


class App:
    def __init__(self):
        self.cfg = cfgmod.load_config()
        self.overlay = None
        self.mini = None
        self.settings = None
        self.snip = None
        self._worker = None
        self._lock = threading.Lock()
        self._api = None
        self._drag = None
        self._hole_key = None
        self._prev_mode = None
        # 前端事件统一由独立线程推送:evaluate_js 会阻塞等待 JS 结果,
        # 若在 Qt 主线程调用会死锁(界面无响应),因此必须走非 GUI 线程。
        self._push_q = queue.Queue(maxsize=128)
        threading.Thread(target=self._push_loop, daemon=True, name="push").start()

    # ================= 启动与窗口 =================
    def start(self):
        self._create_windows()
        self._register_hotkeys()
        # Qt(WebEngine)后端:透明/无边框/置顶/拖拽均支持
        webview.start(gui="qt", debug=False)

    def _push_loop(self):
        while True:
            payload = self._push_q.get()
            js = f"window.__ocrEvent && window.__ocrEvent({json.dumps(payload, ensure_ascii=False)})"
            for win in (self.overlay, self.mini, self.settings, self.snip):
                if win is None:
                    continue
                try:
                    win.evaluate_js(js)
                except Exception:
                    pass

    def _create_windows(self):
        cfg = self.cfg
        mini_mode = cfg.get("mode") == "mini"
        w = int(cfg["window"].get("width", 640))
        h = int(cfg["window"].get("height", 680))
        mw = int(cfg["window"].get("miniWidth", 560))
        mh = int(cfg["window"].get("miniHeight", 46))
        on_top = bool(cfg["window"].get("always_on_top", True))
        api = self.api

        self.overlay = webview.create_window(
            "OCR 助手", _url("overlay"), js_api=api, width=w, height=h,
            frameless=True, easy_drag=False, on_top=on_top, transparent=True,
            hidden=mini_mode, text_select=True,
        )
        self.mini = webview.create_window(
            "OCR 助手", _url("mini"), js_api=api, width=mw, height=mh,
            frameless=True, easy_drag=False, on_top=on_top, transparent=True,
            hidden=not mini_mode,
        )
        self.settings = webview.create_window(
            "设置 - OCR 助手", _url("settings"), js_api=api, width=1000, height=700,
            min_size=(900, 600), resizable=True, hidden=True,
        )
        vs = virtual_screen()
        self.snip = webview.create_window(
            "选择区域", _snip_url(), js_api=api, x=vs["left"], y=vs["top"],
            width=vs["width"], height=vs["height"], frameless=True, on_top=True,
            transparent=True, hidden=True, easy_drag=False,
        )
        self.overlay.events.closed += self.quit_app
        self.mini.events.closed += self.quit_app
        self.settings.events.closed += self._on_settings_closed
        self.snip.events.closed += self._on_snip_closed

    def _on_settings_closed(self):
        self.cfg = cfgmod.load_config()
        self.push({"type": "config", "config": self.cfg})

    def _on_snip_closed(self):
        pass

    # ================= 事件推送 =================
    def push(self, payload: dict):
        """投递前端事件(由独立线程执行,绝不在 Qt 主线程评估 JS)。"""
        try:
            self._push_q.put_nowait(payload)
        except queue.Full:
            pass

    # ================= 模式切换 =================
    def set_mode(self, mode: str):
        if mode not in ("overlay", "snip", "mini"):
            return
        if mode == self.cfg.get("mode") and mode != "snip":
            return

        def do():
            if mode == "snip":
                if self.cfg.get("mode") != "snip":
                    self._prev_mode = self.cfg.get("mode") or "overlay"
                self.overlay.hide()
                self.mini.hide()
                self.snip.show()
            elif mode == "mini":
                self.snip.hide()
                self.overlay.hide()
                self.mini.show()
                self._place_mini_default()
            else:
                self.snip.hide()
                self.mini.hide()
                self.overlay.show()
            self.cfg["mode"] = mode
            cfgmod.save_config(self.cfg)

        run_in_main(do)
        self.push({"type": "config", "config": self.cfg})

    # ================= 迷你条默认位置(任务栏上方居中) =================
    def _place_mini_default(self):
        """首次进入迷你条模式时,把它居中放在任务栏(工作区)上方。"""
        win_cfg = self.cfg.setdefault("window", {})
        if win_cfg.get("mini_x") is not None and win_cfg.get("mini_y") is not None:
            return
        try:
            from PySide6.QtGui import QGuiApplication
            screen = QGuiApplication.primaryScreen()
            g = screen.availableGeometry()  # 已排除任务栏,逻辑像素
            w = int(win_cfg.get("miniWidth", 380))
            h = int(win_cfg.get("miniHeight", 40))
            x = int(g.x() + (g.width() - w) / 2)
            y = int(g.y() + g.height() - h - 18)
            self.mini.move(x, y)
            win_cfg["mini_x"], win_cfg["mini_y"] = x, y
            cfgmod.save_config(self.cfg)
        except Exception:
            pass

    # ================= 窗口拖动(受控拖拽) =================
    def _win(self, which: str):
        return {"overlay": self.overlay, "mini": self.mini}.get(which)

    def drag_begin(self, which: str, sx: float, sy: float) -> bool:
        win = self._win(which)
        if win is None:
            return False
        try:
            self._drag = {"which": which, "x": float(win.x), "y": float(win.y),
                          "px": float(sx), "py": float(sy), "last": None}
            return True
        except Exception:
            self._drag = None
            return False

    def drag_move(self, which: str, sx: float, sy: float) -> bool:
        d = self._drag
        win = self._win(which)
        if not d or win is None or d.get("which") != which:
            return False
        x = int(round(d["x"] + float(sx) - d["px"]))
        y = int(round(d["y"] + float(sy) - d["py"]))
        if d.get("last") == (x, y):
            return True
        d["last"] = (x, y)
        run_in_main(lambda: win.move(x, y))
        return True

    def drag_end(self, which: str) -> bool:
        d = self._drag
        self._drag = None
        win = self._win(which)
        if not d or win is None:
            return False
        try:
            pos = d.get("last") or (int(win.x), int(win.y))
            win_cfg = self.cfg.setdefault("window", {})
            if which == "mini":
                win_cfg["mini_x"], win_cfg["mini_y"] = int(pos[0]), int(pos[1])
            else:
                win_cfg["x"], win_cfg["y"] = int(pos[0]), int(pos[1])
            cfgmod.save_config(self.cfg)
        except Exception:
            pass
        return True

    # ================= 洞口区域鼠标穿透 =================
    def set_hole_region(self, rect: dict) -> bool:
        """把 OCR 洞口从窗口区域中挖掉:洞内鼠标事件直达后方,同时保证洞口边框仍可见。"""
        if not rect:
            return False
        try:
            x, y = int(rect.get("x", 0)), int(rect.get("y", 0))
            w, h = int(rect.get("w", 0)), int(rect.get("h", 0))
        except Exception:
            return False
        key = (x, y, w, h)
        if key == self._hole_key:
            return True
        self._hole_key = key
        run_in_main(lambda: self._apply_region(x, y, w, h))
        return True

    def _apply_region(self, hx: int, hy: int, hw: int, hh: int):
        win = self.overlay
        try:
            hwnd = int(win.native.winId())
        except Exception:
            return
        if not hwnd:
            return
        try:
            import ctypes
            from ctypes import wintypes
            user32 = ctypes.windll.user32
            gdi32 = ctypes.windll.gdi32
            # 必须声明原型:64 位下句柄若按 int 传参会截断,导致区域创建失败
            gdi32.CreateRectRgn.argtypes = [ctypes.c_int] * 4
            gdi32.CreateRectRgn.restype = wintypes.HANDLE
            gdi32.SetRectRgn.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_int,
                                         ctypes.c_int, ctypes.c_int]
            gdi32.SetRectRgn.restype = ctypes.c_int
            gdi32.CombineRgn.argtypes = [wintypes.HANDLE, wintypes.HANDLE, wintypes.HANDLE, ctypes.c_int]
            gdi32.CombineRgn.restype = ctypes.c_int
            gdi32.DeleteObject.argtypes = [wintypes.HANDLE]
            gdi32.DeleteObject.restype = wintypes.BOOL
            user32.GetClientRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
            user32.GetClientRect.restype = wintypes.BOOL
            user32.SetWindowRgn.argtypes = [wintypes.HWND, wintypes.HANDLE, wintypes.BOOL]
            user32.SetWindowRgn.restype = ctypes.c_int
            user32.SetWindowPos.argtypes = [wintypes.HWND, wintypes.HWND, ctypes.c_int, ctypes.c_int,
                                            ctypes.c_int, ctypes.c_int, ctypes.c_uint]

            r = wintypes.RECT()
            if not user32.GetClientRect(hwnd, ctypes.byref(r)):
                return
            cw, ch = int(r.right - r.left), int(r.bottom - r.top)
            if cw < 8 or ch < 8:
                return
            left, top = max(0, hx), max(0, hy)
            right, bottom = min(cw, hx + hw), min(ch, hy + hh)
            if right - left < 4 or bottom - top < 4:
                parts = [(0, 0, cw, ch)]
            else:
                parts = [
                    (0, 0, cw, top),                       # 洞口上方
                    (0, bottom, cw, ch - bottom),          # 洞口下方
                    (0, top, left, bottom - top),          # 洞口左侧
                    (right, top, cw - right, bottom - top),  # 洞口右侧
                ]
            parts = [p for p in parts if p[2] > 0 and p[3] > 0]
            if not parts:
                return

            rgn = gdi32.CreateRectRgn(0, 0, 0, 0)
            if not rgn:
                return
            px, py, pw, ph = parts[0]
            gdi32.SetRectRgn(rgn, px, py, px + pw, py + ph)
            if len(parts) > 1:
                tmp = gdi32.CreateRectRgn(0, 0, 0, 0)
                for px, py, pw, ph in parts[1:]:
                    gdi32.SetRectRgn(tmp, px, py, px + pw, py + ph)
                    gdi32.CombineRgn(rgn, rgn, tmp, 2)  # RGN_OR
                gdi32.DeleteObject(tmp)

            if not user32.SetWindowRgn(hwnd, rgn, True):
                gdi32.DeleteObject(rgn)  # 失败时区域所有权仍在本地
                return
            # 让系统按新区域重算窗口框并重绘
            user32.SetWindowPos(hwnd, None, 0, 0, 0, 0, 0x0020 | 0x0002 | 0x0001 | 0x0004)
            self._hole_active = True
        except Exception:
            pass

    # ================= 设置窗口 =================
    def open_settings(self):
        run_in_main(lambda: self.settings.show())

    def close_settings(self):
        run_in_main(lambda: self.settings.hide())

    # ================= 自由截图 =================
    def start_snip(self):
        self.set_mode("snip")

    def cancel_snip(self):
        back = self._prev_mode if self._prev_mode in ("mini", "overlay") else \
            ("mini" if self.cfg.get("mode") == "mini" else "overlay")
        self.set_mode(back)

    def finish_snip(self, sel: dict, action: str = "run", question: str = ""):
        """完成框选:隐藏遮罩 → 抓取区域 → 识别 或 设为悬浮窗区域。"""
        dpr = float(sel.get("dpr") or 1)
        vs = virtual_screen()
        left = int(vs["left"] + sel["x"] * dpr)
        top = int(vs["top"] + sel["y"] * dpr)
        w = int(sel["w"] * dpr)
        h = int(sel["h"] * dpr)

        run_in_main(lambda: self.snip.hide())
        time.sleep(max(0.06, int(self.cfg["capture"].get("flash_delay_ms", 80)) / 1000.0 + 0.05))
        try:
            png = grab_region(left, top, w, h)
        except CaptureError as exc:
            self.push({"type": "error", "text": str(exc)})
            png = None

        if action == "region":
            self.cfg["window"]["width"] = max(360, w)
            self.cfg["window"]["height"] = max(260, h)
            self.cfg["mode"] = "overlay"
            cfgmod.save_config(self.cfg)

            def do():
                self.overlay.resize(max(360, w), max(260, h))
                self.snip.hide()
                self.mini.hide()
                self.overlay.show()

            run_in_main(do)
            self.push({"type": "status", "text": "已设为悬浮窗区域", "tone": "ok"})
            self.push({"type": "config", "config": self.cfg})
            return

        self.cancel_snip()
        if png:
            self._run(png, question)

    # ================= 识别流程 =================
    def run_pipeline_rect(self, rect: dict, question: str = ""):
        """按悬浮窗内洞口的 CSS 矩形截屏(换算为屏幕物理像素)。"""
        win = self.overlay
        dpr = float(rect.get("dpr") or 1)
        try:
            left = int(win.x + rect["x"] * dpr)
            top = int(win.y + rect["y"] * dpr)
        except Exception:
            left = top = 0
        w = int(rect["w"] * dpr)
        h = int(rect["h"] * dpr)

        self.push({"type": "hideBorder", "value": True})
        time.sleep(max(0.05, int(self.cfg["capture"].get("flash_delay_ms", 80)) / 1000.0))
        try:
            png = grab_region(left, top, w, h)
        except CaptureError as exc:
            self.push({"type": "error", "text": str(exc)})
            return
        finally:
            self.push({"type": "hideBorder", "value": False})
        self._run(png, question)

    def _run(self, png: bytes, question: str = ""):
        with self._lock:
            if self._worker and self._worker.is_alive():
                return
            prov = cfgmod.active_provider(self.cfg)
            if not (prov.get("api_key") or "").strip():
                self.push({"type": "error", "text": "未配置 API Key:请在「设置 → 模型设置」填写"})
                return
            client = AgentClient(
                prov.get("api_key", ""), prov.get("model", ""), prov.get("base_url", ""),
                self.cfg.get("request_template", ""),
                timeout=int(self.cfg.get("timeout", 180)),
                max_side=int(self.cfg["capture"].get("max_side", 2048)),
                max_retries=int(self.cfg["retry"].get("max_retries", 3)),
                backoff=float(self.cfg["retry"].get("backoff", 0.8)),
                enable_thinking=bool(prov.get("enable_thinking", False)),
            )
            from app.worker import PipelineWorker
            self.push({"type": "busy", "value": True})
            self._worker = PipelineWorker(
                client, png, self.cfg["prompts"]["ocr"], self.cfg["prompts"]["answer"],
                question, self.cfg.get("knowledge", []),
                self.cfg.get("ocr", {}).get("mode", "cloud"),
                on_status=lambda t, tone: self.push({"type": "status", "text": t, "tone": tone}),
                on_result=self._on_result,
                on_error=lambda t: self.push({"type": "error", "text": t}),
            )
            self._worker.start()

    def _on_result(self, data: dict):
        self.push({"type": "result", "data": data})
        self.push({"type": "history", "data": history.load()})
        self._save_outputs(data)

    def _save_outputs(self, data: dict):
        storage = self.cfg.get("storage") or {}
        qdir = (storage.get("questions_dir") or "").strip()
        if qdir:
            try:
                d = Path(qdir)
                d.mkdir(parents=True, exist_ok=True)
                with open(d / f"qa_{time.strftime('%Y%m%d')}.txt", "a", encoding="utf-8") as f:
                    f.write(f"【{time.strftime('%Y-%m-%d %H:%M:%S')}】\n"
                            f"题目:\n{data.get('ocr_text', '')}\n回答:\n{data.get('answer', '')}\n{'=' * 30}\n")
            except Exception:
                pass
        if storage.get("add_to_knowledge") and data.get("question"):
            key = str(data["question"]).strip()[:10]
            if len(key) >= 4:
                kb = self.cfg.get("knowledge") or []
                if not any(key in (k.get("keys") or [""])[0] for k in kb):
                    kb.append({"keys": [key], "answer": data.get("answer", ""),
                               "detail": f"来源:{data.get('source', '')}"})
                    self.cfg["knowledge"] = kb[-200:]
                    cfgmod.save_config(self.cfg)

    # ================= 全局快捷键 =================
    def _register_hotkeys(self):
        hk = self.cfg.get("hotkeys") or {}
        mapping = {
            hk.get("capture", "ctrl+f1"): self._hotkey_capture,
            hk.get("snip", "ctrl+shift+a"): lambda: self.start_snip(),
            "ctrl+1": lambda: self.set_mode("overlay"),
            "ctrl+2": lambda: self.set_mode("mini"),
            "ctrl+3": lambda: self.set_mode("snip"),
            hk.get("exit", "ctrl+q"): self.quit_app,
        }
        try:
            import keyboard
            for combo, fn in mapping.items():
                if combo:
                    keyboard.add_hotkey(combo, lambda f=fn: threading.Thread(target=f, daemon=True).start())
        except Exception:
            pass  # 权限/环境不支持时静默降级

    def _hotkey_capture(self):
        if self.cfg.get("mode") == "mini":
            self.start_snip()
        else:
            self.push({"type": "hotkeyCapture"})

    # ================= 其它 =================
    def quit_app(self):
        try:
            self.cfg = cfgmod.load_config()
            cfgmod.save_config(self.cfg)
        except Exception:
            pass
        os._exit(0)

    def open_url(self, url: str):
        if url:
            webbrowser.open(url)

    def open_path(self, path: str):
        if not path:
            return
        try:
            os.startfile(path)  # noqa: S606
        except Exception:
            subprocess.Popen(["explorer", path])

    def resize_overlay(self, w: int, h: int) -> bool:
        w, h = max(360, int(w)), max(260, int(h))
        run_in_main(lambda: self.overlay.resize(w, h))
        self.cfg["window"]["width"] = w
        self.cfg["window"]["height"] = h
        cfgmod.save_config(self.cfg)
        return True

    @property
    def api(self):
        if self._api is None:
            from app.api import Api
            self._api = Api(self)
        return self._api
