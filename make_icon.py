from PIL import Image, ImageFilter
import os

SRC = r"C:\Users\omerf\AppData\Local\hermes\cache\documents\native-inputs\53c8da6b155d790772f9487ed66dc8e24ac7ae3980ebb923ccd65f0042eaa54f\img_665ea4c77fd9.jpg"
OUT = r"C:\Users\omerf\Projects\Nimbus\assets"
os.makedirs(OUT, exist_ok=True)

im = Image.open(SRC).convert("RGB")
top = im.crop((0, 0, im.width, 800))          # cloud only, word excluded

# bounding box of the luminous pixels
mask = top.convert("L").point(lambda v: 255 if v > 55 else 0)
bbox = mask.getbbox()
print("raw bbox", bbox)
x0, y0, x1, y1 = bbox
pad = 26
x0, y0 = max(0, x0 - pad), max(0, y0 - pad)
x1, y1 = min(top.width, x1 + pad), min(top.height, y1 + pad)

# square it around the centre
side = max(x1 - x0, y1 - y0)
cx, cy = (x0 + x1) // 2, (y0 + y1) // 2
x0 = max(0, cx - side // 2); y0 = max(0, cy - side // 2)
x1 = min(top.width, x0 + side); y1 = min(top.height, y0 + side)
mark = top.crop((x0, y0, x1, y1))

# keep the dark backdrop but round it slightly for in-app use
mark.resize((512, 512), Image.LANCZOS).save(os.path.join(OUT, "mark.png"))
mark.resize((256, 256), Image.LANCZOS).save(
    os.path.join(OUT, "nimbus.ico"),
    sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])

# full logo (mark + word) for the About/README
im.resize((512, 512), Image.LANCZOS).save(os.path.join(OUT, "logo.png"))
print("mark box", (x0, y0, x1, y1), "->", mark.size)
for f in os.listdir(OUT):
    print(f, os.path.getsize(os.path.join(OUT, f)) // 1024, "KB")
