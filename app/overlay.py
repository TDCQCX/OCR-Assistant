# -*- coding: utf-8 -*-
"""透明置顶主窗口:上=功能与设置区 / 中=透明矩形工作区(洞口)/ 下=按钮+可折叠回复区。

- 窗口为不透明面板(圆角+描边),仅中部 OCR 工作区(矩形)透明,可透看后方目标窗口;
- 按住上/下栏空白处拖动窗口定位;拖拽窗口边缘/角落缩放,洞口随之缩放(尺寸自动记忆);
- 「配置」打开配置对话框;「主题」打开主题对话框;
- 回复区由三个独立可折叠区块组成:识别结果 / 识别类型与耗时 / 回答;
- 全局快捷键:默认 Ctrl+F1 截图识别、Ctrl+Q 退出。
"""
import time
from pathlib import Path

from PySide6.QtCore import QPoint, QRect, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from app.agent import AgentClient
from app.capturer import CaptureError, capture_widget
from app.config import load_config, save_config
from app.dialogs import SettingsDialog, ThemeDialog
from app.theme import build_stylesheet, theme_bg_color, theme_outline_color
from app.worker import PipelineWorker

MARGIN = 16        # 洞口四周的不透明边框宽度
SPACING = 8        # 根布局控件间距
EDGE = 8           # 缩放热区宽度
MIN_WIN_W = 480
MIN_WIN_H = 540
DEFAULT_QUESTION = "请给出该题目的答案"

# 状态文字:实心圆 ● 颜色(绿=就绪/完成,橙=处理中,红=失败)
STATUS_COLORS = {
    "idle": "#3FB950",
    "working": "#F5A623",
    "ok": "#3FB950",
    "error": "#F85149",
}


class ResizeHandle(QWidget):
    """窗口边缘/角落的隐形缩放热区。"""

    CURSORS = {
        "l": Qt.CursorShape.SizeHorCursor,
        "r": Qt.CursorShape.SizeHorCursor,
        "t": Qt.CursorShape.SizeVerCursor,
        "b": Qt.CursorShape.SizeVerCursor,
        "tl": Qt.CursorShape.SizeFDiagCursor,
        "br": Qt.CursorShape.SizeFDiagCursor,
        "tr": Qt.CursorShape.SizeBDiagCursor,
        "bl": Qt.CursorShape.SizeBDiagCursor,
    }

    def __init__(self, window: QWidget, edge: str):
        super().__init__(window)
        self._window = window
        self.edge = edge
        self.setCursor(self.CURSORS[edge])
        self._start_global = None
        self._start_geo = None

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._start_global = event.globalPosition().toPoint()
            self._start_geo = self._window.geometry()

    def mouseMoveEvent(self, event):
        if self._start_global is None or not (event.buttons() & Qt.MouseButton.LeftButton):
            return
        d = event.globalPosition().toPoint() - self._start_global
        g = self._start_geo
        x, y, w, h = g.x(), g.y(), g.width(), g.height()
        if "l" in self.edge:
            x = g.x() + d.x()
            w = g.width() - d.x()
        if "r" in self.edge:
            w = g.width() + d.x()
        if "t" in self.edge:
            y = g.y() + d.y()
            h = g.height() - d.y()
        if "b" in self.edge:
            h = g.height() + d.y()
        minw, minh = self._window.minimumWidth(), self._window.minimumHeight()
        if w < minw:
            x = x - (minw - w)
            w = minw
        if h < minh:
            y = y - (minh - h)
            h = minh
        self._window.setGeometry(x, y, w, h)

    def mouseReleaseEvent(self, event):
        self._start_global = None


class CaptureArea(QWidget):
    """中部透明工作区(洞口):只画矩形边框,鼠标事件穿透到下层应用。"""

    def __init__(self, owner: QWidget):
        super().__init__()
        self._owner = owner

    def paintEvent(self, event):
        if getattr(self._owner, "_hide_border", False):
            return
        border = self._owner.cfg.get("window", {}).get("border_color", "#FF5252")
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setPen(QPen(QColor(border), 2))
        p.drawRect(self.rect().adjusted(1, 1, -2, -2))


class CollapsibleSection(QWidget):
    """可折叠区块:标题(点击展开/收起)+ 内容控件。"""

    def __init__(self, title: str, content: QWidget, expanded: bool = True, parent=None):
        super().__init__(parent)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(4)
        self.header = QToolButton()
        self.header.setObjectName("sectionHeader")
        self.header.setText(title)
        self.header.setCheckable(True)
        self.header.setChecked(expanded)
        self.header.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.header.setArrowType(Qt.ArrowType.DownArrow if expanded else Qt.ArrowType.RightArrow)
        lay.addWidget(self.header)
        self.content = content
        lay.addWidget(self.content)
        self.header.toggled.connect(self._on_toggle)

    def _on_toggle(self, checked: bool):
        self.header.setArrowType(Qt.ArrowType.DownArrow if checked else Qt.ArrowType.RightArrow)
        self.content.setVisible(checked)

    def set_expanded(self, expanded: bool):
        self.header.setChecked(expanded)

    def set_text(self, text: str):
        if isinstance(self.content, QPlainTextEdit):
            self.content.setPlainText(text)
        elif isinstance(self.content, QLabel):
            self.content.setText(text)


class OverlayWindow(QWidget):
    # 全局快捷键回调 -> 主线程信号(跨线程安全)
    hotkey_capture = Signal()
    hotkey_exit = Signal()

    def __init__(self):
        super().__init__()
        self.cfg = load_config()
        self._hide_border = False
        self._worker = None
        self._drag_global = None
        self._drag_pos = None
        self._geometry_applied = False
        self._bg_pixmap = QPixmap()
        self._top_h = 0
        self._bot_h = 0
        self._pinned_hole = 0
        self._setup_window()
        self._ensure_storage_dirs()
        self._build_ui()
        self._load_settings_to_ui()
        self._refresh_bar_heights()
        self._apply_window_size()
        self._apply_theme()
        self._register_hotkeys()

    # ---------- 窗口属性 ----------
    def _setup_window(self):
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

    def _ensure_storage_dirs(self):
        """确保缓存/题目保存目录存在。"""
        for key in ("cache_dir", "questions_dir"):
            d = (self.cfg.get("storage") or {}).get(key, "")
            if d:
                try:
                    Path(d).mkdir(parents=True, exist_ok=True)
                except Exception:
                    pass

    # ---------- UI ----------
    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(MARGIN, MARGIN, MARGIN, MARGIN)
        root.setSpacing(SPACING)

        # ---- 上部:艺术标题 + 操作区 / 提问 ----
        self.top_bar = QWidget()
        tl = QVBoxLayout(self.top_bar)
        tl.setContentsMargins(0, 0, 0, 0)
        tl.setSpacing(SPACING)

        row1 = QHBoxLayout()
        row1.setSpacing(10)
        title = QLabel("OCR助手")
        title.setObjectName("titleArt")
        row1.addWidget(title)
        sub = QLabel("截图识别 · 智能答题")
        sub.setObjectName("titleSub")
        row1.addWidget(sub, 0, Qt.AlignmentFlag.AlignBottom)
        row1.addStretch(1)
        self.top_check = QCheckBox("置顶")
        row1.addWidget(self.top_check)
        self.btn_settings = QPushButton("配置")
        row1.addWidget(self.btn_settings)
        self.btn_theme = QPushButton("主题")
        row1.addWidget(self.btn_theme)
        btn_quit = QPushButton("退出")
        row1.addWidget(btn_quit)
        tl.addLayout(row1)

        row2 = QHBoxLayout()
        row2.setSpacing(8)
        row2.addWidget(QLabel("提问/指令"))
        self.question_edit = QLineEdit()
        self.question_edit.setPlaceholderText("要模型回答的问题")
        row2.addWidget(self.question_edit, 1)
        tl.addLayout(row2)

        root.addWidget(self.top_bar)

        # ---- 中部:透明工作区(填满中间区域,即"洞口") ----
        self.rect_area = CaptureArea(self)
        self.rect_area.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        root.addWidget(self.rect_area, 1)

        # ---- 下部:按钮 + 状态 + 可折叠回复区(内容驱动高度) ----
        # 折叠/展开区块时,窗口高度同步变化,保持洞口高度不变
        self.bottom_bar = QWidget()
        bl = QVBoxLayout(self.bottom_bar)
        bl.setContentsMargins(0, 0, 0, 0)
        bl.setSpacing(6)

        b1 = QHBoxLayout()
        b1.setSpacing(8)
        self.btn_run = QPushButton("截图并识别")
        self.btn_run.setObjectName("primaryBtn")
        self.btn_run.setDefault(True)
        b1.addWidget(self.btn_run)
        self.btn_copy = QPushButton("复制结果")
        b1.addWidget(self.btn_copy)
        self.btn_clear = QPushButton("清空")
        b1.addWidget(self.btn_clear)
        # 识别类型与耗时:位于清空按钮左侧
        self.meta_label = QLabel("尚未识别")
        self.meta_label.setObjectName("metaInfo")
        self.meta_label.setWordWrap(False)
        b1.addWidget(self.meta_label)
        b1.addStretch(1)
        self.status_label = QLabel()
        b1.addWidget(self.status_label)
        bl.addLayout(b1)

        # 识别结果区
        self.ocr_edit = QPlainTextEdit()
        self.ocr_edit.setReadOnly(True)
        self.ocr_edit.setPlaceholderText("OCR 识别出的原始文字将显示在这里")
        self.ocr_edit.setFixedHeight(110)
        self.section_ocr = CollapsibleSection("识别结果", self.ocr_edit, expanded=True)

        # 回答区(高度随内容自适应,上限受底栏剩余空间约束)
        self.answer_edit = QPlainTextEdit()
        self.answer_edit.setReadOnly(True)
        self.answer_edit.setPlaceholderText("模型回答将显示在这里")
        self.answer_edit.setFixedHeight(80)
        self.section_answer = CollapsibleSection("回答", self.answer_edit, expanded=True)

        bl.addWidget(self.section_ocr)
        bl.addWidget(self.section_answer, 1)

        root.addWidget(self.bottom_bar)
        self.section_ocr.header.toggled.connect(lambda _c: self._adjust_window_for_bottom())
        self.section_answer.header.toggled.connect(lambda _c: self._adjust_window_for_bottom())

        self._create_resize_handles()

        # 窗口最小尺寸(上部设置区 + 下部回复区决定)
        min_w = max(self.top_bar.sizeHint().width(), self.bottom_bar.sizeHint().width())
        self.setMinimumSize(max(min_w + 2 * MARGIN, MIN_WIN_W), MIN_WIN_H)

        # ---- 信号 ----
        self.btn_run.clicked.connect(self._run_pipeline)
        self.btn_copy.clicked.connect(self._copy_result)
        self.btn_clear.clicked.connect(self._clear_result)
        btn_quit.clicked.connect(self.close)
        self.top_check.toggled.connect(self._toggle_topmost)
        self.btn_settings.clicked.connect(self._open_settings)
        self.btn_theme.clicked.connect(self._open_theme)

    def _refresh_bar_heights(self):
        """记录上下栏高度供几何计算;底栏为内容驱动。"""
        self._top_h = self.top_bar.sizeHint().height()
        self._bot_h = self.bottom_bar.sizeHint().height()

    def _fit_answer_height(self):
        """回答框高度随内容自适应,并同步窗口高度。"""
        doc = self.answer_edit.document()
        needed = int(doc.documentLayout().documentSize().height()) + 14
        self.answer_edit.setFixedHeight(max(48, min(needed, 320)))
        self._adjust_window_for_bottom()

    def _adjust_window_for_bottom(self):
        """底栏内容变化(折叠/展开/回答变高)时,待布局生效后同步窗口高度,保持洞口高度不变。"""
        QTimer.singleShot(60, self._do_adjust_window_for_bottom)

    def _do_adjust_window_for_bottom(self, tries: int = 5):
        """按洞口高度偏差收敛调整窗口高度(多轮直到偏差归零)。"""
        if self._pinned_hole < 50:
            self._pinned_hole = self.rect_area.height()
        delta = self.rect_area.height() - self._pinned_hole
        if abs(delta) <= 2 or tries <= 0:
            return
        target = max(self.height() - delta, self.minimumHeight())
        if target != self.height():
            self.resize(self.width(), target)
        QTimer.singleShot(0, lambda: self._do_adjust_window_for_bottom(tries - 1))

    def _load_settings_to_ui(self):
        self.top_check.blockSignals(True)
        self.top_check.setChecked(self.cfg["window"]["always_on_top"])
        self.top_check.blockSignals(False)
        self.question_edit.setText(self.cfg["behavior"]["default_question"])
        self._refresh_provider_ui()

    def _active_provider(self) -> dict:
        from app.config import active_provider
        return active_provider(self.cfg)

    def _refresh_provider_ui(self):
        """根据当前平台刷新按钮提示与状态。"""
        p = self._active_provider()
        self.btn_settings.setToolTip(f"当前平台:{p.get('name','')} · 模型:{p.get('model','')}")
        key_ok = bool((p.get("api_key") or "").strip())
        self._set_status("就绪 · Key 已配置" if key_ok else "就绪 · Key 未配置", "idle")

    def _save_settings(self):
        self.cfg["window"]["always_on_top"] = self.top_check.isChecked()
        save_config(self.cfg)

    # ---------- 主题 ----------
    def _apply_theme(self):
        preset = self.cfg["theme"]["preset"]
        app = QApplication.instance()
        if app is not None:
            app.setStyleSheet(build_stylesheet(preset))
        path = self.cfg["theme"].get("image", "")
        self._bg_pixmap = QPixmap(path) if path else QPixmap()
        self.update()

    def _open_settings(self):
        dlg = SettingsDialog(self.cfg, self)
        if dlg.exec():
            self.question_edit.setText(self.cfg["behavior"]["default_question"])
            self._refresh_provider_ui()

    def _open_theme(self):
        dlg = ThemeDialog(self.cfg, self)
        if dlg.exec():
            self._apply_theme()

    # ---------- 状态文字(加大 + 加粗 + 彩色圆点) ----------
    def _set_status(self, text: str, state: str = "idle"):
        color = STATUS_COLORS.get(state, STATUS_COLORS["idle"])
        self.status_label.setText(
            f"<span style='font-size:15px; font-weight:600;'>"
            f"<span style='color:{color};'>●</span>&nbsp;{text}</span>"
        )

    # ---------- 几何:窗口尺寸记忆 ----------
    def _apply_window_size(self):
        """按配置的窗口尺寸启动(受最小尺寸约束)。"""
        w = max(int(self.cfg["window"].get("width", 640)), self.minimumWidth())
        h = max(int(self.cfg["window"].get("height", 680)), self.minimumHeight())
        self.resize(w, h)

    def _sync_window_size(self):
        """窗口缩放后,把实际尺寸写回配置(退出时持久化)。"""
        if not self._geometry_applied:
            return
        if self.width() < 50 or self.height() < 50:
            return
        self.cfg["window"]["width"] = self.width()
        self.cfg["window"]["height"] = self.height()

    def _toggle_topmost(self, on: bool):
        """用 Win32 SetWindowPos 切换置顶,避免重建原生窗口(重建会导致窗口消失/闪退)。"""
        try:
            import ctypes
            HWND_TOPMOST, HWND_NOTOPMOST = -1, -2
            SWP_NOSIZE, SWP_NOMOVE = 0x0001, 0x0002
            ctypes.windll.user32.SetWindowPos(
                int(self.winId()),
                HWND_TOPMOST if on else HWND_NOTOPMOST,
                0, 0, 0, 0, SWP_NOSIZE | SWP_NOMOVE,
            )
        except Exception:
            pass

    def showEvent(self, event):
        """窗口真正显示后重新断言配置尺寸,覆盖 WM 可能恢复的旧几何。"""
        super().showEvent(event)
        # 启动时立即以持久化配置刷新平台状态(修复退出重进后状态不更新的问题)
        self._refresh_provider_ui()
        if not self._geometry_applied:
            self._geometry_applied = True
            self._refresh_bar_heights()
            QTimer.singleShot(0, self._apply_window_size)

    # ---------- 窗口绘制 / 拖动 / 缩放 ----------
    def paintEvent(self, event):
        """整个窗口填充主题背景(纯色或图片)+ 描边,并在洞口位置挖空。"""
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        hole = QRect(self.rect_area.mapTo(self, QPoint(0, 0)), self.rect_area.size())
        radius = int(self.cfg["window"].get("corner_radius", 12))
        path = QPainterPath()
        path.addRoundedRect(QRectF(self.rect()), radius, radius)
        path.addRect(QRectF(hole))

        preset = self.cfg["theme"]["preset"]
        p.fillPath(path, theme_bg_color(preset))
        if not self._bg_pixmap.isNull():
            p.save()
            p.setClipPath(path)
            scale = self.cfg["theme"].get("image_scale", 100) / 100.0
            w = self._bg_pixmap.width() * scale
            h = self._bg_pixmap.height() * scale
            p.drawPixmap(
                QRectF(self.cfg["theme"].get("image_offset_x", 0),
                       self.cfg["theme"].get("image_offset_y", 0), w, h),
                self._bg_pixmap, QRectF(self._bg_pixmap.rect()),
            )
            p.restore()
        # 窗口描边,增强边缘感
        p.setPen(QPen(theme_outline_color(preset), 1))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawPath(path)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_global = event.globalPosition().toPoint()
            self._drag_pos = self.frameGeometry().topLeft()

    def mouseMoveEvent(self, event):
        if self._drag_global is not None and event.buttons() & Qt.MouseButton.LeftButton:
            delta = event.globalPosition().toPoint() - self._drag_global
            self.move(self._drag_pos + delta)

    def mouseReleaseEvent(self, event):
        self._drag_global = None

    def _create_resize_handles(self):
        self._handles = []
        for edge in ("tl", "t", "tr", "l", "r", "bl", "b", "br"):
            self._handles.append(ResizeHandle(self, edge))
        self._place_handles()

    def _place_handles(self):
        w, h = self.width(), self.height()
        c = EDGE + 6
        geo = {
            "tl": (0, 0, c, c),
            "t": (c, 0, w - 2 * c, EDGE),
            "tr": (w - c, 0, c, c),
            "l": (0, c, EDGE, h - 2 * c),
            "r": (w - EDGE, c, EDGE, h - 2 * c),
            "bl": (0, h - c, c, c),
            "b": (c, h - EDGE, w - 2 * c, EDGE),
            "br": (w - c, h - c, c, c),
        }
        for hdl in self._handles:
            hdl.setGeometry(*geo[hdl.edge])

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._place_handles()
        # 布局稳定后(下一事件循环)再捕获洞口高度,避免测量到未生效的旧布局
        QTimer.singleShot(0, self._capture_pinned_hole)
        QTimer.singleShot(0, self._sync_window_size)

    def _capture_pinned_hole(self):
        if self.rect_area.width() >= 50 and self.rect_area.height() >= 50:
            self._pinned_hole = self.rect_area.height()

    # ---------- 全局快捷键 ----------
    def _register_hotkeys(self):
        """注册全局快捷键(keyboard 库);注册失败静默降级,不影响使用。"""
        self.hotkey_capture.connect(self._run_pipeline)
        self.hotkey_exit.connect(self.close)
        hk = self.cfg.get("hotkeys") or {}
        try:
            import keyboard
            keyboard.add_hotkey(hk.get("capture", "ctrl+f1"), self.hotkey_capture.emit)
            keyboard.add_hotkey(hk.get("exit", "ctrl+q"), self.hotkey_exit.emit)
        except Exception:
            pass  # 权限/环境不支持时仅失去快捷键

    # ---------- 主流程 ----------
    def _run_pipeline(self):
        if self._worker is not None and self._worker.isRunning():
            return
        prov = self._active_provider()
        if not (prov.get("api_key") or "").strip():
            self.section_answer.set_text("未配置 API Key:请点击「配置」→ 模型设置 填写。")
            return
        self._save_settings()

        # 1) 隐藏边框 -> 截图(主线程;后台线程做网络调用)
        self._set_status("正在截图…", "working")
        self._hide_border = True
        self.rect_area.update()
        QApplication.processEvents()
        time.sleep(int(self.cfg["capture"].get("flash_delay_ms", 60)) / 1000.0)
        try:
            png = capture_widget(self.rect_area)
        except CaptureError as exc:
            self._set_status("截图失败", "error")
            self.section_answer.set_text(f"截图失败:{exc}")
            return
        finally:
            self._hide_border = False
            self.rect_area.update()

        # 2) 后台:OCR -> 解析 -> 知识库/回答
        client = AgentClient(
            prov["api_key"], prov["model"], prov["base_url"],
            self.cfg["request_template"],
            timeout=int(self.cfg.get("timeout", 180)),
            max_side=int(self.cfg["capture"].get("max_side", 2048)),
            max_retries=int(self.cfg["retry"].get("max_retries", 3)),
            backoff=float(self.cfg["retry"].get("backoff", 0.8)),
            enable_thinking=bool(prov.get("enable_thinking", False)),
        )
        self._worker = PipelineWorker(
            client, png, self.cfg["prompts"]["ocr"], self.cfg["prompts"]["answer"],
            self.question_edit.text(), self.cfg.get("knowledge", []),
            self.cfg.get("ocr", {}).get("mode", "cloud"), self,
        )
        self._worker.status.connect(self._on_status)
        self._worker.finished_ok.connect(self._on_ok)
        self._worker.failed.connect(self._on_fail)
        self._worker.finished.connect(lambda: self.btn_run.setEnabled(True))
        self.btn_run.setEnabled(False)
        self._worker.start()

    def _on_status(self, text: str, state: str):
        self._set_status(text, state)

    def _on_ok(self, result: dict):
        """结构化结果分发到独立区块,避免 OCR 与题目重复。"""
        self.section_ocr.set_text(result["ocr_text"])
        meta = (
            f"{result['qtype_name']} · 来源: {result['source']} · "
            f"OCR: {result['ocr_time']:.1f}s · 回答: {result['answer_time']:.1f}s"
        )
        self.meta_label.setText(meta)
        text = result["answer"]
        if result.get("detail"):
            text += f"\n解析: {result['detail']}"
        self.section_answer.set_text(text)
        self._fit_answer_height()
        self._save_outputs(result)

    def _save_outputs(self, result: dict):
        """按存储配置保存题目/回答,并可自动加入本地知识库。"""
        storage = self.cfg.get("storage") or {}
        # 保存题目与回答
        qdir = (storage.get("questions_dir") or "").strip()
        if qdir:
            try:
                d = Path(qdir)
                d.mkdir(parents=True, exist_ok=True)
                fname = d / f"qa_{time.strftime('%Y%m%d')}.txt"
                with open(fname, "a", encoding="utf-8") as f:
                    f.write(f"【{time.strftime('%Y-%m-%d %H:%M:%S')}】\n")
                    f.write(f"题目:\n{result['ocr_text']}\n")
                    f.write(f"回答:\n{result['answer']}\n{'=' * 30}\n")
            except Exception:
                pass
        # 自动加入本地知识库
        if storage.get("add_to_knowledge") and result.get("question"):
            key = result["question"].strip()[:10]
            if len(key) >= 4:
                kb = self.cfg.get("knowledge") or []
                if not any(key in (k.get("keys") or [""])[0] for k in kb):
                    kb.append({"keys": [key], "answer": result["answer"],
                               "detail": f"来源:{result.get('source','')}"})
                    self.cfg["knowledge"] = kb[-200:]
                    save_config(self.cfg)

    def _on_fail(self, message: str):
        self.section_answer.set_text(f"流程失败:{message}")

    def _clear_result(self):
        self.section_ocr.set_text("")
        self.meta_label.setText("尚未识别")
        self.section_answer.set_text("")

    def _copy_result(self):
        QApplication.clipboard().setText(self.section_answer.content.toPlainText())

    # ---------- 退出 ----------
    def closeEvent(self, event):
        self._save_settings()
        super().closeEvent(event)
