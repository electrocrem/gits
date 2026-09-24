#!/usr/bin/env python3
"""Frames of the Tachikoma for the lock screen (gits-lock-mascot): tachikoma-0.txt ... next to this file.

With tachikoma.gif next to this file (the installer puts assets/fuchikoma-dance.gif there) the frames are that animation in colour: one
frame per pose, every character a half block (▀/▄) whose foreground and background are two pixels, as Pango markup (hyprlock labels
render it). Without it (a fork without the fan art) they are the hologram below:

A Tachikoma (the think-tank of Ghost in the Shell) modelled from a few signed-distance primitives (abdomen pod, cabin, three eye pods,
four legs on wheels, manipulators, the rear launcher), ray-marched with numpy and turned slowly on a holo platform. Every braille
character is a 2x4 block of dots: the shading is an ordered (Bayer) dither, so the lit side is dense and the far side sparse.
  tachikoma.py [COLUMNS [ROWS [FRAMES]]]   default 52 x 24, 24 frames (3 s a turn at 8 frames a second).  Needs numpy."""
import math
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
COLS = int(sys.argv[1]) if len(sys.argv) > 1 else 52
ROWS = int(sys.argv[2]) if len(sys.argv) > 2 else 24
FRAMES = int(sys.argv[3]) if len(sys.argv) > 3 else 24
SS = 2  # supersampling per dot
BITS = {(0, 0): 0x01, (0, 1): 0x02, (0, 2): 0x04, (1, 0): 0x08, (1, 1): 0x10, (1, 2): 0x20, (0, 3): 0x40, (1, 3): 0x80}
BAYER = np.array([[0, 8, 2, 10], [12, 4, 14, 6], [3, 11, 1, 9], [15, 7, 13, 5]]) / 16 + 1 / 32


def length(v):
    return np.sqrt((v * v).sum(-1))


def ellipsoid(p, c, r):
    r = np.asarray(r, float)
    q = (p - c) / r
    return (length(q) - 1) * r.min()


def capsule(p, a, b, r):
    a, b = np.asarray(a, float), np.asarray(b, float)
    pa, ba = p - a, b - a
    h = np.clip((pa * ba).sum(-1) / (ba * ba).sum(), 0, 1)
    return length(pa - ba * h[..., None]) - r


def wheel(p, c, big, small):
    q = p - c  # a torus standing on the ground, axle along z
    return np.sqrt((np.sqrt(q[..., 0] ** 2 + q[..., 1] ** 2) - big) ** 2 + q[..., 2] ** 2) - small


def smin(a, b, k=0.08):
    h = np.clip(0.5 + 0.5 * (b - a) / k, 0, 1)
    return b * (1 - h) + a * h - k * h * (1 - h)


EYES = ((0.9, 0.86, 0.17), (0.9, 0.86, -0.17), (0.95, 0.6, 0.0))


def eyes(p):
    return np.min([ellipsoid(p, e, (0.13, 0.13, 0.13)) for e in EYES], axis=0)


def scene(p, phase):
    d = ellipsoid(p, (-0.82, 1.02, 0), (0.92, 0.64, 0.6))                    # abdomen pod
    d = smin(d, ellipsoid(p, (0.42, 0.74, 0), (0.48, 0.4, 0.42)))            # cabin
    d = smin(d, capsule(p, (-0.2, 0.84, 0), (0.2, 0.76, 0), 0.22), 0.12)     # waist
    d = np.minimum(d, eyes(p))                                               # the three eye pods
    for z in (0.22, -0.22):                                                  # manipulators
        d = np.minimum(d, capsule(p, (0.55, 0.44, z), (1.05, 0.26, z * 1.1), 0.045))
    d = np.minimum(d, capsule(p, (-1.66, 1.1, 0), (-1.9, 1.16, 0), 0.09))    # rear launcher
    for i, (sx, sz) in enumerate(((1, 1), (1, -1), (-1, 1), (-1, -1))):
        lift = 0.07 * max(0.0, math.sin(phase + i * math.pi / 2))            # a lazy idle shuffle of the feet
        hip = (0.12 * sx - 0.15, 0.62, 0.3 * sz)
        knee = (0.6 * sx - 0.15, 1.25, 0.92 * sz)
        foot = (0.95 * sx - 0.15, 0.16 + lift, 1.12 * sz)
        d = np.minimum(d, capsule(p, hip, knee, 0.07))
        d = np.minimum(d, capsule(p, knee, foot, 0.055))
        d = np.minimum(d, wheel(p, foot, 0.15, 0.05))
    return d


def normal(p, phase):
    e = 0.004
    n = np.stack([scene(p + np.array(v) * e, phase) - scene(p - np.array(v) * e, phase)
                  for v in ((1, 0, 0), (0, 1, 0), (0, 0, 1))], -1)
    return n / np.maximum(length(n)[..., None], 1e-9)


def render(yaw, phase, W, H):
    """Orthographic camera looking down 22 degrees, turned by yaw around the vertical axis. Returns brightness 0..1 per dot."""
    w, h = W * SS, H * SS
    span_x = 4.0
    span_y = span_x * h / w  # braille dots are square: a cell is 2 dots wide, 4 tall, and a character twice as tall as wide
    xs = (np.arange(w) + 0.5) / w * span_x - span_x / 2
    ys = (1 - (np.arange(h) + 0.5) / h) * span_y - span_y / 2
    X, Y = np.meshgrid(xs, ys)
    el = math.radians(26)
    fwd = np.array([-math.cos(el) * math.cos(yaw), -math.sin(el), -math.cos(el) * math.sin(yaw)])
    right = np.array([-math.sin(yaw), 0, math.cos(yaw)])
    up = np.cross(fwd, right)
    target = np.array([-0.4, 0.6, 0])
    o = target - fwd * 6 + X[..., None] * right + Y[..., None] * up
    t = np.zeros(X.shape)
    hit = np.zeros(X.shape, bool)
    live = np.ones(X.shape, bool)  # rays still marching: only those are evaluated
    for _ in range(64):
        idx = np.nonzero(live)
        if not idx[0].size:
            break
        d = scene(o[idx] + fwd * t[idx][..., None], phase)
        t[idx] += d
        done = d < 0.003
        hit[idx[0][done], idx[1][done]] = True
        live[idx[0][done | (t[idx] > 9)], idx[1][done | (t[idx] > 9)]] = False
    lum = np.zeros(X.shape)
    if hit.any():
        p = o[hit] + fwd * t[hit][..., None]
        n = normal(p, phase)
        light = np.array([0.35, 0.8, 0.5])
        light /= np.linalg.norm(light)
        diff = np.clip((n * light).sum(-1), 0, 1)
        rim = np.clip(1 + (n * fwd).sum(-1), 0, 1) ** 3          # hologram edge glow
        shade = np.clip(0.04 + 0.85 * diff ** 1.4 + 0.6 * rim, 0, 1)
        lum[hit] = np.where(eyes(p) < 0.01, 1.0, shade)       # the eye pods are always lit
    # the holo platform: a dotted ellipse on the ground plane (y = 0) under the robot
    g = np.where(fwd[1] != 0, -o[..., 1] / fwd[1], 0)
    gp = o + fwd * g[..., None]
    rr = np.sqrt((gp[..., 0] + 0.4) ** 2 + gp[..., 2] ** 2)
    ring = (~hit) & (np.abs(rr - 1.7) < 0.05) & (np.cos(np.arctan2(gp[..., 2], gp[..., 0] + 0.4) * 24 - yaw * 3) > 0)
    lum[ring] = 0.55
    return lum.reshape(H, SS, W, SS).mean((1, 3))


def braille(lum):
    H, W = lum.shape
    yy, xx = np.mgrid[0:H, 0:W]
    dots = lum > BAYER[yy % 4, xx % 4]
    lines = []
    for r in range(H // 4):
        line = ""
        for c in range(W // 2):
            code = 0
            for (dx, dy), bit in BITS.items():
                if dots[r * 4 + dy, c * 2 + dx]:
                    code |= bit
            line += chr(0x2800 + code)
        lines.append(line.rstrip("⠀") or "⠀")
    return "\n".join(lines)


# --------------------------------------------------------------------------------------------- the dancing gif, in colour
GIF = os.path.join(HERE, "tachikoma.gif")
GIF_COLS = 70      # characters across (one pixel each); rows are half as many characters as pixels
CELL = 1.45        # a half block of the lock screen font (JetBrainsMono, 13 pt) is this much taller than wide: squash the rows to match
GIF_COLOURS = 32   # per frame: fewer colours = longer runs = fewer <span>s for hyprlock to parse 8 times a second


def gif_frames():
    """Every distinct frame of the gif (repeats dropped), cropped to what any frame covers, on black. hyprlock shows them at 10 a second:
    all of the dance, a bit slower than the gif's 30 ms frames."""
    from PIL import Image, ImageSequence
    src = [f.convert("RGB") for f in ImageSequence.Iterator(Image.open(GIF))]
    lit = [np.asarray(f).astype(int).sum(2) > 60 for f in src]
    poses, prev = [], None
    for f, m in zip(src, lit):
        a = np.asarray(f).astype(int)
        if prev is None or np.abs(a - prev).mean() > 1:  # not a repeat of the previous frame
            poses.append((f, m))
        prev = a
    union = np.any(lit, axis=0)
    ys, xs = np.nonzero(union)
    box = (xs.min(), ys.min(), xs.max() + 1, ys.max() + 1)
    h = round((box[3] - box[1]) * GIF_COLS / (box[2] - box[0]) / CELL)
    h += h % 2
    out = []
    for f, m in poses:
        rgb = f.crop(box).resize((GIF_COLS, h), Image.BOX).quantize(GIF_COLOURS).convert("RGB")
        mask = Image.fromarray((m * 255).astype("uint8")).crop(box).resize((GIF_COLS, h), Image.BOX)
        out.append((np.asarray(rgb), np.asarray(mask) > 110))
    return out


def markup(rgb, on):
    """Half blocks as Pango markup: one <span> per run of equal colours. Transparent cells are no-break spaces: hyprlock trims plain
    leading spaces off the text, which shifted the first line to the left."""
    hexc = lambda c: "#%02x%02x%02x" % tuple(int(v) for v in c)
    lines = []
    for r in range(0, rgb.shape[0], 2):
        cells = []
        for c in range(rgb.shape[1]):
            top, bot = on[r, c], on[r + 1, c]
            if top and bot:
                cells.append(("▀", hexc(rgb[r, c]), hexc(rgb[r + 1, c])))
            elif top or bot:
                cells.append(("▀" if top else "▄", hexc(rgb[r if top else r + 1, c]), None))
            else:
                cells.append(("\u00a0", None, None))
        while cells and cells[-1][0] == "\u00a0":
            cells.pop()
        line, prev = "", (None, None)
        for ch, fg, bg in cells:
            if (fg, bg) != prev:
                if prev != (None, None):
                    line += "</span>"
                if fg:
                    line += f'<span foreground="{fg}"' + (f' background="{bg}"' if bg else "") + ">"
                prev = (fg, bg)
            line += ch
        if prev != (None, None):
            line += "</span>"
        lines.append(line or "\u00a0")
    return "\n".join(lines)


def main():
    for old in os.listdir(HERE):
        if old.startswith("tachikoma-") and old.endswith(".txt"):
            os.remove(os.path.join(HERE, old))
    if os.path.exists(GIF):
        frames = gif_frames()
        for n, (rgb, on) in enumerate(frames):
            with open(os.path.join(HERE, f"tachikoma-{n}.txt"), "w", encoding="utf-8") as fh:
                fh.write(markup(rgb, on))
        print(f"{len(frames)} colour frames of {GIF_COLS} characters from {GIF}")
        return
    for n in range(FRAMES):
        f = n / FRAMES
        art = braille(render(math.radians(-30) + f * 2 * math.pi, f * 4 * math.pi, COLS * 2, ROWS * 4))
        with open(os.path.join(HERE, f"tachikoma-{n}.txt"), "w", encoding="utf-8") as fh:
            fh.write(art)
    print(f"{FRAMES} frames of {COLS}x{ROWS} braille cells in {HERE}")


if __name__ == "__main__":
    main()
