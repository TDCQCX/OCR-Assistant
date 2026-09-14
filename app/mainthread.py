# -*- coding: utf-8 -*-
"""Qt 主线程调度:窗口与 WebView 操作必须在 Qt 主线程执行,此处把子线程调用排队回主线程。"""
import threading

_lock = threading.Lock()
_invoker = None


def _ensure_invoker():
    global _invoker
    if _invoker is not None:
        return _invoker
    with _lock:
        if _invoker is not None:
            return _invoker
        from PySide6.QtCore import QObject, Qt, Signal, Slot
        from PySide6.QtWidgets import QApplication

        class _Invoker(QObject):
            sig = Signal(object)

            def __init__(self):
                super().__init__()
                self.sig.connect(self._run, Qt.ConnectionType.QueuedConnection)

            @Slot(object)
            def _run(self, fn):
                try:
                    fn()
                except Exception:
                    pass

        inv = _Invoker()
        app = QApplication.instance()
        if app is not None:
            inv.moveToThread(app.thread())  # 让槽函数在 GUI 线程执行
        _invoker = inv
        return inv


def run_in_main(fn):
    """在主线程执行 fn;若已在主线程或无 Qt 应用则直接执行。"""
    try:
        from PySide6.QtCore import QThread
        from PySide6.QtWidgets import QApplication
    except Exception:
        fn()
        return
    app = QApplication.instance()
    if app is None:
        fn()
        return
    if QThread.currentThread() is app.thread():
        fn()
        return
    _ensure_invoker().sig.emit(fn)
