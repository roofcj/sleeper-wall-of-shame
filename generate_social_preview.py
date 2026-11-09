#!/usr/bin/env python3
"""Make the static social card and square icon for SMS/RCS/iMessage link previews.

Run once in CI with Pillow installed. Output is tracked in docs/.
"""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

OUT = Path(__file__).resolve().parent / "docs"
OUT.mkdir(parents=True, exist_ok=True)

FONTS = (
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf",
    "/usr/share/fonts/truetype/lato/Lato-Heavy.ttf",
)

def font(size):
    for name in FONTS:
        if Path(name).exists():
            return ImageFont.truetype(name, size)
    return ImageFont.load_default()

def t(draw, xy, value, size, fill):
    draw.text(xy, value, font=font(size), fill=fill, anchor="lt")

def gradient(width, height):
    im = Image.new("RGB", (width, height))
    px = im.load()
    for y in range(height):
        for x in range(width):
            shift = 0.65 * (x / width) + 0.35 * (y / height)
            px[x, y] = (int(10 + 18 * shift), int(15 + 18 * shift), int(27 + 23 * shift))
    return im

im = gradient(1200, 630)
d = ImageDraw.Draw(im)
navy, coral, amber = "#0c111c", "#ff6677", "#ffc267"
cyan, white, muted = "#7ce3e9", "#f3f5f9", "#abb9cb"
for x in range(30, 1200, 72):
    d.line((x, 0, x, 630), fill="#202a39", width=1)
for y in range(37, 630, 72):
    d.line((0, y, 1200, y), fill="#1e2735", width=1)
d.rounded_rectangle((34, 30, 1166, 600), radius=27, outline="#36475b", width=3)
d.rounded_rectangle((65, 57, 351, 107), radius=25, fill="#273244", outline="#4e6176", width=2)
t(d, (89, 70), "HOODRICH FANTASY", 23, cyan)
t(d, (66, 159), "WALL OF", 98, white)
t(d, (62, 275), "SHAME.", 127, coral)
d.rounded_rectangle((66, 449, 720, 454), radius=2, fill=coral)
t(d, (69, 478), "ZERO POINTS. NEGATIVE LEGENDS.", 25, white)
t(d, (69, 548), "THE LEAGUE SCOREBOARD", 19, muted)
d.ellipse((802, 139, 1128, 465), fill="#273044", outline=coral, width=13)
d.ellipse((833, 170, 1097, 434), outline="#aa4c5f", width=3)
d.ellipse((886, 222, 1044, 380), fill=navy, outline=white, width=4)
t(d, (920, 234), "0", 104, white)
d.rounded_rectangle((839, 475, 1100, 540), radius=18, fill=coral)
t(d, (877, 492), "0.00 PTS", 26, navy)
for x, y, r in [(790, 130, 6), (1156, 211, 4), (789, 438, 4), (1130, 567, 5)]:
    d.ellipse((x-r, y-r, x+r, y+r), fill=amber)
im.save(OUT / "social-preview.png", format="PNG", optimize=True)

icon = gradient(180, 180)
di = ImageDraw.Draw(icon)
di.rounded_rectangle((8, 8, 172, 172), radius=33, fill="#192331", outline=coral, width=7)
di.ellipse((26, 25, 154, 153), outline=coral, width=13)
t(di, (50, 40), "0", 96, white)
di.rounded_rectangle((42, 141, 138, 154), radius=6, fill=coral)
icon.save(OUT / "apple-touch-icon.png", format="PNG", optimize=True)
print("Generated social-preview.png and apple-touch-icon.png")
