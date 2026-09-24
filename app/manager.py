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
        self.translate = None
        self.settings = None
        self.snip = None
        self._worker = None
        self._lock = threading.Lock()
        self._api = None
        self._drag = None
        self._resize = None
        self._hole_key = None
        self._prev_mode = None
        self._translate_mode = False
        self._last_result = {}
        self._auto_thread = None
        self._auto_stop = threading.Event()
        # 前端事件统一由独立线程推送:evaluate_js 会阻塞等待 JS 结果,
        # 若在 Qt 主线程调用会死锁(界面无响应),因此必须走非 GUI 线程。
        self._push_q = queue.Queue(maxsize=128)
        threading.Thread(target=self._push_loop, daemon=True, name="push").start()

    # ================= 启动与窗口 =================
    def start(self):
        self._create_windows()
        self._register_hotkeys()
        # Qt(WebEngine)后端:透明/无边框/置顶/拖拽均支持。
        # private_mode 必须为 True:pywebview 的 Qt 后端在 private_mode=False 时会为
        # 每个窗口创建一个同名(pywebview)持久化 QWebEngineProfile,多个窗口争抢同一份
        # 磁盘缓存/LevelDB 目录,导致除第一个之外所有窗口的页面都加载不出来
        # (表现为全屏空白、启动极慢)。本程序的设置都存在 config.json,不依赖
        # 浏览器级别的 cookie/localStorage,因此用无痕配置是安全的。
        webview.start(self._bootstrap, gui="qt", debug=False, private_mode=True)

    def _bootstrap(self):
        """启动后校正窗口可见性,并按模式摆好位置。"""
        try:
            from app import local_models
            local_models.apply_settings(self.cfg.get("local") or {})
        except Exception:
            pass
        time.sleep(1.5)
        self._sync_visibility()
        time.sleep(3)
        self._sync_visibility()

    def _sync_visibility(self):
        """只保留当前模式对应的窗口可见(hidden 参数在部分后端不可靠)。"""
        mode = self.cfg.get("mode") or "overlay"
        if mode not in ("overlay", "mini", "translate"):
            mode = "overlay"

        def do():
            for name, win in (("overlay", self.overlay), ("mini", self.mini),
                              ("translate", self.translate)):
                if win is None:
                    continue
                try:
                    win.show() if name == mode else win.hide()
                except Exception:
                    pass
            try:
                for extra in (self.settings, self.snip):
                    if extra is not None:
                        extra.hide()
            except Exception:
                pass
            if mode == "mini":
                self._place_mini_default()
            elif mode == "translate":
                self._place_translate_default()

        run_in_main(do)

    def _on_window_loaded(self):
        """窗口内容加载完成后再次校正可见性(避免被后创建的窗口盖过)。"""
        self._sync_visibility()

    def _push_loop(self):
        while True:
            payload = self._push_q.get()
            js = f"window.__ocrEvent && window.__ocrEvent({json.dumps(payload, ensure_ascii=False)})"
            for win in (self.overlay, self.mini, self.translate, self.settings, self.snip):
                if win is None:
                    continue
                try:
                    win.evaluate_js(js)
                except Exception:
                    pass

    def _create_windows(self):
        cfg = self.cfg
        mode = cfg.get("mode")
        w = int(cfg["window"].get("width", 640))
        h = int(cfg["window"].get("height", 680))
        mw = int(cfg["window"].get("miniWidth", 420))
        # 高度恒定:优先用前端上次实测并写入的 miniHeight,兜底用默认值。
        # 历史版本可能把被拉伸的高度写进了 miniHeight,前端挂载后会立刻校正回来。
        mh = int(cfg["window"].get("miniHeight") or cfg["window"].get("defaultMiniHeight") or 94)
        cfg["window"]["miniHeight"] = mh
        tw = int(cfg["window"].get("translateWidth", 760))
        th = int(cfg["window"].get("translateHeight", 620))
        on_top = bool(cfg["window"].get("always_on_top", True))
        api = self.api

        self.overlay = webview.create_window(
            "OCR 助手", _url("overlay"), js_api=api, width=w, height=h,
            frameless=True, easy_drag=False, on_top=on_top, transparent=True,
            hidden=mode != "overlay", text_select=True,
        )
        self.mini = webview.create_window(
            "OCR 助手", _url("mini"), js_api=api, width=mw, height=mh,
            frameless=True, easy_drag=False, on_top=on_top, transparent=True,
            hidden=mode != "mini",
            # pywebview 默认 min_size=(200,100) 会把迷你条顶到 100px,导致高度「还原不了」;
            # 这里显式放宽下限,高度由前端实测的自然高度锁定(见 set_mini_height)。
            min_size=(320, 56),
        )
        tx, ty = cfg["window"].get("translate_x"), cfg["window"].get("translate_y")
        # 翻译窗口不透明(避免遮挡/看不清内容),默认不置顶
        self.translate = webview.create_window(
            "OCR 助手 - 翻译", _url("translate"), js_api=api, width=tw, height=th,
            frameless=True, easy_drag=False,
            on_top=bool(cfg["window"].get("translate_on_top", False)),
            transparent=False, hidden=mode != "translate", text_select=True,
            **({"x": int(tx), "y": int(ty)} if tx is not None and ty is not None else {}),
        )
        # 设置窗口与框选窗口「按需创建」:每个 WebEngine 窗口都要占一个渲染进程
        # (实测约 65MB),启动时就创建 5 个会让内存和启动时间都明显变差。
        self.settings = None
        self.snip = None
        # 只有"当前模式的窗口"被关闭才退出程序;其它(隐藏的)窗口被关闭不应影响运行
        self.overlay.events.closed += lambda: self._on_window_closed("overlay")
        self.mini.events.closed += lambda: self._on_window_closed("mini")
        self.translate.events.closed += lambda: self._on_window_closed("translate")
        for win in (self.overlay, self.mini, self.translate):
            try:
                win.events.loaded += self._on_window_loaded
            except Exception:
                pass

    def _screen_scale(self) -> float:
        """当前屏幕缩放比(200% 缩放 → 2.0)。"""
        try:
            from PySide6.QtGui import QGuiApplication
            s = QGuiApplication.primaryScreen()
            if s is not None:
                dpr = float(s.devicePixelRatio() or 1.0)
                if dpr > 0:
                    return dpr
        except Exception:
            pass
        return 1.0

    def _snip_geometry(self) -> dict:
        """框选窗口几何:virtual_screen 给的是物理像素,而 Qt 窗口用逻辑像素。

        高 DPI(200%)下如果不除以缩放比,窗口会变成屏幕的 2 倍宽高 = 4 倍面积,
        透明全屏窗口的内存会从 ~170MB 涨到 ~690MB(实测)。
        """
        vs = virtual_screen()
        k = self._screen_scale()
        return {
            "left": int(round(vs["left"] / k)),
            "top": int(round(vs["top"] / k)),
            "width": max(320, int(round(vs["width"] / k))),
            "height": max(240, int(round(vs["height"] / k))),
        }

    def _ensure_settings(self):
        """按需创建设置窗口(首次打开设置时)。"""
        if self.settings is None:
            self.settings = webview.create_window(
                "设置 - OCR 助手", _url("settings"), js_api=self.api, width=1000, height=700,
                min_size=(900, 600), resizable=True, hidden=True,
            )
            self.settings.events.closed += self._on_settings_closed
        return self.settings

    def _ensure_snip(self):
        """按需创建框选窗口(全屏透明遮罩,首次框选时)。"""
        if self.snip is None:
            g = self._snip_geometry()
            self.snip = webview.create_window(
                "选择区域", _snip_url(), js_api=self.api, x=g["left"], y=g["top"],
                width=g["width"], height=g["height"], frameless=True, on_top=True,
                transparent=True, hidden=True, easy_drag=False,
            )
            self.snip.events.closed += self._on_snip_closed
        return self.snip

    def _on_settings_closed(self):
        # 用户关掉设置窗口后释放引用,下次打开设置时重新按需创建
        self.settings = None
        self.cfg = cfgmod.load_config()
        self.push({"type": "config", "config": self.cfg})

    def _on_snip_closed(self):
        # 框选窗口被关闭(例如窗口管理器强关)后置空,下次框选重新创建
        self.snip = None

    # ================= 事件推送 =================
    def push(self, payload: dict):
        """投递前端事件(由独立线程执行,绝不在 Qt 主线程评估 JS)。"""
        try:
            self._push_q.put_nowait(payload)
        except queue.Full:
            pass

    # ================= 模式切换 =================
    def set_mode(self, mode: str):
        if mode not in ("overlay", "snip", "mini", "translate"):
            return
        if mode == self.cfg.get("mode") and mode != "snip":
            return
        prev = self.cfg.get("mode") or "overlay"
        fresh_snip = False
        if mode == "snip" and self.snip is None:
            self._ensure_snip()
            fresh_snip = True

        def do():
            overlay, mini, translate, snip = self.overlay, self.mini, self.translate, self.snip

            def hide_all():
                for w in (overlay, mini, translate, snip):
                    if w is not None:
                        try:
                            w.hide()
                        except Exception:
                            pass

            if mode == "snip":
                if prev != "snip":
                    self._prev_mode = prev
                hide_all()
                if snip is not None:
                    snip.show()
            elif mode == "mini":
                hide_all()
                mini.show()
                self._restore_default_size("mini")
                self._place_mini_default()
            elif mode == "translate":
                hide_all()
                translate.show()
                self._restore_default_size("translate")
                self._place_translate_default()
            else:
                hide_all()
                overlay.show()
                self._restore_default_size("overlay")
            self.cfg["mode"] = mode
            cfgmod.save_config(self.cfg)

        run_in_main(do)
        if fresh_snip:
            # 按需创建的框选窗口由 Qt 异步建好,稍后再显示(此时 snip 对象才真正可用)
            def show_snip_later():
                time.sleep(0.7)
                win = self.snip
                if win is not None:
                    run_in_main(lambda: win.show())
            threading.Thread(target=show_snip_later, daemon=True).start()
        if self._last_result:
            def replay():
                time.sleep(1.6)
                self.push({"type": "result", "data": self._last_result})
            threading.Thread(target=replay, daemon=True).start()
        if mode != "translate":
            self._stop_auto_refresh()
        # 翻译模式:窗口消失前先记录位置
        if prev == "translate" and mode != "translate":
            win_cfg = self.cfg.setdefault("window", {})
            try:
                win_cfg["translate_x"], win_cfg["translate_y"] = int(self.translate.x), int(self.translate.y)
            except Exception:
                pass
        self.push({"type": "config", "config": self.cfg})

    # ================= 模式尺寸(各模式互相独立) =================
    def _restore_default_size(self, mode: str):
        """进入某个模式时,把该模式窗口恢复成「它自己」的尺寸。

        各模式的尺寸分别存放在 window.width/height(悬浮窗)、window.miniWidth/miniHeight
        (迷你条)、window.translateWidth/translateHeight(翻译窗)三组键里,互不干扰;
        这样在迷你条里拉伸/拖动不会污染悬浮窗尺寸,切回原模式也能拿回原来的大小。
        迷你条高度恒定,永远按 defaultMiniHeight 校正。
        """
        win_cfg = self.cfg.get("window") or {}
        if mode == "mini":
            win = self.mini
            w = max(320, int(win_cfg.get("miniWidth", 420)))
            # 高度用前端实测并锁定的 miniHeight(随字号/主题自适应),没有则退回默认值
            h = max(56, int(win_cfg.get("miniHeight") or win_cfg.get("defaultMiniHeight", 78)))
        elif mode == "translate":
            win = self.translate
            w = max(480, int(win_cfg.get("translateWidth", 760)))
            h = max(360, int(win_cfg.get("translateHeight", 620)))
        elif mode == "overlay":
            win = self.overlay
            w = max(360, int(win_cfg.get("width", 640)))
            h = max(260, int(win_cfg.get("height", 680)))
        else:
            return
        if win is None:
            return
        try:
            if (int(win.width), int(win.height)) != (w, h):
                win.resize(w, h)
        except Exception:
            pass

    def reset_window_sizes(self) -> dict:
        """把所有模式的窗口尺寸恢复成默认值(供设置页「恢复默认尺寸」使用)。"""
        win_cfg = self.cfg.setdefault("window", {})
        win_cfg["width"] = int(win_cfg.get("defaultWidth", 640))
        win_cfg["height"] = int(win_cfg.get("defaultHeight", 680))
        win_cfg["miniWidth"] = int(win_cfg.get("defaultMiniWidth", 420))
        # 迷你条高度不在这里重置:它由前端实测内容高度后锁定(随字号/主题自适应)
        win_cfg["translateWidth"] = int(win_cfg.get("defaultTranslateWidth", 760))
        win_cfg["translateHeight"] = int(win_cfg.get("defaultTranslateHeight", 620))
        cfgmod.save_config(self.cfg)

        def do():
            for m in ("overlay", "mini", "translate"):
                self._restore_default_size(m)

        run_in_main(do)
        self.push({"type": "config", "config": self.cfg})
        return dict(win_cfg)

    def set_mini_height(self, h) -> bool:
        """锁定迷你条高度为前端实测的自然高度(字号/主题/内容变化时由前端上报)。

        迷你条不允许上下拉伸,高度必须由内容决定;写死在配置里的固定值会在
        用户放大字号后把第二行(提问输入)裁掉。
        """
        try:
            want = int(round(float(h)))
        except Exception:
            return False
        want = max(56, min(240, want))
        win_cfg = self.cfg.setdefault("window", {})
        if int(win_cfg.get("miniHeight") or 0) != want:
            win_cfg["miniHeight"] = want
            cfgmod.save_config(self.cfg)
        if self.mini is None:
            return True
        try:
            if int(self.mini.height) != want:
                run_in_main(lambda: self.mini.resize(int(self.mini.width), want))
        except Exception:
            pass
        return True

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
            w = int(win_cfg.get("miniWidth", 420))
            h = int(win_cfg.get("miniHeight", 78))
            x = int(g.x() + (g.width() - w) / 2)
            y = int(g.y() + g.height() - h - 18)
            self.mini.move(x, y)
            win_cfg["mini_x"], win_cfg["mini_y"] = x, y
            cfgmod.save_config(self.cfg)
        except Exception:
            pass

    # ================= 翻译窗口默认位置(工作区右侧居中) =================
    def _place_translate_default(self):
        win_cfg = self.cfg.setdefault("window", {})
        if win_cfg.get("translate_x") is not None and win_cfg.get("translate_y") is not None:
            return
        try:
            from PySide6.QtGui import QGuiApplication
            g = QGuiApplication.primaryScreen().availableGeometry()
            w = int(win_cfg.get("translateWidth", 760))
            h = int(win_cfg.get("translateHeight", 620))
            x = int(g.x() + (g.width() - w) / 2)
            y = int(g.y() + max(12, (g.height() - h) / 2))
            self.translate.move(x, y)
            win_cfg["translate_x"], win_cfg["translate_y"] = x, y
            cfgmod.save_config(self.cfg)
        except Exception:
            pass

    # ================= 窗口拖动(受控拖拽) =================
    def _win(self, which: str):
        return {"overlay": self.overlay, "mini": self.mini, "translate": self.translate}.get(which)

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
            elif which == "translate":
                win_cfg["translate_x"], win_cfg["translate_y"] = int(pos[0]), int(pos[1])
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
        # 同时记录窗口「非洞口」部分的高度(标题栏+底部面板),供"设为悬浮窗区域"换算窗口尺寸
        try:
            inner_h = int(rect.get("innerH") or 0)
            if inner_h > h > 0:
                self.cfg.setdefault("window", {})["chromeHeight"] = inner_h - h
                self.cfg["window"]["holeWidth"] = w
                self.cfg["window"]["holeHeight"] = h
        except Exception:
            pass
        key = (x, y, w, h)
        if key == self._hole_key:
            return True
        self._hole_key = key
        run_in_main(lambda: self._apply_region(x, y, w, h))
        return True

    # ================= 窗口缩放(拖拽边框) =================
    def resize_begin(self, which: str, edge: str, sx: float, sy: float) -> bool:
        win = self._win(which)
        if win is None or not edge:
            return False
        try:
            self._resize = {"which": which, "edge": str(edge), "x": float(win.x), "y": float(win.y),
                            "w": float(win.width), "h": float(win.height),
                            "px": float(sx), "py": float(sy), "last": None}
            return True
        except Exception:
            self._resize = None
            return False

    def resize_move(self, which: str, sx: float, sy: float) -> bool:
        d = self._resize
        win = self._win(which)
        if not d or win is None or d.get("which") != which:
            return False
        dx = float(sx) - d["px"]
        dy = float(sy) - d["py"]
        edge = d["edge"]
        minw, minh = (360, 260) if which == "overlay" else (360, 78)
        x, y, w, h = d["x"], d["y"], d["w"], d["h"]
        if "e" in edge:
            w = max(minw, w + dx)
        if "s" in edge and which != "mini":   # 迷你条高度固定,不响应上下拉伸
            h = max(minh, h + dy)
        if "w" in edge:
            nw = max(minw, w - dx)
            x += w - nw
            w = nw
        if "n" in edge:
            nh = max(minh, h - dy)
            y += h - nh
            h = nh
        key = (int(round(x)), int(round(y)), int(round(w)), int(round(h)))
        if d.get("last") == key:
            return True
        d["last"] = key
        run_in_main(lambda: (win.move(key[0], key[1]), win.resize(key[2], key[3])))
        return True

    def resize_end(self, which: str) -> bool:
        d = self._resize
        self._resize = None
        win = self._win(which)
        if not d or win is None:
            return False
        switch_to = ""
        try:
            pos = d.get("last") or (int(win.x), int(win.y), int(win.width), int(win.height))
            win_cfg = self.cfg.setdefault("window", {})
            if which == "translate":
                win_cfg["translate_x"], win_cfg["translate_y"] = pos[0], pos[1]
                win_cfg["translateWidth"], win_cfg["translateHeight"] = pos[2], pos[3]
            elif which == "mini":
                # 注意:迷你条必须写回 mini_* 键,否则会污染悬浮窗尺寸(此前表现为迷你条高度乱变且无法还原)
                win_cfg["mini_x"], win_cfg["mini_y"] = pos[0], pos[1]
                win_cfg["miniWidth"] = pos[2]
                win_cfg["miniHeight"] = int(win_cfg.get("defaultMiniHeight", 78))
            else:
                win_cfg["x"], win_cfg["y"] = pos[0], pos[1]
                win_cfg["width"], win_cfg["height"] = pos[2], pos[3]
                win_cfg["holeWidth"] = max(120, pos[2] - 4)
                win_cfg["holeHeight"] = max(80, pos[3] - int(win_cfg.get("chromeHeight") or 300))
            # 缩到最小 → 迷你条;迷你条拉伸过大 → 悬浮窗
            min_w, min_h = (420, 300) if which == "overlay" else (0, 0)
            max_w = 560
            if which == "overlay" and (pos[2] < min_w or pos[3] < min_h):
                switch_to = "mini"
            elif which == "mini" and pos[2] > max_w:
                switch_to = "overlay"
            cfgmod.save_config(self.cfg)
        except Exception:
            pass
        self.push({"type": "config", "config": self.cfg})
        if switch_to:
            self.push({"type": "status", "text": "已切换到" + ("迷你条模式" if switch_to == "mini" else "悬浮窗模式"),
                       "tone": "ok"})
            self.set_mode(switch_to)
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
        win = self._ensure_settings()

        def do():
            try:
                win.show()
            except Exception:
                pass

        run_in_main(do)

    def close_settings(self):
        if self.settings is None:
            return
        run_in_main(lambda: self.settings.hide())

    # ================= 自由截图 =================
    def start_snip(self):
        self.set_mode("snip")

    def cancel_snip(self):
        back = self._prev_mode if self._prev_mode in ("mini", "overlay", "translate") else \
            (self.cfg.get("mode") if self.cfg.get("mode") in ("mini", "translate") else "overlay")
        self.set_mode(back)

    def finish_snip(self, sel: dict, action: str = "run", question: str = ""):
        """完成框选:隐藏遮罩 → 抓取区域 → 识别 / 翻译 / 设为悬浮窗区域。"""
        dpr = float(sel.get("dpr") or 1)
        vs = virtual_screen()
        left = int(vs["left"] + sel["x"] * dpr)
        top = int(vs["top"] + sel["y"] * dpr)
        w = int(sel["w"] * dpr)
        h = int(sel["h"] * dpr)

        if self.snip is not None:
            run_in_main(lambda: self.snip.hide())
        time.sleep(max(0.06, int(self.cfg["capture"].get("flash_delay_ms", 80)) / 1000.0 + 0.05))
        try:
            png = grab_region(left, top, w, h)
        except CaptureError as exc:
            self.push({"type": "error", "text": str(exc)})
            png = None

        if action == "region":
            win_cfg = self.cfg.setdefault("window", {})
            win_cfg["holeWidth"] = max(160, w)
            win_cfg["holeHeight"] = max(120, h)
            self.cfg["mode"] = "overlay"
            cfgmod.save_config(self.cfg)
            self.push({"type": "status", "text": "已设为悬浮窗区域", "tone": "ok"})
            # 窗口尺寸 = 洞口 + 标题栏/底部面板:由前端按实际渲染高度换算后调用 resize_main
            self.push({"type": "config", "config": self.cfg, "applyHole": True})

            def do():
                for w in (self.snip, self.mini, self.translate):
                    if w is not None:
                        try:
                            w.hide()
                        except Exception:
                            pass
                self.overlay.show()

            run_in_main(do)
            return

        # 记住本次框选区域,供翻译模式反复捕获/自动刷新
        self.cfg.setdefault("capture", {})["last_rect"] = {
            "left": left, "top": top, "w": w, "h": h, "dpr": dpr,
        }
        cfgmod.save_config(self.cfg)

        if action == "translate":
            self._translate_mode = True
            self.set_mode("translate")
            if png:
                self._run(png, question, task="translate")
            self.push({"type": "config", "config": self.cfg})
            return

        self.cancel_snip()
        if png:
            self._run(png, question)

    # ================= 翻译模式 =================
    def run_capture_last(self, question: str = ""):
        """复用上次框选区域直接识别(迷你条快速识别);没有记录则进入框选。"""
        rect = (self.cfg.get("capture") or {}).get("last_rect")
        if not rect:
            self.start_snip()
            return
        try:
            png = grab_region(int(rect["left"]), int(rect["top"]), int(rect["w"]), int(rect["h"]))
        except CaptureError as exc:
            self.push({"type": "error", "text": str(exc)})
            return
        self._run(png, question)

    def run_translate(self, question: str = ""):
        """重新捕获上一次框选区域并翻译(翻译模式的主操作)。"""
        rect = (self.cfg.get("capture") or {}).get("last_rect")
        if not rect:
            self.push({"type": "error", "text": "还没有捕获区域:请先框选一次要翻译的内容"})
            self.start_snip_translate()
            return
        self.push({"type": "status", "text": "正在捕获区域…", "tone": "working"})
        # 关键:翻译窗口是不透明的,必须先隐藏自身再截图,否则会把本程序界面一起拍进去
        png = self._grab_with_windows_hidden(rect)
        if png is None:
            return
        self._translate_mode = True
        self._run(png, question, task="translate")

    def _grab_with_windows_hidden(self, rect: dict):
        """截图前隐藏本程序的窗口(翻译窗/迷你条),避免拍到自身界面。"""
        delay = max(0.08, int(self.cfg["capture"].get("flash_delay_ms", 80)) / 1000.0 + 0.06)
        hidden = []

        def hide():
            for name, win in (("translate", self.translate), ("mini", self.mini)):
                try:
                    if win is not None and win.visible:
                        win.hide()
                        hidden.append(win)
                except Exception:
                    pass

        run_in_main(hide)
        time.sleep(delay)
        try:
            return grab_region(int(rect["left"]), int(rect["top"]), int(rect["w"]), int(rect["h"]))
        except CaptureError as exc:
            self.push({"type": "error", "text": str(exc)})
            return None
        finally:
            def restore():
                for win in hidden:
                    try:
                        win.show()
                    except Exception:
                        pass
            run_in_main(restore)

    def start_snip_translate(self):
        self._prev_mode = "translate"
        self.set_mode("snip")

    # ---- 自动刷新(定时重新捕获并翻译,适合字幕/连续内容) ----
    def set_auto_refresh(self, on: bool) -> bool:
        self.cfg.setdefault("translate", {})["auto_refresh"] = bool(on)
        cfgmod.save_config(self.cfg)
        if on:
            self._start_auto_refresh()
        else:
            self._stop_auto_refresh()
        self.push({"type": "config", "config": self.cfg})
        return True

    def _start_auto_refresh(self):
        if self._auto_thread and self._auto_thread.is_alive():
            return
        self._auto_stop.clear()

        def loop():
            while not self._auto_stop.wait(max(0.8, int(self.cfg.get("translate", {}).get(
                    "auto_interval_ms", 2500)) / 1000.0)):
                if self.cfg.get("mode") != "translate":
                    break
                if self._worker and self._worker.is_alive():
                    continue
                try:
                    self.run_translate("")
                except Exception:
                    pass

        self._auto_thread = threading.Thread(target=loop, daemon=True, name="auto-refresh")
        self._auto_thread.start()

    def _stop_auto_refresh(self):
        self._auto_stop.set()

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

    def _run(self, png: bytes, question: str = "", task: str = "answer"):
        with self._lock:
            if self._worker and self._worker.is_alive():
                return
            prov = cfgmod.active_provider(self.cfg)
            ocr_mode = self.cfg.get("ocr", {}).get("mode", "cloud")
            tr_cfg = dict(self.cfg.get("translate") or {})
            # 翻译模式下:OCR 与翻译都走端侧时,不需要 API Key(完全离线)
            need_key = not (task == "translate" and ocr_mode == "local"
                            and tr_cfg.get("mode", "cloud") == "local")
            if need_key and not (prov.get("api_key") or "").strip():
                self.push({"type": "error", "text": "未配置 API Key:请在「设置 → 模型设置」填写,"
                                                   "或把 OCR/翻译都切换为端侧"})
                return
            tr_cfg["ollama_url"] = self._local_ollama_url()
            tr_cfg["ollama_model"] = self._local_ollama_model()
            client = AgentClient(
                prov.get("api_key", ""), prov.get("model", ""), prov.get("base_url", ""),
                self.cfg.get("request_template", ""),
                timeout=int(self.cfg.get("timeout", 180)),
                max_side=int(self.cfg["capture"].get("max_side", 2048)),
                max_retries=int(self.cfg["retry"].get("max_retries", 3)),
                backoff=float(self.cfg["retry"].get("backoff", 0.8)),
                enable_thinking=bool(prov.get("enable_thinking", False)),
                supports_thinking=str(prov.get("id", "")) in cfgmod.THINKING_PROVIDER_IDS,
            )
            prompts = self.cfg.get("prompts", {})
            from app.worker import PipelineWorker
            self.push({"type": "busy", "value": True})
            self._worker = PipelineWorker(
                client, png, prompts.get("ocr", ""),
                prompts.get("translate" if task == "translate" else "answer", ""),
                question, self.cfg.get("knowledge", []),
                ocr_mode,
                on_status=lambda t, tone: self.push({"type": "status", "text": t, "tone": tone}),
                on_result=self._on_result,
                on_error=lambda t: self.push({"type": "error", "text": t}),
                task=task, translate=tr_cfg,
            )
            self._worker.start()

    def _local_ollama_url(self) -> str:
        for p in self.cfg.get("providers", []):
            if "ollama" in str(p.get("id", "")).lower() or "11434" in str(p.get("base_url", "")):
                return p.get("base_url", "")
        return ""

    def _local_ollama_model(self) -> str:
        for p in self.cfg.get("providers", []):
            if "ollama" in str(p.get("id", "")).lower() or "11434" in str(p.get("base_url", "")):
                return p.get("model", "")
        return ""

    def _on_result(self, data: dict):
        self._last_result = data
        self.push({"type": "result", "data": data})
        self.push({"type": "history", "data": history.load()})
        self._save_outputs(data)

    def last_result(self) -> dict:
        """最近一次结果:窗口(尤其翻译窗)刚显示时页面可能还没就绪,事件会丢,故支持主动回拉。"""
        return self._last_result or {}

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
