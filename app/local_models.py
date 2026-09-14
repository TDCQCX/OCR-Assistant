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


# ================= 档位定义(界面展示 + 下载选择) =================
# 每档包含:名称、体积、来源、语言覆盖,以及给用户看的「代价」说明。
OCR_TIERS = {
    "light": {
        "name": "轻量", "recommend": False, "size_mb": 16,
        "files": {"det": "ch_PP-OCRv4_det_infer.onnx",
                  "rec": "ch_PP-OCRv4_rec_infer.onnx",
                  "cls": "ch_ppocr_mobile_v2.0_cls_infer.onnx"},
        "source": "PyPI rapidocr_onnxruntime(移动端模型)",
        "speed": "最快(CPU 约 0.1-0.3s/张)",
        "quality": "清晰印刷体够用;小字、密排、表格易漏字",
        "cost": "几乎无额外代价",
    },
    "balanced": {
        "name": "均衡", "recommend": True, "size_mb": 120,
        "files": {"det": "ch_PP-OCRv4_det_server_infer.onnx",
                  "rec": "ch_PP-OCRv4_rec_infer.onnx",
                  "cls": "ch_ppocr_mobile_v2.0_cls_infer.onnx"},
        "source": "hf-mirror / HuggingFace —— SWHL/RapidOCR",
        "speed": "较快(det 变大,约 0.3-0.8s/张)",
        "quality": "长文本、密排、表格明显改善(检测是主要瓶颈)",
        "cost": "下载约 120MB,内存占用略增",
    },
    "full": {
        "name": "全量", "recommend": False, "size_mb": 196,
        "files": {"det": "ch_PP-OCRv4_det_server_infer.onnx",
                  "rec": "ch_PP-OCRv4_rec_server_infer.onnx",
                  "cls": "ch_ppocr_mobile_v2.0_cls_infer.onnx"},
        "source": "hf-mirror / HuggingFace —— SWHL/RapidOCR",
        "speed": "较慢(约 0.5-1.5s/张)",
        "quality": "识别最准:小字、模糊、手写体、复杂版式",
        "cost": "下载约 196MB;CPU 占用与耗时明显上升",
    },
}

MT_TIERS = {
    "light": {
        "name": "轻量", "recommend": True, "usable": True, "size_mb": 79,
        "kind": "pair", "source": "argos-net.com —— Argos opus-mt int8",
        "speed": "最快(单段约 0.03-0.1s)",
        "quality": "大意可读,长句与专业词较弱",
        "cost": "每个语言对各需 79MB;换语言要重新下载",
        "covered": "仅英↔中/日/韩/法/德/俄/西/葡/意/阿/泰/越",
    },
    "balanced": {
        "name": "均衡", "recommend": False, "usable": False, "size_mb": 600,
        "kind": "multi", "repo": "JustFrederik/nllb-200-distilled-600M-ct2-int8",
        "source": "hf-mirror / HuggingFace —— NLLB-200 distilled 600M(int8)",
        "speed": "中等(单段约 0.5-2s)",
        "quality": "明显优于轻量档,长句/术语可用",
        "cost": "下载约 600MB(一次性);内存峰值约 1.5GB;首次加载约数秒",
        "covered": "一个模型覆盖 200 种语言,换语言无需再下载",
    },
    "full": {
        "name": "全量", "recommend": False, "usable": False, "size_mb": 1322,
        "kind": "multi", "repo": "JustFrederik/nllb-200-distilled-1.3B-ct2-int8",
        "source": "hf-mirror / HuggingFace —— NLLB-200 distilled 1.3B(int8)",
        "speed": "最慢(单段约 2-10s,取决于 CPU)",
        "quality": "端侧最高:接近可用的人工翻译水平",
        "cost": "下载约 1.32GB;内存峰值约 3GB;首次加载约 10-30s;纯 CPU 建议仅在需要高准确度时使用",
        "covered": "一个模型覆盖 200 种语言",
    },
}


def tier_list(kind: str) -> list:
    """档位清单(供界面展示)。只列出当前可用(已实测)的档位。"""
    table = OCR_TIERS if kind == "ocr" else {k: v for k, v in MT_TIERS.items() if v.get("usable")}
    out = []
    for key, info in table.items():
        st = ocr_tier_status(key) if kind == "ocr" else mt_tier_status(key)
        item = {"key": key, **{k: v for k, v in info.items() if k not in ("files", "repo")}}
        if st:
            item.update({"ready": st["ready"], "size_on_disk": st["size_mb"]})
        out.append(item)
    return out


# ================= OCR 分档 =================
def ocr_tier_status(tier: str) -> dict:
    info = OCR_TIERS.get(tier) or OCR_TIERS["light"]
    d = OCR_DIR / tier
    missing = [n for n in info["files"].values() if not (d / n).exists()]
    if tier == "light" and missing and not (OCR_DIR / "light").exists():
        # 轻量档兼容旧版落盘位置
        legacy = OCR_DIR
        if all((legacy / n).exists() for n in info["files"].values()):
            missing = []
    return {"tier": tier, "ready": not missing, "dir": str(d), "missing": missing,
            "size_mb": _dir_size(d)}


def get_ocr_tier() -> str:
    return DEFAULT_OCR_TIER


def apply_settings(local_cfg: dict) -> None:
    """从配置恢复档位与下载源。"""
    global DEFAULT_OCR_TIER, DEFAULT_MT_TIER
    cfg = local_cfg or {}
    if cfg.get('ocr_tier') in OCR_TIERS:
        DEFAULT_OCR_TIER = cfg['ocr_tier']
    if cfg.get('mt_tier') in MT_TIERS:
        DEFAULT_MT_TIER = cfg['mt_tier']
    if cfg.get('source'):
        set_source(str(cfg['source']))


def remove_mt_tier(tier: str) -> str:
    if tier == 'light':
        return remove('mt')
    d = MT_TIER_DIR / tier
    if d.exists():
        shutil.rmtree(d, ignore_errors=True)
        return f'已删除翻译 {tier} 档模型'
    return '该档位没有已下载的模型'


def current_ocr_tier() -> str:
    """当前生效档位:优先配置的默认档;若该档未下载而其它档已下载,则用已下载的档,避免"切档后反而不可用"。"""
    if ocr_tier_status(DEFAULT_OCR_TIER)["ready"]:
        return DEFAULT_OCR_TIER
    for key in ("light", "balanced", "full"):
        if ocr_tier_status(key)["ready"]:
            return key
    return DEFAULT_OCR_TIER


def set_ocr_tier(tier: str) -> str:
    global DEFAULT_OCR_TIER
    if tier in OCR_TIERS:
        DEFAULT_OCR_TIER = tier
    return DEFAULT_OCR_TIER


def ocr_model_paths() -> dict:
    """按当前档位返回模型路径;缺失时回退内置包内模型(源码环境)。"""
    tier = current_ocr_tier()
    d = OCR_DIR / tier
    info = OCR_TIERS[tier]
    if all((d / n).exists() for n in info["files"].values()):
        return {k: str(d / n) for k, n in info["files"].items()}
    if tier == "light" and all((OCR_DIR / n).exists() for n in info["files"].values()):
        return {k: str(OCR_DIR / n) for k, n in info["files"].items()}
    spec = importlib.util.find_spec("rapidocr_onnxruntime")
    if spec and spec.origin:
        bundled = Path(spec.origin).parent / "models"
        if all((bundled / n).exists() for n in OCR_FILES.values()):
            return {"det": str(bundled / OCR_FILES["det"]), "rec": str(bundled / OCR_FILES["rec"]),
                    "cls": str(bundled / OCR_FILES["cls"])}
    return {}


def download_ocr(tier: str = "", progress=None) -> str:
    """下载指定档位的 OCR 端侧模型。"""
    progress = progress or (lambda pct, text: None)
    tier = tier or current_ocr_tier()
    info = OCR_TIERS.get(tier) or OCR_TIERS["light"]
    d = OCR_DIR / tier
    d.mkdir(parents=True, exist_ok=True)
    if tier == "light":
        # 轻量档直接从 PyPI wheel 取移动端模型
        progress(2, "正在解析下载地址…")
        data = _download(_pypi_wheel_url("rapidocr_onnxruntime"), progress, 5, 85, "正在下载模型包…")
        progress(92, "正在解压模型…")
        count = 0
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            for item in zf.infolist():
                name = Path(item.filename).name
                if name in info["files"].values():
                    with zf.open(item) as src, open(d / name, "wb") as dst:
                        shutil.copyfileobj(src, dst)
                    count += 1
        if count < len(info["files"]):
            raise ModelMissing("ocr", f"模型包内容不完整(找到 {count} 个文件)")
    else:
        # 均衡/全量:从 HuggingFace(或镜像)取 PP-OCR server 模型
        # 注意仓库目录结构:det/rec 在 PP-OCRv4/,cls 在 PP-OCRv1/
        repo = "SWHL/RapidOCR"
        det = info["files"]["det"]
        rec = info["files"]["rec"]
        cls = info["files"]["cls"]
        remote = {
            det: f"PP-OCRv4/{det}",
            rec: f"PP-OCRv4/{rec}",
            cls: f"PP-OCRv1/{cls}",
        }
        for name in (det, rec, cls):
            target = d / name
            if target.exists():
                continue
            # cls 很小且各档相同:优先复用已下载/内置的副本,避免多余下载
            if name == cls:
                for src_dir in (OCR_DIR / "light", OCR_DIR):
                    if (src_dir / name).exists():
                        shutil.copyfile(src_dir / name, target)
                        break
            if target.exists():
                continue
            _fetch(f"/{repo}/resolve/main/{remote[name]}", target, progress, 0, 100)
    progress(100, f"{info['name']}档模型已就绪")
    return f"OCR {info['name']}档下载完成({_dir_size(d)}MB)"


def remove_ocr_tier(tier: str) -> str:
    d = OCR_DIR / tier
    if d.exists():
        shutil.rmtree(d, ignore_errors=True)
        return f"已删除 OCR {tier} 档模型"
    return "该档位没有已下载的模型"


HF_HOSTS = {"hf": "https://huggingface.co", "mirror": "https://hf-mirror.com"}
DEFAULT_SOURCE = "auto"          # auto=先官方后镜像; hf=只用官方; mirror=只用 hf-mirror
DEFAULT_OCR_TIER = "balanced"    # 默认档位:均衡
DEFAULT_MT_TIER = "light"


def set_source(source: str) -> str:
    """设置模型下载源(auto / hf / mirror)。"""
    global DEFAULT_SOURCE
    if source in HF_HOSTS or source == "auto":
        DEFAULT_SOURCE = source
    return DEFAULT_SOURCE


def get_source() -> str:
    return DEFAULT_SOURCE


def _hosts() -> tuple:
    if DEFAULT_SOURCE == "hf":
        return (HF_HOSTS["hf"],)
    if DEFAULT_SOURCE == "mirror":
        return (HF_HOSTS["mirror"],)
    return (HF_HOSTS["hf"], HF_HOSTS["mirror"])


def _fetch(url: str, dest: Path, progress=None, base_pct: int = 0, span: int = 100) -> None:
    """从 HuggingFace(按设置的源与镜像回退)下载单个文件。"""
    progress = progress or (lambda pct, text: None)
    last_err = None
    for host in _hosts():
        for _ in range(2):
            try:
                with requests.get(host + url, timeout=TIMEOUT, stream=True) as resp:
                    resp.raise_for_status()
                    total = int(resp.headers.get("Content-Length") or 0)
                    got = 0
                    tmp = dest.with_suffix(dest.suffix + ".part")
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    with open(tmp, "wb") as fh:
                        for chunk in resp.iter_content(262144):
                            fh.write(chunk)
                            got += len(chunk)
                            if total:
                                progress(base_pct + int(got / total * span),
                                         f"{dest.name} {got / 1048576:.1f}MB")
                    tmp.replace(dest)
                    return
            except Exception as exc:  # noqa: BLE001
                last_err = exc
    raise ModelMissing("mt", f"下载 {dest.name} 失败:{last_err}")


# ================= 翻译档位的落盘与状态 =================
MT_TIER_DIR = MT_DIR / "tier"


def mt_tier_info(tier: str) -> dict:
    return MT_TIERS.get(tier) or MT_TIERS["light"]


def _light_pair_dir() -> Path:
    for d in sorted(MT_DIR.glob("*-*")):
        if d.is_dir() and d.name != "tier" and (d / "model.bin").exists():
            return d
    return MT_DIR / "en-zh"


def mt_current_model() -> tuple:
    """返回 (档位, 模型目录)。

    规则:先用用户设定的档位;该档未下载时才回落到其它已下载的档。
    """
    if DEFAULT_MT_TIER == "light":
        d = _light_pair_dir()
        if (d / "model.bin").exists():
            return "light", d
    else:
        d = MT_TIER_DIR / DEFAULT_MT_TIER
        if (d / "model.bin").exists():
            return DEFAULT_MT_TIER, d
    for tier in ("balanced", "full"):
        d = MT_TIER_DIR / tier
        if (d / "model.bin").exists():
            return tier, d
    d = _light_pair_dir()
    if (d / "model.bin").exists():
        return "light", d
    return DEFAULT_MT_TIER, (MT_TIER_DIR / DEFAULT_MT_TIER if DEFAULT_MT_TIER != "light"
                             else MT_DIR / "en-zh")


def mt_tier_status(tier: str) -> dict:
    if tier == "light":
        d = _light_pair_dir()
        ready = (d / "model.bin").exists()
        return {"tier": "light", "ready": ready, "dir": str(d),
                "size_mb": _dir_size(d), "name": mt_tier_info("light")["name"]}
    d = MT_TIER_DIR / tier
    ready = (d / "model.bin").exists()
    return {"tier": tier, "ready": ready, "dir": str(d),
            "size_mb": _dir_size(d), "name": mt_tier_info(tier)["name"]}


def get_mt_tier() -> str:
    return DEFAULT_MT_TIER


def set_mt_tier(tier: str) -> str:
    global DEFAULT_MT_TIER
    if tier in MT_TIERS:
        DEFAULT_MT_TIER = tier
    return DEFAULT_MT_TIER


def download_mt_tier(tier: str, progress=None) -> str:
    """下载多语言翻译档(均衡 = NLLB-600M,全量 = NLLB-1.3B,均为 int8 专用翻译模型)。"""
    progress = progress or (lambda pct, text: None)
    info = MT_TIERS.get(tier)
    if not info or info.get("kind") != "multi":
        raise ModelMissing("mt", "该档位不是多语言模型")
    repo = info["repo"]
    d = MT_TIER_DIR / tier
    d.mkdir(parents=True, exist_ok=True)
    files = [("model.bin", "model.bin"),
             ("sentencepiece.bpe.model", "sentencepiece.bpe.model"),
             ("shared_vocabulary.txt", "shared_vocabulary.txt")]
    for i, (src, name) in enumerate(files):
        target = d / name
        if target.exists():
            continue
        base = int(i / len(files) * 100)
        span = int(100 / len(files)) - 2
        _fetch(f"/{repo}/resolve/main/{src}", target, progress, base, span)
    progress(100, f"{info['name']}档翻译模型已就绪")
    return f"翻译 {info['name']}档下载完成({_dir_size(d)}MB)"


def remove(kind: str) -> str:
    targets = {"ocr": OCR_DIR, "mt": MT_DIR, "runtime": RUNTIME_DIR, "all": MODEL_ROOT}
    path = targets.get(kind)
    if path and path.exists():
        shutil.rmtree(path, ignore_errors=True)
        return f"已删除端侧{'模型' if kind != 'runtime' else '运行时'}({kind})"
    return "没有可删除的内容"
