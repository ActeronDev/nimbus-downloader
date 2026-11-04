"""Vector icons drawn with QPainter — no image assets, crisp at any DPI. by ActeronDev"""
from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPainterPath, QPen, QPixmap

_CACHE: dict[tuple[str, str, int], QIcon] = {}


def _path(name: str) -> tuple[QPainterPath, bool]:
    """Return (path, filled). Coordinates live on a 24x24 grid."""
    p = QPainterPath()
    filled = False
    if name == "home":
        p.moveTo(4, 11); p.lineTo(12, 4); p.lineTo(20, 11)
        p.moveTo(6.5, 10.5); p.lineTo(6.5, 19.5); p.lineTo(17.5, 19.5); p.lineTo(17.5, 10.5)
    elif name == "download":
        p.moveTo(12, 4); p.lineTo(12, 14.5)
        p.moveTo(7.5, 10.5); p.lineTo(12, 15); p.lineTo(16.5, 10.5)
        p.moveTo(5, 19.5); p.lineTo(19, 19.5)
    elif name == "media":
        p.addRoundedRect(QRectF(4, 6, 16, 12), 2, 2)
        filled_path = QPainterPath(); filled_path.moveTo(10.5, 9.5)
        filled_path.lineTo(15.5, 12); filled_path.lineTo(10.5, 14.5); filled_path.closeSubpath()
        p.addPath(filled_path)
    elif name == "paste":
        p.addRoundedRect(QRectF(6, 5, 12, 15), 2, 2)
        p.addRoundedRect(QRectF(9, 2.5, 6, 4), 1.5, 1.5)
    elif name == "folder":
        p.moveTo(3.5, 7); p.lineTo(9.5, 7); p.lineTo(11.5, 9.5); p.lineTo(20.5, 9.5)
        p.lineTo(20.5, 18.5); p.lineTo(3.5, 18.5); p.closeSubpath()
    elif name == "play":
        p.moveTo(8.5, 5.5); p.lineTo(18.5, 12); p.lineTo(8.5, 18.5); p.closeSubpath()
        filled = True
    elif name == "pause":
        p.addRoundedRect(QRectF(7.5, 5.5, 3.4, 13), 1, 1)
        p.addRoundedRect(QRectF(13.1, 5.5, 3.4, 13), 1, 1)
        filled = True
    elif name == "trash":
        p.moveTo(4.5, 7); p.lineTo(19.5, 7)
        p.moveTo(9.5, 4.5); p.lineTo(14.5, 4.5)
        p.addRoundedRect(QRectF(6.5, 7, 11, 12.5), 1.5, 1.5)
        p.moveTo(10, 10.5); p.lineTo(10, 16.5)
        p.moveTo(14, 10.5); p.lineTo(14, 16.5)
    elif name == "close":
        p.moveTo(6.5, 6.5); p.lineTo(17.5, 17.5)
        p.moveTo(17.5, 6.5); p.lineTo(6.5, 17.5)
    elif name == "refresh":
        p.arcMoveTo(QRectF(5, 5, 14, 14), 60)
        p.arcTo(QRectF(5, 5, 14, 14), 60, 280)
        p.moveTo(15.2, 4.2); p.lineTo(18.6, 7.4); p.lineTo(14.6, 8.6)
    elif name == "back":
        p.moveTo(14, 5.5); p.lineTo(7.5, 12); p.lineTo(14, 18.5)
    elif name == "volume":
        p.moveTo(4, 10); p.lineTo(7, 10); p.lineTo(11, 6.5); p.lineTo(11, 17.5)
        p.lineTo(7, 14); p.lineTo(4, 14); p.closeSubpath()
        filled = True
    return p, filled


def icon(name: str, color: str = "#c9d1dc", size: int = 20) -> QIcon:
    key = (name, color, size)
    if key in _CACHE:
        return _CACHE[key]
    scale = 2
    pm = QPixmap(size * scale, size * scale)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    p.scale(size * scale / 24.0, size * scale / 24.0)
    path, filled = _path(name)
    if filled:
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(color))
        p.drawPath(path)
    else:
        pen = QPen(QColor(color), 1.8)
        pen.setCapStyle(Qt.RoundCap)
        pen.setJoinStyle(Qt.RoundJoin)
        p.setPen(pen)
        p.setBrush(Qt.NoBrush)
        p.drawPath(path)
    p.end()
    pm.setDevicePixelRatio(scale)
    ic = QIcon(pm)
    _CACHE[key] = ic
    return ic
