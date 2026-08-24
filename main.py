# -*- coding: utf-8 -*-
"""透明截图 OCR 识别助手 —— 程序入口。

启动:python main.py (或 .venv\\Scripts\\python main.py)
"""
import ctypes
import sys

from PySide6.QtWidgets import QApplication

from app.overlay import OverlayWindow

# Windows 每显示器 DPI 感知(Per-Monitor V2):
# 让 Qt 逻辑坐标与屏幕物理像素一致,保证 100%/125%/150% 缩放下截图准确。
PER_MONITOR_AWARE_V2 = ctypes.c_void_p(-4)


def setup_dpi_awareness() -> None:
    try:
        ctypes.windll.user32.SetProcessDpiAwarenessContext(PER_MONITOR_AWARE_V2)
    except Exception:
        pass  # 非 Windows 或系统不支持时忽略,由 Qt 自行处理


def main() -> int:
    setup_dpi_awareness()
    app = QApplication(sys.argv)
    app.setApplicationName("截图OCR助手")
    window = OverlayWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
