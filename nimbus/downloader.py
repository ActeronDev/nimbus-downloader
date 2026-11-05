"""Download engine: yt-dlp jobs with progress, pause/resume/cancel. by ActeronDev"""
from __future__ import annotations

import json
import os
import subprocess
import threading
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path

from PySide6.QtCore import QObject, Signal

import yt_dlp

from . import config

VIDEO_QUALITIES = ["Best Quality", "360p", "480p", "720p", "1080p", "1440p", "2160p"]
AUDIO_QUALITIES = ["Best Quality", "MP3 320", "MP3 192"]
HEIGHTS = {"360p": 360, "480p": 480, "720p": 720, "1080p": 1080,
           "1440p": 1440, "2160p": 2160}

PENDING, RUNNING, PAUSED, DONE, ERROR, CANCELED = (
    "Pending", "Downloading", "Paused", "Done", "Error", "Canceled")
PROCESSING = "Processing"


@dataclass
class Job:
    id: str
    url: str
    kind: str            # "video" | "audio"
    quality: str
    outdir: str
    codec: str = "h264"  # "h264" (editors) | "original" (site best)
    title: str = ""
    status: str = PENDING
    pct: float = 0.0
    speed: float = 0.0
    eta: int = 0
    size: int = 0
    filepath: str = ""
    error: str = ""
    created: float = field(default_factory=time.time)


class Manager(QObject):
    changed = Signal(str)        # job id
    queue_changed = Signal()

    def __init__(self, concurrency: int = 2):
        super().__init__()
        self.jobs: dict[str, Job] = {}
        self.order: list[str] = []
        self.concurrency = concurrency
        self._stop: dict[str, str] = {}   # id -> "pause" | "cancel"
        self._lock = threading.Lock()

    # ---------- queue ----------
    def add(self, url: str, kind: str, quality: str, codec: str = "h264") -> Job:
        outdir = config.load_settings()["video_dir" if kind == "video" else "audio_dir"]
        Path(outdir).mkdir(parents=True, exist_ok=True)
        job = Job(uuid.uuid4().hex[:8], url, kind, quality, outdir, codec)
        with self._lock:
            self.jobs[job.id] = job
            self.order.append(job.id)
        self.changed.emit(job.id)
        self.save()
        self._pump()
        return job

    def get(self, job_id: str) -> Job | None:
        return self.jobs.get(job_id)

    def active_count(self) -> int:
        return sum(1 for j in self.jobs.values() if j.status == RUNNING)

    def _pump(self):
        with self._lock:
            for jid in list(self.order):
                if self.active_count() >= self.concurrency:
                    return
                job = self.jobs.get(jid)
                if job and job.status == PENDING and jid not in self._stop:
                    job.status = RUNNING
                    job.error = ""
                    threading.Thread(target=self._run, args=(job,), daemon=True).start()

    # ---------- controls ----------
    def pause(self, job_id: str):
        job = self.jobs.get(job_id)
        if not job:
            return
        if job.status == RUNNING:
            self._stop[job_id] = "pause"
        elif job.status == PENDING:
            job.status = PAUSED
            self.changed.emit(job_id)
        self.save()

    def resume(self, job_id: str):
        job = self.jobs.get(job_id)
        if not job or job.status not in (PAUSED, ERROR, CANCELED):
            return
        job.status = PENDING
        self._stop.pop(job_id, None)
        self.changed.emit(job_id)
        self.save()
        self._pump()

    def cancel(self, job_id: str):
        job = self.jobs.get(job_id)
        if not job:
            return
        if job.status == RUNNING:
            self._stop[job_id] = "cancel"
        elif job.status != DONE:
            job.status = CANCELED
            self.changed.emit(job_id)
            self.save()

    def delete_media(self, job_id: str) -> tuple[bool, str]:
        """Delete the file on disk and every queue entry that points at it."""
        job = self.jobs.get(job_id)
        if not job:
            return False, "Not found"
        path = Path(job.filepath) if job.filepath else None
        err = ""
        if path and path.exists():
            try:
                path.unlink()
            except OSError as e:
                return False, f"Could not delete: {e.strerror or e}"
        if path:
            for suffix in (".part", ".ytdl"):
                try:
                    Path(str(path) + suffix).unlink(missing_ok=True)
                except OSError:
                    pass
        key = str(path).lower() if path else ""
        with self._lock:
            for jid in [j for j in self.order
                        if j in self.jobs and (self.jobs[j].filepath or "").lower() == key]:
                self.jobs.pop(jid, None)
                self.order.remove(jid)
        self.save()
        return True, "Deleted"

    def purge_missing(self) -> int:
        """Forget finished jobs whose file is no longer on disk."""
        gone = 0
        with self._lock:
            for jid in list(self.order):
                j = self.jobs.get(jid)
                if j and j.status == DONE and j.filepath and not Path(j.filepath).exists():
                    self.jobs.pop(jid, None)
                    self.order.remove(jid)
                    gone += 1
        if gone:
            self.save()
        return gone

    def remove(self, job_id: str):
        job = self.jobs.get(job_id)
        if not job:
            return
        self.cancel(job_id)
        with self._lock:
            self.jobs.pop(job_id, None)
            if job_id in self.order:
                self.order.remove(job_id)
        self.save()

    # ---------- worker ----------
    def _run(self, job: Job):
        stop_flag = {"why": None}

        def check_stop():
            why = self._stop.get(job.id)
            if why:
                stop_flag["why"] = why
                raise yt_dlp.utils.DownloadCancelled("stopped by user")

        phases: list[str] = []

        def hook(d):
            if d.get("status") == "downloading":
                if d.get("filename"):
                    job._tmp = d["filename"]
                total = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
                done = d.get("downloaded_bytes") or 0
                # yt-dlp fetches video and audio as separate files: each restarts at 0.
                # Split the bar into 86% video / 12% audio so it never jumps back.
                fn = d.get("filename") or ""
                if fn and fn not in phases:
                    phases.append(fn)
                idx = phases.index(fn) if fn in phases else 0
                local = (done / total) if total else 0.0
                pct = local * 86.0 if idx == 0 else min(98.0, 86.0 + local * 12.0)
                job.pct = round(max(job.pct, pct), 1)
                job.speed = d.get("speed") or 0
                job.eta = d.get("eta") or 0
                job.size = total or done
                info = d.get("info_dict") or {}
                if info.get("title"):
                    job.title = info["title"]
                self.changed.emit(job.id)
                check_stop()
            elif d.get("status") == "finished":
                job.pct = 100.0
                job.status = PROCESSING
                self.changed.emit(job.id)
                check_stop()

        def pp_hook(d):
            info = d.get("info_dict") or {}
            if info.get("title"):
                job.title = info["title"]
            if d.get("status") == "finished" and info.get("filepath"):
                job.filepath = info["filepath"]
            if d.get("status") == "finished":
                job.pct = 100.0
            self.changed.emit(job.id)
            check_stop()

        # Quality tag in the name: 480p and 1080p of the same video must coexist,
        # otherwise yt-dlp sees the old file and reports "already downloaded".
        # [Orig] keeps the non-editable variant from clobbering the H.264 one.
        tag = " [Orig]" if job.kind == "video" and job.codec == "original" else ""
        name = (f"%(title).150B [%(id)s][%(width)sx%(height)s]{tag}.%(ext)s" if job.kind == "video"
                else "%(title).150B [%(id)s].%(ext)s")
        opts = {
            "outtmpl": str(Path(job.outdir) / name),
            "format": _format_string(job.kind, job.quality, job.codec),
            "ffmpeg_location": str(config.ffmpeg_dir()),
            "noplaylist": True,
            "quiet": True,
            "no_warnings": True,
            "noprogress": True,
            "windowsfilenames": True,
            "continuedl": True,
            "retries": 5,
            "fragment_retries": 5,
            "concurrent_fragment_downloads": 4,
            "progress_hooks": [hook],
            "postprocessor_hooks": [pp_hook],
            "js_runtimes": _js_runtimes(),
        }
        if job.kind == "video":
            opts["merge_output_format"] = "mp4"
        else:
            codec, quality = _audio_codec(job.quality)
            if codec:
                opts["postprocessors"] = [{
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": codec,
                    "preferredquality": quality,
                }]

        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(job.url, download=True)
                if info:
                    job.title = info.get("title") or job.title
                    if not job.filepath:
                        job.filepath = _final_path(ydl, info)
            if job.kind == "video" and job.codec == "h264":
                self._to_h264(job, (info or {}).get("vcodec") or "")
            job.status = DONE
            job.pct = 100.0
            self._stop.pop(job.id, None)
        except Exception as e:
            why = self._stop.get(job.id) or stop_flag["why"]
            if why == "pause":
                job.status = PAUSED
            elif why == "cancel":
                job.status = CANCELED
                _cleanup_partial(job)
            else:
                job.status = ERROR
                job.error = str(e).splitlines()[0][:200] if str(e) else type(e).__name__
            self._stop.pop(job.id, None)
        finally:
            self.changed.emit(job.id)
            self.save()
            self._pump()

    def _to_h264(self, job: Job, vcodec: str):
        """Editors can't read VP9/AV1: re-encode the rare 1440p+ pick once."""
        if not job.filepath or vcodec.startswith(("avc1", "h264")):
            return
        src = Path(job.filepath)
        if not src.exists():
            return
        job.status = PROCESSING
        job.pct = 99.0
        self.changed.emit(job.id)
        final = src if src.suffix.lower() == ".mp4" else src.with_suffix(".mp4")
        out = final.with_name(final.stem + ".h264.mp4")
        cmd = [str(config.ffmpeg_dir() / "ffmpeg.exe"), "-y", "-i", str(src),
               "-map", "0:v:0", "-map", "0:a:0?", "-c:v", "libx264", "-preset", "fast",
               "-crf", "19", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k",
               "-movflags", "+faststart", str(out)]
        # shortcut: the encode is not interruptible; pause/cancel lands only when it ends
        r = subprocess.run(cmd, capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW)
        if r.returncode != 0 or not out.exists():
            out.unlink(missing_ok=True)
            raise RuntimeError("Re-encode to H.264 failed")
        os.replace(out, final)
        if final != src:
            src.unlink(missing_ok=True)
            job.filepath = str(final)

    # ---------- persistence ----------
    def save(self):
        data = [self.jobs[i].__dict__ for i in self.order if i in self.jobs]
        try:
            config.QUEUE_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
        except Exception:
            pass
        self.queue_changed.emit()

    def load(self):
        try:
            rows = json.loads(config.QUEUE_FILE.read_text(encoding="utf-8"))
        except Exception:
            return
        for row in rows:
            row = {k: v for k, v in row.items() if k in Job.__dataclass_fields__}
            job = Job(**row)
            if job.status in (RUNNING, PROCESSING):
                job.status = PAUSED
            elif job.status not in (PENDING, PAUSED, DONE, ERROR, CANCELED):
                # older builds wrote localised status strings
                job.status = DONE if job.filepath and Path(job.filepath).exists() else ERROR
            self.jobs[job.id] = job
            self.order.append(job.id)
            self.changed.emit(job.id)
        self.queue_changed.emit()


def _cleanup_partial(job: "Job") -> None:
    base = getattr(job, "_tmp", "")
    if not base:
        return
    for suffix in ("", ".part", ".ytdl", ".temp"):
        try:
            Path(base + suffix).unlink(missing_ok=True)
        except OSError:
            pass


def _format_string(kind: str, quality: str, codec: str = "h264") -> str:
    if kind == "audio":
        return "bestaudio/best"
    h = HEIGHTS.get(quality)
    hf = f"[height<={h}]" if h else ""
    plain = f"bv*{hf}+ba/b{hf}/b" if h else "bv*+ba/b"
    if codec == "original" or (h and h > 1080):
        return plain
    # avc1/mp4a is the pair every editor imports. YouTube has no avc1 above 1080p,
    # so an explicit 1440p/2160p pick takes the VP9/AV1 stream and re-encodes after.
    return f"bv*[vcodec^=avc1]{hf}+ba[acodec^=mp4a]/bv*[vcodec^=avc1]{hf}+ba/{plain}"


def _audio_codec(quality: str):
    if quality.lower().startswith("mp3"):
        return "mp3", quality.split()[1]
    return None, None


def _js_runtimes() -> dict:
    qjs = config.bundle_dir() / "vendor" / "js" / "qjs.exe"
    if qjs.exists():
        return {"quickjs": {"path": str(qjs)}}
    return {"node": {}, "deno": {}}


def _final_path(ydl, info) -> str:
    try:
        req = (info.get("requested_downloads") or [{}])[0]
        if req.get("filepath"):
            return req["filepath"]
    except Exception:
        pass
    try:
        return ydl.prepare_filename(info)
    except Exception:
        return ""
