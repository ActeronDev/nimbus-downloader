"""Nimbus Downloader — paths, constants, settings. by ActeronDev"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

APP_NAME = "Nimbus Downloader"
SHORT_NAME = "Nimbus"
AUTHOR = "ActeronDev"
VERSION = "1.0.0"


def app_dir() -> Path:
    """Folder that holds the exe (frozen) or the project root (source run)."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent


def data_dir() -> Path:
    base = Path(os.environ.get("APPDATA") or Path.home())
    d = base / SHORT_NAME
    d.mkdir(parents=True, exist_ok=True)
    return d


def bundle_dir() -> Path:
    """Where bundled data lives: _internal when frozen, project root in source."""
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
    return Path(__file__).resolve().parent.parent


def ffmpeg_dir() -> Path:
    return bundle_dir() / "vendor" / "ffmpeg"


def default_video_dir() -> Path:
    d = Path.home() / "Videos" / SHORT_NAME
    return d


def default_audio_dir() -> Path:
    d = Path.home() / "Music" / SHORT_NAME
    return d


SETTINGS_FILE = data_dir() / "settings.json"
QUEUE_FILE = data_dir() / "queue.json"

DEFAULTS = {
    "video_dir": str(default_video_dir()),
    "audio_dir": str(default_audio_dir()),
    "concurrency": 2,
}


def load_settings() -> dict:
    data = dict(DEFAULTS)
    try:
        data.update(json.loads(SETTINGS_FILE.read_text(encoding="utf-8")))
    except Exception:
        pass
    return data


def save_settings(data: dict) -> None:
    try:
        SETTINGS_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass
