# -*- coding: utf-8 -*-
"""主题:黑/白/灰三套现代调色板与全局样式表生成。"""
from PySide6.QtGui import QColor

# 每套主题:窗口底色 / 文字 / 次文字 / 输入控件 / 边框 / 按钮三态 / 主色三态 / 滚动条 / 窗口描边 / 卡片
THEMES = {
    "dark": {
        "name": "黑色",
        "bg": "#171A21",
        "card": "#1E222D",
        "fg": "#E8ECF4",
        "secondary": "#8B94A7",
        "control": "#10131A",
        "border": "#2A3140",
        "button": "#232A38",
        "button_hover": "#2C3547",
        "button_pressed": "#1D2430",
        "accent": "#4C8DFF",
        "accent_hover": "#66A1FF",
        "accent_pressed": "#3A76E8",
        "scrollbar": "#343D4E",
        "scrollbar_hover": "#465268",
        "outline": "rgba(255, 255, 255, 16)",
    },
    "light": {
        "name": "白色",
        "bg": "#F2F4F8",
        "card": "#FFFFFF",
        "fg": "#252B36",
        "secondary": "#6E7686",
        "control": "#FFFFFF",
        "border": "#E3E7EF",
        "button": "#ECF0F6",
        "button_hover": "#E0E6F0",
        "button_pressed": "#D4DBE8",
        "accent": "#2F6FED",
        "accent_hover": "#4A85F5",
        "accent_pressed": "#2459C7",
        "scrollbar": "#C7CEDB",
        "scrollbar_hover": "#AFB9CA",
        "outline": "rgba(0, 0, 0, 24)",
    },
    "gray": {
        "name": "灰色",
        "bg": "#5F6672",
        "card": "#686F7D",
        "fg": "#F7F8FB",
        "secondary": "#C6CBD6",
        "control": "#4A515E",
        "border": "#757E8F",
        "button": "#545C6B",
        "button_hover": "#626B7D",
        "button_pressed": "#4A515F",
        "accent": "#7FA8FF",
        "accent_hover": "#96B8FF",
        "accent_pressed": "#6A92F0",
        "scrollbar": "#6E7788",
        "scrollbar_hover": "#7E889A",
        "outline": "rgba(255, 255, 255, 20)",
    },
}

FONT_FAMILY = '"Microsoft YaHei UI", "Microsoft YaHei", "PingFang SC", "Segoe UI", sans-serif'


def build_stylesheet(preset: str) -> str:
    """按预设生成全局样式表(应用到 QApplication,所有窗口/对话框统一生效)。"""
    t = THEMES.get(preset, THEMES["dark"])
    return f"""
* {{ font-family: {FONT_FAMILY}; }}
QWidget {{ font-size: 13px; color: {t['fg']}; }}
QLabel {{ background: transparent; }}
QLabel#title {{ font-size: 15px; font-weight: 700; }}
QLabel#hint {{ color: {t['secondary']}; font-size: 12px; }}

QLineEdit, QSpinBox, QPlainTextEdit, QTextEdit, QComboBox {{
    background: {t['control']}; border: 1px solid {t['border']};
    border-radius: 8px; padding: 5px 10px; selection-background-color: {t['accent']};
    selection-color: #FFFFFF;
}}
QLineEdit:focus, QSpinBox:focus, QPlainTextEdit:focus, QTextEdit:focus, QComboBox:focus {{
    border: 1px solid {t['accent']};
}}
QLineEdit:disabled, QSpinBox:disabled, QPlainTextEdit:disabled {{
    color: {t['secondary']}; background: {t['button']};
}}

QPushButton {{
    background: {t['button']}; border: 1px solid {t['border']};
    border-radius: 8px; padding: 6px 14px; font-weight: 600;
}}
QPushButton:hover {{ background: {t['button_hover']}; border-color: {t['accent']}; }}
QPushButton:pressed {{ background: {t['button_pressed']}; }}
QPushButton:disabled {{ color: {t['secondary']}; background: {t['control']}; border-color: {t['border']}; }}
QPushButton#primaryBtn {{
    background: {t['accent']}; border: none; color: #FFFFFF; padding: 6px 18px;
}}
QPushButton#primaryBtn:hover {{ background: {t['accent_hover']}; }}
QPushButton#primaryBtn:selected, QPushButton#primaryBtn:pressed {{ background: {t['accent_pressed']}; }}

/* 标题:蓝底白字圆角 */
QLabel#titleArt {{
    font-size: 18px; font-weight: 700; letter-spacing: 2px;
    color: #FFFFFF; background: {t['accent']};
    border-radius: 12px; padding: 4px 16px;
}}
QLabel#titleSub {{ color: {t['secondary']}; font-size: 12px; }}

/* 识别类型与耗时(清空按钮左侧) */
QLabel#metaInfo {{
    color: {t['secondary']}; font-size: 13px; font-weight: 600;
    background: {t['button']}; border-radius: 8px; padding: 4px 10px;
}}

/* 可折叠区块标题 */
QToolButton#sectionHeader {{
    border: none; background: transparent; font-weight: 700; font-size: 13px;
    padding: 3px 0; text-align: left; color: {t['fg']};
}}
QToolButton#sectionHeader:hover {{ color: {t['accent']}; }}

/* 圆角卡片 */
QFrame#card {{
    background: {t['card']}; border: 1px solid {t['border']}; border-radius: 12px;
}}
QLabel#cardTitle {{ font-size: 14px; font-weight: 700; color: {t['fg']}; }}

/* 卡片内的选项卡片 */
QFrame#optionCard {{
    background: {t['button']}; border: 1px solid {t['border']}; border-radius: 10px;
}}
QFrame#optionCard QLabel {{ background: transparent; }}

/* 平台卡片(卡片式存放) */
QPushButton#providerCard {{
    text-align: left; padding: 10px 12px; border: 1px solid {t['border']};
    border-radius: 10px; background: {t['card']}; font-weight: 600;
}}
QPushButton#providerCard:hover {{ border-color: {t['accent']}; background: {t['button_hover']}; }}
QPushButton#providerCard:checked {{
    background: rgba(76, 141, 255, 0.16); border: 1px solid rgba(76, 141, 255, 0.4);
    color: {t['accent']};
}}

/* 未配置平台卡片:暗色(白灰/虚化)区分 */
QPushButton#providerCardDim {{
    text-align: left; padding: 10px 12px; border: 1px dashed {t['border']};
    border-radius: 10px; background: transparent; color: {t['secondary']}; font-weight: 600;
}}
QPushButton#providerCardDim:hover {{ border-color: {t['accent']}; color: {t['fg']}; }}
QPushButton#providerCardDim:checked {{
    background: rgba(76, 141, 255, 0.16); border: 1px solid rgba(76, 141, 255, 0.4);
    color: {t['accent']};
}}

/* 平台卡片(QFrame 容器,悬浮显示删除按钮) */
QFrame#providerCard, QFrame#providerCardDim {{
    border-radius: 10px; padding: 0;
}}
QFrame#providerCard {{ background: {t['card']}; border: 1px solid {t['border']}; }}
QFrame#providerCardDim {{ background: transparent; border: 1px dashed {t['border']}; }}
QFrame#providerCard:hover, QFrame#providerCardDim:hover {{ border-color: {t['accent']}; }}
/* 选中高亮:仅背景色,不产生任何边框(避免子元素继承边框) */
QFrame#providerCard[selected="true"], QFrame#providerCardDim[selected="true"] {{
    background: rgba(76, 141, 255, 0.16);
}}
QToolButton#cardDelete {{
    border: none; background: transparent; color: {t['secondary']};
    font-size: 18px; font-weight: 700; padding: 0 5px; border-radius: 6px;
}}
QToolButton#cardDelete:hover {{ color: #F85149; background: rgba(248, 81, 73, 0.12); }}

/* 滚动区透明,保证右侧底色一致 */
QScrollArea, QScrollArea > QWidget > QWidget {{ background: transparent; }}
QStackedWidget#settingsStack, QStackedWidget#settingsStack QWidget#settingsPage {{ background: transparent; }}

/* 左侧导航按钮:选中浅蓝色圆角 */
QPushButton#navBtn {{
    text-align: left; padding: 9px 14px; border: 1px solid transparent; border-radius: 9px;
    background: transparent; color: {t['fg']}; font-weight: 600;
}}
QPushButton#navBtn:hover {{ background: rgba(76, 141, 255, 0.10); }}
QPushButton#navBtn:checked {{
    background: rgba(76, 141, 255, 0.18); color: #4C8DFF;
    border: 1px solid rgba(76, 141, 255, 0.35);
}}

/* 平台选择列表 */
QListWidget#providerList {{ background: transparent; border: none; outline: 0; }}
QListWidget#providerList::item {{ padding: 8px 10px; border-radius: 9px; margin-bottom: 2px; }}
QListWidget#providerList::item:hover {{ background: rgba(76, 141, 255, 0.10); }}
QListWidget#providerList::item:selected {{ background: rgba(76, 141, 255, 0.18); color: {t['fg']}; }}

/* 眼睛按钮(API Key 显隐) */
QToolButton#eyeBtn {{ border: none; background: transparent; padding: 2px; }}
QToolButton#eyeBtn:hover {{ background: {t['button_hover']}; border-radius: 6px; }}

/* 链接文字 */
QLabel#link {{ color: {t['accent']}; }}
QLabel#link:hover {{ color: {t['accent_hover']}; text-decoration: underline; }}

/* 平台名称(可点击编辑,外观如标题) */
QLineEdit#providerNameEdit {{
    background: transparent; border: none; font-size: 17px; font-weight: 700; padding: 0;
}}
QLineEdit#providerNameEdit:focus {{ border-bottom: 1px solid {t['accent']}; }}

/* 云端/本地 互斥按钮(独立圆角) */
QPushButton#segBtnL, QPushButton#segBtnR {{
    background: {t['button']}; border: 1px solid {t['border']};
    padding: 5px 18px; font-weight: 600; border-radius: 8px;
}}
QPushButton#segBtnL {{ margin-right: 6px; }}
QPushButton#segBtnL:hover, QPushButton#segBtnR:hover {{ background: {t['button_hover']}; }}
QPushButton#segBtnL:checked, QPushButton#segBtnR:checked {{
    background: {t['accent']}; color: #FFFFFF; border-color: {t['accent']};
}}

QCheckBox, QRadioButton {{ spacing: 6px; background: transparent; }}
QCheckBox::indicator, QRadioButton::indicator {{
    width: 16px; height: 16px; border: 1px solid {t['border']}; background: {t['control']};
}}
QCheckBox::indicator {{ border-radius: 4px; }}
QCheckBox::indicator:hover {{ border-color: {t['accent']}; }}
QCheckBox::indicator:checked {{ background: {t['accent']}; border-color: {t['accent']}; }}
QRadioButton::indicator {{ border-radius: 8px; }}
QRadioButton::indicator:hover {{ border-color: {t['accent']}; }}
QRadioButton::indicator:checked {{ border: 5px solid {t['accent']}; background: {t['control']}; }}

QScrollBar:vertical {{ background: transparent; width: 8px; margin: 2px; }}
QScrollBar::handle:vertical {{ background: {t['scrollbar']}; border-radius: 4px; min-height: 24px; }}
QScrollBar::handle:vertical:hover {{ background: {t['scrollbar_hover']}; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
QScrollBar:horizontal {{ background: transparent; height: 8px; margin: 2px; }}
QScrollBar::handle:horizontal {{ background: {t['scrollbar']}; border-radius: 4px; min-width: 24px; }}
QScrollBar::handle:horizontal:hover {{ background: {t['scrollbar_hover']}; }}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width: 0; }}

QDialog {{ background: {t['bg']}; }}
QTabWidget::pane {{ border: 1px solid {t['border']}; border-radius: 10px; top: -1px; }}
QTabBar::tab {{
    background: transparent; color: {t['secondary']}; font-weight: 600;
    padding: 7px 18px; border-radius: 8px; margin-right: 4px;
}}
QTabBar::tab:selected {{ background: {t['button']}; color: {t['fg']}; }}
QTabBar::tab:hover:!selected {{ background: {t['button_hover']}; }}

QToolTip {{
    background: {t['control']}; color: {t['fg']};
    border: 1px solid {t['border']}; border-radius: 6px; padding: 4px 8px;
}}
"""


def theme_bg_color(preset: str) -> QColor:
    return QColor(THEMES.get(preset, THEMES["dark"])["bg"])


def theme_outline_color(preset: str) -> QColor:
    return QColor(THEMES.get(preset, THEMES["dark"])["outline"])
