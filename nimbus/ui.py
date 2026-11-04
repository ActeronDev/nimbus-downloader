"""Main window — sidebar navigation, Home / Downloads / Media / Player. by ActeronDev"""
from __future__ import annotations

import json
import re
import subprocess
import threading
import urllib.request
from pathlib import Path

from PySide6.QtCore import Qt, QTimer, QUrl, Signal, QObject
from PySide6.QtGui import QDesktopServices, QPixmap
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer
from PySide6.QtMultimediaWidgets import QVideoWidget
from PySide6.QtWidgets import (QButtonGroup, QFileDialog, QFrame, QGridLayout,
                               QHBoxLayout, QLabel, QLineEdit, QMessageBox,
                               QProgressBar, QPushButton, QScrollArea, QSlider,
                               QStackedWidget, QStyle, QVBoxLayout, QWidget)

import yt_dlp

from . import config, update
from .icons import icon
from .downloader import (AUDIO_QUALITIES, CANCELED, DONE, ERROR, PAUSED,
                         PENDING, RUNNING, VIDEO_QUALITIES, Manager,
                         _js_runtimes)

ACCENT = "#6b8afd"
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

QSS = f"""
* {{ font-family:'Segoe UI'; font-size:13px; color:#e7eaf0; }}
QWidget#root, QWidget#content {{ background:#0a0c10; }}
QWidget#sidebar {{ background:#0d1014; border-right:1px solid #171c24; }}
QStackedWidget > QWidget {{ background:#0a0c10; }}
QScrollArea, QScrollArea > QWidget > QWidget {{ background:transparent; border:none; }}
QLabel {{ background:transparent; }}
QLabel#brand {{ font-size:18px; font-weight:800; letter-spacing:0.4px; }}
QLabel#muted {{ color:#8b93a1; }}
QLabel#hint {{ color:#6f7787; font-size:12px; }}
QLabel#pageTitle {{ font-size:22px; font-weight:700; }}
QLabel#cardTitle {{ font-size:14px; font-weight:600; }}
QLabel#emptyState {{ color:#5b6472; font-size:14px; }}
QLineEdit {{ background:#14171d; border:1px solid #242a34; border-radius:10px; padding:12px 14px; font-size:14px; }}
QLineEdit:focus {{ border-color:{ACCENT}; }}
QPushButton {{ background:#171b22; border:1px solid #262c37; border-radius:10px; padding:10px 16px; }}
QPushButton:hover {{ background:#1e232c; border-color:#323a47; }}
QPushButton#primary {{ background:{ACCENT}; border:none; color:#0a1020; font-weight:700; padding:12px 26px; font-size:14px; }}
QPushButton#primary:hover {{ background:#7f9aff; }}
QPushButton#nav {{ background:transparent; border:none; border-radius:10px; padding:11px 14px; color:#98a0af; text-align:left; font-size:13.5px; }}
QPushButton#nav:hover {{ background:#151a21; color:#e7eaf0; }}
QPushButton#nav:checked {{ background:#1a2130; color:#ffffff; font-weight:600; }}
QPushButton#seg {{ background:#14171d; border:1px solid #242a34; border-radius:10px; padding:10px 24px; color:#9aa3b2; }}
QPushButton#seg:checked {{ background:#1d2635; border-color:{ACCENT}; color:#ffffff; font-weight:600; }}
QPushButton#chip {{ background:#12151b; border:1px solid #232a34; border-radius:9px; padding:10px 14px; color:#9aa3b2; }}
QPushButton#chip:hover {{ border-color:#39424f; color:#e7eaf0; }}
QPushButton#chip:checked {{ background:#1b2740; border-color:{ACCENT}; color:#ffffff; font-weight:600; }}
QPushButton#ghost {{ background:transparent; border:none; color:#8b93a1; padding:7px 11px; }}
QPushButton#ghost:hover {{ color:#e7eaf0; background:#151a21; border-radius:8px; }}
QPushButton#danger {{ background:transparent; border:none; color:#9b6b6b; padding:7px 11px; }}
QPushButton#danger:hover {{ color:#ff8080; background:#241618; border-radius:8px; }}
QFrame#card {{ background:#11141a; border:1px solid #1c222b; border-radius:14px; }}
QFrame#card:hover {{ border-color:#2b3340; }}
QFrame#panel {{ background:#0f1217; border:1px solid #1b212a; border-radius:16px; }}
QFrame#thumb {{ background:#0b0e12; border:1px solid #1c222b; border-radius:10px; }}
QProgressBar {{ background:#181d25; border:none; border-radius:5px; height:8px; }}
QProgressBar::chunk {{ background:{ACCENT}; border-radius:5px; }}
QScrollBar:vertical {{ background:transparent; width:10px; margin:2px; }}
QScrollBar::handle:vertical {{ background:#262c37; border-radius:5px; min-height:30px; }}
QScrollBar::handle:vertical:hover {{ background:#323a47; }}
QScrollBar::add-line, QScrollBar::sub-line {{ height:0; }}
QSlider::groove:horizontal {{ height:5px; background:#232a35; border-radius:2px; }}
QSlider::sub-page:horizontal {{ background:{ACCENT}; border-radius:2px; }}
QSlider::handle:horizontal {{ background:#e7eaf0; width:13px; margin:-4px 0; border-radius:6px; }}
QMenu {{ background:#14171d; border:1px solid #242a34; padding:6px; }}
QMenu::item {{ padding:7px 22px; border-radius:7px; }}
QMenu::item:selected {{ background:#1d2635; }}
"""


# ---------------------------------------------------------------- helpers
def _video_id(url: str) -> str:
    m = re.search(r"(?:v=|youtu\.be/|shorts/|embed/)([A-Za-z0-9_-]{11})", url)
    return m.group(1) if m else ""


def _thumb_path(vid: str) -> Path:
    return THUMBS / f"{vid}.jpg"


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
    def __init__(self, w=160, h=90):
        super().__init__()
        self.setFixedSize(w, h)
        self.setObjectName("thumb")
        self.setAlignment(Qt.AlignCenter)
        self.setStyleSheet("background:#0b0e12;border:1px solid #1c222b;border-radius:10px;color:#4b5563;")
        self.setText("▶")

    def load(self, path: str):
        if path and Path(path).exists():
            pm = QPixmap(path).scaled(self.width(), self.height(),
                                      Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
            self.setPixmap(pm.copy(0, 0, self.width(), self.height()))
            self.setText("")


class QualityPicker(QWidget):
    """Visible quality chips — no dropdown."""

    changed = Signal(str)

    def __init__(self):
        super().__init__()
        self.grid = QGridLayout(self)
        self.grid.setContentsMargins(0, 0, 0, 0)
        self.grid.setHorizontalSpacing(8)
        self.grid.setVerticalSpacing(8)
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


# ---------------------------------------------------------------- home
class HomePage(QWidget):
    def __init__(self, win: "MainWindow"):
        super().__init__()
        self.win = win
        self.settings = config.load_settings()
        self.meta: dict = {}
        self.fetcher = PreviewFetcher(self)
        self.fetcher.done.connect(self._preview_ready)
        self.fetcher.failed.connect(self._preview_failed)

        title = QLabel("Home"); title.setObjectName("pageTitle")
        sub = QLabel("Paste a YouTube link, pick what you want, hit Download.")
        sub.setObjectName("muted")

        self.url = QLineEdit()
        self.url.setPlaceholderText("https://www.youtube.com/watch?v=…")
        self.url.returnPressed.connect(self.start)
        self.url.textChanged.connect(self._queue_preview)
        btn_paste = QPushButton()
        btn_paste.setIcon(icon("paste"))
        btn_paste.setFixedSize(46, 46)
        btn_paste.setToolTip("Paste link from clipboard")
        btn_paste.setCursor(Qt.PointingHandCursor)
        btn_paste.clicked.connect(self.paste)
        row = QHBoxLayout(); row.setSpacing(8); row.addWidget(self.url, 1); row.addWidget(btn_paste)

        self.preview = QFrame(); self.preview.setObjectName("card"); self.preview.setVisible(False)
        self.p_thumb = Thumb(160, 90)
        self.p_title = QLabel(); self.p_title.setObjectName("cardTitle"); self.p_title.setWordWrap(True)
        self.p_meta = QLabel(); self.p_meta.setObjectName("hint")
        pv = QHBoxLayout(self.preview); pv.setContentsMargins(12, 12, 14, 12); pv.setSpacing(14)
        pv.addWidget(self.p_thumb)
        col = QVBoxLayout(); col.setSpacing(4); col.addStretch(1)
        col.addWidget(self.p_title); col.addWidget(self.p_meta); col.addStretch(1)
        pv.addLayout(col, 1)

        self.bg = QButtonGroup(self); self.bg.setExclusive(True)
        self.b_video = QPushButton("Video"); self.b_video.setCheckable(True); self.b_video.setObjectName("seg")
        self.b_audio = QPushButton("Audio"); self.b_audio.setCheckable(True); self.b_audio.setObjectName("seg")
        for b in (self.b_video, self.b_audio):
            self.bg.addButton(b)
        self.b_video.setChecked(True)
        self.bg.buttonClicked.connect(lambda *_: self._fill_qualities())
        seg = QHBoxLayout(); seg.setSpacing(8); seg.addWidget(self.b_video); seg.addWidget(self.b_audio); seg.addStretch(1)

        self.quality = QualityPicker()
        self.folder_lbl = QLabel(); self.folder_lbl.setObjectName("hint")
        btn_folder = QPushButton(); btn_folder.setObjectName("ghost")
        btn_folder.setIcon(icon("folder"))
        btn_folder.setFixedSize(36, 36)
        btn_folder.setToolTip("Change download folder")
        btn_folder.setCursor(Qt.PointingHandCursor)
        btn_folder.clicked.connect(self.pick_folder)
        frow = QHBoxLayout(); frow.setSpacing(6); frow.addWidget(self.folder_lbl, 1); frow.addWidget(btn_folder)

        self.btn = QPushButton(); self.btn.setObjectName("primary")
        self.btn.setIcon(icon("download", "#0a1020", 22))
        self.btn.setFixedSize(84, 46)
        self.btn.setToolTip("Download")
        self.btn.setCursor(Qt.PointingHandCursor)
        self.btn.clicked.connect(self.start)
        brow = QHBoxLayout(); brow.addStretch(1); brow.addWidget(self.btn)

        hint = QLabel("Streams are copied, never re-encoded — full quality preserved.")
        hint.setObjectName("hint")

        lay = QVBoxLayout(self)
        lay.setContentsMargins(28, 22, 28, 24)
        lay.setSpacing(14)
        lay.addWidget(title); lay.addWidget(sub); lay.addSpacing(4)
        lay.addLayout(row)
        lay.addWidget(self.preview)
        lay.addLayout(seg)
        lay.addWidget(self.quality)
        lay.addLayout(frow)
        lay.addLayout(brow)
        lay.addWidget(hint)
        lay.addStretch(1)

        self._fill_qualities()
        self._timer = QTimer(self); self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._fetch_preview)

    def _queue_preview(self):
        self._timer.start(700)

    def _fetch_preview(self):
        url = self.url.text().strip()
        if not url.startswith(("http://", "https://")):
            self.preview.setVisible(False)
            return
        self.p_title.setText("Loading preview…")
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
        self.p_thumb.load(meta.get("thumb", ""))
        self.preview.setVisible(True)

    def _preview_failed(self, msg: str):
        self.meta = {}
        self.p_title.setText("Preview unavailable")
        self.p_meta.setText(msg)
        self.preview.setVisible(True)

    def paste(self):
        cb = self.win.clipboard_text()
        if cb:
            self.url.setText(cb.strip())
            self._fetch_preview()

    def _fill_qualities(self):
        self.quality.set_options(VIDEO_QUALITIES if self.b_video.isChecked() else AUDIO_QUALITIES)
        if hasattr(self, "folder_lbl"):
            self._sync_folder()

    def kind(self) -> str:
        return "video" if self.b_video.isChecked() else "audio"

    def _sync_folder(self):
        key = "video_dir" if self.kind() == "video" else "audio_dir"
        self.folder_lbl.setText("Saving to  " + self.settings.get(key, ""))

    def pick_folder(self):
        key = "video_dir" if self.kind() == "video" else "audio_dir"
        d = QFileDialog.getExistingDirectory(self, "Choose download folder", self.settings[key])
        if d:
            self.settings[key] = d
            config.save_settings(self.settings)
            self._sync_folder()

    def start(self):
        url = self.url.text().strip()
        if not url:
            return
        if not url.startswith(("http://", "https://")):
            url = "https://" + url
        self.win.manager.add(url, self.kind(), self.quality.value())
        self.win.flash("Added to Downloads")
        self.win.go(1)


# ---------------------------------------------------------------- downloads
class Card(QFrame):
    def __init__(self, job, win: "MainWindow"):
        super().__init__()
        self.job_id = job.id
        self.win = win
        self.setObjectName("card")

        self.title = QLabel(); self.title.setObjectName("cardTitle")
        self.meta = QLabel(); self.meta.setObjectName("hint")
        self.bar = QProgressBar(); self.bar.setRange(0, 1000); self.bar.setTextVisible(False)
        self.bar.setFixedHeight(8)
        self.pct = QLabel(); self.pct.setObjectName("muted"); self.pct.setFixedWidth(48)
        self.pct.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.stats = QLabel(); self.stats.setObjectName("hint")

        self.b_toggle = QPushButton(); self.b_toggle.setObjectName("ghost")
        self.b_toggle.setIcon(icon("pause")); self.b_toggle.setFixedSize(34, 34)
        self.b_toggle.setToolTip("Pause")
        self.b_toggle.clicked.connect(lambda: win.toggle(self.job_id))
        self.b_cancel = QPushButton(); self.b_cancel.setObjectName("ghost")
        self.b_cancel.setIcon(icon("close")); self.b_cancel.setFixedSize(34, 34)
        self.b_cancel.setToolTip("Cancel download")
        self.b_cancel.clicked.connect(lambda: win.manager.cancel(self.job_id))

        top = QHBoxLayout(); top.setSpacing(10)
        top.addWidget(self.title, 1); top.addWidget(self.pct)
        bar = QHBoxLayout(); bar.setSpacing(10)
        bar.addWidget(self.bar, 1); bar.addWidget(self.stats)
        bottom = QHBoxLayout(); bottom.setSpacing(2)
        bottom.addWidget(self.meta, 1); bottom.addWidget(self.b_toggle); bottom.addWidget(self.b_cancel)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(16, 13, 12, 11)
        lay.setSpacing(8)
        lay.addLayout(top); lay.addLayout(bar); lay.addLayout(bottom)
        self.refresh(job)

    def refresh(self, job):
        self.title.setText(job.title or job.url)
        kind = "Video" if job.kind == "video" else "Audio"
        self.meta.setText(f"{kind} · {job.quality} · {job.status}" + (f" · {job.error}" if job.error else ""))
        self.bar.setValue(int(job.pct * 10))
        self.pct.setText(f"{job.pct:.0f}%" if job.pct else "")
        bits = []
        if job.speed:
            bits.append(_human(job.speed) + "/s")
        if job.eta:
            bits.append(_hms(job.eta) + " left")
        self.stats.setText("  ·  ".join(bits))
        running = job.status in (RUNNING, PENDING)
        self.b_toggle.setIcon(icon("pause" if running else "play"))
        self.b_toggle.setToolTip("Pause" if running else "Resume")
        self.b_toggle.setVisible(job.status != DONE)


class DownloadsPage(QWidget):
    def __init__(self, win: "MainWindow"):
        super().__init__()
        self.win = win
        self.cards: dict[str, Card] = {}

        t = QLabel("Downloads"); t.setObjectName("pageTitle")
        self.count = QLabel(); self.count.setObjectName("muted")
        head = QHBoxLayout(); head.addWidget(t); head.addWidget(self.count); head.addStretch(1)

        self.empty = QLabel("↓\n\nNo active downloads\nPaste a link on the Home tab to start one")
        self.empty.setObjectName("emptyState"); self.empty.setAlignment(Qt.AlignCenter)

        self.holder = QWidget()
        self.list = QVBoxLayout(self.holder)
        self.list.setContentsMargins(0, 0, 6, 0); self.list.setSpacing(10); self.list.addStretch(1)
        scroll = QScrollArea(); scroll.setWidgetResizable(True); scroll.setWidget(self.holder)
        scroll.viewport().setStyleSheet("background:transparent;")

        lay = QVBoxLayout(self)
        lay.setContentsMargins(28, 22, 28, 22); lay.setSpacing(12)
        lay.addLayout(head); lay.addWidget(self.empty); lay.addWidget(scroll, 1)

    def rebuild(self):
        active = [jid for jid in self.win.manager.order
                  if (j := self.win.manager.jobs.get(jid)) and j.status != DONE]
        for c in self.cards.values():
            c.setParent(None)
        self.cards.clear()
        while self.list.count() > 1:
            it = self.list.takeAt(0)
            if it.widget():
                it.widget().deleteLater()
        for jid in active:
            c = Card(self.win.manager.jobs[jid], self.win)
            self.cards[jid] = c
            self.list.insertWidget(self.list.count() - 1, c)
        self.count.setText(f"· {len(active)}" if active else "")
        self.empty.setVisible(not active)


# ---------------------------------------------------------------- media
class MediaCard(QFrame):
    def __init__(self, job, win: "MainWindow"):
        super().__init__()
        self.job_id = job.id
        self.win = win
        self.setObjectName("card")

        self.thumb = Thumb(128, 72)
        self.title = QLabel(job.title or job.url); self.title.setObjectName("cardTitle"); self.title.setWordWrap(True)
        kind = "Video" if job.kind == "video" else "Audio"
        size = ""
        try:
            if job.filepath and Path(job.filepath).exists():
                mb = Path(job.filepath).stat().st_size / 1048576
                size = f"{mb:.0f} MB" if mb >= 1 else f"{mb*1024:.0f} KB"
        except Exception:
            pass
        meta = "  ·  ".join([b for b in (kind, job.quality, size) if b])
        self.meta = QLabel(meta); self.meta.setObjectName("hint")

        b_play = QPushButton(); b_play.setObjectName("ghost")
        b_play.setIcon(icon("play")); b_play.setFixedSize(34, 34); b_play.setToolTip("Play")
        b_play.setCursor(Qt.PointingHandCursor)
        b_play.clicked.connect(lambda: win.open_player(self.job_id))
        b_open = QPushButton(); b_open.setObjectName("ghost")
        b_open.setIcon(icon("folder")); b_open.setFixedSize(34, 34); b_open.setToolTip("Show in folder")
        b_open.setCursor(Qt.PointingHandCursor)
        b_open.clicked.connect(lambda: win.reveal(self.job_id))
        b_del = QPushButton(); b_del.setObjectName("danger")
        b_del.setIcon(icon("trash", "#a87878")); b_del.setFixedSize(34, 34)
        b_del.setToolTip("Delete file")
        b_del.setCursor(Qt.PointingHandCursor)
        b_del.clicked.connect(lambda: win.delete_media(self.job_id))
        btns = QHBoxLayout(); btns.setSpacing(2)
        btns.addWidget(b_play); btns.addWidget(b_open); btns.addWidget(b_del)

        col = QVBoxLayout(); col.setSpacing(4); col.addStretch(1)
        col.addWidget(self.title); col.addWidget(self.meta); col.addStretch(1)
        col2 = QHBoxLayout(); col2.addLayout(col, 1); col2.addLayout(btns)

        lay = QHBoxLayout(self)
        lay.setContentsMargins(12, 12, 12, 12); lay.setSpacing(14)
        lay.addWidget(self.thumb); lay.addLayout(col2, 1)

        vid = _video_id(job.url)
        if vid:
            p = _thumb_path(vid)
            if p.exists():
                self.thumb.load(str(p))
            else:
                win.request_thumb(vid, job.url, self)

    def set_thumb(self, path: str):
        self.thumb.load(path)


class MediaPage(QWidget):
    def __init__(self, win: "MainWindow"):
        super().__init__()
        self.win = win
        self.cards: dict[str, MediaCard] = {}

        t = QLabel("Media"); t.setObjectName("pageTitle")
        self.count = QLabel(); self.count.setObjectName("muted")
        btn_open = QPushButton(); btn_open.setObjectName("ghost")
        btn_open.setIcon(icon("folder")); btn_open.setFixedSize(34, 34)
        btn_open.setToolTip("Open download folder")
        btn_open.setCursor(Qt.PointingHandCursor)
        btn_open.clicked.connect(win.open_output_folder)
        head = QHBoxLayout(); head.addWidget(t); head.addWidget(self.count); head.addStretch(1); head.addWidget(btn_open)

        self.empty = QLabel("▤\n\nNo media yet\nFinished downloads appear here with a preview")
        self.empty.setObjectName("emptyState"); self.empty.setAlignment(Qt.AlignCenter)

        self.holder = QWidget()
        self.list = QVBoxLayout(self.holder)
        self.list.setContentsMargins(0, 0, 6, 0); self.list.setSpacing(10); self.list.addStretch(1)
        scroll = QScrollArea(); scroll.setWidgetResizable(True); scroll.setWidget(self.holder)
        scroll.viewport().setStyleSheet("background:transparent;")

        lay = QVBoxLayout(self)
        lay.setContentsMargins(28, 22, 28, 22); lay.setSpacing(12)
        lay.addLayout(head); lay.addWidget(self.empty); lay.addWidget(scroll, 1)

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

    def rebuild(self):
        items = self.ready()
        for c in self.cards.values():
            c.setParent(None)
        self.cards = {}
        while self.list.count() > 1:
            it = self.list.takeAt(0)
            if it.widget():
                it.widget().deleteLater()
        for job in items:
            c = MediaCard(job, self.win)
            self.cards[job.id] = c
            self.list.insertWidget(self.list.count() - 1, c)
        self.count.setText(f"· {len(items)}" if items else "")
        self.empty.setVisible(not items)

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

        self.title = QLabel(); self.title.setStyleSheet("font-size:15px; font-weight:600;")
        self.back_btn = QPushButton(); self.back_btn.setObjectName("ghost")
        self.back_btn.setIcon(icon("back")); self.back_btn.setFixedSize(34, 34)
        self.back_btn.setToolTip("Back")
        self.back_btn.clicked.connect(self.back.emit)
        head = QHBoxLayout(); head.addWidget(self.back_btn); head.addWidget(self.title, 1)

        self.play_btn = QPushButton(); self.play_btn.setFixedWidth(38); self.play_btn.setObjectName("ghost")
        self.play_btn.setIcon(icon("pause"))
        self.play_btn.clicked.connect(self.toggle)
        self.time = QLabel("0:00 / 0:00"); self.time.setObjectName("hint")
        self.slider = SeekSlider(Qt.Horizontal); self.slider.setRange(0, 0)
        self.slider.sliderMoved.connect(self.player.setPosition)
        vol = QSlider(Qt.Horizontal); vol.setRange(0, 100); vol.setValue(85); vol.setFixedWidth(90)
        vol.valueChanged.connect(lambda v: self.audio.setVolume(v / 100))

        bar = QHBoxLayout(); bar.setSpacing(10)
        bar.addWidget(self.play_btn); bar.addWidget(self.time); bar.addWidget(self.slider, 1)
        bar.addWidget(QLabel("Volume")); bar.addWidget(vol)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(24, 16, 24, 18); lay.setSpacing(12)
        lay.addLayout(head); lay.addWidget(self.video, 1); lay.addLayout(bar)

        self.player.positionChanged.connect(self._pos)
        self.player.durationChanged.connect(lambda d: self.slider.setRange(0, d))
        self.player.errorOccurred.connect(lambda *_: self.time.setText(self.player.errorString()))
        self.player.mediaStatusChanged.connect(self._status)

    def open(self, path: str, title: str):
        self.title.setText(title or Path(path).name)
        self.player.setSource(QUrl.fromLocalFile(path))
        self.player.play()
        self.play_btn.setIcon(icon("pause"))

    def toggle(self):
        if self.player.playbackState() == QMediaPlayer.PlayingState:
            self.player.pause(); self.play_btn.setIcon(icon("play"))
        else:
            self.player.play(); self.play_btn.setIcon(icon("pause"))

    def _pos(self, ms):
        if not self.slider.isSliderDown():
            self.slider.setValue(ms)
        self.time.setText(f"{_hms(ms / 1000)} / {_hms(self.player.duration() / 1000)}")

    def _status(self, st):
        if st == QMediaPlayer.EndOfMedia:
            self.play_btn.setIcon(icon("play"))

    def stop(self):
        self.player.stop(); self.player.setSource(QUrl())


# ---------------------------------------------------------------- window
class MainWindow(QWidget):
    thumb_ready = Signal(str, str)

    def __init__(self):
        super().__init__()
        self.setObjectName("root")
        self.manager = Manager(concurrency=config.load_settings().get("concurrency", 2))
        self.setWindowTitle(f"{config.APP_NAME} {config.VERSION} by {config.AUTHOR}")
        from PySide6.QtWidgets import QApplication
        scr = QApplication.primaryScreen().availableGeometry()
        w = min(1120, max(880, scr.width() - 140))
        h = min(740, max(580, scr.height() - 140))
        self.setMinimumSize(860, 540)
        self.resize(w, h)
        self.move(max(0, scr.x() + (scr.width() - w) // 2), max(0, scr.y() + (scr.height() - h) // 2))
        self.setStyleSheet(QSS)
        self._last_page = 2
        self.thumb_ready.connect(self._thumb_arrived)

        side = QWidget(); side.setObjectName("sidebar"); side.setFixedWidth(210)
        logo = QLabel()
        mark = config.bundle_dir() / "assets" / "mark.png"
        if mark.exists():
            logo.setPixmap(QPixmap(str(mark)).scaled(30, 30, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        brand = QLabel("Nimbus"); brand.setObjectName("brand")
        brand_row = QHBoxLayout(); brand_row.setSpacing(10)
        brand_row.addWidget(logo); brand_row.addWidget(brand); brand_row.addStretch(1)
        self.nav_home = self._nav("Home", 0, "home")
        self.nav_dl = self._nav("Downloads", 1, "download")
        self.nav_media = self._nav("Media", 2, "media")
        self.btn_update = QPushButton(); self.btn_update.setObjectName("nav")
        self.btn_update.setIcon(icon("refresh")); self.btn_update.setFixedSize(38, 38)
        self.btn_update.setToolTip("Update yt-dlp")
        self.btn_update.clicked.connect(self.update_ytdlp)
        foot = QLabel(f"v{config.VERSION} · by {config.AUTHOR}"); foot.setObjectName("hint")

        sl = QVBoxLayout(side)
        sl.setContentsMargins(14, 20, 14, 16); sl.setSpacing(4)
        sl.addLayout(brand_row); sl.addSpacing(18)
        sl.addWidget(self.nav_home); sl.addWidget(self.nav_dl); sl.addWidget(self.nav_media)
        sl.addStretch(1)
        sl.addWidget(self.btn_update); sl.addSpacing(6); sl.addWidget(foot)

        self.pages = QStackedWidget(); self.pages.setObjectName("content")
        self.page_home = HomePage(self)
        self.page_dl = DownloadsPage(self)
        self.page_media = MediaPage(self)
        self.page_play = PlayerPage()
        self.page_play.back.connect(lambda: self.go(self._last_page))
        for p in (self.page_home, self.page_dl, self.page_media, self.page_play):
            self.pages.addWidget(p)

        self.status = QLabel(); self.status.setObjectName("muted")

        right = QVBoxLayout(); right.setContentsMargins(0, 0, 0, 0); right.setSpacing(0)
        right.addWidget(self.pages, 1)
        srow = QHBoxLayout(); srow.setContentsMargins(28, 6, 28, 10); srow.addWidget(self.status, 1)
        right.addLayout(srow)

        root = QHBoxLayout(self); root.setContentsMargins(0, 0, 0, 0); root.setSpacing(0)
        root.addWidget(side); root.addLayout(right, 1)

        self.manager.changed.connect(self._job_changed)
        self.manager.queue_changed.connect(self._queues_changed)
        self.manager.load()
        self._queues_changed()
        self.go(0)

        self._timer = QTimer(self); self._timer.timeout.connect(self._tick); self._timer.start(1000)

    def _nav(self, text: str, index: int, icon_name: str) -> QPushButton:
        b = QPushButton(f"  {text}"); b.setObjectName("nav"); b.setCheckable(True)
        b.setIcon(icon(icon_name)); b.setCursor(Qt.PointingHandCursor)
        b.clicked.connect(lambda: self.go(index))
        return b

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

    def flash(self, text: str):
        self.status.setText(text)
        QTimer.singleShot(2500, lambda: self.status.setText(""))

    def clipboard_text(self) -> str:
        from PySide6.QtWidgets import QApplication
        return QApplication.clipboard().text().strip()

    def _queues_changed(self):
        self.page_dl.rebuild()
        self.page_media.rebuild()

    def _job_changed(self, job_id: str):
        job = self.manager.get(job_id)
        if not job:
            return
        card = self.page_dl.cards.get(job_id)
        if card:
            card.refresh(job)
            if job.status == DONE:
                self._queues_changed()

    def request_thumb(self, vid: str, url: str, card):
        def work():
            fetcher = PreviewFetcher()
            fetcher.done.connect(lambda m: self.thumb_ready.emit(vid, m.get("thumb", "")))
            fetcher.fetch(url)
        threading.Thread(target=work, daemon=True).start()

    def _thumb_arrived(self, vid: str, path: str):
        if path:
            self.page_media.set_thumb(vid, path)

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
            self.nav_home.setChecked(False); self.nav_dl.setChecked(False); self.nav_media.setChecked(False)
        else:
            self.flash("File not found — it may have been moved or deleted")
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
        ans = QMessageBox.question(
            self, "Delete file",
            f"Delete “{name}” from disk?\nThis cannot be undone.",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if ans != QMessageBox.Yes:
            return
        ok, msg = self.manager.delete_media(job_id)
        self.flash("Deleted" if ok else msg)
        self._queues_changed()

    def open_output_folder(self):
        key = "video_dir" if self.page_home.kind() == "video" else "audio_dir"
        QDesktopServices.openUrl(QUrl.fromLocalFile(self.page_home.settings.get(key, "")))

    def update_ytdlp(self):
        self.flash("Updating yt-dlp…")
        self.btn_update.setEnabled(False)
        def work():
            ok, msg = update.update_ytdlp()
            QTimer.singleShot(0, lambda: self._update_done(ok, msg))
        threading.Thread(target=work, daemon=True).start()

    def _update_done(self, ok: bool, msg: str):
        self.btn_update.setEnabled(True)
        self.flash(msg)
        if not ok:
            QMessageBox.warning(self, "Update", msg)

    def _tick(self):
        running = [j for j in self.manager.jobs.values() if j.status in (RUNNING, "Processing")]
        if running:
            self.status.setText(f"{len(running)} downloading · {_human(sum(j.speed for j in running))}/s")
        elif self.status.text().endswith("/s"):
            self.status.setText("")

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
