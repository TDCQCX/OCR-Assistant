# -*- coding: utf-8 -*-
"""本地 OCR(RapidOCR)测试:生成带文字图片并识别,验证识别正确性与耗时。

运行: .venv\\Scripts\\python scripts\\test_local_ocr.py
"""
import io
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PIL import Image, ImageDraw  # noqa: E402

from app.local_ocr import recognize  # noqa: E402


def make_image() -> bytes:
    img = Image.new("RGB", (640, 140), "white")
    d = ImageDraw.Draw(img)
    d.text((20, 30), "Hello OCR 12345", fill="black")
    d.text((20, 70), "Price: 99.00 USD", fill="black")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def main():
    png = make_image()
    t0 = time.time()
    text = recognize(png)
    print(f"识别耗时: {time.time() - t0:.2f}s")
    print("识别结果:")
    print(text)
    joined = text.replace(" ", "").upper()
    assert "HELLO" in joined and "12345" in joined, f"识别不完整:{text!r}"
    assert "99.00" in joined or "USD" in joined, f"第二行未识别:{text!r}"
    print("本地 OCR 测试通过")


if __name__ == "__main__":
    main()
