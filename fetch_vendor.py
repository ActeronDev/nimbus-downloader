"""Download the bundled tools (ffmpeg + QuickJS) into vendor/. Run once before building."""
import os
import urllib.request

FFMPEG = ("https://github.com/shinchiro/mpv-winbuild-cmake/releases/download/"
          "20261104/ffmpeg-x86_64-git-200a98d5b.7z")
QJS = ("https://github.com/quickjs-ng/quickjs/releases/download/"
       "v0.18.0/qjs-windows-x86_64.exe")
SEVENZR = "https://www.7-zip.org/a/7zr.exe"

os.makedirs("vendor/ffmpeg", exist_ok=True)
os.makedirs("vendor/js", exist_ok=True)
os.makedirs("cache", exist_ok=True)


def get(url, dest):
    if os.path.exists(dest):
        print("have", dest)
        return
    print("downloading", os.path.basename(dest))
    urllib.request.urlretrieve(url, dest)


get(QJS, "vendor/js/qjs.exe")
get(SEVENZR, "cache/7zr.exe")
get(FFMPEG, "cache/ffmpeg.7z")

exe = os.path.abspath("vendor/ffmpeg/ffmpeg.exe")
if not os.path.exists(exe):
    os.system(f'"{os.path.abspath("cache/7zr.exe")}" x cache/ffmpeg.7z -ovendor/ffmpeg -y ffmpeg.exe')
print("ffmpeg:", round(os.path.getsize(exe) / 1048576, 1), "MB")
print("qjs:   ", round(os.path.getsize("vendor/js/qjs.exe") / 1048576, 1), "MB")
