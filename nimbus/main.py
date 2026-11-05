"""Nimbus Downloader — entry point. by ActeronDev"""
from __future__ import annotations

import sys
from pathlib import Path

# Updated yt-dlp dropped next to the exe takes precedence over the bundled copy.
if getattr(sys, "frozen", False):
    upd = Path(sys.executable).parent / "_updates"
    if (upd / "yt_dlp").exists():
        sys.path.insert(0, str(upd))

from PySide6.QtGui import QIcon  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from nimbus import config  # noqa: E402
from nimbus.ui import MainWindow  # noqa: E402


def selftest(argv: list[str]) -> int:
    """Frozen-build check: Nimbus.exe --selftest <url> [video|audio] [quality]."""
    import json
    from PySide6.QtCore import QCoreApplication, QTimer
    from nimbus import config as cfg
    from nimbus import downloader
    a = argv[argv.index("--selftest") + 1:]
    url = a[0] if a else "https://www.youtube.com/watch?v=aqz-KE-bpKQ"
    kind = a[1] if len(a) > 1 else "video"
    quality = a[2] if len(a) > 2 else "480p"
    codec = a[3] if len(a) > 3 else "h264"
    app = QCoreApplication(sys.argv)
    m = downloader.Manager(1)
    job = m.add(url, kind, quality, codec)
    out = cfg.data_dir() / "selftest.json"
    def poll():
        if job.status in (downloader.DONE, downloader.ERROR, downloader.CANCELED):
            out.write_text(json.dumps({"status": job.status, "file": job.filepath,
                                       "error": job.error, "pct": job.pct, "codec": job.codec,
                                       "ffmpeg": str(cfg.ffmpeg_dir())}, ensure_ascii=False), encoding="utf-8")
            app.quit()
    t = QTimer(); t.timeout.connect(poll); t.start(500)
    QTimer.singleShot(240000, app.quit)
    return app.exec()


def main() -> int:
    if "--selftest" in sys.argv:
        return selftest(sys.argv)
    app = QApplication(sys.argv)
    app.setApplicationName(config.SHORT_NAME)
    app.setOrganizationName(config.AUTHOR)
    icon = config.bundle_dir() / "assets" / "nimbus.ico"
    if icon.exists():
        app.setWindowIcon(QIcon(str(icon)))
    w = MainWindow()
    w.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
