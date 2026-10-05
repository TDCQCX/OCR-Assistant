# -*- coding: utf-8 -*-
"""Win32 窗口区域(洞口穿透)与 DPI 坐标换算。

悬浮窗要把「洞口」从窗口区域里挖掉,鼠标才能直达后方的目标内容;截图时又必须
把 WebView 的 CSS 坐标换算成屏幕物理像素。这两件事都需要处理 DPI:

  * pywebview/Qt 的 ``window.x`` / ``window.width`` 是 **逻辑像素(DIP)**;
  * ``mss`` 抓屏与 ``SetWindowRgn`` 用的是 **物理像素**。

在 125% / 150% 缩放的屏幕上两者相差 1.25~1.5 倍,直接用逻辑坐标去截屏会导致
捕获区域整体偏移(窗口越靠右下偏移越大)。因此统一在这里用具名 dwm/user32
接口换算,避免各调用点各写一份换算而互相不一致。
"""
import ctypes
from ctypes import wintypes

# CombineRgn 的合并模式:两个区域求并集
RGN_OR = 2

# SetWindowPos 标志:不改尺寸/位置/层序,但让系统按新区域重算窗口框并重绘
_SWP_FLAGS = 0x0001 | 0x0002 | 0x0004 | 0x0010 | 0x0020


def screen_scale() -> float:
    """当前主屏缩放比(200% 缩放 → 2.0);取不到时返回 1.0。"""
    try:
        from PySide6.QtGui import QGuiApplication
        screen = QGuiApplication.primaryScreen()
        if screen is not None:
            dpr = float(screen.devicePixelRatio() or 1.0)
            if dpr > 0:
                return dpr
    except Exception:
        pass
    return 1.0


def hwnd_of(win) -> int:
    """取窗口句柄(native winId);取不到返回 0。"""
    try:
        return int(win.native.winId()) if win is not None else 0
    except Exception:
        return 0


def client_origin(win):
    """窗口客户区左上角在桌面上的物理像素坐标 (x, y);失败返回 None。

    用 ClientToScreen 而不是 ``win.x * scale``:多显示器且缩放比不同时,
    后者会取错缩放;前者由系统直接给出真实屏幕坐标。
    """
    hwnd = hwnd_of(win)
    if not hwnd:
        return None
    try:
        user32 = ctypes.windll.user32
        user32.ClientToScreen.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.POINT)]
        user32.ClientToScreen.restype = wintypes.BOOL
        pt = wintypes.POINT(0, 0)
        if not user32.ClientToScreen(hwnd, ctypes.byref(pt)):
            return None
        return int(pt.x), int(pt.y)
    except Exception:
        return None


def window_origin_physical(win):
    """窗口左上角(含边框)的物理像素坐标,作为客户区换算的兜底。"""
    hwnd = hwnd_of(win)
    if not hwnd:
        return None
    try:
        user32 = ctypes.windll.user32
        user32.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
        user32.GetWindowRect.restype = wintypes.BOOL
        r = wintypes.RECT()
        if not user32.GetWindowRect(hwnd, ctypes.byref(r)):
            return None
        return int(r.left), int(r.top)
    except Exception:
        return None


def physical_origin(win):
    """客户区原点(物理像素);ClientToScreen 不可用时退回窗口原点 * 缩放比。"""
    origin = client_origin(win)
    if origin is not None:
        return origin
    origin = window_origin_physical(win)
    if origin is not None:
        return origin
    try:
        k = screen_scale()
        return int(round(float(win.x) * k)), int(round(float(win.y) * k))
    except Exception:
        return None


def _client_size(hwnd) -> tuple:
    user32 = ctypes.windll.user32
    user32.GetClientRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
    user32.GetClientRect.restype = wintypes.BOOL
    r = wintypes.RECT()
    if not user32.GetClientRect(hwnd, ctypes.byref(r)):
        return 0, 0
    return int(r.right - r.left), int(r.bottom - r.top)


def apply_hole_region(win, hx: int, hy: int, hw: int, hh: int) -> bool:
    """把矩形 (hx, hy, hw, hh) 从窗口区域中挖掉(物理像素),成功返回 True。

    区域 = 整窗矩形 - 洞口矩形(四块围绕洞口的长条合并);洞口为 0 面积时
    退化为整窗矩形(不挖)。
    """
    hwnd = hwnd_of(win)
    if not hwnd:
        return False
    try:
        user32 = ctypes.windll.user32
        gdi32 = ctypes.windll.gdi32
        # 必须声明原型:64 位下句柄按 int 传参会截断,区域创建会静默失败
        gdi32.CreateRectRgn.argtypes = [ctypes.c_int] * 4
        gdi32.CreateRectRgn.restype = wintypes.HANDLE
        gdi32.SetRectRgn.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_int,
                                     ctypes.c_int, ctypes.c_int]
        gdi32.SetRectRgn.restype = ctypes.c_int
        gdi32.CombineRgn.argtypes = [wintypes.HANDLE, wintypes.HANDLE, wintypes.HANDLE,
                                     ctypes.c_int]
        gdi32.CombineRgn.restype = ctypes.c_int
        gdi32.DeleteObject.argtypes = [wintypes.HANDLE]
        gdi32.DeleteObject.restype = wintypes.BOOL
        user32.SetWindowRgn.argtypes = [wintypes.HWND, wintypes.HANDLE, wintypes.BOOL]
        user32.SetWindowRgn.restype = ctypes.c_int
        user32.SetWindowPos.argtypes = [wintypes.HWND, wintypes.HWND, ctypes.c_int,
                                        ctypes.c_int, ctypes.c_int, ctypes.c_int,
                                        ctypes.c_uint]

        cw, ch = _client_size(hwnd)
        if cw < 8 or ch < 8:
            return False
        left, top = max(0, int(hx)), max(0, int(hy))
        right, bottom = min(cw, int(hx) + int(hw)), min(ch, int(hy) + int(hh))
        if right - left < 4 or bottom - top < 4:
            parts = [(0, 0, cw, ch)]          # 洞口退化:整窗可交互
        else:
            parts = [
                (0, 0, cw, top),                      # 洞口上方
                (0, bottom, cw, ch - bottom),         # 洞口下方
                (0, top, left, bottom - top),         # 洞口左侧
                (right, top, cw - right, bottom - top),  # 洞口右侧
            ]
        parts = [p for p in parts if p[2] > 0 and p[3] > 0]
        if not parts:
            return False

        rgn = gdi32.CreateRectRgn(0, 0, 0, 0)
        if not rgn:
            return False
        px, py, pw, ph = parts[0]
        gdi32.SetRectRgn(rgn, px, py, px + pw, py + ph)
        if len(parts) > 1:
            tmp = gdi32.CreateRectRgn(0, 0, 0, 0)
            for px, py, pw, ph in parts[1:]:
                gdi32.SetRectRgn(tmp, px, py, px + pw, py + ph)
                gdi32.CombineRgn(rgn, rgn, tmp, RGN_OR)
            gdi32.DeleteObject(tmp)

        if not user32.SetWindowRgn(hwnd, rgn, True):
            gdi32.DeleteObject(rgn)          # 失败时区域所有权仍在本地
            return False
        user32.SetWindowPos(hwnd, None, 0, 0, 0, 0, _SWP_FLAGS)
        return True
    except Exception:
        return False


def clear_region(win) -> bool:
    """清掉窗口区域(整窗矩形,全部可绘制/可点击)。"""
    hwnd = hwnd_of(win)
    if not hwnd:
        return False
    try:
        user32 = ctypes.windll.user32
        user32.SetWindowRgn.argtypes = [wintypes.HWND, wintypes.HANDLE, wintypes.BOOL]
        user32.SetWindowRgn.restype = ctypes.c_int
        return bool(user32.SetWindowRgn(hwnd, None, True))
    except Exception:
        return False
