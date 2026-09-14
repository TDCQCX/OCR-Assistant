# -*- coding: utf-8 -*-
"""端侧翻译推理:CTranslate2(int8)+ sentencepiece。

支持两类专用翻译模型(都不是通用大模型,CPU 上可直接跑):
- opus-mt / Argos 包:单语言对,轻量档;
- NLLB-200 distilled(600M / 1.3B,int8):多语言单模型,覆盖 200 种语言,带语言标记。

运行时与模型都不随应用分发,首次使用时按需下载(见 app/local_models.py)。
"""
import threading

from app import local_models

_lock = threading.Lock()
_translator = {}
_sp = {}
_meta = {}

# NLLB 语言标记(FLORES-200)
NLLB_CODES = {
    "中文": "zho_Hans", "英语": "eng_Latn", "日语": "jpn_Jpan", "韩语": "kor_Hang",
    "法语": "fra_Latn", "德语": "deu_Latn", "俄语": "rus_Cyrl", "西班牙语": "spa_Latn",
    "葡萄牙语": "por_Latn", "意大利语": "ita_Latn", "阿拉伯语": "arb_Arab",
    "泰语": "tha_Thai", "越南语": "vie_Latn",
}


class LocalMtError(Exception):
    """端侧翻译失败。"""


def available(source_lang: str, target_lang: str) -> bool:
    return bool(local_models.mt_current_model()[1])


def _import_ct2():
    local_models.ensure_runtime_path()
    try:
        import ctranslate2  # noqa: PLC0415
        return ctranslate2
    except ImportError as exc:
        raise LocalMtError("端侧推理运行时尚未下载(设置 → 翻译设置 → 端侧模型)") from exc


def _import_spm():
    try:
        import sentencepiece as spm  # noqa: PLC0415
        return spm
    except ImportError as exc:
        raise LocalMtError("缺少 sentencepiece:请在设置 → 端侧模型 中下载运行时") from exc


def detect_source(text: str) -> str:
    """NLLB 不支持自动检测来源语言,这里按字符范围做轻量判断。"""
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


def _load() -> tuple:
    """加载当前档位模型,返回 (translator, sp, meta)。"""
    tier, d = local_models.mt_current_model()
    if not d or not (d / "model.bin").exists():
        raise LocalMtError("端侧翻译模型尚未下载:请在设置 → 翻译设置 → 端侧模型 中下载")
    if tier in _translator:
        return _translator[tier], _sp[tier], _meta[tier]
    ct2 = _import_ct2()
    spm = _import_spm()
    sp_file = d / "sentencepiece.model"
    if not sp_file.exists():
        sp_file = d / "sentencepiece.bpe.model"
    translator = ct2.Translator(str(d), device="cpu", compute_type="int8", inter_threads=1,
                                intra_threads=max(2, (ct2.get_cuda_device_count() or 0) or 4))
    sp = spm.SentencePieceProcessor(model_file=str(sp_file))
    info = local_models.mt_tier_info(tier)
    meta = {"tier": tier, "multi": info.get("kind") == "multi", "name": info.get("name", tier)}
    _translator[tier], _sp[tier], _meta[tier] = translator, sp, meta
    return translator, sp, meta


def _clean(text: str) -> str:
    text = (text or "").replace("▁", " ").strip()
    while "  " in text:
        text = text.replace("  ", " ")
    return text


def translate_segments(segments: list, source_lang: str, target_lang: str) -> list:
    """批量按段翻译(单次模型调用)。多语言模型走 NLLB 语言标记。"""
    if not segments:
        return []
    with _lock:
        translator, sp, meta = _load()
        if meta["multi"]:
            src_name = source_lang if source_lang in NLLB_CODES else detect_source("\n".join(segments))
            dst_code = NLLB_CODES.get(target_lang)
            if not dst_code:
                raise LocalMtError(f"NLLB 不支持的目标语言:{target_lang}")
            prefix = NLLB_CODES.get(src_name, "eng_Latn")
            tokens = [[prefix] + sp.encode(s, out_type=str) for s in segments]
            results = translator.translate_batch(
                tokens, target_prefix=[[dst_code] for _ in segments],
                beam_size=4, max_decoding_length=512, max_batch_size=8)
            out = []
            for item in results:
                hyp = item.hypotheses[0] if item.hypotheses else []
                if hyp and hyp[0] == dst_code:
                    hyp = hyp[1:]
                out.append(_clean(sp.decode(hyp)))
            while len(out) < len(segments):
                out.append("")
            return out[:len(segments)]
        batch = [sp.encode(s, out_type=str) for s in segments]
        results = translator.translate_batch(batch, beam_size=4, max_decoding_length=320,
                                             max_batch_size=16)
        out = [_clean(sp.decode(item.hypotheses[0] if item.hypotheses else [])) for item in results]
        while len(out) < len(segments):
            out.append("")
        return out[:len(segments)]


def translate_text(text: str, source_lang: str, target_lang: str) -> str:
    return "\n".join(translate_segments([text], source_lang, target_lang))
