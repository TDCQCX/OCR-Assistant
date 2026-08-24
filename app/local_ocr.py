# -*- coding: utf-8 -*-
"""本地 OCR 引擎:RapidOCR(ONNX Runtime,PP-OCR 模型)。

- 体积小(~50MB 模型,无需 PaddlePaddle),CPU 推理约 100-300ms;
- 懒加载:首次使用时才加载模型并预热;
- 识别结果按阅读顺序(上→下、左→右)排序输出。
"""
import io

from PIL import Image

_engine = None


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


def recognize(png_bytes: bytes) -> str:
    """识别 PNG 图片中的文字,按阅读顺序返回多行文本。"""
    img = Image.open(io.BytesIO(png_bytes)).convert("RGB")
    import numpy as np
    result, _ = _get_engine()(np.array(img))
    if not result:
        return ""
    # result: [[[x1,y1],[x2,y2],[x3,y3],[x4,y4]], text, score],按 上→下、左→右 排序
    boxes = [(item[0], str(item[1])) for item in result if len(item) >= 2]
    boxes.sort(key=lambda b: (min(p[1] for p in b[0]) // 24, min(p[0] for p in b[0])))
    return "\n".join(text for _, text in boxes)
