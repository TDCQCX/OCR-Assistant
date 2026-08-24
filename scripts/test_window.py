# -*- coding: utf-8 -*-
"""GUI 冒烟测试:启动窗口,验证 截图 + 窗口缩放联动 + 面板绘制。

运行: .venv\\Scripts\\python scripts\\test_window.py
"""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PIL import Image  # noqa: E402
from PySide6.QtCore import QTimer  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from app.capturer import capture_widget  # noqa: E402
from app.overlay import OverlayWindow  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent


def main():
    app = QApplication(sys.argv)
    w = OverlayWindow()
    w.show()

    def step1():
        # 截图(隐藏边框)
        w._hide_border = True
        w.rect_area.update()
        app.processEvents()
        time.sleep(0.06)
        png = capture_widget(w.rect_area)
        w._hide_border = False
        w.rect_area.update()
        (ROOT / "test_capture.png").write_bytes(png)
        img = Image.open(__import__("io").BytesIO(png))
        print(f"capture ok: {img.size}, bytes={len(png)}")
        # 窗口缩放 -> 洞口应随之变大,宽/高输入框同步
        w.resize(1000, 820)
        QTimer.singleShot(200, step2)

    def step2():
        app.processEvents()
        print("after resize: rect_area =", w.rect_area.width(), "x", w.rect_area.height(),
              "| 配置记忆窗口尺寸 =", w.cfg["window"]["width"], "x", w.cfg["window"]["height"])
        # 面板绘制(含挖洞)不崩溃,并导出可见外观
        w.grab().save(str(ROOT / "test_window_grab.png"))
        print("grab saved")
        app.quit()

    QTimer.singleShot(1200, step1)
    app.exec()
    print("window test done")


if __name__ == "__main__":
    main()
