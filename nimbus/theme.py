"""Design tokens and the single global stylesheet. by ActeronDev"""
from __future__ import annotations

# ---- color ---------------------------------------------------------------
BG = "#0b0e13"            # app background
PANEL = "#0f131a"         # sidebar / panels
CARD = "#141923"          # cards
CARD_HOVER = "#182030"
BORDER = "#1e2531"
BORDER_STRONG = "#2a3340"
ACCENT = "#6b8afd"
ACCENT_HOVER = "#8aa2ff"
ACCENT_PRESSED = "#5871d8"
TEXT = "#e9edf4"
MUTED = "#99a3b3"
DIM = "#677184"
SUCCESS = "#4ade80"
ERROR = "#f87171"
WARNING = "#fbbf24"
TRACK = "#1d2532"

_FAMILIES = ("Segoe UI Variable Text", "Segoe UI", "Inter", "Arial")


def font_family() -> str:
    """First installed family from the stack — Qt QSS wants one name, not a list."""
    from PySide6.QtGui import QFontDatabase
    installed = set(QFontDatabase.families())
    for fam in _FAMILIES:
        if fam in installed:
            return fam
    return "Segoe UI"

# ---- spacing / radius (8px grid) ----------------------------------------
XS, SM, MD, LG, XL = 4, 8, 16, 24, 32
R_CARD, R_BTN = 14, 10


def qss() -> str:
    return f"""
* {{ font-family:'{font_family()}'; font-size:13px; color:{TEXT}; }}
QWidget#root, QWidget#content, QStackedWidget, QStackedWidget > QWidget {{ background:{BG}; }}
QWidget#sidebar {{ background:{PANEL}; border-right:1px solid {BORDER}; }}
QLabel {{ background:transparent; }}
QLabel#brand {{ font-size:17px; font-weight:700; letter-spacing:0.2px; }}
QLabel#muted {{ color:{MUTED}; }}
QLabel#hint {{ color:{DIM}; font-size:12px; }}
QLabel#pageTitle {{ font-size:28px; font-weight:700; }}
QLabel#cardTitle {{ font-size:15px; font-weight:600; }}
QLabel#sectionTitle {{ font-size:15px; font-weight:600; }}
QLabel#toastText {{ font-size:13px; }}

QLineEdit {{ background:{CARD}; border:1px solid {BORDER}; border-radius:{R_BTN}px;
            padding:14px 16px; font-size:14px; selection-background-color:{ACCENT}; }}
QLineEdit:hover {{ border-color:{BORDER_STRONG}; }}
QLineEdit:focus {{ border-color:{ACCENT}; background:{CARD_HOVER}; }}

QPushButton {{ background:{CARD}; border:1px solid {BORDER}; border-radius:{R_BTN}px;
              padding:10px 16px; color:{TEXT}; }}
QPushButton:hover {{ background:{CARD_HOVER}; border-color:{BORDER_STRONG}; }}
QPushButton:pressed {{ background:{PANEL}; }}
QPushButton:disabled {{ color:{DIM}; border-color:{BORDER}; background:{PANEL}; }}

QPushButton#primary {{ background:{ACCENT}; border:1px solid {ACCENT}; color:#0a1020;
                      font-weight:700; font-size:14px; padding:12px 24px; }}
QPushButton#primary:hover {{ background:{ACCENT_HOVER}; border-color:{ACCENT_HOVER}; }}
QPushButton#primary:pressed {{ background:{ACCENT_PRESSED}; border-color:{ACCENT_PRESSED}; }}
QPushButton#primary:disabled {{ background:{TRACK}; border-color:{TRACK}; color:{DIM}; }}

QPushButton#nav {{ background:transparent; border:none; border-radius:{R_BTN}px;
                  padding:11px 12px; color:{MUTED}; text-align:left; font-size:13px; }}
QPushButton#nav:hover {{ background:{CARD}; color:{TEXT}; }}
QPushButton#nav:checked {{ background:{CARD_HOVER}; color:#ffffff; font-weight:600; }}

QPushButton#ghost {{ background:transparent; border:none; color:{MUTED}; padding:7px 10px; }}
QPushButton#ghost:hover {{ color:{TEXT}; background:{CARD}; }}
QPushButton#ghost:disabled {{ color:{DIM}; background:transparent; }}
QPushButton#danger {{ background:transparent; border:none; color:{DIM}; padding:7px 10px; }}
QPushButton#danger:hover {{ color:{ERROR}; background:rgba(248,113,113,0.12); }}

QPushButton#seg {{ background:transparent; border:1px solid transparent; border-radius:8px;
                  padding:8px 22px; color:{MUTED}; font-size:13px; }}
QPushButton#seg:hover {{ color:{TEXT}; }}
QPushButton#seg:checked {{ background:{CARD_HOVER}; border-color:{BORDER_STRONG}; color:#ffffff;
                          font-weight:600; }}

QPushButton#chip {{ background:{CARD}; border:1px solid {BORDER}; border-radius:9px;
                   padding:8px 15px; color:{MUTED}; font-size:12.5px; }}
QPushButton#chip:hover {{ border-color:{BORDER_STRONG}; color:{TEXT}; }}
QPushButton#chip:checked {{ background:rgba(107,138,253,0.16); border-color:{ACCENT}; color:#ffffff; }}

QPushButton#pill {{ background:{CARD}; border:1px solid {BORDER}; border-radius:12px;
                   padding:6px 12px; color:{MUTED}; font-size:12px; }}
QPushButton#pill:hover {{ color:{TEXT}; border-color:{BORDER_STRONG}; }}

QFrame#card {{ background:{CARD}; border:1px solid {BORDER}; border-radius:{R_CARD}px; }}
QFrame#card:hover {{ background:{CARD_HOVER}; border-color:{BORDER_STRONG}; }}
QFrame#panel {{ background:{PANEL}; border:1px solid {BORDER}; border-radius:{R_CARD}px; }}
QFrame#meta {{ background:{TRACK}; border:none; border-radius:8px; }}

QLabel#thumb {{ background:{PANEL}; border:1px solid {BORDER}; border-radius:10px; color:{DIM}; }}
QLabel#thumbBig {{ background:{PANEL}; border:1px solid {BORDER}; border-radius:12px; color:{DIM}; }}

QProgressBar {{ background:{TRACK}; border:none; border-radius:3px; }}
QProgressBar::chunk {{ background:{ACCENT}; border-radius:3px; }}

QScrollArea {{ background:transparent; border:none; }}
QScrollArea > QWidget > QWidget {{ background:transparent; }}
QScrollBar:vertical {{ background:transparent; width:8px; margin:2px; }}
QScrollBar::handle:vertical {{ background:#242c39; border-radius:4px; min-height:28px; }}
QScrollBar::handle:vertical:hover {{ background:{BORDER_STRONG}; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height:0; }}
QScrollBar::add-page, QScrollBar::sub-page {{ background:transparent; }}
QScrollBar:horizontal {{ height:0; }}

QSlider::groove:horizontal {{ height:4px; background:{TRACK}; border-radius:2px; }}
QSlider::sub-page:horizontal {{ background:{ACCENT}; border-radius:2px; }}
QSlider::handle:horizontal {{ background:{TEXT}; width:12px; margin:-5px 0; border-radius:6px; }}

QToolTip {{ background:{CARD_HOVER}; color:{TEXT}; border:1px solid {BORDER_STRONG};
           padding:6px 8px; border-radius:8px; }}
QMenu {{ background:{CARD}; border:1px solid {BORDER_STRONG}; padding:6px; border-radius:10px; }}
QMenu::item {{ padding:7px 20px; border-radius:7px; }}
QMenu::item:selected {{ background:{CARD_HOVER}; }}
"""
