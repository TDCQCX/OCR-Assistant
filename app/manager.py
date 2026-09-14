# -*- coding: utf-8 -*-
"""应用控制器:多窗口(悬浮窗/迷你条/设置/选区)、模式切换、识别流程、全局快捷键。

注意:窗口与 WebView 操作统一通过 run_in_main 排队到 Qt 主线程执行。
"""
import json
import os
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

    # ================= 启动与窗口 =================
    def start(self):
        self._create_windows()
        self._register_hotkeys()
        # Qt(WebEngine)后端:透明/无边框/置顶/拖拽均支持
        webview.start(gui="qt", debug=False)

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
            frameless=True, easy_drag=True, on_top=on_top, transparent=True,
            hidden=mini_mode, text_select=True,
        )
        self.mini = webview.create_window(
            "OCR 助手", _url("mini"), js_api=api, width=mw, height=mh,
            frameless=True, easy_drag=True, on_top=on_top, transparent=True,
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
        js = f"window.__ocrEvent && window.__ocrEvent({json.dumps(payload, ensure_ascii=False)})"

        def do():
            for win in (self.overlay, self.mini, self.settings, self.snip):
                if not win:
                    continue
                try:
                    win.evaluate_js(js)
                except Exception:
                    pass

        run_in_main(do)

    # ================= 模式切换 =================
    def set_mode(self, mode: str):
        if mode not in ("overlay", "snip", "mini"):
            return

        def do():
            if mode == "snip":
                self.overlay.hide()
                self.mini.hide()
                self.snip.show()
            elif mode == "mini":
                self.snip.hide()
                self.overlay.hide()
                self.mini.show()
            else:
                self.snip.hide()
                self.mini.hide()
                self.overlay.show()
            self.cfg["mode"] = mode
            cfgmod.save_config(self.cfg)

        run_in_main(do)
        self.push({"type": "config", "config": self.cfg})

    # ================= 设置窗口 =================
    def open_settings(self):
        run_in_main(lambda: self.settings.show())

    def close_settings(self):
        run_in_main(lambda: self.settings.hide())

    # ================= 自由截图 =================
    def start_snip(self):
        self.set_mode("snip")

    def cancel_snip(self):
        back = "mini" if self.cfg.get("mode") == "mini" else "overlay"
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
