# -*- coding: utf-8 -*-
"""本地 OCR 引擎:RapidOCR(ONNX Runtime,PP-OCR 模型)。

- 体积小(~50MB 模型,无需 PaddlePaddle),CPU 推理约 100-300ms;
- 懒加载:首次使用时才加载模型并预热;
- 识别结果按阅读顺序(上→下、左→右)排序,并把同一视觉行内的文字块合并成一行,
  避免把一句话拆成逐词的多个片段。
"""
import io

from PIL import Image

_engine = None

_CJK = lambda ch: "\u3000" <= ch <= "\u9fff" or "\uff00" <= ch <= "\uffef"  # noqa: E731


def _get_engine():
    global _engine
    if _engine is None:
        try:
            from rapidocr_onnxruntime import RapidOCR
        except ImportError as exc:
            raise RuntimeError(
                "本地 OCR 模型未安装:请执行 pip install rapidocr_onnxruntime"
            ) from exc
        _engine = RapidOCR()
        # 预热,消除首次推理延迟
        import numpy as np
        warm = np.zeros((60, 120, 3), dtype=np.uint8)
        warm[:] = 255
        _engine(warm)
    return _engine


def _join(parts: list) -> str:
    """同一行内相邻文字块的拼接:中文之间不加空格,其余加空格。"""
    out = ""
    for part in parts:
        part = part.strip()
        if not part:
            continue
        if not out:
            out = part
        elif _CJK(out[-1]) and _CJK(part[0]):
            out += part
        else:
            out += " " + part
    return out


def _merge_lines(boxes: list) -> list:
    """把同一视觉行(竖直方向重叠、中心线接近)的文字块合并为一行。"""
    items = []
    for box, text in boxes:
        ys = [p[1] for p in box]
        xs = [p[0] for p in box]
        items.append({
            "text": text, "top": min(ys), "bottom": max(ys), "left": min(xs),
            "center": (min(ys) + max(ys)) / 2.0, "height": max(1.0, max(ys) - min(ys)),
        })
    items.sort(key=lambda it: (it["center"], it["left"]))

    lines, cur = [], []
    for it in items:
        if not cur:
            cur = [it]
            continue
        ref = cur[0]
        ref_h = max(ref["height"], it["height"])
        overlap = min(ref["bottom"], it["bottom"]) - max(ref["top"], it["top"])
        same_line = overlap > ref_h * 0.45 or abs(it["center"] - (sum(c["center"] for c in cur) / len(cur))) < ref_h * 0.6
        if same_line:
            cur.append(it)
        else:
            lines.append(cur)
            cur = [it]
    if cur:
        lines.append(cur)

    out = []
    for line in lines:
        line.sort(key=lambda it: it["left"])
        out.append(_join([it["text"] for it in line]))
    return [ln for ln in out if ln.strip()]


def recognize(png_bytes: bytes) -> str:
    """识别 PNG 图片中的文字,按阅读顺序返回多行文本(同一行已合并)。"""
    img = Image.open(io.BytesIO(png_bytes)).convert("RGB")
    import numpy as np
    result, _ = _get_engine()(np.array(img))
    if not result:
        return ""
    # result: [[[x1,y1],[x2,y2],[x3,y3],[x4,y4]], text, score]
    boxes = [(item[0], str(item[1])) for item in result if len(item) >= 2]
    return "\n".join(_merge_lines(boxes))
