# -*- coding: utf-8 -*-
"""设置对话框:左导航(模型设置/常规设置/关于应用)+ 卡片式内容。

模型设置 = 左中右:AI平台管理(卡片式平台列表+logo) / 具体设置区(选项卡片嵌套);
常规设置 = 左右:保存设置 / AI设置 / 提示词设置(选项卡片嵌套);
关于应用 = 应用信息 / GitHub 风格请求记录(灰色方块) / 网站与社区 / 开源许可证。
另有主题对话框(三色/图片背景/预览)。
"""
import json
import re
import time
from pathlib import Path

from PySide6.QtCore import QRectF, QSize, Qt, QThread, Signal
from PySide6.QtGui import QColor, QFont, QIcon, QPainter, QPainterPath, QPen, QPixmap
from PySide6.QtWidgets import (
    QAbstractSpinBox,
    QButtonGroup,
    QCheckBox,
    QDialog,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QStackedWidget,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from app import request_log
from app.agent import AgentClient
from app.config import DEFAULT_REQUEST_TEMPLATE, ROOT, save_config
from app.theme import THEMES

PREVIEW_W, PREVIEW_H = 360, 240
LOGO_CACHE = {}

# 测试按钮 / 延迟文字配色
TEST_COLORS = {"idle": "#3FB950", "testing": "#8B94A7", "ok": "#3FB950", "fail": "#F85149"}
TEST_TEXTS = {"idle": "测试连通性", "testing": "测试中…", "ok": "连接成功", "fail": "测试失败"}


# ---------- 工具 ----------
def provider_logo(name: str, color: str, size: int = 44, logo_path: str = "") -> QPixmap:
    """生成平台 logo:优先自定义路径 -> assets/logos/<name>.png -> 绘制文字徽标。"""
    cache_key = (name, color, size, logo_path)
    if cache_key in LOGO_CACHE:
        return LOGO_CACHE[cache_key]
    for candidate in (logo_path, str(ROOT / "assets" / "logos" / f"{name}.png")):
        if candidate:
            pm = QPixmap(candidate)
            if not pm.isNull():
                pm = pm.scaled(size, size, Qt.AspectRatioMode.KeepAspectRatio,
                               Qt.TransformationMode.SmoothTransformation)
                LOGO_CACHE[cache_key] = pm
                return pm
    pm = QPixmap(size, size)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setBrush(QColor(color))
    p.setPen(Qt.PenStyle.NoPen)
    p.drawRoundedRect(0, 0, size, size, size // 4, size // 4)
    p.setPen(QColor("#FFFFFF"))
    f = QFont("Microsoft YaHei UI", size // 2, QFont.Weight.Bold)
    p.setFont(f)
    p.drawText(QRectF(0, 0, size, size), Qt.AlignmentFlag.AlignCenter, name[:1])
    p.end()
    LOGO_CACHE[cache_key] = pm
    return pm


def make_eye_icon(size: int = 18) -> QIcon:
    """绘制简单的眼睛图标(不依赖 emoji)。"""
    pm = QPixmap(size, size)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setPen(QPen(QColor("#8B94A7"), 1.6))
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.drawEllipse(QRectF(1, 4, size - 2, size - 6))
    p.setBrush(QColor("#8B94A7"))
    p.setPen(Qt.PenStyle.NoPen)
    p.drawEllipse(QRectF(size / 2 - 2, size / 2 - 1, 4, 4))
    p.end()
    return QIcon(pm)


def _option_card() -> tuple:
    """横向选项卡片(标签 + 控件)。"""
    f = QFrame()
    f.setObjectName("optionCard")
    lay = QHBoxLayout(f)
    lay.setContentsMargins(12, 8, 12, 8)
    lay.setSpacing(10)
    return f, lay


def _option_card_v() -> tuple:
    """纵向选项卡片(标签 + 多行控件)。"""
    f = QFrame()
    f.setObjectName("optionCard")
    lay = QVBoxLayout(f)
    lay.setContentsMargins(12, 8, 12, 8)
    lay.setSpacing(6)
    return f, lay


def _field_label(text: str, width: int = 96) -> QLabel:
    """等宽左对齐的字段标签,保证各输入框纵向对齐且左侧无多余空白。"""
    lab = QLabel(text)
    lab.setFixedWidth(width)
    lab.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
    return lab


def _footer(ok_text: str = "保存"):
    """底部按钮行:右对齐的 取消 / 主按钮。"""
    row = QHBoxLayout()
    row.addStretch(1)
    btn_cancel = QPushButton("取消")
    btn_ok = QPushButton(ok_text)
    btn_ok.setObjectName("primaryBtn")
    btn_ok.setDefault(True)
    row.addWidget(btn_cancel)
    row.addWidget(btn_ok)
    return row, btn_cancel, btn_ok


def _make_transparent(widget):
    """让控件背景透明,保持整体底色一致。"""
    widget.setAutoFillBackground(False)
    if isinstance(widget, QScrollArea):
        widget.setFrameShape(QFrame.Shape.NoFrame)
        widget.viewport().setAutoFillBackground(False)


# ---------- GitHub 风格请求记录图(灰色方块) ----------
class RequestGrid(QWidget):
    """最近请求记录:7 行 × N 周方格,灰色底 + 绿色强度,仿 GitHub 提交记录。"""

    LEVEL_COLORS = ["#9AA3B0", "#9BE9A8", "#40C463", "#30A14E", "#216E39"]
    CELL = 11
    GAP = 3
    WEEKS = 20

    def __init__(self, parent=None):
        super().__init__(parent)
        self._counts = {}
        w = self.WEEKS * (self.CELL + self.GAP)
        h = 7 * (self.CELL + self.GAP)
        self.setFixedSize(w + 4, h + 4)

    def refresh(self):
        self._counts = request_log.day_counts(self.WEEKS * 7)
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        today = time.localtime()
        total = self.WEEKS * 7
        for i in range(total):
            day = time.mktime((today.tm_year, today.tm_mon, today.tm_mday - (total - 1 - i),
                               0, 0, 0, 0, 0, -1))
            dstr = time.strftime("%Y-%m-%d", time.localtime(day))
            count = self._counts.get(dstr, 0)
            level = min(4, count)
            col = i // 7
            row = i % 7
            x = 2 + col * (self.CELL + self.GAP)
            y = 2 + row * (self.CELL + self.GAP)
            p.setBrush(QColor(self.LEVEL_COLORS[level]))
            p.setPen(Qt.PenStyle.NoPen)
            p.drawRoundedRect(x, y, self.CELL, self.CELL, 2, 2)
        p.end()


# ---------- 平台卡片(悬浮显示删除按钮,点击选中) ----------
class ProviderCard(QFrame):
    def __init__(self, name: str, pixmap: QPixmap, dimmed: bool, on_select, on_delete, parent=None):
        super().__init__(parent)
        self.setObjectName("providerCardDim" if dimmed else "providerCard")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._on_select = on_select
        lay = QHBoxLayout(self)
        lay.setContentsMargins(10, 8, 6, 8)
        lay.setSpacing(8)
        self.icon_label = QLabel()
        self.icon_label.setPixmap(pixmap)
        lay.addWidget(self.icon_label)
        self.name_label = QLabel(name)
        lay.addWidget(self.name_label, 1)
        self.btn_del = QToolButton()
        self.btn_del.setObjectName("cardDelete")
        self.btn_del.setText("×")
        self.btn_del.setToolTip("删除该平台")
        self.btn_del.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_del.setVisible(False)
        lay.addWidget(self.btn_del)
        self.btn_del.clicked.connect(on_delete)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._on_select()
        super().mousePressEvent(event)

    def enterEvent(self, event):
        self.btn_del.setVisible(True)
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.btn_del.setVisible(False)
        super().leaveEvent(event)

    def set_selected(self, selected: bool):
        """选中高亮:通过动态属性触发 QSS(仅背景色,无边框)。"""
        if self.property("selected") == selected:
            return
        self.setProperty("selected", selected)
        self.style().unpolish(self)
        self.style().polish(self)


# ---------- 连通性测试线程 ----------
class TestThread(QThread):
    done = Signal(bool, int, str)  # (成功?, 耗时ms, 结果说明)

    def __init__(self, api_key, model, base_url, timeout, parent=None):
        super().__init__(parent)
        self._api_key = api_key
        self._model = model
        self._base_url = base_url
        self._timeout = timeout

    def run(self):
        t0 = time.time()
        client = AgentClient(self._api_key, self._model, self._base_url, timeout=self._timeout)
        msg = client.test_connection()
        ms = int((time.time() - t0) * 1000)
        self.done.emit(msg.startswith("连接成功"), ms, msg)


# ---------- 请求模板编辑对话框 ----------
class TemplateEditDialog(QDialog):
    def __init__(self, template: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle("请求模板")
        self.setMinimumSize(640, 480)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(16, 14, 16, 14)
        hint = QLabel("占位符 {model}/{prompt}/{image_url} 自动替换为 JSON 值(勿加引号);"
                      "enable_thinking 由平台设置自动注入。")
        hint.setObjectName("hint")
        hint.setWordWrap(True)
        lay.addWidget(hint)
        self.edit = QPlainTextEdit()
        self.edit.setPlainText(template)
        lay.addWidget(self.edit, 1)
        footer, btn_cancel, btn_ok = _footer("保存")
        lay.addLayout(footer)
        btn_ok.clicked.connect(self._on_save)
        btn_cancel.clicked.connect(self.reject)

    def _on_save(self):
        tpl = self.edit.toPlainText().strip()
        try:
            json.loads(tpl.replace("{model}", '"m"').replace("{prompt}", '"p"')
                          .replace("{image_url}", '"u"'))
        except Exception as exc:
            QMessageBox.warning(self, "模板无效", f"JSON 请求体模板无法解析:\n{exc}")
            return
        self.result_template = tpl
        self.accept()


# ---------- 设置对话框 ----------
class SettingsDialog(QDialog):
    def __init__(self, cfg: dict, parent=None):
        super().__init__(parent)
        self.cfg = cfg
        self._current = -1
        self._test_thread = None
        self.setWindowTitle("设置")
        self.setMinimumSize(960, 660)

        root = QHBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 14)
        root.setSpacing(14)

        # ---- 左侧导航(互斥选中) ----
        nav_box = QWidget()
        nav_box.setFixedWidth(152)
        nav = QVBoxLayout(nav_box)
        nav.setContentsMargins(0, 4, 0, 0)
        nav.setSpacing(6)
        self.nav_group = QButtonGroup(self)
        self.nav_group.setExclusive(True)
        self.nav_btns = {}
        for key, label in (("model", "模型设置"), ("general", "常规设置"), ("about", "关于应用")):
            b = QPushButton(label)
            b.setCheckable(True)
            b.setObjectName("navBtn")
            b.setFixedHeight(40)
            nav.addWidget(b)
            b.clicked.connect(lambda _, k=key: self._switch(k))
            self.nav_group.addButton(b)
            self.nav_btns[key] = b
        nav.addStretch(1)
        btn_close = QPushButton("关闭")
        btn_close.setObjectName("primaryBtn")
        btn_close.setFixedHeight(36)
        nav.addWidget(btn_close)
        btn_close.clicked.connect(self._on_close)
        root.addWidget(nav_box)

        # ---- 内容区 ----
        self.stack = QStackedWidget()
        self.stack.setObjectName("settingsStack")
        self._build_model_page()
        self._build_general_page()
        self._build_about_page()
        root.addWidget(self.stack, 1)

        self.nav_btns["model"].setChecked(True)
        self._switch("model")

    def _switch(self, key: str):
        self.stack.setCurrentIndex(list(self.nav_btns).index(key))

    # ================= 模型设置(左中右) =================
    def _build_model_page(self):
        page = QWidget()
        page.setObjectName("settingsPage")
        _make_transparent(page)
        h = QHBoxLayout(page)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(12)

        # 中部:AI平台管理(按是否已配置分区,未配置暗色显示)
        mid = QWidget()
        mid.setFixedWidth(260)
        _make_transparent(mid)
        mv = QVBoxLayout(mid)
        mv.setContentsMargins(0, 0, 0, 0)
        mv.setSpacing(6)
        t = QLabel("AI平台管理")
        t.setObjectName("cardTitle")
        mv.addWidget(t)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        _make_transparent(scroll)
        self.provider_container = QWidget()
        _make_transparent(self.provider_container)
        self.provider_box = QVBoxLayout(self.provider_container)
        self.provider_box.setContentsMargins(0, 0, 0, 0)
        self.provider_box.setSpacing(8)
        scroll.setWidget(self.provider_container)
        mv.addWidget(scroll, 1)
        btn_add = QPushButton("+ 自定义平台")
        btn_add.clicked.connect(self._add_provider)
        mv.addWidget(btn_add)
        h.addWidget(mid)

        # 右侧:具体设置区
        self._build_provider_settings(h)

        self._rebuild_provider_cards()
        page.setLayout(h)
        self.stack.addWidget(page)

    def _rebuild_provider_cards(self):
        """按「是否已配置(已填 API Key)」分区重建平台卡片;未配置的以暗色显示。

        卡片为可点击选中的容器,悬浮时右侧显示删除按钮。
        """
        while self.provider_box.count():
            item = self.provider_box.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()
        self.provider_btns = []
        providers = self.cfg.get("providers", [])

        def add_section_header(text):
            lab = QLabel(text)
            lab.setObjectName("hint")
            self.provider_box.addWidget(lab)

        def add_card(idx, p, dimmed):
            pm = provider_logo(p.get("name", "?"), p.get("color", "#8B94A7"), 24,
                               p.get("logo", ""))
            if dimmed:  # 未配置:logo 降透明度
                dpm = QPixmap(pm.size())
                dpm.fill(Qt.GlobalColor.transparent)
                qp = QPainter(dpm)
                qp.setOpacity(0.45)
                qp.drawPixmap(0, 0, pm)
                qp.end()
                pm = dpm
            card = ProviderCard(
                p.get("name", "?"), pm, dimmed,
                on_select=lambda i=idx: self._select_provider(i),
                on_delete=lambda i=idx: self._delete_provider(i),
            )
            card.setProperty("provIdx", idx)
            self.provider_box.addWidget(card)
            self.provider_btns.append(card)

        configured = [(i, p) for i, p in enumerate(providers) if (p.get("api_key") or "").strip()]
        unconfigured = [(i, p) for i, p in enumerate(providers) if not (p.get("api_key") or "").strip()]

        if configured:
            add_section_header(f"已配置({len(configured)})")
            for i, p in configured:
                add_card(i, p, dimmed=False)
        if unconfigured:
            add_section_header(f"未配置({len(unconfigured)})")
            for i, p in unconfigured:
                add_card(i, p, dimmed=True)
        self.provider_box.addStretch(1)

        active = self.cfg.get("active_provider", "")
        for i, p in enumerate(providers):
            if p.get("id") == active:
                self._select_provider(i)
                return
        self._select_provider(0 if providers else -1)

    def _select_provider(self, idx: int):
        """选中平台:高亮卡片并载入字段。"""
        if not (0 <= idx < len(self.cfg["providers"])):
            return
        for i, card in enumerate(self.provider_btns):
            card.set_selected(i == idx)
        self._current = idx
        self._load_provider_fields()

    def _delete_provider(self, idx: int):
        """删除平台(带确认)。"""
        if not (0 <= idx < len(self.cfg["providers"])):
            return
        p = self.cfg["providers"][idx]
        ret = QMessageBox.question(
            self, "确认删除", f"确定删除平台「{p.get('name', '')}」吗?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if ret != QMessageBox.StandardButton.Yes:
            return
        self.cfg["providers"].pop(idx)
        if self.cfg.get("active_provider") == p.get("id"):
            self.cfg["active_provider"] = self.cfg["providers"][0].get("id", "") if self.cfg["providers"] else ""
        self._rebuild_provider_cards()
        self._select_provider(min(self._current, len(self.cfg["providers"]) - 1))

    def _build_provider_settings(self, parent_layout):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        _make_transparent(scroll)
        container = QWidget()
        _make_transparent(container)
        cv = QVBoxLayout(container)
        cv.setContentsMargins(0, 0, 4, 0)
        cv.setSpacing(12)

        # ---- 卡片1:连接设置(内含选项卡片) ----
        card = QFrame()
        card.setObjectName("card")
        c1 = QVBoxLayout(card)
        c1.setContentsMargins(16, 14, 16, 14)
        c1.setSpacing(10)

        row0 = QHBoxLayout()
        row0.setSpacing(12)
        self.provider_logo_label = QLabel()
        self.provider_logo_label.setFixedSize(46, 46)
        row0.addWidget(self.provider_logo_label)
        # 平台名称:可点击编辑(点击进入输入,失焦/回车自动提交)
        self.provider_name_edit = QLineEdit()
        self.provider_name_edit.setObjectName("providerNameEdit")
        self.provider_name_edit.setFixedWidth(220)
        row0.addWidget(self.provider_name_edit)
        row0.addStretch(1)
        self.latency_label = QLabel("")
        row0.addWidget(self.latency_label)
        self.btn_test = QPushButton("测试连通性")
        self.btn_test.setCursor(Qt.CursorShape.PointingHandCursor)
        row0.addWidget(self.btn_test)
        c1.addLayout(row0)
        self.btn_test.clicked.connect(self._test_connection)
        self.provider_name_edit.editingFinished.connect(self._on_name_committed)
        self._apply_test_state("idle")

        # 选项卡片:统一宽度(以最宽者为准)并水平居中
        opt_cards = []

        def add_opt(f):
            opt_cards.append(f)
            c1.addWidget(f, 0, Qt.AlignmentFlag.AlignHCenter)

        # 备注
        f, r = _option_card()
        r.addWidget(_field_label("备注"))
        self.note_edit = QLineEdit()
        r.addWidget(self.note_edit, 1)
        add_opt(f)
        # 官网链接
        f, r = _option_card()
        r.addWidget(_field_label("官网链接"))
        self.home_edit = QLineEdit()
        r.addWidget(self.home_edit, 1)
        add_opt(f)
        # API Key(眼睛图标在输入框内部)
        f, r = _option_card()
        r.addWidget(_field_label("API Key"))
        self.key_edit = QLineEdit()
        self.key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        r.addWidget(self.key_edit, 1)
        add_opt(f)
        self.eye_action = self.key_edit.addAction(
            make_eye_icon(), QLineEdit.ActionPosition.TrailingPosition)
        self.eye_action.setToolTip("显示 / 隐藏")
        self.eye_action.triggered.connect(self._toggle_key_visible)
        # 模型ID
        f, r = _option_card()
        r.addWidget(_field_label("模型ID"))
        self.model_edit = QLineEdit()
        r.addWidget(self.model_edit, 1)
        add_opt(f)
        # Base URL
        f, r = _option_card()
        r.addWidget(_field_label("Base URL"))
        self.base_edit = QLineEdit()
        r.addWidget(self.base_edit, 1)
        add_opt(f)
        # 是否开启思考
        f, r = _option_card()
        r.addWidget(_field_label("思考模式"))
        self.think_check = QCheckBox("开启思考模式(响应更慢但推理更强)")
        r.addWidget(self.think_check, 1)
        add_opt(f)

        # 统一各选项卡片长度:以最宽(思考模式)卡片为准,右端对齐
        ref_w = max(f.sizeHint().width() for f in opt_cards)
        for f in opt_cards:
            f.setFixedWidth(ref_w)
        cv.addWidget(card)

        # ---- 卡片2:JSON 请求预览 ----
        card2 = QFrame()
        card2.setObjectName("card")
        c2 = QVBoxLayout(card2)
        c2.setContentsMargins(16, 12, 16, 14)
        c2.setSpacing(8)
        hd = QHBoxLayout()
        t2 = QLabel("JSON 请求预览")
        t2.setObjectName("cardTitle")
        hd.addWidget(t2)
        hd.addStretch(1)
        btn_tpl = QPushButton("编辑模板")
        hd.addWidget(btn_tpl)
        c2.addLayout(hd)
        self.preview_edit = QPlainTextEdit()
        self.preview_edit.setReadOnly(True)
        self.preview_edit.setFixedHeight(170)
        self.preview_edit.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        c2.addWidget(self.preview_edit)
        btn_tpl.clicked.connect(self._edit_template)
        cv.addWidget(card2)

        cv.addStretch(1)
        scroll.setWidget(container)
        parent_layout.addWidget(scroll, 1)

        # 字段变更 -> 保存到当前平台 + 刷新预览
        for w in (self.note_edit, self.home_edit, self.key_edit,
                  self.model_edit, self.base_edit):
            w.textChanged.connect(self._on_field_edit)
        self.think_check.toggled.connect(self._on_field_edit)

    def _current_provider(self) -> dict:
        if 0 <= self._current < len(self.cfg["providers"]):
            return self.cfg["providers"][self._current]
        return {}

    def _load_provider_fields(self):
        p = self._current_provider()
        if not p:
            return
        # 屏蔽信号,避免 setText 触发的 textChanged 把半空的字段写回配置
        edits = (self.note_edit, self.home_edit, self.key_edit,
                 self.model_edit, self.base_edit)
        for w in edits:
            w.blockSignals(True)
        self.think_check.blockSignals(True)
        self.provider_logo_label.setPixmap(provider_logo(
            p.get("name", "?"), p.get("color", "#8B94A7"), 46, p.get("logo", "")))
        self.provider_name_edit.setText(p.get("name", ""))
        self.note_edit.setText(p.get("note", ""))
        self.home_edit.setText(p.get("homepage", ""))
        self.key_edit.setText(p.get("api_key", ""))
        self.model_edit.setText(p.get("model", ""))
        self.base_edit.setText(p.get("base_url", ""))
        self.think_check.setChecked(bool(p.get("enable_thinking", False)))
        for w in edits:
            w.blockSignals(False)
        self.think_check.blockSignals(False)
        self._apply_test_state("idle")
        self._update_preview()

    def _on_name_committed(self):
        """平台名称编辑完成:提交修改并刷新列表。"""
        p = self._current_provider()
        if not p:
            return
        name = self.provider_name_edit.text().strip()
        if not name:
            self.provider_name_edit.setText(p.get("name", ""))
            return
        if name == p.get("name"):
            return
        p["name"] = name
        self.provider_logo_label.setPixmap(provider_logo(
            name, p.get("color", "#8B94A7"), 46, p.get("logo", "")))
        idx = self._current
        self._rebuild_provider_cards()
        self._select_provider(idx)

    def _on_field_edit(self, *_):
        p = self._current_provider()
        if not p:
            return
        p["note"] = self.note_edit.text().strip()
        p["homepage"] = self.home_edit.text().strip()
        p["api_key"] = self.key_edit.text().strip()
        p["model"] = self.model_edit.text().strip()
        p["base_url"] = self.base_edit.text().strip()
        p["enable_thinking"] = self.think_check.isChecked()
        self._update_preview()

    def _update_preview(self):
        p = self._current_provider()
        tpl = self.cfg.get("request_template", DEFAULT_REQUEST_TEMPLATE)
        body = (
            tpl.replace("{model}", json.dumps(p.get("model", ""), ensure_ascii=False))
               .replace("{prompt}", json.dumps("…提示词…", ensure_ascii=False))
               .replace("{image_url}", json.dumps("data:image/png;base64,…", ensure_ascii=False))
        )
        body = re.sub(
            r'"enable_thinking"\s*:\s*(true|false)',
            f'"enable_thinking": {str(bool(p.get("enable_thinking", False))).lower()}',
            body,
        )
        try:
            self.preview_edit.setPlainText(json.dumps(json.loads(body), ensure_ascii=False, indent=2))
        except Exception:
            self.preview_edit.setPlainText(body)

    def _toggle_key_visible(self):
        self.key_edit.setEchoMode(
            QLineEdit.EchoMode.Normal if self.key_edit.echoMode() == QLineEdit.EchoMode.Password
            else QLineEdit.EchoMode.Password
        )

    def _apply_test_state(self, state: str, ms: int = 0):
        """测试按钮:绿(初始/成功) -> 灰(测试中) -> 红(失败);成功时左侧显示响应耗时。"""
        self.btn_test.setText(TEST_TEXTS.get(state, "测试连通性"))
        self.btn_test.setStyleSheet(
            f"QPushButton {{ background: {TEST_COLORS[state]}; color: #FFFFFF;"
            f" border: none; border-radius: 8px; padding: 6px 14px; font-weight: 600; }}"
        )
        if state == "ok" and ms > 0:
            color = "#3FB950" if ms < 1500 else ("#F5A623" if ms < 3500 else "#F85149")
            self.latency_label.setText(f"响应 {ms / 1000:.1f}s")
            self.latency_label.setStyleSheet(f"color: {color}; font-size: 13px; font-weight: 600;")
        else:
            self.latency_label.setText("")

    def _test_connection(self):
        p = self._current_provider()
        if not p:
            return
        self._apply_test_state("testing")
        self._test_thread = TestThread(
            p.get("api_key", ""), p.get("model", ""), p.get("base_url", ""),
            int(self.cfg.get("timeout", 180)), self,
        )
        self._test_thread.done.connect(self._on_test_done)
        self._test_thread.start()

    def _on_test_done(self, ok: bool, ms: int, _msg: str):
        self._apply_test_state("ok" if ok else "fail", ms=ms)

    def _edit_template(self):
        dlg = TemplateEditDialog(self.cfg.get("request_template", ""), self)
        if dlg.exec():
            self.cfg["request_template"] = dlg.result_template
            self._update_preview()

    def _add_provider(self):
        """添加自定义平台:无弹窗,右侧内容区清空为空白预设,JSON 预览为默认格式。"""
        self.cfg["providers"].append({
            "id": f"custom{int(time.time())}", "name": f"自定义平台{len(self.cfg['providers']) + 1}",
            "color": "#8B94A7", "logo": "", "note": "", "homepage": "",
            "api_key": "", "base_url": "", "model": "", "enable_thinking": False,
        })
        self._rebuild_provider_cards()
        self._select_provider(len(self.cfg["providers"]) - 1)

    # ================= 常规设置(左右,可滚动) =================
    def _build_general_page(self):
        page = QWidget()
        page.setObjectName("settingsPage")
        _make_transparent(page)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        _make_transparent(scroll)
        container = QWidget()
        _make_transparent(container)
        pv = QVBoxLayout(container)
        pv.setContentsMargins(0, 0, 6, 0)
        pv.setSpacing(12)

        # ---- 保存设置(内含选项卡片) ----
        card = QFrame()
        card.setObjectName("card")
        c = QVBoxLayout(card)
        c.setContentsMargins(16, 12, 16, 14)
        c.setSpacing(10)
        t = QLabel("保存设置")
        t.setObjectName("cardTitle")
        c.addWidget(t)
        f, r = _option_card()
        r.addWidget(QLabel("应用缓存位置"))
        self.cache_edit = QLineEdit()
        r.addWidget(self.cache_edit, 1)
        btn_cache = QPushButton("浏览…")
        r.addWidget(btn_cache)
        c.addWidget(f)
        btn_cache.clicked.connect(lambda: self._pick_dir(self.cache_edit))
        f, r = _option_card()
        r.addWidget(QLabel("题目保存位置"))
        self.questions_edit = QLineEdit()
        r.addWidget(self.questions_edit, 1)
        btn_q = QPushButton("浏览…")
        r.addWidget(btn_q)
        c.addWidget(f)
        btn_q.clicked.connect(lambda: self._pick_dir(self.questions_edit))
        f, r = _option_card()
        r.addWidget(QLabel("本地知识库"))
        self.add_kb_check = QCheckBox("将 AI 回答自动添加到本地知识库")
        r.addWidget(self.add_kb_check, 1)
        c.addWidget(f)
        pv.addWidget(card)

        # ---- AI设置(紧凑数字输入 + 右侧单位) ----
        card = QFrame()
        card.setObjectName("card")
        c = QVBoxLayout(card)
        c.setContentsMargins(16, 12, 16, 14)
        c.setSpacing(10)
        t = QLabel("AI设置")
        t.setObjectName("cardTitle")
        c.addWidget(t)

        # 是否启用云端OCR(云端/本地 互斥;说明在文字下方,按钮在最右侧)
        f, r = _option_card_v()
        top = QHBoxLayout()
        top.setSpacing(10)
        top.addWidget(_field_label("是否启用云端OCR", 120))
        top.addStretch(1)
        self.ocr_group = QButtonGroup(self)
        self.ocr_group.setExclusive(True)
        self.btn_ocr_cloud = QPushButton("云端")
        self.btn_ocr_cloud.setCheckable(True)
        self.btn_ocr_cloud.setObjectName("segBtnL")
        self.btn_ocr_local = QPushButton("本地")
        self.btn_ocr_local.setCheckable(True)
        self.btn_ocr_local.setObjectName("segBtnR")
        top.addWidget(self.btn_ocr_cloud)
        top.addWidget(self.btn_ocr_local)
        self.ocr_group.addButton(self.btn_ocr_cloud)
        self.ocr_group.addButton(self.btn_ocr_local)
        r.addLayout(top)
        hint_ocr = QLabel("云端:使用所选大模型识别(精度更高,消耗 token);"
                          "本地:内置 RapidOCR(离线免费、轻量快速,约50MB,CPU 100-300ms)。")
        hint_ocr.setObjectName("hint")
        hint_ocr.setWordWrap(True)
        r.addWidget(hint_ocr)
        c.addWidget(f)

        def compact_spin() -> QSpinBox:
            s = QSpinBox()
            s.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.NoButtons)
            s.setFixedWidth(72)
            s.setAlignment(Qt.AlignmentFlag.AlignRight)
            return s

        f, r = _option_card()
        r.addWidget(_field_label("模型最长响应时间", 120))
        r.addStretch(1)
        self.timeout_spin = compact_spin()
        self.timeout_spin.setRange(30, 600)
        r.addWidget(self.timeout_spin)
        r.addWidget(QLabel("秒"))
        c.addWidget(f)
        f, r = _option_card()
        r.addWidget(_field_label("失败自动尝试次数", 120))
        r.addStretch(1)
        self.retry_spin = compact_spin()
        self.retry_spin.setRange(1, 5)
        r.addWidget(self.retry_spin)
        r.addWidget(QLabel("次"))
        c.addWidget(f)
        pv.addWidget(card)

        # ---- 提示词设置 ----
        card = QFrame()
        card.setObjectName("card")
        c = QVBoxLayout(card)
        c.setContentsMargins(16, 12, 16, 14)
        c.setSpacing(10)
        t = QLabel("提示词设置")
        t.setObjectName("cardTitle")
        c.addWidget(t)
        f, r = _option_card_v()
        r.addWidget(QLabel("OCR提示词"))
        self.ocr_edit = QPlainTextEdit()
        self.ocr_edit.setFixedHeight(70)
        r.addWidget(self.ocr_edit)
        c.addWidget(f)
        f, r = _option_card_v()
        r.addWidget(QLabel("回答提示词"))
        self.answer_edit = QPlainTextEdit()
        self.answer_edit.setFixedHeight(100)
        r.addWidget(self.answer_edit)
        c.addWidget(f)
        pv.addWidget(card)

        pv.addStretch(1)
        scroll.setWidget(container)
        outer = QVBoxLayout(page)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll)
        self.stack.addWidget(page)

    def _pick_dir(self, line_edit):
        d = QFileDialog.getExistingDirectory(self, "选择目录")
        if d:
            line_edit.setText(d)

    # ================= 关于应用(可滚动) =================
    def _build_about_page(self):
        page = QWidget()
        page.setObjectName("settingsPage")
        _make_transparent(page)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        _make_transparent(scroll)
        container = QWidget()
        _make_transparent(container)
        pv = QVBoxLayout(container)
        pv.setContentsMargins(0, 0, 6, 0)
        pv.setSpacing(12)
        app_cfg = self.cfg.get("app", {})

        # ---- 应用信息 ----
        card = QFrame()
        card.setObjectName("card")
        c = QHBoxLayout(card)
        c.setContentsMargins(18, 16, 18, 16)
        c.setSpacing(16)
        logo = QLabel()
        logo.setPixmap(provider_logo("OCR", "#4C8DFF", 56))
        c.addWidget(logo)
        info = QVBoxLayout()
        info.setSpacing(4)
        name = QLabel("OCR助手")
        name.setStyleSheet("font-size: 19px; font-weight: 700;")
        info.addWidget(name)
        ver = QLabel(f"版本 v{app_cfg.get('version', '1.0.0')} · {app_cfg.get('features', '')}")
        ver.setObjectName("hint")
        ver.setWordWrap(True)
        info.addWidget(ver)
        c.addLayout(info, 1)
        btn_update = QPushButton("获取新版本")
        c.addWidget(btn_update, 0, Qt.AlignmentFlag.AlignTop)
        btn_update.clicked.connect(lambda: self._open_url(app_cfg.get("github", "")))
        pv.addWidget(card)

        # ---- 请求记录(灰色方块 + 小刷新按钮) ----
        card = QFrame()
        card.setObjectName("card")
        c = QVBoxLayout(card)
        c.setContentsMargins(18, 12, 18, 14)
        c.setSpacing(10)
        hd = QHBoxLayout()
        t = QLabel("请求记录(最近 20 周)")
        t.setObjectName("cardTitle")
        hd.addWidget(t)
        hd.addStretch(1)
        btn_refresh = QPushButton("刷新")
        btn_refresh.setFixedWidth(64)
        btn_refresh.setFixedHeight(28)
        hd.addWidget(btn_refresh)
        c.addLayout(hd)
        self.grid = RequestGrid()
        c.addWidget(self.grid)
        btn_refresh.clicked.connect(self.grid.refresh)
        pv.addWidget(card)

        # ---- 网站与社区 ----
        card = QFrame()
        card.setObjectName("card")
        c = QVBoxLayout(card)
        c.setContentsMargins(18, 12, 18, 14)
        c.setSpacing(10)
        t = QLabel("网站与社区")
        t.setObjectName("cardTitle")
        c.addWidget(t)
        row1 = QHBoxLayout()
        row1.addWidget(QLabel("GitHub 仓库:"))
        self.github_label = QLabel(app_cfg.get("github", ""))
        self.github_label.setObjectName("link")
        row1.addWidget(self.github_label, 1)
        btn_gh = QPushButton("打开")
        row1.addWidget(btn_gh)
        c.addLayout(row1)
        btn_gh.clicked.connect(lambda: self._open_url(app_cfg.get("github", "")))
        row2 = QHBoxLayout()
        row2.addWidget(QLabel("QQ 群:"))
        qq = QLabel(app_cfg.get("qq_group", "") or "暂未创建")
        qq.setObjectName("hint")
        row2.addWidget(qq, 1)
        c.addLayout(row2)
        pv.addWidget(card)

        # ---- 开源许可证 ----
        card = QFrame()
        card.setObjectName("card")
        c = QVBoxLayout(card)
        c.setContentsMargins(18, 12, 18, 14)
        c.setSpacing(8)
        t = QLabel(f"开源许可证:{app_cfg.get('license', 'MIT')}")
        t.setObjectName("cardTitle")
        c.addWidget(t)
        lic = QLabel("MIT License — 允许自由使用、修改与分发,需保留版权声明。")
        lic.setObjectName("hint")
        lic.setWordWrap(True)
        c.addWidget(lic)
        pv.addWidget(card)

        pv.addStretch(1)
        scroll.setWidget(container)
        outer = QVBoxLayout(page)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll)
        self.stack.addWidget(page)

    def _open_url(self, url: str):
        if not url:
            return
        import webbrowser
        webbrowser.open(url)

    # ================= 保存(关闭窗口自动保存) =================
    def _save_all(self):
        self._on_field_edit()  # 确保当前平台字段已写回
        self.cfg["timeout"] = self.timeout_spin.value()
        self.cfg["retry"]["max_retries"] = self.retry_spin.value()
        self.cfg["ocr"]["mode"] = "cloud" if self.btn_ocr_cloud.isChecked() else "local"
        self.cfg["prompts"]["ocr"] = self.ocr_edit.toPlainText()
        self.cfg["prompts"]["answer"] = self.answer_edit.toPlainText()
        storage = self.cfg["storage"]
        storage["cache_dir"] = self.cache_edit.text().strip()
        storage["questions_dir"] = self.questions_edit.text().strip()
        storage["add_to_knowledge"] = self.add_kb_check.isChecked()
        p = self._current_provider()
        if p:
            self.cfg["active_provider"] = p.get("id", "")
        save_config(self.cfg)

    def _on_close(self):
        self._save_all()
        self.accept()

    def closeEvent(self, event):
        self._save_all()
        super().closeEvent(event)

    def showEvent(self, event):
        super().showEvent(event)
        # 首次显示时载入当前字段并刷新请求记录
        self._load_provider_fields()
        self.grid.refresh()
        self.cache_edit.setText(self.cfg["storage"]["cache_dir"])
        self.questions_edit.setText(self.cfg["storage"]["questions_dir"])
        self.add_kb_check.setChecked(bool(self.cfg["storage"]["add_to_knowledge"]))
        self.timeout_spin.setValue(int(self.cfg.get("timeout", 180)))
        self.retry_spin.setValue(int(self.cfg["retry"].get("max_retries", 3)))
        ocr_mode = self.cfg.get("ocr", {}).get("mode", "cloud")
        cloud = ocr_mode == "cloud"
        self.btn_ocr_cloud.blockSignals(True)
        self.btn_ocr_local.blockSignals(True)
        self.btn_ocr_cloud.setChecked(cloud)
        self.btn_ocr_local.setChecked(not cloud)
        self.btn_ocr_cloud.blockSignals(False)
        self.btn_ocr_local.blockSignals(False)
        self.ocr_edit.setPlainText(self.cfg["prompts"]["ocr"])
        self.answer_edit.setPlainText(self.cfg["prompts"]["answer"])


# ---------- 主题对话框 ----------
class ThemeDialog(QDialog):
    def __init__(self, cfg: dict, parent=None):
        super().__init__(parent)
        self.cfg = cfg
        theme = cfg.get("theme") or {}
        self._image_path = theme.get("image", "")
        self.setWindowTitle("主题")
        self.setMinimumSize(680, 400)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(16, 14, 16, 12)
        lay.setSpacing(10)

        body = QHBoxLayout()
        body.setSpacing(12)

        # ---- 左列:设置项 ----
        left = QVBoxLayout()
        left.setSpacing(8)

        left.addWidget(QLabel("窗口颜色"))
        row = QHBoxLayout()
        row.setSpacing(8)
        self.group = QButtonGroup(self)
        self.group.setExclusive(True)
        self.swatch = {}
        for key, info in THEMES.items():
            b = QPushButton(info["name"])
            b.setCheckable(True)
            b.setFixedSize(84, 56)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.setStyleSheet(
                "QPushButton { background: %s; color: %s; border: 2px solid transparent;"
                " border-radius: 10px; font-weight: 600; }"
                "QPushButton:hover { border-color: #8B94A7; }"
                "QPushButton:checked { border-color: #4C8DFF; }"
                % (info["bg"], info["fg"])
            )
            self.swatch[key] = b
            self.group.addButton(b)
            row.addWidget(b)
            b.toggled.connect(self._update_preview)
        left.addLayout(row)
        self.swatch.get(theme.get("preset", "light"), self.swatch["light"]).setChecked(True)

        left.addWidget(QLabel("图片背景(可选,叠加在颜色之上)"))
        img_row = QHBoxLayout()
        self.img_check = QCheckBox("使用图片")
        self.img_check.setChecked(bool(self._image_path))
        img_row.addWidget(self.img_check)
        self.btn_pick = QPushButton("选择图片…")
        img_row.addWidget(self.btn_pick)
        left.addLayout(img_row)
        self.img_label = QLabel(self._image_path or "未选择图片")
        self.img_label.setObjectName("hint")
        self.img_label.setWordWrap(True)
        left.addWidget(self.img_label)

        pos_grid = QGridLayout()
        pos_grid.setHorizontalSpacing(10)
        pos_grid.setVerticalSpacing(10)
        pos_grid.addWidget(QLabel("缩放"), 0, 0)
        self.scale_spin = QSpinBox()
        self.scale_spin.setRange(20, 500)
        self.scale_spin.setSuffix(" %")
        self.scale_spin.setValue(theme.get("image_scale", 100))
        pos_grid.addWidget(self.scale_spin, 0, 1)
        pos_grid.addWidget(QLabel("X 偏移"), 1, 0)
        self.ox_spin = QSpinBox()
        self.ox_spin.setRange(-5000, 5000)
        self.ox_spin.setValue(theme.get("image_offset_x", 0))
        pos_grid.addWidget(self.ox_spin, 1, 1)
        pos_grid.addWidget(QLabel("Y 偏移"), 2, 0)
        self.oy_spin = QSpinBox()
        self.oy_spin.setRange(-5000, 5000)
        self.oy_spin.setValue(theme.get("image_offset_y", 0))
        pos_grid.addWidget(self.oy_spin, 2, 1)
        left.addLayout(pos_grid)
        left.addStretch(1)

        # ---- 右列:预览 ----
        right = QVBoxLayout()
        right.addWidget(QLabel("预览"))
        self.preview = QLabel()
        self.preview.setFixedSize(PREVIEW_W, PREVIEW_H)
        self.preview.setStyleSheet("border: 1px dashed #8A93A6; border-radius: 8px; background: transparent;")
        right.addWidget(self.preview, 0, Qt.AlignmentFlag.AlignHCenter)
        right.addStretch(1)

        body.addLayout(left, 3)
        body.addLayout(right, 2)
        lay.addLayout(body)

        footer, btn_cancel, btn_ok = _footer("保存")
        lay.addLayout(footer)
        btn_ok.clicked.connect(self._on_save)
        btn_cancel.clicked.connect(self.reject)

        self.img_check.toggled.connect(self._update_preview)
        self.btn_pick.clicked.connect(self._pick_image)
        for spin in (self.scale_spin, self.ox_spin, self.oy_spin):
            spin.valueChanged.connect(self._update_preview)
        self._update_preview()

    def _current_preset(self) -> str:
        for key, b in self.swatch.items():
            if b.isChecked():
                return key
        return "light"

    def _pick_image(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "选择背景图片", "", "图片文件 (*.png *.jpg *.jpeg *.bmp *.webp)"
        )
        if path:
            self._image_path = path
            self.img_label.setText(path)
            self.img_check.setChecked(True)
            self._update_preview()

    def _update_preview(self):
        if not hasattr(self, "preview"):
            return  # 控件尚未创建完成(构造期间信号触发)
        pm = QPixmap(self.preview.size())
        pm.fill(Qt.GlobalColor.transparent)
        p = QPainter(pm)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        t = THEMES[self._current_preset()]
        rect = QRectF(4, 4, pm.width() - 8, pm.height() - 8)
        hole = QRectF(rect.x() + 46, rect.y() + 56, rect.width() - 92, rect.height() - 112)
        path = QPainterPath()
        path.addRoundedRect(rect, 10, 10)
        path.addRect(hole)

        img = QPixmap(self._image_path) if (self.img_check.isChecked() and self._image_path) else QPixmap()
        p.fillPath(path, QColor(t["bg"]))
        if not img.isNull():
            p.save()
            p.setClipPath(path)
            scale = self.scale_spin.value() / 100.0
            w, h = img.width() * scale, img.height() * scale
            p.drawPixmap(QRectF(self.ox_spin.value() + 4, self.oy_spin.value() + 4, w, h),
                         img, QRectF(img.rect()))
            p.restore()
        # 洞口边框(红色,模拟主窗口)
        p.setPen(QPen(QColor(255, 82, 82), 1))
        p.drawRect(hole.adjusted(0.5, 0.5, -0.5, -0.5))
        p.end()
        self.preview.setPixmap(pm)

    def _on_save(self):
        self.cfg["theme"] = {
            "preset": self._current_preset(),
            "image": self._image_path if self.img_check.isChecked() else "",
            "image_scale": self.scale_spin.value(),
            "image_offset_x": self.ox_spin.value(),
            "image_offset_y": self.oy_spin.value(),
        }
        save_config(self.cfg)
        self.accept()
