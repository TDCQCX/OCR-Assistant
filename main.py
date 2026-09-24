# -*- coding: utf-8 -*-
"""OCR 助手 —— 程序入口(React + pywebview/Qt 界面,Python 后端)。"""
import os
import sys

# 优化启动速度与内存占用:限制渲染进程数量、关闭 GPU 合成与后台网络。
# 必须在导入 pywebview(进而导入 QtWebEngine)之前设置。
os.environ.setdefault(
    "QTWEBENGINE_CHROMIUM_FLAGS",
    "--disable-gpu --disable-gpu-compositing --disable-software-rasterizer "
    "--disable-dev-shm-usage --disable-background-networking --disable-sync "
    "--disable-features=Translate,BackForwardCache,MediaRouter "
    "--renderer-process-limit=2 --process-per-site --js-flags=--max-old-space-size=96",
)
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from app.manager import App


def main() -> int:
    # DPI 感知由 Qt 默认的 PerMonitorV2 处理,无需额外设置
    App().start()
    return 0


if __name__ == "__main__":
    sys.exit(main())
