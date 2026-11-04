"""yt-dlp updater. Source run: pip. Frozen app: drop latest wheel into _updates/. by ActeronDev"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import urllib.request
import zipfile
from pathlib import Path

from . import config

UPDATES = config.app_dir() / "_updates"


def update_ytdlp() -> tuple[bool, str]:
    try:
        if not getattr(sys, "frozen", False):
            r = subprocess.run([sys.executable, "-m", "pip", "install", "-q", "-U", "yt-dlp"],
                               capture_output=True, text=True, timeout=300)
            if r.returncode != 0:
                return False, "pip hatası: " + (r.stderr or "").strip().splitlines()[-1]
            import importlib, yt_dlp
            importlib.reload(yt_dlp)
            return True, f"yt-dlp güncel: {yt_dlp.version.__version__}"
        return _update_frozen()
    except Exception as e:
        return False, f"Güncelleme başarısız: {e}"


def _update_frozen() -> tuple[bool, str]:
    meta = json.load(urllib.request.urlopen("https://pypi.org/pypi/yt-dlp/json", timeout=30))
    ver = meta["info"]["version"]
    wheel = next((u for u in meta["urls"] if u["filename"].endswith("py3-none-any.whl")), None)
    if not wheel:
        return False, "Uygun wheel bulunamadı."
    tmp = config.data_dir() / "yt_dlp_update.whl"
    urllib.request.urlretrieve(wheel["url"], tmp)
    UPDATES.mkdir(parents=True, exist_ok=True)
    target = UPDATES / "yt_dlp"
    if target.exists():
        shutil.rmtree(target)
    with zipfile.ZipFile(tmp) as z:
        names = [n for n in z.namelist() if n.startswith("yt_dlp/")]
        z.extractall(UPDATES, members=names)
    tmp.unlink(missing_ok=True)
    return True, f"yt-dlp {ver} indirildi — programı yeniden başlat."
