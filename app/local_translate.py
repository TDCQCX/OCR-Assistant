# -*- coding: utf-8 -*-
"""端侧(本地)翻译引擎。

优先级:
1. Argos Translate —— 完全离线的端侧翻译模型(需 `pip install argostranslate` 并安装语言包);
2. Ollama —— 本机大模型(需本机运行 Ollama)。

两者都不可用时返回明确的提示,由界面展示,不影响云端翻译。

注意:argostranslate / ollama 均通过 importlib 动态导入,
这样打包(PyInstaller)时不会把庞大的推理依赖带进 exe。
"""
import importlib
import importlib.util
import json
import threading

import requests

from app.config import LANG_CODES

_install_lock = threading.Lock()


class LocalTranslateError(Exception):
    """端侧翻译不可用或失败。"""


def _lang_code(name: str, default: str = "") -> str:
    return LANG_CODES.get((name or "").strip(), default)


def argos_installed() -> bool:
    try:
        return importlib.util.find_spec("argostranslate") is not None
    except Exception:
        return False


def _argos_module():
    return importlib.import_module("argostranslate.translate")


def argos_languages() -> list:
    """已安装的端侧语言包列表:['en->zh', ...]"""
    if not argos_installed():
        return []
    try:
        tr = _argos_module()
        out = []
        for lang in tr.get_installed_languages():
            for t in lang.translations_from:
                if t.from_lang.code != t.to_lang.code:
                    out.append(f"{t.from_lang.code}->{t.to_lang.code}")
        return out
    except Exception:
        return []


def argos_has_pair(src: str, dst: str) -> bool:
    return bool(src and dst and f"{src}->{dst}" in argos_languages())


def ollama_reachable(base_url: str, timeout: float = 2.0) -> bool:
    url = (base_url or "").strip()
    if not url:
        return False
    root = url.rstrip("/")
    if root.endswith("/v1"):
        root = root[:-3]
    try:
        resp = requests.get(root.rstrip("/") + "/api/tags", timeout=timeout)
        return resp.status_code == 200
    except requests.RequestException:
        return False


def status(ollama_url: str = "") -> dict:
    """端侧翻译可用性检测(供设置界面展示)。"""
    langs = argos_languages()
    ok_ollama = ollama_reachable(ollama_url)
    return {
        "argos_installed": argos_installed(),
        "argos_pairs": langs,
        "ollama": ok_ollama,
        "ready": bool(langs) or ok_ollama,
    }


def _split_lines(text: str) -> list:
    return [ln for ln in (text or "").replace("\r\n", "\n").split("\n")]


# 句子结束标点:以此判断一行是否已经构成完整语义单位
_SENT_END = tuple("。.!?！？;；…\"'’)）】》")


def segment_text(text: str, max_len: int = 400) -> list:
    """把识别出的多行文本合并成「句/段」级翻译单元。

    翻译按句/段进行,而不是逐行逐词:
    - 空白行作为段落分隔;
    - 未以句末标点结束的行与下一行合并(处理换行造成的断句);
    - 单段过长时按 max_len 拆开,避免超出模型上下文。
    """
    segs, cur = [], []

    def flush():
        nonlocal cur
        if cur:
            segs.append(" ".join(cur).strip())
            cur = []

    for raw in _split_lines(text):
        line = raw.strip()
        if not line:
            flush()
            continue
        cur.append(line)
        joined = " ".join(cur)
        if len(joined) >= max_len or line.endswith(_SENT_END):
            flush()
    flush()
    return [s for s in segs if s]


def _join_pairs(src_lines: list, dst_lines: list) -> list:
    """把逐段译文与原文对齐成 [{src, dst}]。"""
    out = []
    for i, src in enumerate(src_lines):
        dst = dst_lines[i] if i < len(dst_lines) else ""
        out.append({"src": src, "dst": dst})
    return out


def _translate_argos(lines: list, src: str, dst: str) -> list:
    tr = _argos_module()
    if not argos_has_pair(src, dst):
        raise LocalTranslateError(
            f"端侧模型缺少语言包 {src}->{dst}:请在「设置 → 翻译设置」中下载语言包")
    try:
        translator = tr.get_translation_from_codes(src, dst)
    except Exception as exc:  # noqa: BLE001
        raise LocalTranslateError(f"端侧模型加载失败:{exc}") from exc
    out = []
    for line in lines:
        if not line.strip():
            out.append("")
            continue
        out.append(translator.translate(line))
    return out


OLLAMA_SYSTEM = ("你是专业翻译引擎。逐行翻译用户给出的内容,输出行数必须与输入完全一致,"
                 "每行输出「原文<TAB>译文」,不要解释、不要编号。")


def _translate_ollama(lines: list, src: str, dst: str, base_url: str, model: str,
                      timeout: int = 120) -> list:
    url = (base_url or "").strip().rstrip("/")
    if url.endswith("/v1"):
        url = url[:-3]
    if not url:
        raise LocalTranslateError("未配置 Ollama 地址(设置 → 翻译设置)")
    body = "\n".join(lines)
    payload = {
        "model": model or "qwen2.5:7b",
        "messages": [
            {"role": "system", "content": OLLAMA_SYSTEM},
            {"role": "user", "content": f"来源语言:{src};目标语言:{dst}\n\n{body}"},
        ],
        "stream": False,
        "options": {"temperature": 0},
    }
    try:
        resp = requests.post(url + "/api/chat", json=payload, timeout=timeout)
    except requests.RequestException as exc:
        raise LocalTranslateError(f"本地大模型不可用:{exc}") from exc
    if resp.status_code != 200:
        raise LocalTranslateError(f"本地大模型返回 {resp.status_code}:{resp.text[:200]}")
    try:
        content = resp.json()["message"]["content"]
    except Exception as exc:
        raise LocalTranslateError(f"本地大模型响应解析失败:{exc}") from exc
    out = []
    for i, line in enumerate(_split_lines(content)):
        if i >= len(lines):
            break
        out.append(line.split("\t")[-1].strip() if "\t" in line else line.strip())
    while len(out) < len(lines):
        out.append("")
    return out


def translate_lines(text: str, source_lang: str, target_lang: str, engine: str = "auto",
                    ollama_url: str = "", ollama_model: str = "", timeout: int = 120) -> dict:
    """按句/段翻译,返回 {pairs:[{src,dst}], engine, src_code, dst_code}。"""
    src = _lang_code(source_lang)
    dst = _lang_code(target_lang)
    segments = segment_text(text)
    if not text or not text.strip():
        raise LocalTranslateError("没有可翻译的内容")
    if not segments:
        raise LocalTranslateError("没有可翻译的内容")
    if not dst:
        raise LocalTranslateError(f"不支持的目标语言:{target_lang}")
    if source_lang and source_lang != "自动检测" and not src:
        raise LocalTranslateError(f"不支持的来源语言:{source_lang}")

    engine = (engine or "auto").lower()
    errors = []

    if engine in ("auto", "argos") and src and argos_has_pair(src, dst):
        with _install_lock:
            dst_lines = _translate_argos(segments, src, dst)
        return {"pairs": _join_pairs(segments, dst_lines), "engine": "Argos 端侧模型",
                "src_code": src, "dst_code": dst}

    if engine == "argos" and not argos_installed():
        raise LocalTranslateError("未安装端侧翻译模型:请执行 pip install argostranslate,"
                                 "或在设置中改用 Ollama / 云端翻译")
    if engine == "argos" and src and not argos_has_pair(src, dst):
        raise LocalTranslateError(f"端侧模型缺少语言包 {src}->{dst}:请在设置 → 翻译设置中下载")

    if engine == "ollama" or (engine == "auto" and ollama_url):
        try:
            dst_lines = _translate_ollama(segments, source_lang, target_lang, ollama_url,
                                          ollama_model, timeout)
            return {"pairs": _join_pairs(segments, dst_lines), "engine": "Ollama 本地模型",
                    "src_code": src or "auto", "dst_code": dst}
        except LocalTranslateError as exc:
            errors.append(str(exc))

    if engine == "auto":
        if not argos_installed():
            errors.append("未安装端侧翻译模型(可 pip install argostranslate)")
        elif not src:
            errors.append("自动检测来源语言时不支持端侧模型,请手动选择来源语言")
        else:
            errors.append(f"端侧模型缺少语言包 {src}->{dst}")
    raise LocalTranslateError(";".join(errors) or "端侧翻译不可用")


def install_argos_pack(source_lang: str, target_lang: str) -> str:
    """下载并安装端侧语言包(需联网,仅一次)。"""
    if not argos_installed():
        return "未安装 argostranslate:请先执行 pip install argostranslate"
    src, dst = _lang_code(source_lang), _lang_code(target_lang)
    if not src or not dst:
        return "语言不支持端侧模型(请选择具体语言,不要用自动检测)"
    try:
        package = importlib.import_module("argostranslate.package")
        tr = _argos_module()
        if argos_has_pair(src, dst):
            return f"语言包 {src}->{dst} 已存在"
        package.update_package_index()
        cands = [p for p in package.get_available_packages()
                 if p.from_code == src and p.to_code == dst]
        if not cands:
            return f"未找到语言包 {src}->{dst}"
        best = max(cands, key=lambda p: str(getattr(p, "package_version", "0")))
        package.install_from_path(best.download())
        _ = tr.get_installed_languages()
        return f"语言包 {src}->{dst} 安装完成"
    except Exception as exc:  # noqa: BLE001
        return f"语言包安装失败:{exc}"


def pairs_from_text(text: str, source_text: str) -> list:
    """把云端模型输出解析成逐行对照(支持 原文<TAB>译文 与逐行对应两种形式)。"""
    src_lines = _split_lines(source_text)
    out_lines = _split_lines(text)
    pairs = []
    for i, line in enumerate(out_lines):
        if not line.strip() and i >= len(src_lines):
            continue
        if "\t" in line:
            a, b = line.split("\t", 1)
        elif "|||" in line:
            a, b = line.split("|||", 1)
        else:
            a = src_lines[i] if i < len(src_lines) else ""
            b = line
        pairs.append({"src": a.strip(), "dst": b.strip()})
    return pairs or [{"src": source_text.strip(), "dst": (text or "").strip()}]


def parse_translation_output(raw: str, segments: list) -> list:
    """解析云端翻译结果:优先按 JSON 数组(逐段),否则退化为逐行对齐。"""
    txt = (raw or "").strip().replace("```json", "").replace("```", "").strip()
    if txt.startswith("["):
        try:
            arr = json.loads(txt[txt.find("["):txt.rfind("]") + 1])
            if isinstance(arr, list) and arr:
                return [{"src": segments[i] if i < len(segments) else "",
                         "dst": str(v).strip()} for i, v in enumerate(arr)]
        except Exception:
            pass
    return pairs_from_text(txt, "\n".join(segments))
