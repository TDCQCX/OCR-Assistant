# -*- coding: utf-8 -*-
"""生成应用图标 assets/app.ico(蓝色圆角 + OCR 字样)。"""
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def main():
    size = 256
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    # 蓝色圆角底
    d.rounded_rectangle([8, 8, size - 8, size - 8], radius=52, fill=(76, 141, 255, 255))
    # 放大镜图形
    cx, cy, r = 110, 108, 62
    d.ellipse([cx - r, cy - r, cx + r, cy + r], outline=(255, 255, 255, 255), width=16)
    d.line([cx + r * 0.72, cy + r * 0.72, cx + 92, cy + 92], fill=(255, 255, 255, 255), width=18)
    # 文字 OCR
    try:
        font = ImageFont.truetype("C:/Windows/Fonts/msyh.ttc", 44)
    except Exception:
        font = ImageFont.load_default()
    d.text((cx - 40, cy - 26), "OCR", fill=(255, 255, 255, 255), font=font)
    img.save(str(Path(__file__).resolve().parent.parent / "assets" / "app.ico"),
             format="ICO", sizes=[(256, 256), (64, 64), (48, 48), (32, 32), (16, 16)])
    print("app.ico 已生成")


if __name__ == "__main__":
    main()
