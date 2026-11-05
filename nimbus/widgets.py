"""Small reusable widgets: badges, smooth progress, toasts, empty states. by ActeronDev"""
from __future__ import annotations

from PySide6.QtCore import QEasingCurve, QObject, QPropertyAnimation, QTimer, Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (QFrame, QGraphicsOpacityEffect, QHBoxLayout, QLabel,
                               QProgressBar, QPushButton, QScrollArea, QSizePolicy,
                               QVBoxLayout, QWidget)

from . import theme
from .icons import icon


def rgba(color: str, alpha: float) -> str:
    c = QColor(color)
    return f"rgba({c.red()},{c.green()},{c.blue()},{alpha})"


class ElidedLabel(QLabel):
    """One line, ends in … instead of stretching the layout. Full text on hover."""

    def __init__(self, text: str = ""):
        super().__init__()
        self._full = text or ""
        self.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        self._elide()

    def setText(self, text: str):  # noqa: N802 - Qt API
        self._full = text or ""
        self.setToolTip(self._full)
        self._elide()

    def full_text(self) -> str:
        return self._full

    def _elide(self):
        super().setText(self.fontMetrics().elidedText(self._full, Qt.ElideRight,
                                                      max(10, self.width())))

    def resizeEvent(self, e):  # noqa: N802 - Qt API
        super().resizeEvent(e)
        self._elide()


class Badge(QLabel):
    """Pill with a status dot."""

    def __init__(self):
        super().__init__()
        self.setAlignment(Qt.AlignCenter)

    def set_state(self, text: str, color: str):
        self.setText(f"● {text}")
        self.setStyleSheet(
            f"background:{rgba(color, 0.14)}; color:{color}; border-radius:9px;"
            f"padding:3px 9px; font-size:11.5px; font-weight:600;")


class SmoothBar(QProgressBar):
    """Progress bar that eases to the new value instead of jumping."""

    def __init__(self):
        super().__init__()
        self.setRange(0, 1000)
        self.setTextVisible(False)
        self.setFixedHeight(6)
        self._anim = QPropertyAnimation(self, b"value", self)
        self._anim.setDuration(260)
        self._anim.setEasingCurve(QEasingCurve.OutCubic)

    def set_pct(self, pct: float):
        target = int(max(0.0, min(100.0, pct)) * 10)
        if target == self.value():
            return
        self._anim.stop()
        self._anim.setStartValue(self.value())
        self._anim.setEndValue(target)
        self._anim.start()


class EmptyState(QWidget):
    def __init__(self, glyph: str, title: str, hint: str):
        super().__init__()
        g = QLabel(glyph)
        g.setAlignment(Qt.AlignCenter)
        g.setStyleSheet(f"color:{theme.DIM}; font-size:34px;")
        t = QLabel(title)
        t.setAlignment(Qt.AlignCenter)
        t.setStyleSheet(f"color:{theme.MUTED}; font-size:15px; font-weight:600;")
        h = QLabel(hint)
        h.setAlignment(Qt.AlignCenter)
        h.setWordWrap(True)
        h.setStyleSheet(f"color:{theme.DIM}; font-size:12px;")
        lay = QVBoxLayout(self)
        lay.setSpacing(6)
        lay.addStretch(1)
        lay.addWidget(g)
        lay.addWidget(t)
        lay.addWidget(h)
        lay.addStretch(1)


class SlimScroll(QScrollArea):
    """Vertical-only scroll area; the handle fades in while the pointer is over it."""

    HANDLE = ""
    HOVER = "QScrollBar::handle:vertical { background:%s; border-radius:4px; min-height:28px; }" % theme.BORDER_STRONG

    def __init__(self):
        super().__init__()
        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.NoFrame)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.viewport().setAutoFillBackground(False)
        self.setStyleSheet("QScrollArea{background:transparent;border:none;}")
        self._fade_handle(False)

    def _fade_handle(self, on: bool):
        self.verticalScrollBar().setStyleSheet(
            self.HOVER if on else "QScrollBar::handle:vertical { background:transparent; }")

    def enterEvent(self, e):  # noqa: N802
        self._fade_handle(True)
        super().enterEvent(e)

    def leaveEvent(self, e):  # noqa: N802
        self._fade_handle(False)
        super().leaveEvent(e)


class Toast(QFrame):
    def __init__(self, parent: QWidget, text: str, kind: str = "info"):
        super().__init__(parent)
        self.setObjectName("toast")
        color = {"success": theme.SUCCESS, "error": theme.ERROR,
                 "warning": theme.WARNING}.get(kind, theme.ACCENT)
        bar = QFrame()
        bar.setFixedWidth(3)
        bar.setStyleSheet(f"background:{color}; border-radius:2px;")
        label = QLabel(text)
        label.setObjectName("toastText")
        label.setWordWrap(True)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(10, 9, 14, 9)
        lay.setSpacing(10)
        lay.addWidget(bar)
        lay.addWidget(label, 1)
        self.setFixedWidth(320)
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setStyleSheet(f"QFrame#toast {{ background:{theme.CARD_HOVER};"
                           f" border:1px solid {theme.BORDER_STRONG}; border-radius:12px; }}")
        self._effect = QGraphicsOpacityEffect(self)
        self._effect.setOpacity(0.0)
        self.setGraphicsEffect(self._effect)
        self.layout().activate()
        self.adjustSize()
        self.layout().activate()
        self._anim = QPropertyAnimation(self._effect, b"opacity", self)
        self._anim.setDuration(150)
        self._anim.setEasingCurve(QEasingCurve.OutCubic)

    def fade(self, to: float):
        self._anim.stop()
        self._anim.setStartValue(self._effect.opacity())
        self._anim.setEndValue(to)
        self._anim.start()


class Toaster(QObject):
    """Bottom-right stack of auto-dismissing toasts."""

    MARGIN = 22
    GAP = 8

    def __init__(self, window: QWidget):
        super().__init__(window)
        self.window = window
        self.items: list[Toast] = []

    def show(self, text: str, kind: str = "info", ms: int = 3200):
        t = Toast(self.window, text, kind)
        self.items.append(t)
        t.show()
        t.raise_()
        t.layout().activate()
        t.adjustSize()
        self.reposition()
        # second pass once the label has wrapped for real
        QTimer.singleShot(0, self.reposition)
        t.fade(1.0)
        QTimer.singleShot(ms, lambda: self._dismiss(t))

    def _dismiss(self, t: Toast):
        if t not in self.items:
            return
        t.fade(0.0)

        def done():
            if t in self.items:
                self.items.remove(t)
                t.deleteLater()
                self.reposition()
        from PySide6.QtCore import QTimer
        QTimer.singleShot(180, done)

    def reposition(self):
        bottom = self.window.height() - self.MARGIN
        for t in reversed(self.items):
            t.adjustSize()
            x = self.window.width() - t.width() - self.MARGIN
            t.move(x, bottom - t.height())
            bottom -= t.height() + self.GAP


def fade_in(widget: QWidget, ms: int = 180):
    eff = widget.graphicsEffect()
    if not isinstance(eff, QGraphicsOpacityEffect):
        eff = QGraphicsOpacityEffect(widget)
        widget.setGraphicsEffect(eff)
    eff.setOpacity(0.0)
    anim = QPropertyAnimation(eff, b"opacity", widget)
    anim.setDuration(ms)
    anim.setStartValue(0.0)
    anim.setEndValue(1.0)
    anim.setEasingCurve(QEasingCurve.OutCubic)
    anim.start()
    widget._fade_anim = anim


class HoverIconButton(QPushButton):
    """Icon-only button that brightens with its card."""

    def __init__(self, name: str, tooltip: str, size: int = 32, color: str = theme.DIM):
        super().__init__()
        self._name = name
        self._dim = color
        self.setFixedSize(size, size)
        self.setToolTip(tooltip)
        self.setCursor(Qt.PointingHandCursor)
        self.setIcon(icon(name, color))
        self.setIconSize(self.size() * 0.5)
        self.setObjectName("ghost")
        self.setStyleSheet("padding:0;")

    def brighten(self, on: bool):
        self.setIcon(icon(self._name, theme.TEXT if on else self._dim))
