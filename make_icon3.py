from PIL import Image
import os

SRC = r"C:\Users\omerf\AppData\Local\hermes\cache\documents\native-inputs\f32f492d248f17f362c057c135ac0b4ec4dc44ea24e0a2473a7b7b5fa31a1b1e\img_03db6c416511.jpg"
OUT = r"C:\Users\omerf\Projects\Nimbus\assets"

im = Image.open(SRC).convert("RGB")
full = im.convert("RGBA")
px = full.load()
w, h = full.size
lo, hi = 14.0, 60.0
for y in range(h):
    for x in range(w):
        r, g, b, _ = px[x, y]
        lum = max(r, g, b)
        a = 0 if lum <= lo else 255 if lum >= hi else int((lum - lo) * 255 / (hi - lo))
        px[x, y] = (r, g, b, a)

# row occupancy -> find the blank band that separates the mark from the word
rows = [any(px[x, y][3] > 30 for x in range(0, w, 3)) for y in range(h)]
gaps, start = [], None
for y, filled in enumerate(rows):
    if not filled and start is None:
        start = y
    elif filled and start is not None:
        if y - start >= 12:
            gaps.append((start, y))
        start = None
print("gaps", gaps)
cut = next((g[0] for g in reversed(gaps) if g[0] > h * 0.45), None)
print("cut at", cut, "of", h)

area = full.crop((0, 0, w, cut or int(h * 0.72)))
bbox = area.getbbox()
x0, y0, x1, y1 = bbox
pad = 10
x0, y0 = max(0, x0 - pad), max(0, y0 - pad)
x1, y1 = min(w, x1 + pad), min(area.height, y1 + pad)
side = max(x1 - x0, y1 - y0)
cx, cy = (x0 + x1) // 2, (y0 + y1) // 2
half = side // 2
x0 = max(0, cx - half); y0 = max(0, cy - half)
x1 = min(w, x0 + side); y1 = min(area.height, y0 + side)
mark = area.crop((x0, y0, x1, y1))
print("mark", mark.size, "corner alpha", mark.getpixel((0, 0))[3])

mark.resize((512, 512), Image.LANCZOS).save(os.path.join(OUT, "mark.png"))
mark.resize((256, 256), Image.LANCZOS).save(
    os.path.join(OUT, "nimbus.ico"),
    sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
im.resize((512, 512), Image.LANCZOS).save(os.path.join(OUT, "logo.png"))
print("done")
