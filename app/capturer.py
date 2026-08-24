# -*- coding: utf-8 -*-
"""屏幕区域截图:Qt 逻辑坐标 -> mss 物理像素,支持多显示器与不同 DPI 缩放。"""
import io

import mss
from PIL import Image
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QWidget


class CaptureError(Exception):
    pass


def capture_widget(widget: QWidget) -> bytes:
    """截取 widget 覆盖的屏幕区域,返回 PNG 字节。

    Qt 坐标是逻辑像素,mss 需要物理像素:按每个屏幕的 devicePixelRatio
    分别换算,并支持窗口跨越多个缩放不同的屏幕(逐屏截取后拼接)。
    """
    from PySide6.QtCore import QPoint

    tl = widget.mapToGlobal(widget.rect().topLeft())
    # bottomRight() 是 (宽-1, 高-1),需 +1 才是完整的右/下边界
    br = widget.mapToGlobal(widget.rect().bottomRight()) + QPoint(1, 1)
    bbox = (tl.x(), tl.y(), br.x(), br.y())
    if bbox[2] <= bbox[0] or bbox[3] <= bbox[1]:
        raise CaptureError("捕获区域为空")

    with mss.mss() as sct:
        parts = []  # (PIL.Image, 相对左上角物理x, 相对左上角物理y)
        for scr in QGuiApplication.screens():
            geo = scr.geometry()
            dpr = scr.devicePixelRatio()
            ix0, iy0 = max(bbox[0], geo.x()), max(bbox[1], geo.y())
            ix1, iy1 = min(bbox[2], geo.x() + geo.width()), min(bbox[3], geo.y() + geo.height())
            if ix1 <= ix0 or iy1 <= iy0:
                continue
            region = {
                "left": int(ix0 * dpr),
                "top": int(iy0 * dpr),
                "width": int((ix1 - ix0) * dpr),
                "height": int((iy1 - iy0) * dpr),
            }
            shot = sct.grab(region)
            img = Image.frombytes("RGB", shot.size, shot.bgra, "raw", "BGRX")
            parts.append((img, int((ix0 - bbox[0]) * dpr), int((iy0 - bbox[1]) * dpr)))

        if not parts:
            raise CaptureError("捕获区域不在任何屏幕内")

        canvas_w = max(x + img.width for img, x, _ in parts)
        canvas_h = max(y + img.height for img, _, y in parts)
        canvas = Image.new("RGB", (canvas_w, canvas_h), (0, 0, 0))
        for img, x, y in parts:
            canvas.paste(img, (x, y))

    buf = io.BytesIO()
    canvas.save(buf, format="PNG")
    return buf.getvalue()
