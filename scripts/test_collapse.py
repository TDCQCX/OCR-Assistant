# -*- coding: utf-8 -*-
"""验证:折叠/展开识别结果与回答区时,窗口高度跟随变化,且洞口高度保持不变。"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PySide6.QtCore import QTimer  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from app.overlay import OverlayWindow  # noqa: E402


def main():
    app = QApplication(sys.argv)
    w = OverlayWindow()
    w.show()
    state = {}

    def step1():
        state["hole0"] = w.rect_area.height()
        print(f"初始: 窗口{w.height()} 洞口{state['hole0']}")
        w.section_ocr.set_expanded(False)
        QTimer.singleShot(300, step2)

    def step2():
        hole1 = w.rect_area.height()
        print(f"折叠OCR后: 窗口{w.height()} 洞口{hole1} | "
              f"底栏 sizeHint={w.bottom_bar.sizeHint().height()} 实际={w.bottom_bar.height()}")
        assert abs(hole1 - state["hole0"]) <= 2, f"洞口高度变化:{state['hole0']}->{hole1}"
        w.section_answer.set_expanded(False)
        QTimer.singleShot(300, step3)

    def step3():
        hole2 = w.rect_area.height()
        print(f"再折叠回答后: 窗口{w.height()} 洞口{hole2}")
        assert abs(hole2 - state["hole0"]) <= 2, f"洞口高度变化:{state['hole0']}->{hole2}"
        w.section_ocr.set_expanded(True)
        w.section_answer.set_expanded(True)
        QTimer.singleShot(300, step4)

    def step4():
        print(f"全部展开: 窗口{w.height()} 洞口{w.rect_area.height()}")
        print("折叠逻辑验证 OK")
        app.quit()

    QTimer.singleShot(900, step1)
    app.exec()


if __name__ == "__main__":
    main()
