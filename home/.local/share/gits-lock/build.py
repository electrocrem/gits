#!/usr/bin/env python3
"""Frames of the dancing Lain for the lock screen (gits-lock-lain): braille art, 8 text files lain-0.txt ... lain-7.txt next to this file.

hyprlock cannot animate a picture (an image widget reloads once a second at best) but it refreshes a text label ten times a second,
so Lain is text: every character is a 2x4 block of braille dots, dithered from the hologram sprite of the radio popup.
  build.py [COLUMNS [ROWS]]   default 34 x 26.  Needs Pillow and numpy and ~/.config/gits-widgets/dancer.py."""
import os
import sys

import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.expanduser("~"), ".config", "gits-widgets"))
import dancer  # noqa: E402

COLS = int(sys.argv[1]) if len(sys.argv) > 1 else 34
ROWS = int(sys.argv[2]) if len(sys.argv) > 2 else 26
# braille dot bits: (dx, dy) -> bit
BITS = {(0, 0): 0x01, (0, 1): 0x02, (0, 2): 0x04, (1, 0): 0x08, (1, 1): 0x10, (1, 2): 0x20, (0, 3): 0x40, (1, 3): 0x80}

frames = dancer._pil_frames(300, "holo", src=dancer.GIF)   # always Lain: the lock screen mascot "lain", whatever the theme's dancer
W, H = COLS * 2, ROWS * 4
for n, im in enumerate(frames):
    a = np.asarray(im).astype(float)
    alpha = a[..., 3] / 255.0
    gray = a[..., :3].mean(axis=2) / 255.0
    # fit into W x H keeping the proportions, feet on the bottom line, centred
    k = min(W / im.width, H / im.height)
    tw, th = max(1, round(im.width * k)), max(1, round(im.height * k))
    lum = Image.fromarray((np.clip(gray * 1.25, 0, 1) * alpha * 255).astype("uint8")).resize((tw, th), Image.LANCZOS)
    mask = Image.fromarray((alpha * 255).astype("uint8")).resize((tw, th), Image.LANCZOS)
    canvas = Image.new("L", (W, H), 0)
    canvas.paste(lum, ((W - tw) // 2, H - th))
    cover_im = Image.new("L", (W, H), 0)
    cover_im.paste(mask, ((W - tw) // 2, H - th))
    cover = np.asarray(cover_im) > 90
    light = np.asarray(canvas) > 105                   # the bright parts of the hologram (jacket, face) are solid, the dark ones (ink, skirt) a checkerboard
    yy, xx = np.mgrid[0:H, 0:W]
    dots = cover & (light | ((xx + yy) % 2 == 0))
    lines = []
    for r in range(ROWS):
        line = ""
        for c in range(COLS):
            code = 0
            for (dx, dy), bit in BITS.items():
                if dots[r * 4 + dy, c * 2 + dx]:
                    code |= bit
            line += chr(0x2800 + code)
        lines.append(line.rstrip("⠀") or "⠀")
    open(os.path.join(HERE, f"lain-{n}.txt"), "w", encoding="utf-8").write("\n".join(lines))
print(f"{len(frames)} frames of {COLS}x{ROWS} braille cells in {HERE}")
