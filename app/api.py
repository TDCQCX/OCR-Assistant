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


def _dialog(kind: str):
    """pywebview 新版用 FileDialog 枚举,旧版是模块级常量;这里做兼容。"""
    fd = getattr(webview, "FileDialog", None)
    if fd is not None:
        return getattr(fd, kind)
    return getattr(webview, f"{kind}_DIALOG")

def _set_path(cfg: dict, path: str, value):
    parts = path.split(".")
    node = cfg
    for part in parts[:-1]:
        node = node.setdefault(part, {})
    node[parts[-1]] = value


class Api:
    def __init__(self, app):
        self.app = app

    def __dir__(self):
        """只把公开的桥接方法暴露给 pywebview。

        pywebview 注入 JS API 时会对 js_api 做 dir() 递归扫描:非可调用且带
        __module__ 的属性会被继续递归。我们的 Api 持有 App → 模式窗口 → 后端原生
        控件(WebEngine/.NET)的整张对象图,实测每个窗口要扫 213 个对象 / 1.1 万个属性
        (21ms),换用 WebView2 后端时更会因 .NET/COM 对象爆栈。这里只返回公开方法名,
        既去掉这段无用扫描,也让桥接面更明确。
        """
        names = []
        for klass in type(self).__mro__:
            for name, value in vars(klass).items():
                if name.startswith("_") or name in names:
                    continue
                if callable(value):
                    names.append(name)
        return sorted(names)

    # ================= 状态 =================
    def get_state(self) -> dict:
        cfg = self.app.cfg
        prov = cfgmod.active_provider(cfg)
        return {
            "config": cfg,
            "version": cfgmod.APP_VERSION,
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
        # 从端侧切回云端时,把常驻的端侧模型释放掉(否则一直占着几百 MB~2.4GB)
        if str(path) == "translate.mode" and str(value) != "local":
            self._release_local_models("已切回云端翻译,已释放端侧模型")
        elif str(path) == "ocr.mode" and str(value) != "local":
            self._release_local_models("已切回云端识别,已释放端侧模型")
        self.app.push({"type": "config", "config": cfg})
        return True

    def _release_local_models(self, note: str = "") -> int:
        """释放端侧识别/翻译模型的常驻内存(OCR 侧只有加载日志,不驻留大对象)。"""
        freed = 0
        try:
            from app import local_mt
            freed = local_mt.release()
        except Exception:
            freed = 0
        if freed and note:
            self.app.push({"type": "status", "text": note, "tone": "ok"})
        return freed

    def loaded_local_models(self) -> dict:
        """当前常驻内存的端侧模型档位(设置页显示/验证用)。"""
        try:
            from app import local_mt
            return {"mt": local_mt.loaded_tiers()}
        except Exception:
            return {"mt": []}

    def pick_directory(self):
        try:
            res = webview.windows[0].create_file_dialog(_dialog('FOLDER'))
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
        active = cfg.get("active_provider")
        items = []
        for i, p in enumerate(cfg.get("providers", [])):
            items.append({"i": i, "id": p.get("id"), "name": p.get("name"),
                          "color": p.get("color", "#8b94a7"),
                          "ready": cfgmod.provider_ready(p),
                          "has_model": bool((p.get("model") or "").strip()),
                          "active": p.get("id") == active})
        ids = [p.get("id") for p in cfg.get("providers", [])]
        return {"list": items, "active": active,
                "index": ids.index(active) if active in ids else 0}

    def provider_get(self, i: int) -> dict:
        cfg = self.app.cfg
        provs = cfg.get("providers", [])
        if not (0 <= int(i) < len(provs)):
            return {"provider": {}, "preview": "", "hints": {}}
        prov = provs[int(i)]
        # 带上该平台的常用模型 ID(配置里的 providers 是列表,不会随默认配置补齐,故按 id 回查预设)
        models = list(prov.get("models") or []) or cfgmod.models_for(prov.get("id"))
        return {"provider": prov, "preview": self.provider_preview(i),
                "hints": {}, "models": models}

    def reset_provider_defaults(self, i: int) -> bool:
        """把某个平台的 Base URL / 模型还原为预设默认值(用户改坏地址后一键恢复)。"""
        cfg = self.app.cfg
        provs = cfg.get("providers", [])
        if not (0 <= int(i) < len(provs)):
            return False
        prov = provs[int(i)]
        preset = next((p for p in cfgmod.PROVIDER_PRESETS if p.get("id") == prov.get("id")), None)
        if not preset:
            return False
        prov["base_url"] = preset.get("base_url", "")
        if not (prov.get("model") or "").strip():
            prov["model"] = preset.get("model", "")
        cfgmod.save_config(cfg)
        self.app.push({"type": "config", "config": cfg})
        return True

    def reset_template(self) -> str:
        """把 JSON 请求模板还原为默认模板。"""
        self.app.cfg["request_template"] = cfgmod.DEFAULT_REQUEST_TEMPLATE
        cfgmod.save_config(self.app.cfg)
        return cfgmod.DEFAULT_REQUEST_TEMPLATE

    def reset_window_sizes(self) -> dict:
        """把悬浮窗/迷你条/翻译窗的尺寸全部恢复为默认值。"""
        return self.app.reset_window_sizes()

    def set_mini_height(self, h) -> bool:
        """前端上报迷你条内容自然高度,由后端锁定窗口高度。"""
        return self.app.set_mini_height(h)

    # ================= 新手教程 =================
    def guide_begin(self, mode: str) -> bool:
        """教程开始:临时清掉洞口穿透区域 / 给迷你条加高,让气泡可见可点。"""
        return self.app.guide_begin(str(mode))

    def guide_end(self, mode: str) -> bool:
        """教程结束:恢复洞口穿透区域与迷你条高度。"""
        return self.app.guide_end(str(mode))

    def guide_start(self, mode: str) -> bool:
        """从任意入口(设置页/各模式的「新手教程」按钮)发起某个模式的引导。

        需要先把对应模式的窗口显示出来,再记为待引导并广播 guideStart 事件。
        """
        mode = str(mode or "")
        if mode in ("overlay", "mini", "translate", "snip"):
            self.app.set_mode(mode)
        self.app._guide_pending = mode

        def later():
            time.sleep(0.45)   # 等窗口显示/页面就绪
            self.app.push({"type": "guideStart", "mode": mode})

        threading.Thread(target=later, daemon=True).start()
        return True

    def guide_pending(self) -> str:
        """前端挂载时拉取待引导模式(事件可能早于监听注册而丢失)。"""
        return self.app.guide_pending()

    def guide_done(self, mode: str) -> bool:
        """标记某个模式的教程已完成(下次进入不再自动弹出)。"""
        mode = str(mode or "")
        if not mode:
            return False
        ui = self.app.cfg.setdefault("ui", {})
        done = ui.setdefault("guideDone", {})
        done[mode] = True
        cfgmod.save_config(self.app.cfg)
        return True

    def guide_reset(self) -> dict:
        """清空所有模式的"已看过教程"记录。"""
        return self.app.guide_reset()

    # ================= 退出 / 最小化 =================
    def request_quit(self) -> bool:
        """点退出按钮或按 Ctrl+Q:按配置弹询问框 / 直接退出 / 最小化到任务栏。"""
        self.app.request_quit()
        return True

    def minimize_app(self) -> bool:
        """最小化到托盘(程序继续在后台运行)。"""
        self.app.minimize_app()
        return True

    def restore_app(self) -> bool:
        """从托盘唤回主界面(托盘图标左键/菜单「显示主界面」也走这里)。"""
        return self.app.restore_app()

    def pause_hole(self, on: bool = True) -> bool:
        """弹窗打开/关闭时调用:打开时临时取消洞口穿透(否则居中的弹窗会被裁掉看不见),
        关闭后恢复。返回 True 表示已按预期设置。"""
        return self.app.pause_hole(bool(on))

    def set_quit_action(self, action: str) -> bool:
        """记住退出方式:ask=每次都问 / exit=直接退出 / tray=最小化到托盘(后台运行)。"""
        action = str(action or "ask")
        if action == "minimize":       # 旧值:曾被实现成"缩到任务栏",现统一为托盘
            action = "tray"
        if action not in ("ask", "exit", "tray"):
            return False
        self.app.cfg.setdefault("behavior", {})["quit_action"] = action
        cfgmod.save_config(self.app.cfg)
        self.app.push({"type": "config", "config": self.app.cfg})
        return True

    def provider_set(self, i: int, field: str, value) -> bool:
        cfg = self.app.cfg
        provs = cfg.get("providers", [])
        if not (0 <= int(i) < len(provs)):
            return False
        if field in ("api_key", "model", "base_url", "note", "homepage", "name") and isinstance(value, str):
            value = value.strip()
        provs[int(i)][field] = value
        # Key 被填上/清空都会影响"选中平台"是否可用:让规则重新收敛一次
        before = cfg.get("active_provider")
        cfgmod.ensure_active_provider(cfg)
        cfgmod.save_config(cfg)
        if cfg.get("active_provider") != before:
            picked = next((p for p in provs if p.get("id") == cfg.get("active_provider")), {})
            self.app.push({"type": "status",
                           "text": f"已自动切换使用平台:{picked.get('name', cfg.get('active_provider'))}",
                           "tone": "ok"})
            self.app.push({"type": "config", "config": cfg})
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
        provs.pop(int(i))
        # 删掉的正好是选中平台 → 回落到其它已配置的平台(而不是硬取第一个,可能是未配置的)
        cfgmod.ensure_active_provider(cfg)
        cfgmod.save_config(cfg)
        self.app.push({"type": "config", "config": cfg})
        return True

    def set_active_provider(self, pid: str) -> bool:
        """切换"当前使用的平台"。只允许选中已配置(填了 Key)的平台。"""
        cfg = self.app.cfg
        pid = str(pid or "")
        prov = next((p for p in cfg.get("providers", []) if p.get("id") == pid), None)
        if prov is None or not cfgmod.provider_ready(prov):
            return False
        if cfg.get("active_provider") == pid:
            return True
        cfg["active_provider"] = pid
        cfgmod.save_config(cfg)
        missing_model = not (prov.get("model") or "").strip()
        self.app.push({"type": "status",
                       "text": f"已切换使用平台:{prov.get('name', pid)}"
                               + ("(该平台还没填模型 ID)" if missing_model else ""),
                       "tone": "warn" if missing_model else "ok"})
        self.app.push({"type": "config", "config": cfg})
        return True

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
            res = win.create_file_dialog(_dialog('SAVE'), save_filename="ocr-assistant-theme.json")
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
            res = win.create_file_dialog(_dialog('OPEN'), allow_multiple=False,
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

    # ================= 端侧模型(按需下载 / 分档) =================
    def local_models_status(self) -> dict:
        from app import local_models
        cfg_tr = self.app.cfg.get("translate") or {}
        local = self.app.cfg.get("local") or {}
        st = local_models.summary()
        st["mt"] = local_models.mt_status(cfg_tr.get("source_lang", "自动检测"),
                                          cfg_tr.get("target_lang", "中文"))
        cur_ocr = local_models.get_ocr_tier()
        st["ocr"] = local_models.ocr_tier_status(cur_ocr)
        st["tiers"] = {
            "ocr": local_models.tier_list("ocr"),
            "mt": local_models.tier_list("mt"),
        }
        st["current"] = {
            "ocr": local_models.get_ocr_tier(),
            "mt": local_models.get_mt_tier(),
            "source": local_models.get_source(),
        }
        st["source"] = local_models.get_source()
        st["hf_runtime"] = local_models.hf_runtime_status()
        st["ocr_local"] = self.app.cfg.get("ocr", {}).get("mode", "cloud") == "local"
        st["mt_local"] = (cfg_tr.get("mode") or "cloud") == "local"
        _ = local
        return st

    def set_local_tier(self, kind: str, tier: str) -> dict:
        """切换端侧档位(ocr / mt)或下载源(auto / hf / mirror),并持久化。"""
        from app import local_models
        cfg = self.app.cfg
        local = cfg.setdefault("local", {})
        if kind == "ocr":
            local["ocr_tier"] = local_models.set_ocr_tier(str(tier))
        elif kind == "mt":
            local["mt_tier"] = local_models.set_mt_tier(str(tier))
            # 切档位后立刻释放上一档模型:600M 档常驻约 2.4GB,留着会与 1.3B 档叠加
            try:
                from app import local_mt
                freed = local_mt.release(keep=local["mt_tier"])
                if freed:
                    self.app.push({"type": "status",
                                   "text": f"已释放 {freed} 个旧档位模型(内存回收)", "tone": "ok"})
            except Exception:
                pass
        elif kind == "source":
            local["source"] = local_models.set_source(str(tier))
        cfgmod.save_config(cfg)
        self.app.push({"type": "config", "config": cfg})
        return local

    def download_local_model(self, kind: str, tier: str = "") -> bool:
        """kind: ocr / mt / runtime;tier: 档位(可选)"""
        threading.Thread(target=self._download_model, args=(str(kind), str(tier or "")),
                         daemon=True).start()
        return True

    def _download_model(self, kind: str, tier: str = ""):
        from app import local_models
        cfg_tr = self.app.cfg.get("translate") or {}

        def progress(pct, text):
            self.app.push({"type": "download", "kind": kind, "tier": tier, "pct": int(pct), "text": text})

        try:
            self.app.push({"type": "download", "kind": kind, "tier": tier, "pct": 0,
                           "text": "准备下载…"})
            if kind == "ocr":
                msg = local_models.download_ocr(tier or local_models.get_ocr_tier(), progress)
            elif kind == "runtime":
                msg = local_models.download_runtime(progress)
            elif kind == "mt":
                tier = tier or local_models.get_mt_tier()
                info = local_models.mt_tier_info(tier)
                if info.get("kind") == "hf":
                    msg = local_models.download_hf_mt(tier, progress)
                elif tier == "light":
                    msg = local_models.download_mt(cfg_tr.get("source_lang", "英语"),
                                                   cfg_tr.get("target_lang", "中文"), progress)
                else:
                    msg = local_models.download_mt_tier(tier, progress)
            elif kind == "hf_runtime":
                msg = local_models.download_hf_runtime(progress)
            else:
                msg = "未知的模型类型"
            self.app.push({"type": "download", "kind": kind, "tier": tier, "pct": 100,
                           "done": True, "message": msg})
            self.app.push({"type": "status", "text": msg, "tone": "ok"})
        except Exception as exc:  # noqa: BLE001
            self.app.push({"type": "download", "kind": kind, "tier": tier, "pct": 0, "done": True,
                           "error": str(exc)})
            self.app.push({"type": "status", "text": str(exc), "tone": "danger"})

    def remove_local_model(self, kind: str, tier: str = "") -> str:
        from app import local_models
        if kind == "ocr" and tier:
            return local_models.remove_ocr_tier(tier)
        if kind == "mt" and tier:
            info = local_models.mt_tier_info(tier)
            if info.get("kind") == "hf":
                return local_models.remove_hf_mt(tier)
            return local_models.remove_mt_tier(tier)
        return local_models.remove(str(kind))

    # ================= 剪贴板 =================
    def copy_text(self, text: str) -> bool:
        """由后端写入系统剪贴板(WebView 内的 navigator.clipboard 常静默失败)。"""
        from app.clipboard import copy_text as _copy
        return _copy(text)

    def last_result(self) -> dict:
        """最近一次识别/翻译结果(供窗口刚显示时主动回拉,避免丢事件)。"""
        return self.app.last_result()

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
                for win in (self.app.overlay, self.app.mini, self.app.translate):
                    try:
                        if win is not None:
                            win.on_top = on
                    except Exception:
                        pass
                # pywebview 的 on_set_on_top 内部会无条件 show() 窗口,
                # 会把隐藏的模式窗口也显示出来(表现为两个模式界面同时出现),
                # 因此设置完标志位后立即按当前模式重新校正可见性。
                self.app._sync_visibility()

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

    def request_log_stats(self) -> dict:
        """请求统计:总次数 / 失败次数 / 成功率 / 平均耗时(关于页右侧卡片用)。"""
        return request_log.stats(140)
