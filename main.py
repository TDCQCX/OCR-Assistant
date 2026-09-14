# -*- coding: utf-8 -*-
"""OCR 助手 —— 程序入口(React + pywebview/Qt 界面,Python 后端)。"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from app.manager import App


def main() -> int:
    # DPI 感知由 Qt 默认的 PerMonitorV2 处理,无需额外设置
    App().start()
    return 0


if __name__ == "__main__":
    sys.exit(main())
