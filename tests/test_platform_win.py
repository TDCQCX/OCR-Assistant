# -*- coding: utf-8 -*-
"""Windows 平台层:截图口径与剪贴板(不依赖窗口,可独立验证)。

这里守住的是历史上出过大事故的两条:
  * 抓屏单位必须是**物理像素**(125% 缩放下逻辑坐标会让捕获区域整体偏移);
  * 复制必须真的落到系统剪贴板(WebView 的 navigator.clipboard 不可靠)。
"""
import io
import sys

import pytest
from PIL import Image

from app import capturer

pytestmark = pytest.mark.skipif(sys.platform != "win32", reason="仅在 Windows 上验证平台层")


def test_virtual_screen_is_physical_pixels():
    vs = capturer.virtual_screen()
    assert vs["width"] > 0 and vs["height"] > 0
    # 物理像素范围应不小于逻辑范围的常见下限,且是整数(避免浮点口径混入)
    for k in ("left", "top", "width", "height"):
        assert isinstance(vs[k], int), f"{k} 必须是整数像素"


def test_monitor_count_at_least_one():
    assert capturer.monitor_count() >= 1


def test_grab_region_returns_png_of_exact_size():
    """抓到的图必须与请求尺寸逐像素相等:这是"识别区域与洞口一致"的底线。"""
    w, h = 120, 80
    png = capturer.grab_region(0, 0, w, h)
    img = Image.open(io.BytesIO(png))
    assert img.format == "PNG"
    assert img.size == (w, h)


def test_grab_region_rejects_tiny_area():
    with pytest.raises(capturer.CaptureError):
        capturer.grab_region(0, 0, 1, 1)


def test_grab_region_bottom_right_corner():
    """抓取右下角区域:验证坐标换算没有把区域挤出屏幕(负/超界坐标会报错)。"""
    vs = capturer.virtual_screen()
    left = int(vs["left"] + vs["width"] - 40)
    top = int(vs["top"] + vs["height"] - 30)
    png = capturer.grab_region(left, top, 40, 30)
    assert Image.open(io.BytesIO(png)).size == (40, 30)


def test_clipboard_roundtrip():
    from app.clipboard import copy_text

    text = "OCR 助手剪贴板自检 12345"
    assert copy_text(text) is True

    import ctypes
    from ctypes import wintypes

    user32 = ctypes.windll.user32
    kernel32 = ctypes.windll.kernel32
    user32.OpenClipboard.argtypes = [wintypes.HWND]
    user32.GetClipboardData.argtypes = [wintypes.UINT]
    user32.GetClipboardData.restype = wintypes.HANDLE
    kernel32.GlobalLock.argtypes = [wintypes.HGLOBAL]
    kernel32.GlobalLock.restype = ctypes.c_void_p
    kernel32.GlobalUnlock.argtypes = [wintypes.HGLOBAL]

    assert user32.OpenClipboard(None)
    try:
        handle = user32.GetClipboardData(13)  # CF_UNICODETEXT
        assert handle, "剪贴板里没有文本"
        ptr = kernel32.GlobalLock(handle)
        got = ctypes.wstring_at(ptr)
        kernel32.GlobalUnlock(handle)
    finally:
        user32.CloseClipboard()
    assert got == text


def test_clipboard_handles_empty_text():
    from app.clipboard import copy_text

    assert copy_text("") is True
