# -*- coding: utf-8 -*-
"""前端(pywebview)与 Python 后端之间的 API 桥。

前端通过 window.pywebview.api.<method>(...) 调用,返回值需可 JSON 序列化。
"""
import json
import threading
import time
from pathlib import Path

import webview

from app import config as cfgmod
from app import history, request_log
from app.agent import AgentClient
from app.mainthread import run_in_main

COLOR_KEYS = ("bg", "card", "panel", "fg", "muted", "line", "accent", "accentFg",
              "ok", "warn", "danger")


def _get_path(cfg: dict, path: str, default=None):
    node = cfg
    for part in path.split("."):
        if not isinstance(node, dict) or part not in node:
            return default
        node = node[part]
    return node


def _set_path(cfg: dict, path: str, value):
    parts = path.split(".")
    node = cfg
    for part in parts[:-1]:
        node = node.setdefault(part, {})
    node[parts[-1]] = value


class Api:
    def __init__(self, app):
        self.app = app

    # ================= 状态 =================
    def get_state(self) -> dict:
        cfg = self.app.cfg
        prov = cfgmod.active_provider(cfg)
        return {
            "config": cfg,
            "version": cfg.get("app", {}).get("version", "2.0.0"),
            "key_ready": bool((prov.get("api_key") or "").strip()),
            "history": history.load(),
            "mode": cfg.get("mode", "overlay"),
        }

    def save_ui(self, patch: dict) -> bool:
        cfg = self.app.cfg
        cfg.setdefault("ui", {}).update(patch or {})
        cfgmod.save_config(cfg)
        self.app.push({"type": "config", "config": cfg})
        return True

    def set_config_value(self, path: str, value):
        cfg = self.app.cfg
        _set_path(cfg, path, value)
        cfgmod.save_config(cfg)
        self.app.push({"type": "config", "config": cfg})
        return True

    def pick_directory(self):
        try:
            res = webview.windows[0].create_file_dialog(webview.FOLDER_DIALOG)
            if res:
                return res[0] if isinstance(res, (list, tuple)) else res
        except Exception:
            pass
        return None

    def open_config_file(self):
        self.app.open_path(str(cfgmod.CONFIG_PATH))

    def open_data_dir(self):
        self.app.open_path(str(cfgmod.ROOT))

    def open_url(self, url: str):
        self.app.open_url(url)

    # ================= 平台管理 =================
    def list_providers(self) -> dict:
        cfg = self.app.cfg
        items = []
        for i, p in enumerate(cfg.get("providers", [])):
            items.append({"i": i, "id": p.get("id"), "name": p.get("name"),
                          "color": p.get("color", "#8b94a7"),
                          "ready": bool((p.get("api_key") or "").strip())})
        ids = [p.get("id") for p in cfg.get("providers", [])]
        active = cfg.get("active_provider")
        return {"list": items, "active": active,
                "index": ids.index(active) if active in ids else 0}

    def provider_get(self, i: int) -> dict:
        cfg = self.app.cfg
        provs = cfg.get("providers", [])
        if not (0 <= int(i) < len(provs)):
            return {"provider": {}, "preview": ""}
        return {"provider": provs[int(i)], "preview": self.provider_preview(i)}

    def provider_set(self, i: int, field: str, value) -> bool:
        cfg = self.app.cfg
        provs = cfg.get("providers", [])
        if not (0 <= int(i) < len(provs)):
            return False
        if field in ("api_key", "model", "base_url", "note", "homepage", "name") and isinstance(value, str):
            value = value.strip()
        provs[int(i)][field] = value
        cfgmod.save_config(cfg)
        return True

    def provider_add(self) -> int:
        cfg = self.app.cfg
        n = len(cfg.get("providers", []))
        cfg.setdefault("providers", []).append({
            "id": f"custom{int(time.time())}", "name": f"自定义平台{n + 1}",
            "color": "#8b94a7", "logo": "", "note": "", "homepage": "",
            "api_key": "", "base_url": "", "model": "", "enable_thinking": False,
        })
        cfgmod.save_config(cfg)
        return n

    def provider_remove(self, i: int) -> bool:
        cfg = self.app.cfg
        provs = cfg.get("providers", [])
        if not (0 <= int(i) < len(provs)):
            return False
        removed = provs.pop(int(i))
        if cfg.get("active_provider") == removed.get("id"):
            cfg["active_provider"] = provs[0].get("id", "") if provs else ""
        cfgmod.save_config(cfg)
        self.app.push({"type": "config", "config": cfg})
        return True

    def set_active_provider(self, pid: str) -> bool:
        cfg = self.app.cfg
        if any(p.get("id") == pid for p in cfg.get("providers", [])):
            cfg["active_provider"] = pid
            cfgmod.save_config(cfg)
            self.app.push({"type": "config", "config": cfg})
            return True
        return False

    def provider_preview(self, i: int) -> str:
        """按当前平台字段生成 JSON 请求预览。"""
        cfg = self.app.cfg
        provs = cfg.get("providers", [])
        if not (0 <= int(i) < len(provs)):
            return ""
        p = provs[int(i)]
        body = (cfg.get("request_template", "")
                .replace("{model}", json.dumps(p.get("model", ""), ensure_ascii=False))
                .replace("{prompt}", json.dumps("…提示词…", ensure_ascii=False))
                .replace("{image_url}", json.dumps("data:image/png;base64,…", ensure_ascii=False)))
        import re
        body = re.sub(r'"enable_thinking"\s*:\s*(true|false)',
                      f'"enable_thinking": {str(bool(p.get("enable_thinking"))).lower()}', body)
        try:
            return json.dumps(json.loads(body), ensure_ascii=False, indent=2)
        except Exception:
            return body

    def get_template(self) -> str:
        return self.app.cfg.get("request_template", "")

    def set_template(self, text: str) -> bool:
        try:
            probe = (text or "").replace("{model}", '"m"').replace("{prompt}", '"p"').replace("{image_url}", '"u"')
            json.loads(probe)
        except Exception as exc:
            return f"模板无效:{exc}"
        self.app.cfg["request_template"] = text
        cfgmod.save_config(self.app.cfg)
        return True

    def test_connection(self, i: int) -> dict:
        """连通性测试:后台线程执行,结果通过 conn 事件推送给前端(避免阻塞界面)。"""
        threading.Thread(target=self._test_connection, args=(int(i),), daemon=True).start()
        return {"started": True}

    def _test_connection(self, i: int):
        cfg = self.app.cfg
        provs = cfg.get("providers", [])
        if not (0 <= i < len(provs)):
            self.app.push({"type": "conn", "i": i, "ok": False, "ms": 0, "message": "平台不存在"})
            return
        p = provs[i]
        if not (p.get("api_key") or "").strip():
            self.app.push({"type": "conn", "i": i, "ok": False, "ms": 0, "message": "未配置 API Key"})
            return
        t0 = time.time()
        client = AgentClient(p.get("api_key", ""), p.get("model", ""), p.get("base_url", ""),
                             timeout=min(int(cfg.get("timeout", 180)), 20))
        msg = client.test_connection()
        ms = int((time.time() - t0) * 1000)
        self.app.push({"type": "conn", "i": i, "ok": msg.startswith("连接成功"), "ms": ms, "message": msg})

    # ================= 主题 =================
    def export_theme(self, theme_json: str) -> bool:
        try:
            win = self.app.settings or self.app.overlay
            res = win.create_file_dialog(webview.SAVE_DIALOG, save_filename="ocr-assistant-theme.json")
            if not res:
                return False
            path = res if isinstance(res, str) else res[0]
            Path(path).write_text(theme_json, encoding="utf-8")
            return True
        except Exception:
            return False

    def import_theme(self):
        try:
            win = self.app.settings or self.app.overlay
            res = win.create_file_dialog(webview.OPEN_DIALOG, allow_multiple=False,
                                         file_types=("主题文件 (*.json)", "所有文件 (*.*)"))
            if not res:
                return None
            path = res if isinstance(res, str) else res[0]
            return Path(path).read_text(encoding="utf-8")
        except Exception:
            return None

    # ================= 识别与窗口 =================
    def run_pipeline_rect(self, rect: dict, question: str = "") -> bool:
        self.app.push({"type": "busy", "value": True})
        self.app.run_pipeline_rect(rect or {}, question or "")
        return True

    def set_mode(self, mode: str) -> bool:
        self.app.set_mode(mode)
        return True

    # ================= 窗口拖动 / 洞口穿透 =================
    def drag_begin(self, which: str, sx: float, sy: float) -> bool:
        return self.app.drag_begin(which, sx, sy)

    def drag_move(self, which: str, sx: float, sy: float) -> bool:
        return self.app.drag_move(which, sx, sy)

    def drag_end(self, which: str) -> bool:
        return self.app.drag_end(which)

    def set_hole_region(self, rect: dict) -> bool:
        return self.app.set_hole_region(rect or {})

    def resize_begin(self, which: str, edge: str, sx: float, sy: float) -> bool:
        return self.app.resize_begin(which, edge, sx, sy)

    def resize_move(self, which: str, sx: float, sy: float) -> bool:
        return self.app.resize_move(which, sx, sy)

    def resize_end(self, which: str) -> bool:
        return self.app.resize_end(which)

    # ================= 翻译模式 =================
    def run_translate(self, question: str = "") -> bool:
        threading.Thread(target=self.app.run_translate, args=(question or "",), daemon=True).start()
        return True

    def run_mini_capture(self, question: str = "") -> bool:
        """迷你条快速识别:复用上次框选区域,没有则进入框选。"""
        threading.Thread(target=self.app.run_capture_last, args=(question or "",), daemon=True).start()
        return True

    def snip_translate(self):
        self.app.start_snip_translate()

    def set_auto_refresh(self, on: bool) -> bool:
        return self.app.set_auto_refresh(bool(on))

    def languages(self) -> dict:
        return {"list": list(cfgmod.LANGUAGES), "codes": dict(cfgmod.LANG_CODES)}

    def translate_status(self) -> dict:
        from app import local_translate
        st = local_translate.status(self.app._local_ollama_url())  # noqa: SLF001
        st["source_lang"] = self.app.cfg.get("translate", {}).get("source_lang")
        st["target_lang"] = self.app.cfg.get("translate", {}).get("target_lang")
        return st

    def install_translate_pack(self, source_lang: str, target_lang: str) -> bool:
        threading.Thread(target=self._install_pack, args=(source_lang, target_lang),
                         daemon=True).start()
        return True

    def _install_pack(self, source_lang: str, target_lang: str):
        from app import local_translate
        self.app.push({"type": "status", "text": "正在下载端侧语言包…", "tone": "working"})
        msg = local_translate.install_argos_pack(source_lang, target_lang)
        ok = "安装完成" in msg or "已存在" in msg
        self.app.push({"type": "pack", "ok": ok, "message": msg})
        self.app.push({"type": "status", "text": msg, "tone": "ok" if ok else "danger"})

    # ================= 端侧模型(按需下载) =================
    def local_models_status(self) -> dict:
        from app import local_models
        cfg_tr = self.app.cfg.get("translate") or {}
        st = local_models.summary()
        st["mt"] = local_models.mt_status(cfg_tr.get("source_lang", "自动检测"),
                                          cfg_tr.get("target_lang", "中文"))
        st["ocr_local"] = self.app.cfg.get("ocr", {}).get("mode", "cloud") == "local"
        st["mt_local"] = (cfg_tr.get("mode") or "cloud") == "local"
        return st

    def download_local_model(self, kind: str) -> bool:
        """kind: ocr / runtime / mt"""
        threading.Thread(target=self._download_model, args=(str(kind),), daemon=True).start()
        return True

    def _download_model(self, kind: str):
        from app import local_models
        cfg_tr = self.app.cfg.get("translate") or {}

        def progress(pct, text):
            self.app.push({"type": "download", "kind": kind, "pct": int(pct), "text": text})

        try:
            self.app.push({"type": "download", "kind": kind, "pct": 0, "text": "准备下载…"})
            if kind == "ocr":
                msg = local_models.download_ocr(progress)
            elif kind == "runtime":
                msg = local_models.download_runtime(progress)
            elif kind == "mt":
                msg = local_models.download_mt(cfg_tr.get("source_lang", "英语"),
                                               cfg_tr.get("target_lang", "中文"), progress)
            else:
                msg = "未知的模型类型"
            self.app.push({"type": "download", "kind": kind, "pct": 100, "done": True, "message": msg})
            self.app.push({"type": "status", "text": msg, "tone": "ok"})
        except Exception as exc:  # noqa: BLE001
            self.app.push({"type": "download", "kind": kind, "pct": 0, "done": True,
                           "error": str(exc)})
            self.app.push({"type": "status", "text": str(exc), "tone": "danger"})

    def remove_local_model(self, kind: str) -> str:
        from app import local_models
        return local_models.remove(str(kind))

    # ================= 提问记忆(自输入自动保存) =================
    def remember_question(self, text: str) -> list:
        text = (text or "").strip()
        beh = self.app.cfg.setdefault("behavior", {})
        hist = [q for q in (beh.get("question_history") or []) if q != text]
        if text:
            hist.insert(0, text)
        beh["question_history"] = hist[:20]
        cfgmod.save_config(self.app.cfg)
        return beh["question_history"]

    def start_snip(self):
        self.app.start_snip()

    def finish_snip(self, sel: dict, action: str = "run", question: str = ""):
        self.app.finish_snip(sel or {}, action, question or "")

    def cancel_snip(self):
        self.app.cancel_snip()

    def resize_main(self, w: int, h: int) -> bool:
        try:
            return self.app.resize_overlay(w, h)
        except Exception:
            return False

    def move_main(self, x: int, y: int) -> bool:
        try:
            run_in_main(lambda: self.app.overlay.move(int(x), int(y)))
            return True
        except Exception:
            return False

    def set_topmost(self, on: bool) -> bool:
        try:
            on = bool(on)

            def do():
                try:
                    self.app.overlay.on_top = on
                    self.app.mini.on_top = on
                except Exception:
                    pass

            run_in_main(do)
            self.app.cfg["window"]["always_on_top"] = on
            cfgmod.save_config(self.app.cfg)
            return True
        except Exception:
            return False

    def open_settings(self):
        self.app.open_settings()

    def close_settings(self):
        self.app.close_settings()

    def quit_app(self):
        self.app.quit_app()

    # ================= 历史 / 记录 =================
    def history_list(self) -> list:
        return history.load()

    def history_clear(self) -> bool:
        history.clear()
        self.app.push({"type": "history", "data": []})
        return True

    def request_log_days(self) -> dict:
        return request_log.day_counts(140)
