# -*- coding: utf-8 -*-
"""端侧翻译(官方模型):HuggingFace transformers + torch,模型与分词器同源配套。

用于"均衡/全量"档:NLLB-200 distilled 600M / 1.3B。
- 与 CTranslate2 路线不同,这里用的是官方仓库的 config/tokenizer/model 三件套,
  不存在第三方转换产物的词表错配问题(此前 NLLB/M2M100 的 ct2fast 转换即因此退化为重复词)。
- transformers/torch 运行时按需下载到 models/runtime/hf,不随应用分发。
"""
import importlib
import importlib.util
import sys
import threading
from pathlib import Path

from app import local_models

_lock = threading.Lock()
_cache = {}

# NLLB(FLORES-200)语言标记
NLLB_CODES = {
    "中文": "zho_Hans", "英语": "eng_Latn", "日语": "jpn_Jpan", "韩语": "kor_Hang",
    "法语": "fra_Latn", "德语": "deu_Latn", "俄语": "rus_Cyrl", "西班牙语": "spa_Latn",
    "葡萄牙语": "por_Latn", "意大利语": "ita_Latn", "阿拉伯语": "arb_Arab",
    "泰语": "tha_Thai", "越南语": "vie_Latn",
}


class HfMtError(Exception):
    """官方模型端侧翻译失败。"""


def _has(pkg: str) -> bool:
    """包是否可用:先看当前环境,再看按需下载的运行时目录。"""
    if importlib.util.find_spec(pkg) is not None:
        return True
    return (local_models.HF_RUNTIME_DIR / pkg).exists()


def runtime_ready() -> bool:
    """transformers + torch 是否可用(venv 内或已下载的运行时目录)。"""
    return _has("transformers") and _has("torch")


def _ensure_path() -> None:
    d = str(local_models.HF_RUNTIME_DIR)
    if d not in sys.path and (Path(d) / "transformers").exists():
        sys.path.insert(0, d)
    importlib.invalidate_caches()


def detect_source(text: str) -> str:
    """NLLB 不支持自动检测来源语言,按字符范围做轻量判断。"""
    for ch in text or "":
        code = ord(ch)
        if 0x3040 <= code <= 0x30FF:
            return "日语"
        if 0xAC00 <= code <= 0xD7AF:
            return "韩语"
        if 0x0E00 <= code <= 0x0E7F:
            return "泰语"
        if 0x0600 <= code <= 0x06FF:
            return "阿拉伯语"
        if 0x0400 <= code <= 0x04FF:
            return "俄语"
        if 0x4E00 <= code <= 0x9FFF:
            return "中文"
    return "英语"


def _load(tier: str):
    if tier in _cache:
        return _cache[tier]
    _ensure_path()
    try:
        transformers = importlib.import_module("transformers")
        torch = importlib.import_module("torch")
    except Exception as exc:  # noqa: BLE001
        raise HfMtError("端侧大模型运行时未安装:请在设置 → 端侧模型 中下载(约 2.5GB)") from exc
    d = local_models.HF_MT_DIR / tier
    if not (d / "config.json").exists():
        raise HfMtError(f"{tier} 档模型尚未下载")
    tokenizer = transformers.AutoTokenizer.from_pretrained(str(d))
    model = transformers.AutoModelForSeq2SeqLM.from_pretrained(str(d))
    model.eval()
    try:
        if getattr(model, "generation_config", None) is not None:
            model.generation_config.max_length = None
    except Exception:
        pass
    try:
        torch.set_num_threads(max(2, min(8, (torch.get_num_threads() or 4))))
    except Exception:
        pass
    _cache[tier] = (tokenizer, model, torch)
    return _cache[tier]


def release(keep: str = "") -> int:
    """释放已加载的模型(切档位/关闭端侧翻译时调用),返回释放的档位数量。

    NLLB-600M 加载后常驻约 2.4GB;切到 1.3B 档若两个都留在内存里会叠加,
    因此切档时必须把上一档丢掉。keep 指定要保留的档位(通常是即将使用的档)。
    """
    freed = 0
    with _lock:
        for tier in [t for t in list(_cache) if t != keep]:
            tok, model, _torch = _cache.pop(tier)
            try:
                model.to("cpu")
            except Exception:
                pass
            del tok, model
            freed += 1
        if freed:
            try:
                import gc
                gc.collect()
            except Exception:
                pass
    return freed


def loaded_tiers() -> list:
    """当前已加载(常驻内存)的档位列表,供设置页展示与验证。"""
    with _lock:
        return sorted(_cache)


def _lang_id(tokenizer, code: str):
    """NLLB 语言标记 -> id(优先 lang_code_to_id,回退 convert_tokens_to_ids)。"""
    mapping = getattr(tokenizer, "lang_code_to_id", None)
    if isinstance(mapping, dict) and code in mapping:
        return int(mapping[code])
    tid = tokenizer.convert_tokens_to_ids(code)
    if tid is None or tid == tokenizer.unk_token_id:
        raise HfMtError(f"分词器不识别语言标记:{code}")
    return int(tid)


def translate_segments(segments: list, source_lang: str, target_lang: str, tier: str = "") -> list:
    """按段翻译:源语言在编码前显式设定,目标语言用 forced_bos_token_id 强制。"""
    if not segments:
        return []
    tier = tier or local_models.get_mt_tier()
    with _lock:
        tokenizer, model, torch = _load(tier)
        src_name = source_lang if source_lang in NLLB_CODES else detect_source("\n".join(segments))
        src_code = NLLB_CODES.get(src_name, "eng_Latn")
        dst_code = NLLB_CODES.get(target_lang)
        if not dst_code:
            raise HfMtError(f"NLLB 不支持的目标语言:{target_lang}")
        tokenizer.src_lang = src_code
        forced = _lang_id(tokenizer, dst_code)
        out = []
        with torch.no_grad():
            for seg in segments:
                if not seg.strip():
                    out.append("")
                    continue
                batch = tokenizer(seg, return_tensors="pt", truncation=True, max_length=400)
                generated = model.generate(**batch, forced_bos_token_id=forced, num_beams=4,
                                           max_new_tokens=256, no_repeat_ngram_size=0,
                                           length_penalty=1.0, early_stopping=True)
                text = tokenizer.batch_decode(generated, skip_special_tokens=True)[0].strip()
                out.append(text)
        return out


def translate_text(text: str, source_lang: str, target_lang: str, tier: str = "") -> str:
    return "\n".join(translate_segments([text], source_lang, target_lang, tier))
