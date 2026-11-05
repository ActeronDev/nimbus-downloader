"""Design tokens and the single global stylesheet. by ActeronDev"""
from __future__ import annotations

# ---- surfaces (four levels, darkest → lightest) --------------------------
BG = "#08090d"            # app background
SIDEBAR = "#0b0e14"       # sidebar / rails
CARD = "#11151d"          # cards and panels
ELEV = "#161b25"          # hover / selected / raised
PANEL = SIDEBAR           # legacy alias
CARD_HOVER = ELEV

# ---- lines ---------------------------------------------------------------
BORDER = "#1c222d"
BORDER_STRONG = "#2a3342"

# ---- accent (blue → violet, matches the cloud mark) ----------------------
ACCENT_A = "#6b8afd"
ACCENT_B = "#a06bfd"
ACCENT = ACCENT_A
ACCENT_HOVER = "#849cff"
ACCENT_PRESSED = "#5871d8"

# ---- text ----------------------------------------------------------------
TEXT = "#eef2f8"
MUTED = "#9aa4b4"
DIM = "#6b7587"

# ---- semantic ------------------------------------------------------------
SUCCESS = "#4ade80"
ERROR = "#f87171"
WARNING = "#fbbf24"
TRACK = "#1a2130"

# ---- motion --------------------------------------------------------------
DUR_FAST, DUR, DUR_SLOW = 120, 180, 240

# ---- radius / spacing (8px grid) ----------------------------------------
R_CARD, R_BTN, R_PILL = 14, 10, 18
XS, SM, MD, LG, XL = 4, 8, 16, 24, 32

_FAMILIES = ("Segoe UI Variable Text", "Segoe UI", "Inter", "Arial")


def font_family() -> str:
    """First installed family from the stack — Qt QSS wants one name, not a list."""
    from PySide6.QtGui import QFontDatabase
    installed = set(QFontDatabase.families())
    for fam in _FAMILIES:
        if fam in installed:
            return fam
    return "Segoe UI"


GRADIENT = f"qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 {ACCENT_A}, stop:1 {ACCENT_B})"
GRADIENT_HOVER = "qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #85a0ff, stop:1 #b585ff)"


def qss() -> str:
    return f"""
* {{ font-family:'{font_family()}'; font-size:13px; color:{TEXT};
     selection-background-color:{ACCENT_A}; selection-color:#0a1020; }}
QWidget#root, QWidget#content, QStackedWidget, QStackedWidget > QWidget {{ background:{BG}; }}
QWidget#sidebar {{ background:{SIDEBAR}; border-right:1px solid {BORDER}; }}
QLabel {{ background:transparent; }}
QLabel#brand {{ font-size:17px; font-weight:700; letter-spacing:0.2px; }}
QLabel#muted {{ color:{MUTED}; }}
QLabel#hint {{ color:{DIM}; font-size:12px; }}
QLabel#pageTitle {{ font-size:30px; font-weight:700; letter-spacing:-0.5px; }}
QLabel#cardTitle {{ font-size:15px; font-weight:600; }}
QLabel#sectionTitle {{ font-size:15px; font-weight:600; }}
QLabel#micro {{ color:{DIM}; font-size:11px; font-weight:600; letter-spacing:1.4px; }}
QLabel#toastText {{ font-size:13px; }}

QLineEdit {{ background:{CARD}; border:1px solid {BORDER}; border-radius:{R_PILL}px;
            padding:16px 20px; font-size:14.5px; }}
QLineEdit:hover {{ border-color:{BORDER_STRONG}; }}
QLineEdit:focus {{ border-color:{ACCENT_A}; background:{ELEV}; }}

QPushButton {{ background:{CARD}; border:1px solid {BORDER}; border-radius:{R_BTN}px;
              padding:10px 16px; color:{TEXT}; }}
QPushButton:hover {{ background:{ELEV}; border-color:{BORDER_STRONG}; }}
QPushButton:pressed {{ background:{SIDEBAR}; }}
QPushButton:disabled {{ color:{DIM}; border-color:{BORDER}; background:{BG}; }}
QPushButton:focus {{ border-color:{ACCENT_A}; }}

QPushButton#primary {{ background:{GRADIENT}; border:1px solid {ACCENT_A}; color:#0a1020;
                      font-weight:700; font-size:14px; padding:12px 26px; }}
QPushButton#primary:hover {{ background:{GRADIENT_HOVER}; border-color:{ACCENT_B}; }}
QPushButton#primary:pressed {{ background:{ACCENT_PRESSED}; border-color:{ACCENT_PRESSED}; }}
QPushButton#primary:disabled {{ background:{TRACK}; border-color:{TRACK}; color:{DIM}; }}

QPushButton#nav {{ background:transparent; border:none; border-radius:{R_BTN}px;
                  padding:11px 12px; color:{MUTED}; text-align:left; font-size:13px; }}
QPushButton#nav:hover {{ background:{CARD}; color:{TEXT}; }}
QPushButton#nav:checked {{ background:{ELEV}; color:#ffffff; font-weight:600; }}

QPushButton#ghost {{ background:transparent; border:none; color:{MUTED}; padding:7px 10px; }}
QPushButton#ghost:hover {{ color:{TEXT}; background:{CARD}; }}
QPushButton#ghost:disabled {{ color:{DIM}; background:transparent; }}
QPushButton#danger {{ background:transparent; border:none; color:{DIM}; padding:7px 10px; }}
QPushButton#danger:hover {{ color:{ERROR}; background:rgba(248,113,113,0.12); }}

QPushButton#seg {{ background:transparent; border:1px solid transparent; border-radius:9px;
                  padding:8px 22px; color:{MUTED}; font-size:13px; }}
QPushButton#seg:hover {{ color:{TEXT}; }}
QPushButton#seg:checked {{ background:{ELEV}; border-color:{BORDER_STRONG}; color:#ffffff;
                          font-weight:600; }}

QPushButton#chip {{ background:{CARD}; border:1px solid {BORDER}; border-radius:9px;
                   padding:8px 15px; color:{MUTED}; font-size:12.5px; }}
QPushButton#chip:hover {{ border-color:{BORDER_STRONG}; color:{TEXT}; }}
QPushButton#chip:checked {{ background:rgba(107,138,253,0.16); border-color:{ACCENT_A}; color:#ffffff; }}

QPushButton#pill {{ background:{CARD}; border:1px solid {BORDER}; border-radius:{R_PILL}px;
                   padding:6px 14px; color:{MUTED}; font-size:12px; }}
QPushButton#pill:hover {{ color:{TEXT}; border-color:{BORDER_STRONG}; }}
QPushButton#pill:checked {{ background:rgba(107,138,253,0.16); border-color:{ACCENT_A}; color:#ffffff; }}

QFrame#card {{ background:{CARD}; border:1px solid {BORDER}; border-radius:{R_CARD}px; }}
QFrame#card:hover {{ background:{ELEV}; border-color:{BORDER_STRONG}; }}
QFrame#panel {{ background:{CARD}; border:1px solid {BORDER}; border-radius:{R_CARD}px; }}
QFrame#statusbar {{ background:{SIDEBAR}; border-top:1px solid {BORDER}; }}

QLabel#thumb {{ background:{SIDEBAR}; border:1px solid {BORDER}; border-radius:10px; color:{DIM}; }}
QLabel#thumbBig {{ background:{SIDEBAR}; border:1px solid {BORDER}; border-radius:12px; color:{DIM}; }}

QProgressBar {{ background:{TRACK}; border:none; border-radius:3px; }}
QProgressBar::chunk {{ background:{GRADIENT}; border-radius:3px; }}

QScrollArea {{ background:transparent; border:none; }}
QScrollArea > QWidget > QWidget {{ background:transparent; }}
QScrollBar:vertical {{ background:transparent; width:8px; margin:2px; }}
QScrollBar::handle:vertical {{ background:#242c39; border-radius:4px; min-height:28px; }}
QScrollBar::handle:vertical:hover {{ background:{BORDER_STRONG}; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height:0; }}
QScrollBar::add-page, QScrollBar::sub-page {{ background:transparent; }}
QScrollBar:horizontal {{ height:0; }}

QSlider::groove:horizontal {{ height:4px; background:{TRACK}; border-radius:2px; }}
QSlider::sub-page:horizontal {{ background:{GRADIENT}; border-radius:2px; }}
QSlider::handle:horizontal {{ background:{TEXT}; width:12px; margin:-5px 0; border-radius:6px; }}

QToolTip {{ background:{ELEV}; color:{TEXT}; border:1px solid {BORDER_STRONG};
           padding:6px 8px; border-radius:8px; }}
QMenu {{ background:{CARD}; border:1px solid {BORDER_STRONG}; padding:6px; border-radius:10px; }}
QMenu::item {{ padding:7px 20px; border-radius:7px; }}
QMenu::item:selected {{ background:{ELEV}; }}
"""
