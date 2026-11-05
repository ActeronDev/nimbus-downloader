"""Small reusable widgets: badges, smooth progress, toasts, empty states. by ActeronDev"""
from __future__ import annotations

from PySide6.QtCore import (QEasingCurve, Property, QObject, QPoint,
                            QPropertyAnimation, QRectF, QTimer, Qt)
from PySide6.QtGui import (QColor, QLinearGradient, QPainter, QPainterPath, QPen,
                           QPixmap, QRadialGradient)
from PySide6.QtWidgets import (QFrame, QGraphicsDropShadowEffect,
                               QGraphicsOpacityEffect, QHBoxLayout, QLabel,
                               QProgressBar, QPushButton, QScrollArea, QSizePolicy,
                               QVBoxLayout, QWidget)

from . import theme
from .icons import icon


def rgba(color, alpha: float) -> str:
    c = color if isinstance(color, QColor) else QColor(color)
    return f"rgba({c.red()},{c.green()},{c.blue()},{alpha})"


def add_shadow(w: QWidget, blur: int = 26, dy: int = 8, alpha: int = 90):
    eff = QGraphicsDropShadowEffect(w)
    eff.setBlurRadius(blur)
    eff.setOffset(0, dy)
    eff.setColor(QColor(0, 0, 0, alpha))
    w.setGraphicsEffect(eff)
    return eff


def dominant_color(path: str) -> QColor | None:
    """Cheap 'content drives colour': pick the busiest saturated bucket in the thumb."""
    pm = QPixmap(path)
    if pm.isNull():
        return None
    img = pm.scaled(24, 14, Qt.IgnoreAspectRatio, Qt.FastTransformation).toImage()
    buckets: dict[tuple[int, int, int], list[int]] = {}
    for y in range(img.height()):
        for x in range(img.width()):
            c = img.pixelColor(x, y)
            if c.saturationF() * c.valueF() < 0.15:
                continue
            key = (c.red() // 48, c.green() // 48, c.blue() // 48)
            b = buckets.setdefault(key, [0, 0, 0, 0])
            b[0] += c.red(); b[1] += c.green(); b[2] += c.blue(); b[3] += 1
    if not buckets:
        return None
    r, g, bl, n = max(buckets.values(), key=lambda v: v[3])
    c = QColor(r // n, g // n, bl // n)
    if c.valueF() < 0.45:            # keep it readable on a dark surface
        c = c.lighter(155)
    return c


class GlowPage(QWidget):
    """Page background with a soft accent glow behind the header."""

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        grad = QRadialGradient(self.width() * 0.30, -self.height() * 0.10,
                               max(self.width() * 0.85, 420))
        top = QColor(theme.ACCENT_A)
        top.setAlphaF(0.12)
        mid = QColor(theme.ACCENT_B)
        mid.setAlphaF(0.055)
        grad.setColorAt(0.0, top)
        grad.setColorAt(0.45, mid)
        grad.setColorAt(1.0, QColor(0, 0, 0, 0))
        p.fillRect(self.rect(), grad)


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
        self.setText(f"●  {text}")
        self.setStyleSheet(
            f"background:{rgba(color, 0.14)}; color:{color}; border-radius:9px;"
            f"padding:3px 9px; font-size:11.5px; font-weight:600;")

    def pop(self):
        """Small scale bounce when the number behind it changes."""
        geo = self.geometry()
        a = QPropertyAnimation(self, b"geometry", self)
        a.setDuration(theme.DUR_FAST)
        a.setStartValue(geo.adjusted(-4, -2, 4, 2))
        a.setEndValue(geo)
        a.setEasingCurve(QEasingCurve.OutBack)
        a.start()
        self._pop_anim = a


class SmoothBar(QProgressBar):
    """Progress bar that eases to the new value instead of jumping."""

    def __init__(self):
        super().__init__()
        self.setRange(0, 1000)
        self.setTextVisible(False)
        self.setFixedHeight(6)
        self._anim = QPropertyAnimation(self, b"value", self)
        self._anim.setDuration(theme.DUR_SLOW)
        self._anim.setEasingCurve(QEasingCurve.OutCubic)

    def set_pct(self, pct: float):
        target = int(max(0.0, min(100.0, pct)) * 10)
        if target == self.value():
            return
        self._anim.stop()
        self._anim.setStartValue(self.value())
        self._anim.setEndValue(target)
        self._anim.start()

    def set_tint(self, color: QColor | None):
        if color is None:
            return
        self.setStyleSheet(
            f"QProgressBar{{background:{theme.TRACK};border:none;border-radius:3px;}}"
            f"QProgressBar::chunk{{background:qlineargradient(x1:0,y1:0,x2:1,y2:0,"
            f"stop:0 {color.name()}, stop:1 {color.lighter(130).name()});border-radius:3px;}}")


class EmptyState(QWidget):
    def __init__(self, glyph: str, title: str, hint: str, action: str = "", on_action=None):
        super().__init__()
        g = QLabel(glyph)
        g.setAlignment(Qt.AlignCenter)
        g.setStyleSheet(f"color:{theme.ACCENT_A}; font-size:40px;")
        t = QLabel(title)
        t.setAlignment(Qt.AlignCenter)
        t.setStyleSheet(f"color:{theme.TEXT}; font-size:16px; font-weight:600;")
        h = QLabel(hint)
        h.setAlignment(Qt.AlignCenter)
        h.setWordWrap(True)
        h.setStyleSheet(f"color:{theme.MUTED}; font-size:12.5px;")
        lay = QVBoxLayout(self)
        lay.setSpacing(8)
        lay.addStretch(1)
        lay.addWidget(g)
        lay.addWidget(t)
        lay.addWidget(h)
        if action and on_action:
            b = QPushButton(action)
            b.setObjectName("primary")
            b.setCursor(Qt.PointingHandCursor)
            b.setFixedHeight(38)
            b.clicked.connect(on_action)
            wrap = QHBoxLayout()
            wrap.addStretch(1)
            wrap.addWidget(b)
            wrap.addStretch(1)
            lay.addSpacing(6)
            lay.addLayout(wrap)
        lay.addStretch(1)


class SlimScroll(QScrollArea):
    """Vertical-only scroll area; the handle fades in while the pointer is over it."""

    HOVER = "QScrollBar::handle:vertical { background:%s; border-radius:4px; min-height:28px; }" % theme.BORDER_STRONG

    def __init__(self):
        super().__init__()
        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.NoFrame)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.setContentsMargins(0, 0, 0, 0)
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


class StatusBar(QFrame):
    """Slim fixed bar at the bottom of the content area; hidden when idle."""

    def __init__(self):
        super().__init__()
        self.setObjectName("statusbar")
        self.setFixedHeight(30)
        self.dot = QLabel("●")
        self.text = QLabel("")
        self.text.setObjectName("hint")
        lay = QHBoxLayout(self)
        lay.setContentsMargins(theme.LG + 4, 4, theme.LG + 4, 4)
        lay.setSpacing(8)
        lay.addWidget(self.dot)
        lay.addWidget(self.text, 1)
        self._on = False
        self._bright = True
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._blink)
        self._paint_dot()

    def _paint_dot(self):
        c = theme.ACCENT_A if self._bright else theme.ACCENT_PRESSED
        self.dot.setStyleSheet(f"color:{c}; font-size:10px;")

    def _blink(self):
        self._bright = not self._bright
        self._paint_dot()

    def set_active(self, text: str):
        if not text:
            if self._on:
                self._on = False
                self._timer.stop()
                self.hide()
            return
        if not self._on:
            self._on = True
            self.show()
            self._timer.start(650)
        self.text.setText(text)


class Toast(QFrame):
    def __init__(self, parent: QWidget, text: str, kind: str = "info", on_close=None):
        super().__init__(parent)
        self.setObjectName("toast")
        color = {"success": theme.SUCCESS, "error": theme.ERROR,
                 "warning": theme.WARNING}.get(kind, theme.ACCENT_A)
        bar = QFrame()
        bar.setFixedWidth(3)
        bar.setStyleSheet(f"background:{color}; border-radius:2px;")
        self.label = QLabel(text)
        self.label.setObjectName("toastText")
        self.label.setWordWrap(True)
        close = QPushButton()
        close.setObjectName("ghost")
        close.setIcon(icon("close", theme.DIM, 14))
        close.setFixedSize(20, 20)
        close.setCursor(Qt.PointingHandCursor)
        close.setToolTip("Dismiss")
        close.clicked.connect(lambda: on_close(self) if on_close else None)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(10, 8, 8, 8)
        lay.setSpacing(10)
        lay.addWidget(bar)
        lay.addWidget(self.label, 1)
        lay.addWidget(close, 0, Qt.AlignTop)
        self.setFixedWidth(330)
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setStyleSheet(f"QFrame#toast {{ background:{theme.ELEV};"
                           f" border:1px solid {theme.BORDER_STRONG}; border-radius:12px; }}")
        self._effect = QGraphicsOpacityEffect(self)
        self._effect.setOpacity(0.0)
        self.setGraphicsEffect(self._effect)
        self.layout().activate()
        self.adjustSize()
        self._anim = QPropertyAnimation(self._effect, b"opacity", self)
        self._anim.setDuration(theme.DUR)
        self._anim.setEasingCurve(QEasingCurve.OutCubic)
        self._pos = QPropertyAnimation(self, b"pos", self)
        self._pos.setDuration(theme.DUR)
        self._pos.setEasingCurve(QEasingCurve.OutCubic)

    def fade(self, to: float):
        self._anim.stop()
        self._anim.setStartValue(self._effect.opacity())
        self._anim.setEndValue(to)
        self._anim.start()

    def slide_to(self, target: QPoint, animate: bool = True):
        self._pos.stop()
        if not animate:
            self.move(target)
            return
        self._pos.setStartValue(self.pos())
        self._pos.setEndValue(target)
        self._pos.start()


class Toaster(QObject):
    """Bottom-right overlay above the status bar: max 3, duplicates merged."""

    MARGIN = 20
    GAP = 8
    MAX = 3
    LIFE = 4000

    def __init__(self, window: QWidget):
        super().__init__(window)
        self.window = window
        self.items: list[Toast] = []
        self.bottom_offset = 34
        self._timers: dict[Toast, QTimer] = {}

    def set_bottom_offset(self, px: int):
        self.bottom_offset = px
        self.reposition()

    def show(self, text: str, kind: str = "info", ms: int = LIFE):
        for t in self.items:
            if t.label.text() == text:
                self._restart(t, ms)
                return
        while len(self.items) >= self.MAX:
            self._dismiss(self.items[0], quick=True)
        t = Toast(self.window, text, kind, on_close=lambda x: self._dismiss(x))
        self.items.append(t)
        t.show()
        t.raise_()
        t.layout().activate()
        t.adjustSize()
        self.reposition(animate=False)
        start = t.pos()
        t.move(start.x(), start.y() + 10)
        t.slide_to(start, animate=True)
        t.fade(1.0)
        self._restart(t, ms)

    def _restart(self, t: Toast, ms: int):
        timer = self._timers.get(t)
        if timer is None:
            timer = QTimer(self.window)
            timer.setSingleShot(True)
            timer.timeout.connect(lambda: self._dismiss(t))
            self._timers[t] = timer
        timer.start(ms)

    def _dismiss(self, t: Toast, quick: bool = False):
        if t not in self.items:
            return
        self.items.remove(t)
        timer = self._timers.pop(t, None)
        if timer:
            timer.stop()
        t.fade(0.0)
        QTimer.singleShot(70 if quick else 170,
                          lambda: (t.deleteLater(), self.reposition()))

    def reposition(self, animate: bool = True):
        y = self.window.height() - self.bottom_offset - self.MARGIN
        for t in reversed(self.items):
            t.adjustSize()
            x = self.window.width() - t.width() - self.MARGIN
            y -= t.height()
            t.slide_to(QPoint(x, y), animate=animate)
            y -= self.GAP


def fade_in(widget: QWidget, ms: int = theme.DUR):
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


class Card(QFrame):
    """Card with a 1px inner top highlight so it reads as raised, not painted on."""

    def __init__(self):
        super().__init__()
        self.setObjectName("card")

    def paintEvent(self, e):
        super().paintEvent(e)
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setClipRect(0, 0, self.width(), 7)
        p.setPen(QPen(QColor(255, 255, 255, 26), 1))
        path = QPainterPath()
        path.addRoundedRect(QRectF(0.5, 0.5, self.width() - 1, self.height() - 1),
                            theme.R_CARD - 0.5, theme.R_CARD - 0.5)
        p.drawPath(path)


class LiveBar(QWidget):
    """Progress bar with an accent gradient and a shine that moves while active."""

    def __init__(self):
        super().__init__()
        self.setFixedHeight(6)
        self._pct = 0.0
        self._tint: QColor | None = None
        self._active = False
        self._phase = 0.0
        self._anim = QPropertyAnimation(self, b"pct", self)
        self._anim.setDuration(theme.DUR_SLOW)
        self._anim.setEasingCurve(QEasingCurve.OutCubic)
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._step)

    def _get_pct(self) -> float:
        return self._pct

    def _set_pct(self, v: float):
        self._pct = max(0.0, min(1.0, float(v)))
        self.update()

    pct = Property(float, _get_pct, _set_pct)

    def set_pct(self, percent: float):
        target = max(0.0, min(1.0, percent / 100.0))
        if abs(target - self._pct) < 0.002:
            return
        self._anim.stop()
        self._anim.setStartValue(self._pct)
        self._anim.setEndValue(target)
        self._anim.start()

    def set_active(self, on: bool):
        self._active = on
        if on and not self._timer.isActive():
            self._timer.start(40)
        elif not on:
            self._timer.stop()
            self.update()

    def set_tint(self, color: QColor | None):
        self._tint = color
        self.update()

    def _step(self):
        self._phase = (self._phase + 0.02) % 1.0
        self.update()

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        r = self.rect()
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(theme.TRACK))
        p.drawRoundedRect(r, 3, 3)
        w = int(r.width() * self._pct)
        if w <= 1:
            return
        chunk = QRectF(r.left(), r.top(), w, r.height())
        grad = QLinearGradient(chunk.left(), 0, chunk.right(), 0)
        a = self._tint or QColor(theme.ACCENT_A)
        b = self._tint.lighter(135) if self._tint else QColor(theme.ACCENT_B)
        grad.setColorAt(0, a)
        grad.setColorAt(1, b)
        p.setBrush(grad)
        p.drawRoundedRect(chunk, 3, 3)
        if self._active and w > 24:
            shine = QColor(255, 255, 255, 60)
            x = chunk.left() + self._phase * chunk.width()
            band = QRectF(x - 18, chunk.top(), 36, chunk.height())
            p.setClipRect(chunk.toRect())
            p.setBrush(shine)
            p.drawRect(band)


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
