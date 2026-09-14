# -*- coding: utf-8 -*-
"""端侧翻译推理:CTranslate2(int8)+ sentencepiece。

运行时与模型都不随应用分发,首次使用时按需下载(见 app/local_models.py):
- 运行时:ctranslate2 wheel → models/runtime
- 模型:Argos .argosmodel 包 → models/mt/<src>-<dst>
"""
import threading

from app import local_models

_lock = threading.Lock()
_translator = {}
_sp = {}


class OnnxMtError(Exception):
    """端侧翻译失败。"""


def available(source_lang: str, target_lang: str) -> bool:
    return local_models.mt_ready(source_lang, target_lang)


def _import_ct2():
    local_models.ensure_runtime_path()
    try:
        import ctranslate2  # noqa: PLC0415
        return ctranslate2
    except ImportError as exc:
        raise OnnxMtError("端侧推理运行时尚未下载(设置 → 翻译设置 → 端侧模型)") from exc


def _import_spm():
    try:
        import sentencepiece as spm  # noqa: PLC0415
        return spm
    except ImportError as exc:
        raise OnnxMtError("缺少 sentencepiece:请执行 pip install sentencepiece") from exc


def _load(source_lang: str, target_lang: str):
    key = f"{source_lang}->{target_lang}"
    if key in _translator:
        return _translator[key], _sp[key]
    d = local_models.mt_dir(source_lang, target_lang)
    if not (d / "model.bin").exists():
        raise OnnxMtError("端侧翻译模型尚未下载")
    ct2 = _import_ct2()
    spm = _import_spm()
    translator = ct2.Translator(str(d), device="cpu", compute_type="int8",
                                inter_threads=1, intra_threads=max(2, (ct2.get_cuda_device_count() or 0) or 4))
    sp = spm.SentencePieceProcessor(model_file=str(d / "sentencepiece.model"))
    _translator[key] = translator
    _sp[key] = sp
    return translator, sp


def _clean(text: str) -> str:
    text = (text or "").replace("▁", " ").strip()
    while "  " in text:
        text = text.replace("  ", " ")
    return text


def translate_segments(segments: list, source_lang: str, target_lang: str) -> list:
    """批量按段翻译(单次模型调用,速度快)。"""
    if not segments:
        return []
    with _lock:
        translator, sp = _load(source_lang, target_lang)
        batch = [sp.encode(s, out_type=str) for s in segments]
        results = translator.translate_batch(batch, beam_size=4, max_decoding_length=320,
                                             max_batch_size=16)
        out = []
        for item in results:
            hyp = item.hypotheses[0] if item.hypotheses else []
            out.append(_clean(sp.decode(hyp)))
        while len(out) < len(segments):
            out.append("")
        return out[:len(segments)]


def translate_text(text: str, source_lang: str, target_lang: str) -> str:
    return "\n".join(translate_segments([text], source_lang, target_lang))
