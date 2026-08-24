# -*- coding: utf-8 -*-
"""API 冒烟测试:用一张程序生成的带文字图片,验证 百炼 OCR + 图文问答 全链路。

运行: .venv\\Scripts\\python scripts\\smoke.py
"""
import io
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PIL import Image, ImageDraw  # noqa: E402

from app.agent import AgentClient  # noqa: E402
from app.config import load_config  # noqa: E402


def make_test_image() -> bytes:
    img = Image.new("RGB", (640, 200), "white")
    d = ImageDraw.Draw(img)
    d.text((20, 30), "Hello OCR 12345", fill="black")
    d.text((20, 80), "Price: 99.00 USD", fill="black")
    d.text((20, 130), "Qwen3.7-Flash Vision Test", fill="black")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def main():
    cfg = load_config()
    from app.config import active_provider
    p = active_provider(cfg)
    client = AgentClient(
        p["api_key"], p["model"], p["base_url"],
        cfg["request_template"],
        timeout=int(cfg.get("timeout", 180)),
        max_side=int(cfg["capture"].get("max_side", 2048)),
        enable_thinking=bool(p.get("enable_thinking", False)),
    )
    png = make_test_image()

    print("== 第1步:云端 OCR ==")
    ocr = client.ocr(png, cfg["prompts"]["ocr"])
    print(ocr)

    print("\n== 第2步:图文问答 ==")
    prompt = (
        cfg["prompts"]["answer"]
        .replace("{qtype}", "未知")
        .replace("{qtitle}", "未知")
        .replace("{options}", "无选项")
        .replace("{question}", "图中显示的商品单价是多少?")
        .replace("{ocr_text}", ocr)
    )
    print(client.answer(png, prompt))


if __name__ == "__main__":
    main()
