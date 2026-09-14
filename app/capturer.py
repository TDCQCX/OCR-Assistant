# -*- coding: utf-8 -*-
"""屏幕截图:按物理像素区域抓取(mss),并获取虚拟桌面范围。"""
import io

import mss
from PIL import Image


class CaptureError(Exception):
    """截图失败。"""


def set_dpi_awareness() -> None:
    """Windows 每显示器 DPI 感知,保证坐标与物理像素一致。"""
    try:
        import ctypes
        ctypes.windll.shcore.SetProcessDpiAwareness(2)  # PROCESS_PER_MONITOR_DPI_AWARE
    except Exception:
        try:
            import ctypes
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass


def virtual_screen() -> dict:
    """虚拟桌面(所有显示器合并)范围,单位:物理像素。"""
    with mss.mss() as sct:
        m = sct.monitors[0]
        return {"left": m["left"], "top": m["top"], "width": m["width"], "height": m["height"]}


def monitor_count() -> int:
    with mss.mss() as sct:
        return max(1, len(sct.monitors) - 1)


def grab_region(left: int, top: int, width: int, height: int) -> bytes:
    """抓取屏幕区域(物理像素),返回 PNG 字节。"""
    if width < 2 or height < 2:
        raise CaptureError("捕获区域过小")
    with mss.mss() as sct:
        shot = sct.grab({"left": int(left), "top": int(top),
                         "width": int(width), "height": int(height)})
        img = Image.frombytes("RGB", shot.size, shot.bgra, "raw", "BGRX")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()
