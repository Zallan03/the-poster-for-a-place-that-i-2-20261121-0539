#!/usr/bin/env python3
"""Velmara - a travel poster for a place that isn't there.

Generates one 768x1024 PNG travel poster for VELMARA, the floating isles
that never touch the sea, and writes it to /output/entry.png.

Pure Python standard library only (no network, no third-party packages):
the PNG is encoded by hand with zlib. Fully deterministic: the same run
always produces the same bytes.

Run:  python3 main.py
"""

import math
import os
import random
import struct
import zlib

W, H = 768, 1024
OUT = os.environ.get("ENTRY_PNG", "/output/entry.png")

# ---------------------------------------------------------------- canvas
buf = bytearray(W * H * 3)


def _clamp(v, lo=0, hi=255):
    return lo if v < lo else hi if v > hi else v


def lerp(a, b, t):
    return a + (b - a) * t


def mix(c1, c2, t):
    """Blend colour c1 towards c2 by t (0..1)."""
    return (
        int(lerp(c1[0], c2[0], t)),
        int(lerp(c1[1], c2[1], t)),
        int(lerp(c1[2], c2[2], t)),
    )


def span(y, x0, x1, col):
    """Fill a horizontal run of pixels on row y (fast slice fill)."""
    if y < 0 or y >= H:
        return
    x0 = max(0, int(x0))
    x1 = min(W - 1, int(x1))
    if x1 < x0:
        return
    i = (y * W + x0) * 3
    n = x1 - x0 + 1
    buf[i:i + n * 3] = bytes(col) * n


def rect(x, y, w, h, col):
    for yy in range(y, y + h):
        span(yy, x, x + w - 1, col)


def set_px(x, y, col):
    if 0 <= x < W and 0 <= y < H:
        i = (y * W + x) * 3
        buf[i], buf[i + 1], buf[i + 2] = col


def line(x0, y0, x1, y1, col):
    """Bresenham line, for birds and balloon strings."""
    dx = abs(x1 - x0)
    dy = -abs(y1 - y0)
    sx = 1 if x0 < x1 else -1
    sy = 1 if y0 < y1 else -1
    err = dx + dy
    while True:
        set_px(x0, y0, col)
        if x0 == x1 and y0 == y1:
            break
        e2 = 2 * err
        if e2 >= dy:
            err += dy
            x0 += sx
        if e2 <= dx:
            err += dx
            y0 += sy


def gradient_rows(stops):
    """stops: list of (y, colour). Returns per-row colour list."""
    rows = []
    for y in range(H):
        if y <= stops[0][0]:
            rows.append(stops[0][1])
            continue
        if y >= stops[-1][0]:
            rows.append(stops[-1][1])
            continue
        for (y0, c0), (y1, c1) in zip(stops, stops[1:]):
            if y0 <= y <= y1:
                t = (y - y0) / max(1, y1 - y0)
                rows.append(mix(c0, c1, t))
                break
    return rows


def ellipse(cx, cy, rx, ry, col, alpha=1.0, bg_rows=None):
    """Filled ellipse; if alpha < 1 blend against the background row colour."""
    for y in range(cy - ry, cy + ry + 1):
        if y < 0 or y >= H:
            continue
        t = (y - cy) / ry
        hw = rx * math.sqrt(max(0.0, 1.0 - t * t))
        c = col
        if alpha < 1.0 and bg_rows is not None:
            c = mix(bg_rows[y], col, alpha)
        span(y, cx - hw, cx + hw, c)


# ------------------------------------------------------------------- font
# 5x7 bitmap font, drawn scaled. Letters are blocky on purpose: the
# retro poster look, and it stays legible at any scale.
FONT = {
    "A": ("01110", "10001", "10001", "11111", "10001", "10001", "10001"),
    "B": ("11110", "10001", "10001", "11110", "10001", "10001", "11110"),
    "C": ("01110", "10001", "10000", "10000", "10000", "10001", "01110"),
    "D": ("11110", "10001", "10001", "10001", "10001", "10001", "11110"),
    "E": ("11111", "10000", "10000", "11110", "10000", "10000", "11111"),
    "F": ("11111", "10000", "10000", "11110", "10000", "10000", "10000"),
    "G": ("01110", "10001", "10000", "10111", "10001", "10001", "01111"),
    "H": ("10001", "10001", "10001", "11111", "10001", "10001", "10001"),
    "I": ("01110", "00100", "00100", "00100", "00100", "00100", "01110"),
    "J": ("00111", "00010", "00010", "00010", "00010", "10010", "01100"),
    "K": ("10001", "10010", "10100", "11000", "10100", "10010", "10001"),
    "L": ("10000", "10000", "10000", "10000", "10000", "10000", "11111"),
    "M": ("10001", "11011", "10101", "10101", "10001", "10001", "10001"),
    "N": ("10001", "11001", "10101", "10011", "10001", "10001", "10001"),
    "O": ("01110", "10001", "10001", "10001", "10001", "10001", "01110"),
    "P": ("11110", "10001", "10001", "11110", "10000", "10000", "10000"),
    "Q": ("01110", "10001", "10001", "10001", "10101", "10010", "01101"),
    "R": ("11110", "10001", "10001", "11110", "10100", "10010", "10001"),
    "S": ("01111", "10000", "10000", "01110", "00001", "00001", "11110"),
    "T": ("11111", "00100", "00100", "00100", "00100", "00100", "00100"),
    "U": ("10001", "10001", "10001", "10001", "10001", "10001", "01110"),
    "V": ("10001", "10001", "10001", "10001", "10001", "01010", "00100"),
    "W": ("10001", "10001", "10001", "10101", "10101", "11011", "10001"),
    "X": ("10001", "10001", "01010", "00100", "01010", "10001", "10001"),
    "Y": ("10001", "10001", "01010", "00100", "00100", "00100", "00100"),
    "Z": ("11111", "00001", "00010", "00100", "01000", "10000", "11111"),
    "0": ("01110", "10001", "10011", "10101", "11001", "10001", "01110"),
    "1": ("00100", "01100", "00100", "00100", "00100", "00100", "01110"),
    "2": ("01110", "10001", "00001", "00110", "01000", "10000", "11111"),
    "3": ("11111", "00010", "00100", "00010", "00001", "10001", "01110"),
    "4": ("00010", "00110", "01010", "10010", "11111", "00010", "00010"),
    "5": ("11111", "10000", "11110", "00001", "00001", "10001", "01110"),
    "6": ("01110", "10000", "10000", "11110", "10001", "10001", "01110"),
    "7": ("11111", "00001", "00010", "00100", "01000", "01000", "01000"),
    "8": ("01110", "10001", "10001", "01110", "10001", "10001", "01110"),
    "9": ("01110", "10001", "10001", "01111", "00001", "00001", "01110"),
    " ": ("00000", "00000", "00000", "00000", "00000", "00000", "00000"),
    ".": ("00000", "00000", "00000", "00000", "00000", "01100", "01100"),
    "-": ("00000", "00000", "00000", "01110", "00000", "00000", "00000"),
    "'": ("00100", "00100", "01000", "00000", "00000", "00000", "00000"),
}

CREAM = (255, 243, 214)
GOLD = (255, 214, 138)
SHADOW = (22, 18, 52)


def text_width(text, scale):
    return len(text) * 6 * scale - scale


def draw_text(text, x, y, scale, col, shadow=True):
    if shadow:
        _draw_text_raw(text, x + max(2, scale // 4), y + max(2, scale // 3),
                       scale, SHADOW)
    _draw_text_raw(text, x, y, scale, col)


def _draw_text_raw(text, x, y, scale, col):
    cx = x
    for ch in text:
        glyph = FONT.get(ch, FONT[" "])
        for r, row in enumerate(glyph):
            for c, bit in enumerate(row):
                if bit == "1":
                    rect(cx + c * scale, y + r * scale, scale, scale, col)
        cx += 6 * scale


def draw_text_centred(text, y, scale, col):
    draw_text(text, (W - text_width(text, scale)) // 2, y, scale, col)


# ------------------------------------------------------------------ scene
SKY_STOPS = [
    (0, (16, 22, 54)),
    (220, (58, 48, 102)),
    (380, (146, 64, 104)),
    (500, (214, 110, 90)),
    (620, (247, 171, 92)),
]
SEA_STOPS = [
    (640, (38, 110, 118)),
    (760, (24, 80, 96)),
    (1024, (10, 38, 58)),
]
SUN_C, SUN_R = (300, 490), 78
SUN_CORE = (255, 236, 190)
SUN_GLOW = (255, 196, 120)


def draw_sky(rows):
    for y in range(0, 641):
        span(y, 0, W - 1, rows[y])


def draw_stars():
    rng = random.Random(20261121)
    for _ in range(90):
        x = rng.randrange(0, W)
        y = rng.randrange(0, 300)
        if 90 <= x <= 680 and 40 <= y <= 230:  # keep the title band clear
            continue
        s = rng.random()
        col = (255, 250, 235) if s > 0.7 else (210, 215, 245)
        if s > 0.92:
            rect(x, y, 2, 2, col)
        else:
            set_px(x, y, col)


def draw_sun(rows):
    # halo: two faint rings fading into the sky, no hard bands
    for ring in (2, 1):
        r = SUN_R + ring * 26
        a = 0.05 + 0.04 * ring
        for y in range(SUN_C[1] - r, SUN_C[1] + r + 1):
            if y < 0 or y >= 641:
                continue
            dy = (y - SUN_C[1]) / r
            hw = r * math.sqrt(max(0.0, 1.0 - dy * dy))
            span(y, SUN_C[0] - hw, SUN_C[0] + hw, mix(rows[y], SUN_GLOW, a))
    # disc: flat warm gold; the heart only a breath lighter, no ring step
    for y in range(SUN_C[1] - SUN_R, SUN_C[1] + SUN_R + 1):
        dy = (y - SUN_C[1]) / SUN_R
        hw = SUN_R * math.sqrt(max(0.0, 1.0 - dy * dy))
        span(y, SUN_C[0] - hw, SUN_C[0] + hw, (255, 214, 140))
    for y in range(SUN_C[1] - 40, SUN_C[1] + 41):
        dy = (y - SUN_C[1]) / 40
        hw = 40 * math.sqrt(max(0.0, 1.0 - dy * dy))
        span(y, SUN_C[0] - hw, SUN_C[0] + hw, (255, 226, 165))


def draw_clouds(rows):
    clouds = [
        (150, 330, 95, 12, 0.20),
        (560, 380, 110, 13, 0.18),
        (400, 250, 70, 9, 0.16),
        (130, 470, 80, 7, 0.16),
    ]
    for cx, cy, rx, ry, a in clouds:
        ellipse(cx, cy, rx, ry, (250, 205, 160), alpha=a, bg_rows=rows)


def draw_sea(rows):
    for y in range(640, H):
        span(y, 0, W - 1, rows[y])
    # sun path on the water: a soft shimmering gold column under the sun
    for y in range(645, H):
        depth = (y - 645) / (H - 645)
        w = 24 + depth * 55
        cx = SUN_C[0] + 6 * math.sin(y * 0.04)
        shimmer = 0.85 + 0.15 * math.sin(y * 0.35)
        bright = 0.38 * shimmer
        mid = 0.20 * shimmer
        span(y, cx - w, cx + w, mix(rows[y], (255, 190, 110), mid))
        span(y, cx - w * 0.55, cx + w * 0.55,
             mix(rows[y], (255, 215, 150), bright))


def draw_island(cx, top_y, half_w, depth, rock, rock_dark, grass=None):
    """A floating island: plateau on top, rocky underside tapering to a point."""
    # plateau top (slightly domed)
    for y in range(top_y, top_y + 26):
        t = (y - top_y) / 26
        hw = half_w * (1.0 - 0.12 * t)
        span(y, cx - hw, cx + hw, rock)
    # grassy rim
    if grass is not None:
        for y in range(top_y, top_y + 9):
            t = (y - top_y) / 26
            hw = half_w * (1.0 - 0.12 * t)
            span(y, cx - hw, cx + hw, grass)
    # rocky underside, narrowing to a point with a wobble
    for y in range(top_y + 26, top_y + 26 + depth):
        t = (y - (top_y + 26)) / depth
        wob = 1.0 + 0.07 * math.sin(y * 0.33) + 0.05 * math.sin(y * 0.11 + 2.0)
        hw = half_w * 0.88 * ((1.0 - t) ** 0.85) * wob
        col = mix(rock, rock_dark, 0.45) if (y // 22) % 3 == 0 else rock
        span(y, cx - hw, cx + hw, col)


def draw_spire(x, base_y, height, col, tip_col):
    """The crystal spire: Velmara's landmark lighthouse, glowing at the tip."""
    for y in range(base_y - height, base_y + 1):
        t = (y - (base_y - height)) / height  # 0 at tip, 1 at base
        hw = 4 + 16 * t
        c = mix(tip_col, col, t)
        span(y, x - hw, x + hw, c)
    # beacon glow at the tip (small, so it reads as a lamp, not a second sun)
    tip_y = base_y - height
    for ring in range(2, 0, -1):
        r = 7 + ring * 6
        ellipse(x, tip_y, r, r, (255, 230, 160), alpha=0.12 * (3 - ring))
    ellipse(x, tip_y, 6, 6, (255, 246, 216))


def draw_house(x, y, w=22, h=16):
    rect(x, y, w, h, (246, 222, 178))            # warm wall
    for dy in range(h):                          # roof triangle
        t = dy / h
        span(y - 9 + dy, x + w // 2 - int(w * 0.62 * t) + 2,
             x + w // 2 + int(w * 0.62 * t) - 2, (122, 52, 74))
    rect(x + 4, y + 5, 4, 5, (255, 214, 120))    # lit window
    rect(x + w - 8, y + 5, 4, 5, (255, 214, 120))


def draw_tree(x, y, s=1.0):
    rect(x - 1, y - 6, 3, 7, (74, 44, 34))
    for k, (tw, th) in enumerate(((16, 12), (12, 10))):
        ty = y - 6 - k * 8
        for dy in range(th):
            t = dy / th
            span(ty - th + dy, x - int(tw * 0.5 * t), x + int(tw * 0.5 * t),
                 (52, 96, 66))


def draw_balloon(cx, cy, rx, ry):
    # striped envelope: cream and coral bands
    for y in range(cy - ry, cy + ry + 1):
        dy = (y - cy) / ry
        hw = rx * math.sqrt(max(0.0, 1.0 - dy * dy))
        x0, x1 = int(cx - hw), int(cx + hw)
        x = x0
        while x <= x1:
            band = ((x - cx) // 11) % 2
            col = (255, 240, 210) if band == 0 else (214, 82, 92)
            xe = min(x1, x + 10)
            span(y, x, xe, col)
            x = xe + 1
    # basket and strings
    line(cx - int(rx * 0.55), cy + int(ry * 0.85), cx - 6, cy + ry + 26, (60, 40, 30))
    line(cx + int(rx * 0.55), cy + int(ry * 0.85), cx + 6, cy + ry + 26, (60, 40, 30))
    rect(cx - 7, cy + ry + 26, 14, 11, (122, 84, 52))


def draw_bird(x, y, s=7):
    line(x - s, y, x, y + 5, (30, 24, 60))
    line(x, y + 5, x + s, y, (30, 24, 60))


# -------------------------------------------------------------------- png
def chunk(typ, data):
    out = struct.pack(">I", len(data)) + typ + data
    out += struct.pack(">I", zlib.crc32(typ + data) & 0xFFFFFFFF)
    return out


def encode_png():
    raw = bytearray()
    for y in range(H):
        raw.append(0)  # filter: none
        raw += buf[y * W * 3:(y + 1) * W * 3]
    ihdr = struct.pack(">IIBBBBB", W, H, 8, 2, 0, 0, 0)
    png = b"\x89PNG\r\n\x1a\n"
    png += chunk(b"IHDR", ihdr)
    png += chunk(b"IDAT", zlib.compress(bytes(raw), 9))
    png += chunk(b"IEND", b"")
    return png


# ------------------------------------------------------------------- main
def main():
    sky = gradient_rows(SKY_STOPS)
    sea = gradient_rows(SEA_STOPS)

    draw_sky(sky)
    draw_stars()
    draw_sun(sky)
    draw_clouds(sky)
    draw_sea(sea)

    # far island, small and hazy on the left
    draw_island(195, 556, 105, 130, (58, 42, 99), (40, 28, 74))
    draw_spire(195, 556, 52, (120, 96, 150), (255, 220, 150))

    # small isle on the right, with a domed hut and a pennant
    draw_island(672, 636, 62, 108, (46, 34, 84), (32, 22, 62))
    ellipse(672, 640, 14, 8, (246, 222, 178))
    rect(671, 612, 2, 20, (200, 170, 120))
    for dy in range(7):  # little pennant
        span(612 + dy, 673, 673 + 10 - dy, (214, 82, 92))

    # the main isle of Velmara, home of the great crystal spire
    draw_island(470, 600, 175, 200, (52, 38, 92), (34, 24, 66),
                grass=(86, 122, 84))
    draw_spire(470, 600, 150, (232, 190, 120), (255, 240, 190))
    draw_house(352, 584)
    draw_house(408, 588, w=18, h=13)
    draw_house(540, 584)
    draw_tree(330, 600)
    draw_tree(580, 600)
    draw_tree(610, 598)

    # balloons drifting over the isles (clear of the title and subtitle)
    draw_balloon(170, 300, 36, 44)
    draw_balloon(640, 300, 26, 32)

    # birds
    for bx, by in ((250, 180), (300, 158), (520, 330), (560, 300), (340, 388)):
        draw_bird(bx, by)

    # type, set with intent: name first, then the promise
    draw_text_centred("VELMARA", 64, 13, CREAM)
    draw_text_centred("ISLES THAT NEVER TOUCH THE SEA", 196, 3, GOLD)
    span(232, 304, 464, GOLD)  # rule sits below the subtitle, never through it
    draw_text_centred("SAIL THE SKY", 952, 4, CREAM)

    os.makedirs(os.path.dirname(OUT) or ".", exist_ok=True)
    png = encode_png()
    with open(OUT, "wb") as f:
        f.write(png)
    print("wrote %s (%d bytes, %dx%d)" % (OUT, len(png), W, H))


if __name__ == "__main__":
    main()
