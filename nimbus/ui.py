"""Main window — sidebar navigation, Home / Downloads / Media / Player. by ActeronDev"""
from __future__ import annotations

import json
import re
import subprocess
import threading
import urllib.request
from pathlib import Path

from PySide6.QtCore import (QEasingCurve, QPropertyAnimation, QRectF, QTimer, QUrl,
                            QVariantAnimation, Qt, Signal, QObject)
from PySide6.QtGui import (QColor, QDesktopServices, QLinearGradient, QPainter,
                           QPainterPath, QPixmap, QRadialGradient)
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer
from PySide6.QtMultimediaWidgets import QVideoWidget
from PySide6.QtWidgets import (QButtonGroup, QFileDialog, QFrame, QGraphicsDropShadowEffect,
                               QGraphicsOpacityEffect, QGridLayout, QHBoxLayout, QLabel,
                               QLineEdit, QMessageBox, QPushButton, QSlider,
                               QStackedWidget, QVBoxLayout, QWidget)

import yt_dlp

from . import config, theme, update
from .downloader import (AUDIO_QUALITIES, CANCELED, DONE, ERROR, PAUSED,
                         PENDING, PROCESSING, RUNNING, VIDEO_QUALITIES, Manager,
                         _js_runtimes)
from .icons import icon
from .widgets import (Badge, Card, ElidedLabel, EmptyState, GlowPage, HoverIconButton,
                      LiveBar, SlimScroll, StatusBar, Toaster, dominant_color, rgba)

THUMBS = config.data_dir() / "thumbs"
THUMBS.mkdir(parents=True, exist_ok=True)

QUALITY_LABELS = {
    "Best Quality": "Best Quality",
    "360p": "360p",
    "480p": "480p",
    "720p": "720p (HD)",
    "1080p": "1080p (FHD)",
    "1440p": "1440p (2K)",
    "2160p": "2160p (4K)",
    "MP3 320": "MP3 320",
    "MP3 192": "MP3 192",
}

STATUS_TEXT = {
    PENDING: ("Queued", theme.WARNING),
    RUNNING: ("Downloading", theme.ACCENT_A),
    PROCESSING: ("Processing", theme.ACCENT_A),
    PAUSED: ("Paused", theme.WARNING),
    DONE: ("Completed", theme.SUCCESS),
    ERROR: ("Failed", theme.ERROR),
    CANCELED: ("Canceled", theme.DIM),
}

_ERROR_MAP = (
    (("sign in", "login", "logged in", "authentication", "account"),
     "This video requires you to be logged in."),
    (("ssl", "unable to download webpage", "urlopen", "getaddrinfo", "failed to resolve",
      "connection", "network"), "Could not reach the page. Check your connection and try again."),
    (("private video", "video unavailable", "no longer available", "removed"),
     "This video is unavailable or private."),
    (("unsupported url",), "This link isn't supported."),
    (("http error 403", "403 forbidden"), "The site refused the request. Try updating yt-dlp."),
    (("http error 404",), "Not found — the link may be broken."),
    (("no space",), "Not enough disk space."),
    (("timed out", "timeout"), "The connection timed out."),
    (("re-encode",), "Could not convert the file to H.264."),
    (("ffmpeg",), "Media processing failed (ffmpeg)."),
    (("cancelled", "canceled"), "Download canceled."),
)


def _friendly_error(raw: str) -> str:
    low = (raw or "").lower()
    for keys, msg in _ERROR_MAP:
        if any(k in low for k in keys):
            return msg
    first = (raw or "").splitlines()[0] if raw else ""
    return first.replace("ERROR: ", "").strip()[:120] or "Something went wrong."


# ---------------------------------------------------------------- helpers
def _video_id(url: str) -> str:
    m = re.search(r"(?:v=|youtu\.be/|shorts/|embed/)([A-Za-z0-9_-]{11})", url)
    return m.group(1) if m else ""


def _thumb_path(vid: str) -> Path:
    return THUMBS / f"{vid}.jpg"


def _label(text: str, name: str = "") -> QLabel:
    lbl = QLabel(text)
    if name:
        lbl.setObjectName(name)
    return lbl


def _tabular(lbl: QLabel):
    """Tabular figures stop percentages and speeds from jiggling."""
    f = lbl.font()
    try:
        f.setFeature("tnum", 1)
        lbl.setFont(f)
    except Exception:
        pass


def _size_text(path: str) -> str:
    try:
        if path and Path(path).exists():
            mb = Path(path).stat().st_size / 1048576
            return f"{mb:.0f} MB" if mb >= 1 else f"{mb * 1024:.0f} KB"
    except Exception:
        pass
    return ""


class PreviewFetcher(QObject):
    done = Signal(dict)
    failed = Signal(str)

    def fetch(self, url: str):
        threading.Thread(target=self._run, args=(url,), daemon=True).start()

    def _run(self, url: str):
        try:
            vid = _video_id(url)
            cached = _thumb_path(vid) if vid else None
            if cached and cached.exists():
                meta = _load_meta(vid)
                if meta:
                    self.done.emit(meta)
                    return
            opts = {"quiet": True, "no_warnings": True, "noplaylist": True,
                    "skip_download": True, "js_runtimes": _js_runtimes()}
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(url, download=False)
            if not info:
                self.failed.emit("Nothing found at this link")
                return
            vid = info.get("id") or vid
            meta = {
                "id": vid,
                "title": info.get("title") or "",
                "duration": int(info.get("duration") or 0),
                "channel": info.get("uploader") or info.get("channel") or "",
                "thumb": "",
            }
            if vid and info.get("thumbnail"):
                dest = _thumb_path(vid)
                try:
                    urllib.request.urlretrieve(info["thumbnail"], dest)
                    meta["thumb"] = str(dest)
                except Exception:
                    pass
            _save_meta(vid, meta)
            self.done.emit(meta)
        except Exception as e:
            self.failed.emit(str(e).splitlines()[0][:160])


def _save_meta(vid: str, meta: dict):
    try:
        (THUMBS / f"{vid}.json").write_text(json.dumps(meta, ensure_ascii=False), encoding="utf-8")
    except Exception:
        pass


def _load_meta(vid: str) -> dict | None:
    try:
        return json.loads((THUMBS / f"{vid}.json").read_text(encoding="utf-8"))
    except Exception:
        return None


class SeekSlider(QSlider):
    def _jump(self, x: int):
        if self.maximum() <= self.minimum():
            return
        ratio = min(max(x / max(1, self.width()), 0.0), 1.0)
        self.setValue(self.minimum() + round((self.maximum() - self.minimum()) * ratio))
        self.sliderMoved.emit(self.value())

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self._jump(int(e.position().x()))
            e.accept()
            return
        super().mousePressEvent(e)

    def mouseMoveEvent(self, e):
        if e.buttons() & Qt.LeftButton:
            self._jump(int(e.position().x()))
            e.accept()
            return
        super().mouseMoveEvent(e)


class Thumb(QLabel):
    """Rounded thumbnail that zooms a hair on hover."""

    def __init__(self, w=160, h=90, big: bool = False):
        super().__init__()
        self.setFixedSize(w, h)
        self.setObjectName("thumbBig" if big else "thumb")
        self.setAlignment(Qt.AlignCenter)
        self._path = ""
        self.setText("▶")

    def load(self, path: str):
        self._path = path or ""
        self._render(1.0)

    def _render(self, zoom: float):
        if not self._path or not Path(self._path).exists():
            return
        w, h = self.width(), self.height()
        pm = QPixmap(self._path).scaled(int(w * zoom) + 2, int(h * zoom) + 2,
                                        Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
        x = max(0, (pm.width() - w) // 2)
        y = max(0, (pm.height() - h) // 2)
        self.setPixmap(pm.copy(x, y, w, h))
        self.setText("")

    def enterEvent(self, e):
        if self._path:
            self._render(1.04)
        super().enterEvent(e)

    def leaveEvent(self, e):
        if self._path:
            self._render(1.0)
        super().leaveEvent(e)


class PillInput(QLineEdit):
    """Big pill URL field with the paste button sitting inside it."""

    def __init__(self, on_paste):
        super().__init__()
        self.setPlaceholderText("https://www.youtube.com/watch?v=…")
        self.setMinimumHeight(56)
        self.btn = QPushButton(self)
        self.btn.setObjectName("ghost")
        self.btn.setIcon(icon("paste", theme.MUTED))
        self.btn.setFixedSize(40, 40)
        self.btn.setToolTip("Paste link from clipboard")
        self.btn.setCursor(Qt.PointingHandCursor)
        self.btn.clicked.connect(on_paste)
        self.setTextMargins(6, 0, 48, 0)

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self.btn.move(self.width() - 48, (self.height() - 40) // 2)


class GlowCard(QFrame):
    """Card that glows in the thumbnail's dominant colour."""

    def __init__(self):
        super().__init__()
        self.setObjectName("card")
        self._glow: QColor | None = None

    def set_glow(self, color: QColor | None):
        self._glow = color
        self.update()

    def paintEvent(self, e):
        super().paintEvent(e)
        if not self._glow:
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        path = QPainterPath()
        path.addRoundedRect(QRectF(1, 1, self.width() - 2, self.height() - 2),
                            theme.R_CARD - 1, theme.R_CARD - 1)
        p.setClipPath(path)
        g = QRadialGradient(self.width() * 0.12, self.height() * 0.5,
                            max(self.width() * 0.55, 260))
        c = QColor(self._glow)
        c.setAlphaF(0.20)
        g.setColorAt(0.0, c)
        c2 = QColor(self._glow)
        c2.setAlphaF(0.0)
        g.setColorAt(1.0, c2)
        p.fillRect(self.rect(), g)


# ---------------------------------------------------------------- pickers
class QualityPicker(QWidget):
    """Visible quality chips — no dropdown."""

    changed = Signal(str)

    def __init__(self):
        super().__init__()
        self.grid = QGridLayout(self)
        self.grid.setContentsMargins(0, 0, 0, 0)
        self.grid.setHorizontalSpacing(theme.SM)
        self.grid.setVerticalSpacing(theme.SM)
        self.group = QButtonGroup(self)
        self.group.setExclusive(True)
        self.group.buttonClicked.connect(lambda b: self.changed.emit(b.property("value")))

    def set_options(self, options: list[str]):
        for b in self.group.buttons():
            self.group.removeButton(b)
            b.setParent(None)
        while self.grid.count():
            it = self.grid.takeAt(0)
            if it.widget():
                it.widget().deleteLater()
        for i, opt in enumerate(options):
            b = QPushButton(QUALITY_LABELS.get(opt, opt))
            b.setObjectName("chip")
            b.setCheckable(True)
            b.setProperty("value", opt)
            b.setCursor(Qt.PointingHandCursor)
            self.group.addButton(b)
            self.grid.addWidget(b, i // 4, i % 4)
            if i == 0:
                b.setChecked(True)
        self.grid.setColumnStretch(4, 1)

    def value(self) -> str:
        b = self.group.checkedButton()
        return b.property("value") if b else (VIDEO_QUALITIES[0])


class CodecPicker(QWidget):
    """Codec chips under the quality row: editors vs smallest file."""

    def __init__(self):
        super().__init__()
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(theme.SM)
        self.group = QButtonGroup(self)
        self.group.setExclusive(True)
        for label, val in (("H.264 / AAC — editing compatible", "h264"),
                           ("Original (AV1/VP9) — smallest file", "original")):
            b = QPushButton(label)
            b.setObjectName("chip")
            b.setCheckable(True)
            b.setProperty("value", val)
            b.setCursor(Qt.PointingHandCursor)
            self.group.addButton(b)
            row.addWidget(b)
            if val == "h264":
                b.setChecked(True)
        row.addStretch(1)

    def value(self) -> str:
        b = self.group.checkedButton()
        return b.property("value") if b else "h264"


# ---------------------------------------------------------------- home
class HomePage(GlowPage):
    def __init__(self, win: "MainWindow"):
        super().__init__()
        self.win = win
        self.settings = config.load_settings()
        self.meta: dict = {}
        self._busy = False
        self.fetcher = PreviewFetcher(self)
        self.fetcher.done.connect(self._preview_ready)
        self.fetcher.failed.connect(self._preview_failed)

        title = _label("What do you want to download?", "pageTitle")
        sub = _label("Paste a YouTube or TikTok link, pick a quality, hit Download.", "muted")

        self.url = PillInput(self.paste)
        self.url.returnPressed.connect(self.start)
        self.url.textChanged.connect(self._queue_preview)
        self.url.textChanged.connect(self._sync_button)

        self.preview = GlowCard()
        self.preview.setVisible(False)
        self.p_thumb = Thumb(150, 84)
        self.p_title = ElidedLabel()
        self.p_title.setObjectName("cardTitle")
        self.p_meta = QLabel()
        self.p_meta.setObjectName("hint")
        pv = QHBoxLayout(self.preview)
        pv.setContentsMargins(12, 12, 18, 12)
        pv.setSpacing(16)
        pv.addWidget(self.p_thumb)
        col = QVBoxLayout()
        col.setSpacing(6)
        col.addStretch(1)
        col.addWidget(self.p_title)
        col.addWidget(self.p_meta)
        col.addStretch(1)
        pv.addLayout(col, 1)

        # ---- options panel
        panel = QFrame()
        panel.setObjectName("panel")
        self.bg = QButtonGroup(self)
        self.bg.setExclusive(True)
        self.b_video = QPushButton("Video")
        self.b_video.setCheckable(True)
        self.b_video.setObjectName("seg")
        self.b_audio = QPushButton("Audio")
        self.b_audio.setCheckable(True)
        self.b_audio.setObjectName("seg")
        for b in (self.b_video, self.b_audio):
            b.setCursor(Qt.PointingHandCursor)
            self.bg.addButton(b)
        self.b_video.setChecked(True)
        self.bg.buttonClicked.connect(lambda *_: self._fill_qualities())
        seg_box = QFrame()
        seg_box.setStyleSheet(f"background:{theme.SIDEBAR}; border-radius:11px;")
        seg = QHBoxLayout(seg_box)
        seg.setContentsMargins(3, 3, 3, 3)
        seg.setSpacing(2)
        seg.addWidget(self.b_video)
        seg.addWidget(self.b_audio)
        seg.addStretch(1)

        self.quality = QualityPicker()
        self.codec = CodecPicker()
        self.codec_lbl = _label("CODEC", "micro")
        self.quality_lbl = _label("QUALITY", "micro")

        self.folder_lbl = QLabel()
        self.folder_lbl.setObjectName("hint")
        btn_folder = QPushButton()
        btn_folder.setObjectName("ghost")
        btn_folder.setIcon(icon("folder", theme.MUTED))
        btn_folder.setFixedSize(30, 30)
        btn_folder.setToolTip("Change download folder")
        btn_folder.setCursor(Qt.PointingHandCursor)
        btn_folder.clicked.connect(self.pick_folder)
        frow = QHBoxLayout()
        frow.setSpacing(theme.SM)
        frow.addWidget(self.folder_lbl, 1)
        frow.addWidget(btn_folder)

        hint = QLabel("H.264/AAC is copied straight from the source when available; "
                      "1440p and 2160p are re-encoded once.")
        hint.setObjectName("hint")
        hint.setWordWrap(True)

        pl = QVBoxLayout(panel)
        pl.setContentsMargins(theme.MD + 2, theme.MD, theme.MD + 2, theme.MD)
        pl.setSpacing(theme.SM + 2)
        pl.addWidget(seg_box, 0, Qt.AlignLeft)
        pl.addSpacing(2)
        pl.addWidget(self.quality_lbl)
        pl.addWidget(self.quality)
        pl.addSpacing(2)
        pl.addWidget(self.codec_lbl)
        pl.addWidget(self.codec)
        pl.addSpacing(4)
        pl.addLayout(frow)
        pl.addWidget(hint)

        self.btn = QPushButton("Download")
        self.btn.setObjectName("primary")
        self.btn.setIcon(icon("download", "#0a1020", 18))
        self.btn.setMinimumSize(210, 48)
        self.btn.setToolTip("Download")
        self.btn.setCursor(Qt.PointingHandCursor)
        self.btn.clicked.connect(self.start)

        brow = QHBoxLayout()
        brow.setContentsMargins(theme.LG + 4, theme.SM, theme.LG + 4, theme.SM)
        brow.addWidget(self.btn)
        brow.addStretch(1)

        inner = QWidget()
        lay = QVBoxLayout(inner)
        lay.setContentsMargins(theme.LG + 4, theme.MD + 6, theme.LG + 4, theme.SM)
        lay.setSpacing(theme.MD - 2)
        lay.addWidget(title)
        lay.addWidget(sub)
        lay.addSpacing(theme.SM)
        lay.addWidget(self.url)
        lay.addWidget(self.preview)
        lay.addSpacing(theme.XS)
        lay.addWidget(panel)
        lay.addStretch(1)

        scroll = SlimScroll()
        scroll.setWidget(inner)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        outer.addWidget(scroll, 1)
        outer.addLayout(brow)

        self._fill_qualities()
        self._sync_button()
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._fetch_preview)

    # ---- preview
    def _host(self) -> str:
        from urllib.parse import urlparse
        return (urlparse(self.url.text().strip()).netloc or "").lower()

    def _is_youtube(self) -> bool:
        h = self._host()
        return not h or "youtube.com" in h or "youtu.be" in h

    def _queue_preview(self):
        host = self._host()
        if host != getattr(self, "_host_now", None):
            self._host_now = host
            self._fill_qualities()
        self._timer.start(700)

    def _fetch_preview(self):
        url = self.url.text().strip()
        if not url.startswith(("http://", "https://")):
            self.preview.setVisible(False)
            return
        self.p_title.setText("Fetching preview…")
        self.p_meta.setText("")
        self.p_thumb.setPixmap(QPixmap())
        self.p_thumb.setText("…")
        self.preview.setVisible(True)
        self.fetcher.fetch(url)

    def _preview_ready(self, meta: dict):
        self.meta = meta
        self.p_title.setText(meta.get("title") or "Untitled")
        bits = [meta.get("channel") or ""]
        if meta.get("duration"):
            bits.append(_hms(meta["duration"]))
        self.p_meta.setText("  ·  ".join([b for b in bits if b]))
        thumb = meta.get("thumb", "")
        self.p_thumb.load(thumb)
        self.preview.set_glow(dominant_color(thumb) if thumb else None)
        self.preview.setVisible(True)

    def _preview_failed(self, msg: str):
        # a dead link should not leave a broken card behind
        self.meta = {}
        self.preview.setVisible(False)

    def paste(self):
        cb = self.win.clipboard_text()
        if cb:
            self.url.setText(cb.strip())
            self._fetch_preview()

    def _fill_qualities(self):
        video = self.b_video.isChecked()
        if video:
            # TikTok and other single-format sites only offer one real choice
            options = VIDEO_QUALITIES if self._is_youtube() else ["Best Quality"]
        else:
            options = AUDIO_QUALITIES
        self.quality.set_options(options)
        self.quality_lbl.setVisible(video)
        self.codec_lbl.setVisible(video)
        self.codec.setVisible(video)
        if hasattr(self, "folder_lbl"):
            self._sync_folder()

    def kind(self) -> str:
        return "video" if self.b_video.isChecked() else "audio"

    def _sync_folder(self):
        key = "video_dir" if self.kind() == "video" else "audio_dir"
        self.folder_lbl.setText("Saving to  " + self.settings.get(key, ""))

    def _sync_button(self):
        self.btn.setEnabled(bool(self.url.text().strip()) and not self._busy)

    def pick_folder(self):
        key = "video_dir" if self.kind() == "video" else "audio_dir"
        d = QFileDialog.getExistingDirectory(self, "Choose download folder", self.settings[key])
        if d:
            self.settings[key] = d
            config.save_settings(self.settings)
            self._sync_folder()

    def start(self):
        url = self.url.text().strip()
        if not url or self._busy:
            return
        if not url.startswith(("http://", "https://")):
            url = "https://" + url
        self.win.manager.add(url, self.kind(), self.quality.value(), self.codec.value())
        self._busy = True
        self.btn.setText("Starting…")
        self._sync_button()
        QTimer.singleShot(900, self._idle)
        self.win.go(1)

    def _idle(self):
        self._busy = False
        self.btn.setText("Download")
        self._sync_button()

    def enterEvent(self, e):
        super().enterEvent(e)

    def leaveEvent(self, e):
        super().leaveEvent(e)


# ---------------------------------------------------------------- downloads
class DownloadCard(Card):
    def __init__(self, job, win: "MainWindow"):
        super().__init__()
        self.job_id = job.id
        self.win = win
        self._tint: QColor | None = None

        self.thumb = Thumb(112, 63)
        self.title = ElidedLabel()
        self.title.setObjectName("cardTitle")
        self.badge = Badge()
        self.meta = ElidedLabel()
        self.meta.setObjectName("hint")
        self.bar = LiveBar()
        self.pct = _label("", "muted")
        self.pct.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.pct.setFixedWidth(44)
        _tabular(self.pct)
        self.stats = ElidedLabel()
        self.stats.setObjectName("hint")

        self.b_toggle = HoverIconButton("pause", "Pause", color=theme.MUTED)
        self.b_toggle.clicked.connect(lambda: win.toggle(self.job_id))
        self.b_retry = HoverIconButton("refresh", "Retry", color=theme.MUTED)
        self.b_retry.clicked.connect(lambda: win.retry(self.job_id))
        self.b_remove = HoverIconButton("close", "Remove from list", color=theme.MUTED)
        self.b_remove.clicked.connect(lambda: win.hide_job(self.job_id))
        self.b_details = QPushButton("Details")
        self.b_details.setObjectName("ghost")
        self.b_details.setCursor(Qt.PointingHandCursor)
        self.b_details.setStyleSheet("font-size:11.5px; padding:2px 6px;")
        self.b_details.clicked.connect(self._toggle_details)
        self.raw = QLabel()
        self.raw.setObjectName("hint")
        self.raw.setWordWrap(True)
        self.raw.setVisible(False)

        head = QHBoxLayout()
        head.setSpacing(theme.SM)
        head.addWidget(self.title, 1)
        head.addWidget(self.badge)
        head.addWidget(self.pct)

        bar = QHBoxLayout()
        bar.setSpacing(theme.SM)
        bar.addWidget(self.bar, 1)
        bar.addWidget(self.stats)

        foot = QHBoxLayout()
        foot.setSpacing(2)
        foot.addWidget(self.meta, 1)
        foot.addWidget(self.b_details)
        foot.addWidget(self.b_retry)
        foot.addWidget(self.b_toggle)
        foot.addWidget(self.b_remove)

        col = QVBoxLayout()
        col.setSpacing(6)
        col.addLayout(head)
        col.addLayout(bar)
        col.addLayout(foot)
        col.addWidget(self.raw)

        lay = QHBoxLayout(self)
        lay.setContentsMargins(12, 12, 12, 12)
        lay.setSpacing(14)
        lay.addWidget(self.thumb)
        lay.addLayout(col, 1)

        vid = _video_id(job.url)
        if vid and _thumb_path(vid).exists():
            self._apply_thumb(str(_thumb_path(vid)))
        elif vid:
            win.request_thumb(vid, job.url)
        self.refresh(job)

    def _apply_thumb(self, path: str):
        self.thumb.load(path)
        self._tint = dominant_color(path)
        self.bar.set_tint(self._tint)

    def set_thumb(self, path: str):
        if path:
            self._apply_thumb(path)

    def _toggle_details(self):
        self.raw.setVisible(not self.raw.isVisible())

    def refresh(self, job):
        self.title.setText(job.title or job.url)
        kind = "Video" if job.kind == "video" else "Audio"
        codec = " · Original" if job.kind == "video" and job.codec == "original" else ""
        self.meta.setText(f"{kind} · {job.quality}{codec}")
        text, color = STATUS_TEXT.get(job.status, (job.status, theme.MUTED))
        self.badge.set_state(text, color)
        self.bar.set_pct(job.pct)
        self.bar.set_active(job.status in (RUNNING, PROCESSING))
        self.pct.setText(f"{job.pct:.0f}%" if job.pct else "")
        bits = []
        if job.speed:
            bits.append(_human(job.speed) + "/s")
        if job.eta:
            bits.append(_hms(job.eta) + " left")
        self.stats.setText("  ·  ".join(bits))

        active = job.status in (RUNNING, PENDING, PAUSED)
        self.b_toggle.setVisible(active)
        name = "pause" if job.status in (RUNNING, PENDING) else "play"
        self.b_toggle._name = name
        self.b_toggle.setToolTip("Pause" if name == "pause" else "Resume")
        self.b_toggle.setIcon(icon(name, theme.MUTED))
        self.b_retry.setVisible(job.status in (ERROR, CANCELED))
        self.b_details.setVisible(bool(job.error))
        if job.error:
            self.badge.setToolTip(_friendly_error(job.error))
            self.raw.setText(job.error)

        if job.status == ERROR:
            self.setStyleSheet(f"QFrame#card {{ border:1px solid {rgba(theme.ERROR, 0.45)}; }}")
        elif self._tint:
            self.setStyleSheet(f"QFrame#card {{ border:1px solid {rgba(self._tint, 0.35)}; }}")
        else:
            self.setStyleSheet("")

    def enterEvent(self, e):
        super().enterEvent(e)

    def leaveEvent(self, e):
        super().leaveEvent(e)


class DownloadsPage(GlowPage):
    def __init__(self, win: "MainWindow"):
        super().__init__()
        self.win = win
        self.cards: dict[str, DownloadCard] = {}

        t = _label("Downloads", "pageTitle")
        self.count = _label("", "muted")
        self.live = QLabel("")
        self.live.setStyleSheet(f"color:{theme.ACCENT_A}; font-size:12px; font-weight:600;")
        self.live.hide()
        self.btn_clear = QPushButton("Clear finished")
        self.btn_clear.setObjectName("ghost")
        self.btn_clear.setCursor(Qt.PointingHandCursor)
        self.btn_clear.clicked.connect(win.clear_finished)
        head = QHBoxLayout()
        head.setSpacing(theme.SM)
        head.setContentsMargins(0, 0, 8, 0)
        head.addWidget(t)
        head.addWidget(self.count)
        head.addWidget(self.live)
        head.addStretch(1)
        head.addWidget(self.btn_clear)

        self.empty = EmptyState("↓", "Nothing here yet",
                                "Paste a link on the Home tab and your download shows up here.",
                                "Go to Home", lambda: win.go(0))
        self.holder = QWidget()
        self.list = QVBoxLayout(self.holder)
        self.list.setContentsMargins(0, 0, 8, 12)
        self.list.setSpacing(12)
        self.list.addStretch(1)
        self.scroll = SlimScroll()
        self.scroll.setWidget(self.holder)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(theme.LG + 4, theme.MD + 6, theme.LG + 4, theme.SM)
        lay.setSpacing(theme.MD - 4)
        lay.addLayout(head)
        lay.addWidget(self.empty, 1)
        lay.addWidget(self.scroll, 1)

    def visible_jobs(self) -> list[str]:
        return [jid for jid in self.win.manager.order
                if (j := self.win.manager.jobs.get(jid)) and not j.hidden]

    def set_live(self, text: str):
        self.live.setText(text)
        self.live.setVisible(bool(text))

    def rebuild(self):
        jobs = self.visible_jobs()
        for c in self.cards.values():
            c.setParent(None)
        self.cards.clear()
        while self.list.count() > 1:
            it = self.list.takeAt(0)
            if it.widget():
                it.widget().deleteLater()
        for jid in jobs:
            c = DownloadCard(self.win.manager.jobs[jid], self.win)
            self.cards[jid] = c
            self.list.insertWidget(self.list.count() - 1, c)
        self.count.setText(f"· {len(jobs)}" if jobs else "")
        self.empty.setVisible(not jobs)
        self.scroll.setVisible(bool(jobs))
        self.btn_clear.setVisible(any(self.win.manager.jobs[j].status in (DONE, CANCELED)
                                      for j in jobs))

    def set_thumb(self, vid: str, path: str):
        for c in self.cards.values():
            j = self.win.manager.get(c.job_id)
            if j and _video_id(j.url) == vid:
                c.set_thumb(path)


# ---------------------------------------------------------------- media
class MediaThumb(Thumb):
    """Thumbnail with a play button that fades in on hover."""

    def __init__(self, w=128, h=72):
        super().__init__(w, h, big=True)
        self.play = QPushButton(self)
        self.play.setObjectName("primary")
        self.play.setIcon(icon("play", "#0a1020", 16))
        self.play.setFixedSize(34, 34)
        self.play.setCursor(Qt.PointingHandCursor)
        self.play.setStyleSheet("border-radius:17px; padding:0;")
        self.play.hide()

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self.play.move((self.width() - self.play.width()) // 2,
                       (self.height() - self.play.height()) // 2)

    def enterEvent(self, e):
        super().enterEvent(e)
        self.play.show()
        self.play.raise_()

    def leaveEvent(self, e):
        super().leaveEvent(e)
        self.play.hide()


def _chip_row(labels: list[str]) -> QHBoxLayout:
    chips = QHBoxLayout()
    chips.setSpacing(6)
    for text in labels:
        chip = QLabel(text)
        chip.setStyleSheet(f"background:{theme.TRACK}; color:{theme.MUTED};"
                           f"border-radius:7px; padding:2px 8px; font-size:11px;")
        chips.addWidget(chip)
    chips.addStretch(1)
    return chips


class MediaCard(Card):
    def __init__(self, job, win: "MainWindow"):
        super().__init__()
        self.job_id = job.id
        self.win = win

        self.thumb = MediaThumb(128, 72)
        self.thumb.play.clicked.connect(lambda: win.open_player(self.job_id))
        self.title = ElidedLabel(job.title or job.url)
        self.title.setObjectName("cardTitle")

        kind = "Video" if job.kind == "video" else "Audio"
        chips = _chip_row([b for b in (kind, job.quality, _size_text(job.filepath)) if b])

        self.b_play = HoverIconButton("play", "Play")
        self.b_play.clicked.connect(lambda: win.open_player(self.job_id))
        self.b_open = HoverIconButton("folder", "Show in folder")
        self.b_open.clicked.connect(lambda: win.reveal(self.job_id))
        self.b_del = HoverIconButton("trash", "Delete file")
        self.b_del.clicked.connect(self._ask_delete)
        actions = QHBoxLayout()
        actions.setSpacing(2)
        actions.addWidget(self.b_play)
        actions.addWidget(self.b_open)
        actions.addWidget(self.b_del)

        self.action_row = QWidget()
        ar = QHBoxLayout(self.action_row)
        ar.setContentsMargins(0, 0, 0, 0)
        ar.addLayout(actions)

        self.confirm = QWidget()
        cf = QHBoxLayout(self.confirm)
        cf.setContentsMargins(0, 0, 0, 0)
        cf.setSpacing(6)
        ask = QLabel("Delete file?")
        ask.setStyleSheet(f"color:{theme.MUTED}; font-size:12px;")
        yes = QPushButton("Delete")
        yes.setCursor(Qt.PointingHandCursor)
        yes.setStyleSheet(f"color:{theme.ERROR}; padding:5px 10px;")
        yes.clicked.connect(lambda: win.delete_media(self.job_id))
        no = QPushButton("Cancel")
        no.setObjectName("ghost")
        no.setCursor(Qt.PointingHandCursor)
        no.clicked.connect(self._cancel_delete)
        cf.addWidget(ask)
        cf.addWidget(yes)
        cf.addWidget(no)
        self.confirm.hide()

        right = QVBoxLayout()
        right.setSpacing(4)
        right.addWidget(self.action_row, 0, Qt.AlignRight)
        right.addStretch(1)
        right.addWidget(self.confirm, 0, Qt.AlignRight)

        col = QVBoxLayout()
        col.setSpacing(5)
        col.addStretch(1)
        col.addWidget(self.title)
        col.addLayout(chips)
        col.addStretch(1)
        col2 = QHBoxLayout()
        col2.addLayout(col, 1)
        col2.addLayout(right)

        lay = QHBoxLayout(self)
        lay.setContentsMargins(12, 12, 12, 12)
        lay.setSpacing(14)
        lay.addWidget(self.thumb)
        lay.addLayout(col2, 1)

        vid = _video_id(job.url)
        if vid:
            p = _thumb_path(vid)
            if p.exists():
                self.thumb.load(str(p))
            else:
                win.request_thumb(vid, job.url)

    def _ask_delete(self):
        self.action_row.hide()
        self.confirm.show()
        QTimer.singleShot(5000, self._cancel_delete)

    def _cancel_delete(self):
        self.confirm.hide()
        self.action_row.show()

    def enterEvent(self, e):
        for b in (self.b_play, self.b_open, self.b_del):
            b.brighten(True)
        super().enterEvent(e)

    def leaveEvent(self, e):
        for b in (self.b_play, self.b_open, self.b_del):
            b.brighten(False)
        super().leaveEvent(e)

    def set_thumb(self, path: str):
        self.thumb.load(path)


class MediaTile(Card):
    """Grid-view card: big thumbnail, title and meta underneath."""

    def __init__(self, job, win: "MainWindow"):
        super().__init__()
        self.job_id = job.id
        self.win = win
        self.setFixedHeight(214)

        self.thumb = MediaThumb(232, 130)
        self.thumb.play.clicked.connect(lambda: win.open_player(self.job_id))
        self.title = ElidedLabel(job.title or job.url)
        self.title.setObjectName("cardTitle")
        kind = "Video" if job.kind == "video" else "Audio"
        meta = _label("  ·  ".join([b for b in (kind, job.quality, _size_text(job.filepath)) if b]),
                      "hint")

        lay = QVBoxLayout(self)
        lay.setContentsMargins(12, 12, 12, 12)
        lay.setSpacing(6)
        lay.addWidget(self.thumb, 0, Qt.AlignHCenter)
        lay.addWidget(self.title)
        lay.addWidget(meta)

        vid = _video_id(job.url)
        if vid:
            p = _thumb_path(vid)
            if p.exists():
                self.thumb.load(str(p))
            else:
                win.request_thumb(vid, job.url)

    def enterEvent(self, e):
        super().enterEvent(e)

    def leaveEvent(self, e):
        super().leaveEvent(e)


class MediaPage(GlowPage):
    def __init__(self, win: "MainWindow"):
        super().__init__()
        self.win = win
        self.cards: dict[str, QWidget] = {}
        self.grid_mode = False

        t = _label("Media", "pageTitle")
        self.count = _label("", "muted")
        self.total = _label("", "hint")
        self.search = QLineEdit()
        self.search.setPlaceholderText("Search…")
        self.search.setFixedSize(190, 34)
        self.search.setStyleSheet(
            f"QLineEdit{{background:{theme.CARD};border:1px solid {theme.BORDER};"
            f"border-radius:9px;padding:6px 12px;font-size:12.5px;}}"
            f"QLineEdit:focus{{border-color:{theme.ACCENT_A};}}")
        self.search.textChanged.connect(lambda *_: self.rebuild())
        self.b_view = QPushButton()
        self.b_view.setObjectName("pill")
        self.b_view.setCheckable(True)
        self.b_view.setFixedSize(38, 34)
        self.b_view.setIcon(icon("media", theme.MUTED))
        self.b_view.setToolTip("Toggle grid view")
        self.b_view.setCursor(Qt.PointingHandCursor)
        self.b_view.toggled.connect(self._toggle_view)
        btn_open = HoverIconButton("folder", "Open download folder")
        btn_open.clicked.connect(win.open_output_folder)

        head = QHBoxLayout()
        head.setSpacing(theme.SM)
        head.setContentsMargins(0, 0, 8, 0)
        head.addWidget(t)
        head.addWidget(self.count)
        head.addWidget(self.total)
        head.addStretch(1)
        head.addWidget(self.search)
        head.addWidget(self.b_view)
        head.addWidget(btn_open)

        self.empty = EmptyState("▤", "Nothing here yet",
                                "Finished downloads show up here with a preview.",
                                "Go to Home", lambda: win.go(0))

        self.list_holder = QWidget()
        self.list = QVBoxLayout(self.list_holder)
        self.list.setContentsMargins(0, 0, 8, 12)
        self.list.setSpacing(12)
        self.list.addStretch(1)

        self.grid_holder = QWidget()
        self.grid = QGridLayout(self.grid_holder)
        self.grid.setContentsMargins(0, 0, 8, 12)
        self.grid.setHorizontalSpacing(12)
        self.grid.setVerticalSpacing(12)
        self.grid.setColumnStretch(2, 1)

        self.stack = QStackedWidget()
        self.stack.addWidget(self.list_holder)
        self.stack.addWidget(self.grid_holder)
        self.scroll = SlimScroll()
        self.scroll.setWidget(self.stack)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(theme.LG + 4, theme.MD + 6, theme.LG + 4, theme.SM)
        lay.setSpacing(theme.MD - 4)
        lay.addLayout(head)
        lay.addWidget(self.empty, 1)
        lay.addWidget(self.scroll, 1)

    def _toggle_view(self, on: bool):
        self.grid_mode = on
        self.stack.setCurrentIndex(1 if on else 0)
        self.rebuild()

    def ready(self) -> list:
        """Finished jobs whose file still exists; one entry per file on disk."""
        seen, out = set(), []
        for jid in reversed(self.win.manager.order):
            j = self.win.manager.jobs.get(jid)
            if not j or j.status != DONE or not j.filepath:
                continue
            p = Path(j.filepath)
            if not p.exists():
                continue
            key = str(p.resolve()).lower()
            if key in seen:
                continue
            seen.add(key)
            out.append(j)
        return out

    def _clear(self, layout):
        while layout.count():
            it = layout.takeAt(0)
            if it.widget():
                it.widget().deleteLater()

    def rebuild(self):
        items = self.ready()
        q = self.search.text().strip().lower()
        if q:
            items = [j for j in items if q in (j.title or j.url).lower()]
        for c in self.cards.values():
            c.setParent(None)
        self.cards = {}
        self._clear(self.list)
        self._clear(self.grid)
        self.list.addStretch(1)

        total = 0
        for job in items:
            try:
                total += Path(job.filepath).stat().st_size
            except Exception:
                pass

        if self.grid_mode:
            for i, job in enumerate(items):
                c = MediaTile(job, self.win)
                self.cards[job.id] = c
                self.grid.addWidget(c, i // 3, i % 3)
            rows = (len(items) + 2) // 3
            self.grid.setRowStretch(rows, 1)
        else:
            for job in items:
                c = MediaCard(job, self.win)
                self.cards[job.id] = c
                self.list.insertWidget(self.list.count() - 1, c)

        self.count.setText(f"· {len(items)}" if items else "")
        self.total.setText(f"· {_human(total)} total" if items else "")
        self.empty.setVisible(not items)
        self.scroll.setVisible(bool(items))

    def set_thumb(self, vid: str, path: str):
        for c in self.cards.values():
            j = self.win.manager.get(c.job_id)
            if j and _video_id(j.url) == vid:
                c.set_thumb(path)


# ---------------------------------------------------------------- player
class PlayerPage(QWidget):
    back = Signal()

    def __init__(self):
        super().__init__()
        self.player = QMediaPlayer(self)
        self.audio = QAudioOutput(self)
        self.audio.setVolume(0.85)
        self.player.setAudioOutput(self.audio)
        self.video = QVideoWidget()
        self.player.setVideoOutput(self.video)

        self.title = ElidedLabel()
        self.title.setObjectName("sectionTitle")
        self.back_btn = QPushButton()
        self.back_btn.setObjectName("ghost")
        self.back_btn.setIcon(icon("back", theme.MUTED))
        self.back_btn.setFixedSize(34, 34)
        self.back_btn.setToolTip("Back")
        self.back_btn.setCursor(Qt.PointingHandCursor)
        self.back_btn.clicked.connect(self.back.emit)
        head = QHBoxLayout()
        head.setSpacing(theme.SM)
        head.addWidget(self.back_btn)
        head.addWidget(self.title, 1)

        self.play_btn = QPushButton()
        self.play_btn.setFixedSize(38, 38)
        self.play_btn.setObjectName("ghost")
        self.play_btn.setIcon(icon("pause", theme.TEXT))
        self.play_btn.setCursor(Qt.PointingHandCursor)
        self.play_btn.clicked.connect(self.toggle)
        self.time = _label("0:00 / 0:00", "hint")
        self.slider = SeekSlider(Qt.Horizontal)
        self.slider.setRange(0, 0)
        self.slider.sliderMoved.connect(self.player.setPosition)
        vol = QSlider(Qt.Horizontal)
        vol.setRange(0, 100)
        vol.setValue(85)
        vol.setFixedWidth(90)
        vol.valueChanged.connect(lambda v: self.audio.setVolume(v / 100))
        vol_lbl = _label("Volume", "hint")

        bar = QHBoxLayout()
        bar.setSpacing(theme.SM)
        bar.addWidget(self.play_btn)
        bar.addWidget(self.time)
        bar.addWidget(self.slider, 1)
        bar.addWidget(vol_lbl)
        bar.addWidget(vol)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(theme.LG, theme.MD, theme.LG, theme.MD)
        lay.setSpacing(theme.MD - 4)
        lay.addLayout(head)
        lay.addWidget(self.video, 1)
        lay.addLayout(bar)

        self.player.positionChanged.connect(self._pos)
        self.player.durationChanged.connect(lambda d: self.slider.setRange(0, d))
        self.player.errorOccurred.connect(lambda *_: self.time.setText(self.player.errorString()))
        self.player.mediaStatusChanged.connect(self._status)

    def open(self, path: str, title: str):
        self.title.setText(title or Path(path).name)
        self.player.setSource(QUrl.fromLocalFile(path))
        self.player.play()
        self.play_btn.setIcon(icon("pause", theme.TEXT))

    def toggle(self):
        if self.player.playbackState() == QMediaPlayer.PlayingState:
            self.player.pause()
            self.play_btn.setIcon(icon("play", theme.TEXT))
        else:
            self.player.play()
            self.play_btn.setIcon(icon("pause", theme.TEXT))

    def _pos(self, ms):
        if not self.slider.isSliderDown():
            self.slider.setValue(ms)
        self.time.setText(f"{_hms(ms / 1000)} / {_hms(self.player.duration() / 1000)}")

    def _status(self, st):
        if st == QMediaPlayer.EndOfMedia:
            self.play_btn.setIcon(icon("play", theme.TEXT))

    def stop(self):
        self.player.stop()
        self.player.setSource(QUrl())


# ---------------------------------------------------------------- window
class NavButton(QPushButton):
    """Sidebar item with an accent bar and a count badge."""

    def __init__(self, text: str, icon_name: str):
        super().__init__(f"   {text}")
        self.setObjectName("nav")
        self.setCheckable(True)
        self.setIcon(icon(icon_name, theme.MUTED))
        self.setCursor(Qt.PointingHandCursor)
        self._count = 0
        self.bar = QFrame(self)
        self.bar.setFixedSize(3, 18)
        self.bar.setStyleSheet(f"background:{theme.ACCENT_A}; border-radius:1px;")
        self.bar.hide()
        self.badge = QLabel(self)
        self.badge.setStyleSheet(f"background:{theme.ACCENT_A}; color:#0a1020; border-radius:8px;"
                                 f"padding:1px 6px; font-size:10.5px; font-weight:700;")
        self.badge.hide()
        self.toggled.connect(lambda *_: self._place())

    def _place(self):
        self.bar.setVisible(self.isChecked())
        self.bar.move(5, (self.height() - self.bar.height()) // 2)
        if self._count > 0:
            self.badge.move(self.width() - self.badge.width() - 10,
                            (self.height() - self.badge.height()) // 2)

    def set_count(self, n: int, pop: bool = False):
        grew = n != self._count and n > 0
        self._count = n
        if n <= 0:
            self.badge.hide()
            return
        self.badge.setText(str(n))
        self.badge.adjustSize()
        self._place()
        self.badge.show()
        self.badge.raise_()
        if pop and grew:
            geo = self.badge.geometry()
            a = QPropertyAnimation(self.badge, b"geometry", self)
            a.setDuration(theme.DUR_FAST)
            a.setStartValue(geo.adjusted(-3, -2, 3, 2))
            a.setEndValue(geo)
            a.setEasingCurve(QEasingCurve.OutBack)
            a.start()
            self._pop = a

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self._place()


class MainWindow(QWidget):
    thumb_ready = Signal(str, str)

    def __init__(self):
        super().__init__()
        self.setObjectName("root")
        self.manager = Manager(concurrency=config.load_settings().get("concurrency", 2))
        self.setWindowTitle(f"{config.APP_NAME} {config.VERSION} by {config.AUTHOR}")
        from PySide6.QtWidgets import QApplication
        scr = QApplication.primaryScreen().availableGeometry()
        w = min(1180, max(960, scr.width() - 160))
        h = min(780, max(640, scr.height() - 160))
        self.setMinimumSize(900, 600)
        self.resize(w, h)
        self.move(max(0, scr.x() + (scr.width() - w) // 2),
                  max(0, scr.y() + (scr.height() - h) // 2))
        self.setStyleSheet(theme.qss())
        self._last_page = 2
        self._prev_status: dict[str, str] = {}
        self._badge_n = 0
        self.thumb_ready.connect(self._thumb_arrived)
        self.toaster = Toaster(self)

        side = QWidget()
        side.setObjectName("sidebar")
        side.setFixedWidth(216)
        logo = QLabel()
        mark = config.bundle_dir() / "assets" / "mark.png"
        if mark.exists():
            logo.setPixmap(QPixmap(str(mark)).scaled(28, 28, Qt.KeepAspectRatio,
                                                     Qt.SmoothTransformation))
        glow = QGraphicsDropShadowEffect(logo)
        glow.setBlurRadius(22)
        glow.setOffset(0, 0)
        glow.setColor(QColor(107, 138, 253, 150))
        logo.setGraphicsEffect(glow)
        brand = _label("Nimbus", "brand")
        brand_row = QHBoxLayout()
        brand_row.setSpacing(10)
        brand_row.addWidget(logo)
        brand_row.addWidget(brand)
        brand_row.addStretch(1)

        self.nav_home = NavButton("Home", "home")
        self.nav_home.clicked.connect(lambda: self.go(0))
        self.nav_dl = NavButton("Downloads", "download")
        self.nav_dl.clicked.connect(lambda: self.go(1))
        self.nav_media = NavButton("Media", "media")
        self.nav_media.clicked.connect(lambda: self.go(2))

        self.btn_pause_all = QPushButton("Pause all")
        self.btn_pause_all.setObjectName("ghost")
        self.btn_pause_all.setCursor(Qt.PointingHandCursor)
        self.btn_pause_all.clicked.connect(self.toggle_all)
        self.btn_pause_all.hide()

        divider = QFrame()
        divider.setFixedHeight(1)
        divider.setStyleSheet(f"background:{theme.BORDER};")

        self.btn_update = QPushButton()
        self.btn_update.setObjectName("nav")
        self.btn_update.setIcon(icon("refresh", theme.MUTED))
        self.btn_update.setFixedSize(38, 38)
        self.btn_update.setToolTip("Update yt-dlp")
        self.btn_update.setCursor(Qt.PointingHandCursor)
        self.btn_update.clicked.connect(self.update_ytdlp)
        foot = _label(f"v{config.VERSION} · by {config.AUTHOR}", "hint")

        sl = QVBoxLayout(side)
        sl.setContentsMargins(14, theme.MD + 4, 14, theme.MD)
        sl.setSpacing(4)
        sl.addLayout(brand_row)
        sl.addSpacing(theme.MD + 6)
        sl.addWidget(self.nav_home)
        sl.addWidget(self.nav_dl)
        sl.addWidget(self.nav_media)
        sl.addStretch(1)
        sl.addWidget(self.btn_pause_all)
        sl.addSpacing(6)
        sl.addWidget(divider)
        sl.addSpacing(6)
        sl.addWidget(self.btn_update)
        sl.addSpacing(2)
        sl.addWidget(foot)

        self.pages = QStackedWidget()
        self.pages.setObjectName("content")
        self.page_home = HomePage(self)
        self.page_dl = DownloadsPage(self)
        self.page_media = MediaPage(self)
        self.page_play = PlayerPage()
        self.page_play.back.connect(lambda: self.go(self._last_page))
        for p in (self.page_home, self.page_dl, self.page_media, self.page_play):
            self.pages.addWidget(p)

        self.statusbar = StatusBar()
        self.statusbar.hide()

        right = QVBoxLayout()
        right.setContentsMargins(0, 0, 0, 0)
        right.setSpacing(0)
        right.addWidget(self.pages, 1)
        right.addWidget(self.statusbar)

        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        root.addWidget(side)
        root.addLayout(right, 1)

        self.manager.changed.connect(self._job_changed)
        self.manager.queue_changed.connect(self._queues_changed)
        self.manager.load()
        self._queues_changed()
        self.go(0)

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(1000)

    # ---- navigation
    def go(self, index: int):
        if index != 3:
            self.page_play.stop()
            self._last_page = index
        self.pages.setCurrentIndex(index)
        self.nav_home.setChecked(index == 0)
        self.nav_dl.setChecked(index == 1)
        self.nav_media.setChecked(index == 2)
        if index == 2:
            self.manager.purge_missing()
            self.page_media.rebuild()
        if index < 3:  # a graphics effect over the native video surface breaks playback
            page = self.pages.widget(index)
            eff = page.graphicsEffect()
            if not isinstance(eff, QGraphicsOpacityEffect):
                eff = QGraphicsOpacityEffect(page)
                page.setGraphicsEffect(eff)
            eff.setOpacity(0.0)
            anim = QPropertyAnimation(eff, b"opacity", self)
            anim.setDuration(theme.DUR)
            anim.setStartValue(0.0)
            anim.setEndValue(1.0)
            anim.setEasingCurve(QEasingCurve.OutCubic)
            anim.finished.connect(lambda: eff.setOpacity(1.0))
            anim.start()
            QTimer.singleShot(260, lambda: eff.setOpacity(1.0))
            lay = page.layout()
            if lay is not None:
                base = lay.contentsMargins()
                slide = QVariantAnimation(self)
                slide.setDuration(theme.DUR)
                slide.setStartValue(10.0)
                slide.setEndValue(0.0)
                slide.setEasingCurve(QEasingCurve.OutCubic)
                slide.valueChanged.connect(
                    lambda v: lay.setContentsMargins(base.left(), base.top() + int(v),
                                                     base.right(), base.bottom()))
                slide.start()
                page._slide = slide

    def resizeEvent(self, e):
        super().resizeEvent(e)
        if hasattr(self, "toaster"):
            self.toaster.reposition()

    def toast(self, text: str, kind: str = "info"):
        self.toaster.show(text, kind)

    def flash(self, text: str):
        self.toast(text, "info")

    def clipboard_text(self) -> str:
        from PySide6.QtWidgets import QApplication
        return QApplication.clipboard().text().strip()

    # ---- queue plumbing
    def _queues_changed(self):
        self.page_dl.rebuild()
        self.page_media.rebuild()
        self._sync_badge()

    def _sync_badge(self):
        active = sum(1 for j in self.manager.jobs.values()
                     if j.status in (PENDING, RUNNING, PROCESSING))
        self.nav_dl.set_count(active, pop=active > self._badge_n)
        self._badge_n = active
        self.btn_pause_all.setVisible(active > 0)
        running = any(j.status == RUNNING for j in self.manager.jobs.values())
        self.btn_pause_all.setText("Pause all" if running else "Resume all")

    def _job_changed(self, job_id: str):
        job = self.manager.get(job_id)
        if not job:
            return
        prev = self._prev_status.get(job_id)
        self._prev_status[job_id] = job.status
        if prev != job.status:
            title = job.title or "Download"
            short = title if len(title) <= 42 else title[:41] + "…"
            if job.status == PENDING and prev is None:
                self.toast(f"Download started · {short}", "info")
            elif job.status == DONE:
                self.toast(f"Download complete · {short}", "success")
            elif job.status == ERROR:
                self.toast(f"Failed · {_friendly_error(job.error)}", "error")
        card = self.page_dl.cards.get(job_id)
        if card:
            card.refresh(job)
        if job.status in (DONE, ERROR, CANCELED):
            self._queues_changed()
        self._sync_badge()

    def clear_finished(self):
        n = self.manager.hide_finished()
        if n:
            self.toast(f"Cleared {n} finished item{'s' if n != 1 else ''}", "info")
        self._queues_changed()

    def hide_job(self, job_id: str):
        self.manager.hide(job_id)
        self._queues_changed()

    def retry(self, job_id: str):
        self.manager.resume(job_id)
        self._queues_changed()

    def toggle_all(self):
        running = any(j.status == RUNNING for j in self.manager.jobs.values())
        for j in list(self.manager.jobs.values()):
            if running and j.status in (RUNNING, PENDING):
                self.manager.pause(j.id)
            elif not running and j.status in (PAUSED, PENDING):
                self.manager.resume(j.id)

    def request_thumb(self, vid: str, url: str):
        def work():
            fetcher = PreviewFetcher()
            fetcher.done.connect(lambda m: self.thumb_ready.emit(vid, m.get("thumb", "")))
            fetcher.fetch(url)
        threading.Thread(target=work, daemon=True).start()

    def _thumb_arrived(self, vid: str, path: str):
        if not path:
            return
        self.page_media.set_thumb(vid, path)
        self.page_dl.set_thumb(vid, path)

    # ---- actions
    def toggle(self, job_id: str):
        job = self.manager.get(job_id)
        if not job:
            return
        if job.status in (RUNNING, PENDING):
            self.manager.pause(job_id)
        else:
            self.manager.resume(job_id)

    def open_player(self, job_id: str):
        job = self.manager.get(job_id)
        if job and job.filepath and Path(job.filepath).exists():
            self.page_play.open(job.filepath, job.title)
            self.pages.setCurrentIndex(3)
            self.nav_home.setChecked(False)
            self.nav_dl.setChecked(False)
            self.nav_media.setChecked(False)
        else:
            self.toast("File not found — it may have been moved or deleted", "warning")
            self.page_media.rebuild()

    def reveal(self, job_id: str):
        job = self.manager.get(job_id)
        if not job:
            return
        target = Path(job.filepath) if job.filepath else Path(job.outdir)
        if target.is_file():
            subprocess.Popen(["explorer", "/select,", str(target)])
        else:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(target)))

    def delete_media(self, job_id: str):
        job = self.manager.get(job_id)
        if not job:
            return
        name = Path(job.filepath).name if job.filepath else (job.title or "this item")
        ok, msg = self.manager.delete_media(job_id)
        if ok:
            self.toast(f"Deleted · {name[:38]}", "info")
        else:
            self.toast(msg, "error")
        self._queues_changed()

    def open_output_folder(self):
        key = "video_dir" if self.page_home.kind() == "video" else "audio_dir"
        QDesktopServices.openUrl(QUrl.fromLocalFile(self.page_home.settings.get(key, "")))

    def update_ytdlp(self):
        self.toast("Updating yt-dlp…", "info")
        self.btn_update.setEnabled(False)

        def work():
            ok, msg = update.update_ytdlp()
            QTimer.singleShot(0, lambda: self._update_done(ok, msg))
        threading.Thread(target=work, daemon=True).start()

    def _update_done(self, ok: bool, msg: str):
        self.btn_update.setEnabled(True)
        self.toast(msg, "success" if ok else "error")
        if not ok:
            QMessageBox.warning(self, "Update", msg)

    def _tick(self):
        running = [j for j in self.manager.jobs.values() if j.status in (RUNNING, PROCESSING)]
        if running:
            speed = _human(sum(j.speed for j in running))
            self.statusbar.set_active(f"{len(running)} downloading · {speed}/s")
            self.page_dl.set_live(f"● {speed}/s")
            self.toaster.set_bottom_offset(38)
        else:
            self.statusbar.set_active("")
            self.page_dl.set_live("")
            self.toaster.set_bottom_offset(8)

    def keyPressEvent(self, e):
        if self.pages.currentIndex() == 3 and e.key() == Qt.Key_Escape:
            self.go(self._last_page)
        elif self.pages.currentIndex() == 3 and e.key() == Qt.Key_Space:
            self.page_play.toggle()
        else:
            super().keyPressEvent(e)


def _human(bps: float) -> str:
    if not bps:
        return "0 B"
    for unit in ("B", "KB", "MB", "GB"):
        if bps < 1024:
            return f"{bps:.0f} {unit}"
        bps /= 1024
    return f"{bps:.1f} TB"


def _hms(sec) -> str:
    sec = int(sec or 0)
    h, m, s = sec // 3600, (sec % 3600) // 60, sec % 60
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"
