# -*- coding: utf-8 -*-
"""端侧模型管理:检测 / 下载 OCR、翻译模型与端侧推理运行时。

打包版默认**不携带**任何端侧模型与推理运行时,首次切换到「端侧」时才提示下载:
- OCR 模型:从 PyPI 下载 rapidocr_onnxruntime wheel,仅解压其中的 onnx 模型(约 16MB);
- 翻译运行时:从 PyPI 下载 ctranslate2 wheel,解压到 models/runtime(约 60MB);
- 翻译模型:下载 Argos 的 .argosmodel 包(每对语言约 80-110MB)。

下载均带进度回调,可查询状态与删除,便于用户自行控制磁盘占用。
"""
import importlib.util
import io
import platform
import shutil
import sys
import zipfile
from pathlib import Path

import requests

from app.config import ROOT

MODEL_ROOT = ROOT / "models"
OCR_DIR = MODEL_ROOT / "ocr"
MT_DIR = MODEL_ROOT / "mt"
RUNTIME_DIR = MODEL_ROOT / "runtime"

OCR_FILES = {
    "det": "ch_PP-OCRv4_det_infer.onnx",
    "rec": "ch_PP-OCRv4_rec_infer.onnx",
    "cls": "ch_ppocr_mobile_v2.0_cls_infer.onnx",
}

# 端侧翻译:Argos 包(内含 CTranslate2 int8 模型 + sentencepiece)
MT_PACKAGES = {
    ("en", "zh"): "https://argos-net.com/v1/translate-en_zh-1_9.argosmodel",
    ("zh", "en"): "https://argos-net.com/v1/translate-zh_en-1_9.argosmodel",
    ("en", "ja"): "https://argos-net.com/v1/translate-en_ja-1_1.argosmodel",
    ("ja", "en"): "https://argos-net.com/v1/translate-ja_en-1_1.argosmodel",
    ("en", "ko"): "https://argos-net.com/v1/translate-en_ko-1_1.argosmodel",
    ("ko", "en"): "https://argos-net.com/v1/translate-ko_en-1_1.argosmodel",
    ("en", "fr"): "https://argos-net.com/v1/translate-en_fr-1_9.argosmodel",
    ("fr", "en"): "https://argos-net.com/v1/translate-fr_en-1_9.argosmodel",
    ("en", "de"): "https://argos-net.com/v1/translate-en_de-1_3.argosmodel",
    ("de", "en"): "https://argos-net.com/v1/translate-de_en-1_3.argosmodel",
    ("en", "ru"): "https://argos-net.com/v1/translate-en_ru-1_9.argosmodel",
    ("ru", "en"): "https://argos-net.com/v1/translate-ru_en-1_9.argosmodel",
    ("en", "es"): "https://argos-net.com/v1/translate-en_es-1_0.argosmodel",
    ("es", "en"): "https://argos-net.com/v1/translate-es_en-1_9.argosmodel",
    ("en", "pt"): "https://argos-net.com/v1/translate-en_pt-1_9.argosmodel",
    ("pt", "en"): "https://argos-net.com/v1/translate-pt_en-1_9.argosmodel",
    ("en", "it"): "https://argos-net.com/v1/translate-en_it-1_0.argosmodel",
    ("it", "en"): "https://argos-net.com/v1/translate-it_en-1_0.argosmodel",
    ("en", "ar"): "https://argos-net.com/v1/translate-en_ar-1_0.argosmodel",
    ("ar", "en"): "https://argos-net.com/v1/translate-ar_en-1_0.argosmodel",
    ("en", "th"): "https://argos-net.com/v1/translate-en_th-1_9.argosmodel",
    ("th", "en"): "https://argos-net.com/v1/translate-th_en-1_9.argosmodel",
    ("en", "vi"): "https://argos-net.com/v1/translate-en_vi-1_9.argosmodel",
    ("vi", "en"): "https://argos-net.com/v1/translate-vi_en-1_9.argosmodel",
}
MT_INDEX_URL = "https://raw.githubusercontent.com/argosopentech/argospm-index/main/index.json"
MT_LOCAL_FILES = ("model.bin", "sentencepiece.model", "shared_vocabulary.json")

TIMEOUT = (10, 60)


class ModelMissing(Exception):
    """端侧模型/运行时缺失,需要用户确认后下载。"""

    def __init__(self, kind: str, message: str):
        super().__init__(message)
        self.kind = kind
        self.message = message


def _dir_size(path: Path) -> float:
    if not path.exists():
        return 0.0
    return round(sum(f.stat().st_size for f in path.rglob("*") if f.is_file()) / 1048576, 1)


def _download(url: str, progress=None, base=0, span=100, label="下载中") -> bytes:
    progress = progress or (lambda pct, text: None)
    with requests.get(url, timeout=TIMEOUT, stream=True) as resp:
        resp.raise_for_status()
        total = int(resp.headers.get("Content-Length") or 0)
        buf = io.BytesIO()
        got = 0
        for chunk in resp.iter_content(262144):
            buf.write(chunk)
            got += len(chunk)
            if total:
                progress(base + int(got / total * span), f"{label} {got / 1048576:.1f}MB")
    return buf.getvalue()


# ================= OCR 模型 =================
def ocr_status() -> dict:
    missing = [name for name in OCR_FILES.values() if not (OCR_DIR / name).exists()]
    return {"ready": not missing, "dir": str(OCR_DIR), "missing": missing, "size_mb": _dir_size(OCR_DIR)}


def ocr_model_paths() -> dict:
    """用户已下载的优先,其次内置包内模型(源码环境)。"""
    if ocr_status()["ready"]:
        return {"det": str(OCR_DIR / OCR_FILES["det"]), "rec": str(OCR_DIR / OCR_FILES["rec"]),
                "cls": str(OCR_DIR / OCR_FILES["cls"])}
    spec = importlib.util.find_spec("rapidocr_onnxruntime")
    if spec and spec.origin:
        bundled = Path(spec.origin).parent / "models"
        if all((bundled / n).exists() for n in OCR_FILES.values()):
            return {"det": str(bundled / OCR_FILES["det"]), "rec": str(bundled / OCR_FILES["rec"]),
                    "cls": str(bundled / OCR_FILES["cls"])}
    return {}


def _pypi_wheel_url(pkg: str, prefer: str = "") -> str:
    meta = requests.get(f"https://pypi.org/pypi/{pkg}/json", timeout=TIMEOUT).json()
    wheels = [u for u in (meta.get("urls") or []) if u["filename"].endswith(".whl")]
    if not wheels:
        raise ModelMissing(pkg, f"PyPI 上没有可用的 {pkg} wheel")
    tag = prefer or f"cp{sys.version_info.major}{sys.version_info.minor}"
    win = [u for u in wheels if tag in u["filename"] and "win_amd64" in u["filename"]]
    pool = win or [u for u in wheels if "win_amd64" in u["filename"]] or wheels
    pool.sort(key=lambda u: (tag not in u["filename"], u["filename"]))
    return pool[0]["url"]


def download_ocr(progress=None) -> str:
    progress = progress or (lambda pct, text: None)
    OCR_DIR.mkdir(parents=True, exist_ok=True)
    progress(2, "正在解析下载地址…")
    data = _download(_pypi_wheel_url("rapidocr_onnxruntime"), progress, 5, 85, "正在下载 OCR 模型包…")
    progress(92, "正在解压模型…")
    count = 0
    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        for info in zf.infolist():
            name = Path(info.filename).name
            if name in OCR_FILES.values():
                with zf.open(info) as src, open(OCR_DIR / name, "wb") as dst:
                    shutil.copyfileobj(src, dst)
                count += 1
    if count < len(OCR_FILES):
        raise ModelMissing("ocr", f"模型包内容不完整(找到 {count} 个模型文件)")
    progress(100, "OCR 端侧模型已就绪")
    return f"OCR 端侧模型下载完成({_dir_size(OCR_DIR)}MB)"


# ================= 翻译运行时(CTranslate2) =================
def runtime_installed() -> bool:
    if importlib.util.find_spec("ctranslate2") is not None and \
            importlib.util.find_spec("sentencepiece") is not None:
        return True
    return (RUNTIME_DIR / "ctranslate2").exists() and (RUNTIME_DIR / "sentencepiece").exists()


def runtime_status() -> dict:
    return {"ready": runtime_installed(), "dir": str(RUNTIME_DIR), "size_mb": _dir_size(RUNTIME_DIR)}


def ensure_runtime_path() -> str:
    d = str(RUNTIME_DIR)
    if d not in sys.path and (RUNTIME_DIR / "ctranslate2").exists():
        sys.path.insert(0, d)
    return d


def download_runtime(progress=None) -> str:
    """下载端侧推理运行时 ctranslate2 + sentencepiece(约 62MB,打包版不内置)。"""
    progress = progress or (lambda pct, text: None)
    RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
    for i, pkg in enumerate(("ctranslate2", "sentencepiece")):
        if importlib.util.find_spec(pkg) is not None:
            continue
        progress(2 + i * 45, f"正在解析 {pkg} 下载地址…")
        data = _download(_pypi_wheel_url(pkg, prefer=platform.python_version()),
                         progress, 5 + i * 45, 40, f"正在下载 {pkg}…")
        progress(88 + i * 5, f"正在解压 {pkg}…")
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            zf.extractall(RUNTIME_DIR)
    ensure_runtime_path()
    importlib.invalidate_caches()
    progress(100, "端侧推理运行时已就绪")
    return f"端侧推理运行时下载完成({_dir_size(RUNTIME_DIR)}MB)"


# ================= 翻译模型(Argos 包) =================
def _mt_codes(source_lang: str, target_lang: str):
    from app.config import LANG_CODES
    return (LANG_CODES.get((source_lang or "").strip(), ""),
            LANG_CODES.get((target_lang or "").strip(), ""))


def _mt_url(src: str, dst: str) -> str:
    url = MT_PACKAGES.get((src, dst))
    if url:
        return url
    try:
        index = requests.get(MT_INDEX_URL, timeout=TIMEOUT).json()
        for item in index:
            if item.get("from_code") == src and item.get("to_code") == dst and item.get("links"):
                return item["links"][0]
    except Exception:
        pass
    return ""


def mt_status(source_lang: str, target_lang: str) -> dict:
    src, dst = _mt_codes(source_lang, target_lang)
    d = mt_dir(source_lang, target_lang)
    missing = [f for f in MT_LOCAL_FILES if not (d / f).exists()]
    return {
        "ready": bool(src and dst) and not missing,
        "supported": bool(src and dst) and (bool(MT_PACKAGES.get((src, dst))) or True),
        "pair": f"{src}->{dst}",
        "dir": str(d),
        "missing": missing,
        "size_mb": _dir_size(d),
    }


def mt_dir(source_lang: str, target_lang: str) -> Path:
    src, dst = _mt_codes(source_lang, target_lang)
    return MT_DIR / f"{src or 'x'}-{dst or 'y'}"


def mt_ready(source_lang: str, target_lang: str) -> bool:
    return mt_status(source_lang, target_lang)["ready"]


def download_mt(source_lang: str, target_lang: str, progress=None) -> str:
    """下载某一语言对的端侧翻译模型(Argos 包,约 80-110MB)。"""
    progress = progress or (lambda pct, text: None)
    src, dst = _mt_codes(source_lang, target_lang)
    if not src or not dst or src == dst:
        raise ModelMissing("mt", f"端侧模型不支持 {source_lang} → {target_lang}(请选择具体语言)")
    url = _mt_url(src, dst)
    if not url:
        raise ModelMissing("mt", f"未找到 {src}->{dst} 的端侧模型,请改用云端翻译或本机 Ollama")
    d = mt_dir(source_lang, target_lang)
    d.mkdir(parents=True, exist_ok=True)
    data = _download(url, progress, 2, 92, f"正在下载 {src}->{dst} 模型…")
    progress(94, "正在解压模型…")
    keep = {"model.bin", "sentencepiece.model", "shared_vocabulary.json",
            "shared_vocabulary.txt", "config.json"}
    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        for info in zf.infolist():
            name = Path(info.filename).name
            if name in keep:
                with zf.open(info) as fsrc, open(d / name, "wb") as fdst:
                    shutil.copyfileobj(fsrc, fdst)
    if not (d / "model.bin").exists() or not (d / "sentencepiece.model").exists():
        raise ModelMissing("mt", "模型包内容不完整")
    progress(100, "端侧翻译模型已就绪")
    return f"端侧翻译模型下载完成({src}->{dst},{_dir_size(d)}MB)"


# ================= 汇总 / 删除 =================
def summary() -> dict:
    return {"root": str(MODEL_ROOT), "ocr": ocr_status(), "mt": mt_status("中文", "英语"),
            "runtime": runtime_status(), "total_mb": _dir_size(MODEL_ROOT)}


def remove(kind: str) -> str:
    targets = {"ocr": OCR_DIR, "mt": MT_DIR, "runtime": RUNTIME_DIR, "all": MODEL_ROOT}
    path = targets.get(kind)
    if path and path.exists():
        shutil.rmtree(path, ignore_errors=True)
        return f"已删除端侧{'模型' if kind != 'runtime' else '运行时'}({kind})"
    return "没有可删除的内容"
