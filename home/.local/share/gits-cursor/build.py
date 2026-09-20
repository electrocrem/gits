#!/usr/bin/env python3
"""Build the GitS-Cursors X11 cursor theme: drawn from scratch with cairo, no Bibata pixels.

Look: angular "stealth" arrow, thin cyan neon outline on navy-black, a red tick as the "eye", targeting-reticle
crosshair, segmented ring for busy. Everything is vector, so every size is crisp. The symlink aliases (nw-resize,
pointer, ...) are taken over from Bibata-Modern-Ice, only the real files are redrawn.

  ./build.py                    # writes ~/.local/share/icons/GitS-Cursors
  ./build.py --preview out.png  # contact sheet, does not install anything
"""
import math
import os
import struct
import sys

import cairo

SRC = os.path.expanduser("~/.local/share/icons/Bibata-Modern-Ice")
DST = os.path.expanduser("~/.local/share/icons/GitS-Cursors")
SIZES = [16, 20, 24, 28, 32, 40, 48, 64, 80, 96]
FONT = "JetBrainsMono NFM"

CY, CYH, NAVY, RED, GREEN, YEL = "2ED3D7", "5EF1F5", "060A14", "E5432B", "34D399", "E8C547"
G = 32.0  # design grid


def col(h, a=1.0):
    return int(h[0:2], 16) / 255, int(h[2:4], 16) / 255, int(h[4:6], 16) / 255, a


def path(c, pts, close=True):
    c.move_to(*pts[0])
    for p in pts[1:]:
        c.line_to(*p)
    if close:
        c.close_path()


def halo(c, lw, color=CY):
    """Soft neon bloom around the path that is currently built."""
    c.set_line_join(cairo.LINE_JOIN_ROUND)
    c.set_line_cap(cairo.LINE_CAP_ROUND)
    for extra, a in ((5.0, 0.07), (3.0, 0.12)):
        c.set_source_rgba(*col(color, a))
        c.set_line_width(lw + extra)
        c.stroke_preserve()


def outlined(c, lw, fill, edge, glow=CY, fill_a=0.94):
    """Fill + edge for a path that is already built (miter joins = sharp angular corners)."""
    halo(c, lw, glow)
    c.set_line_join(cairo.LINE_JOIN_MITER)
    c.set_source_rgba(*col(fill, fill_a))
    c.fill_preserve()
    c.set_source_rgba(*col(edge))
    c.set_line_width(lw)
    c.stroke()


def solid(c, lw, pts, fill=CY, edge=NAVY):
    """Bright solid shape with a dark keyline, readable on light and dark backgrounds."""
    path(c, pts)
    halo(c, lw, fill)
    c.set_line_join(cairo.LINE_JOIN_MITER)
    c.set_source_rgba(*col(edge))
    c.set_line_width(lw + 1.4)
    c.stroke_preserve()
    c.set_source_rgba(*col(fill))
    c.fill()


def stroke_line(c, lw, segs, color=CY, under=True, cap=cairo.LINE_CAP_BUTT):
    """Segments drawn as a bright line over a dark keyline."""
    def build():
        for pts in segs:
            path(c, pts, close=False)
    c.set_line_join(cairo.LINE_JOIN_MITER)
    c.set_line_cap(cap)
    if under:
        build()
        c.set_source_rgba(*col(NAVY, 0.95))
        c.set_line_width(lw + 2.0)
        c.stroke()
    build()
    c.set_source_rgba(*col(color))
    c.set_line_width(lw)
    c.stroke()


def square(c, cx, cy, s, fill=RED):
    pts = [(cx - s, cy - s), (cx + s, cy - s), (cx + s, cy + s), (cx - s, cy + s)]
    path(c, pts)
    c.set_source_rgba(*col(NAVY))
    c.set_line_width(1.2)
    c.stroke_preserve()
    c.set_source_rgba(*col(fill))
    c.fill()


def head(c, lw, tip, ang, size=6.5, wid=4.8, fill=CY):
    """Triangular arrow head with its tip at `tip`, pointing along `ang` (radians, screen coords)."""
    dx, dy = math.cos(ang), math.sin(ang)
    bx, by = tip[0] - dx * size, tip[1] - dy * size
    solid(c, lw, [tip, (bx - dy * wid, by + dx * wid), (bx + dy * wid, by - dx * wid)], fill)


def rot(c, deg, cx=16, cy=16):
    c.translate(cx, cy)
    c.rotate(math.radians(deg))
    c.translate(-cx, -cy)


# --------------------------------------------------------------------------------------------- shapes
ARROW = [(4, 3), (4, 25.5), (9.6, 20.2), (13.6, 28.8), (17.6, 27), (13.7, 18.5), (21, 18.5)]
HOT_ARROW = (4, 3)


def arrow(c, lw, scale=1.0, fill=NAVY, edge=CY, tick=RED):
    c.save()
    c.translate(*HOT_ARROW)
    c.scale(scale, scale)
    c.translate(-HOT_ARROW[0], -HOT_ARROW[1])
    path(c, ARROW)
    if fill == NAVY:
        outlined(c, lw, NAVY, edge)
    else:  # "active" variants: bright body, dark keyline
        halo(c, lw, fill)
        c.set_line_join(cairo.LINE_JOIN_MITER)
        c.set_source_rgba(*col(NAVY))
        c.set_line_width(lw + 1.4)
        c.stroke_preserve()
        c.set_source_rgba(*col(fill))
        c.fill()
    # the "eye": red tick across the tail end
    c.set_line_cap(cairo.LINE_CAP_BUTT)
    c.set_source_rgba(*col(tick))
    c.set_line_width(lw * 1.5)
    c.move_to(13.6 + 0.2, 28.8 - 0.5)
    c.line_to(17.6 - 0.2, 27 - 0.2)
    c.stroke()
    c.restore()


def ibeam(c, lw, t):
    stroke_line(c, lw, [[(16, 6), (16, 26)], [(11, 5.5), (21, 5.5)], [(11, 26.5), (21, 26.5)]])
    stroke_line(c, lw, [[(16, 14), (16, 18)]], RED, under=False)


def crosshair(c, lw, t):
    stroke_line(c, lw, [[(16, 3), (16, 12)], [(16, 20), (16, 29)], [(3, 16), (12, 16)], [(20, 16), (29, 16)]])
    # corner brackets
    for sx, sy in ((-1, -1), (1, -1), (1, 1), (-1, 1)):
        stroke_line(c, lw * 0.8, [[(16 + sx * 8, 16 + sy * 5), (16 + sx * 8, 16 + sy * 8), (16 + sx * 5, 16 + sy * 8)]], CYH, under=False)
    square(c, 16, 16, 1.5)


def cell(c, lw, t):
    stroke_line(c, lw * 1.8, [[(16, 5), (16, 27)], [(5, 16), (27, 16)]], CY)
    square(c, 16, 16, 2.2)


def move(c, lw, t):
    stroke_line(c, lw, [[(16, 8), (16, 24)], [(8, 16), (24, 16)]])
    for a in (0, 90, 180, 270):
        c.save()
        rot(c, a)
        head(c, lw, (16, 3), -math.pi / 2, 6, 4.5)
        c.restore()
    square(c, 16, 16, 2)


def double(c, lw, t, deg=0):
    c.save()
    rot(c, deg)
    stroke_line(c, lw, [[(9, 16), (23, 16)]])
    head(c, lw, (3, 16), math.pi)
    head(c, lw, (29, 16), 0)
    square(c, 16, 16, 1.6)
    c.restore()


def single(c, lw, t, deg=0):
    c.save()
    rot(c, deg)
    stroke_line(c, lw, [[(16, 11), (16, 27)]])
    stroke_line(c, lw * 1.2, [[(9, 28.5), (23, 28.5)]], RED, under=False)
    head(c, lw, (16, 3), -math.pi / 2)
    c.restore()


def ring(c, lw, cx, cy, r, n, head_i, width):
    for i in range(n):
        a0 = 2 * math.pi * i / n - math.pi / 2
        a1 = a0 + 2 * math.pi / n * 0.68
        age = (head_i - i) % n
        color = RED if age == 0 else CYH if age <= 2 else CY
        alpha = 1.0 if age == 0 else max(0.18, 1.0 - age / n * 1.15)
        c.new_path()
        c.arc(cx, cy, r, a0, a1)
        c.set_line_cap(cairo.LINE_CAP_BUTT)
        c.set_source_rgba(*col(NAVY, 0.9))
        c.set_line_width(width + 2)
        c.stroke_preserve()
        c.set_source_rgba(*col(color, alpha))
        c.set_line_width(width)
        c.stroke()


def wait(c, lw, t):
    ring(c, lw, 16, 16, 10.5, 12, int(t * 12) % 12, 3.4)
    square(c, 16, 16, 1.4, CYH)


def progress(c, lw, t):
    arrow(c, lw, 0.8)
    ring(c, lw, 23, 23, 5.4, 8, int(t * 8) % 8, 2.2)


def zoom(c, lw, t, plus=True):
    c.new_path()
    c.arc(13, 13, 8, 0, 2 * math.pi)
    c.set_source_rgba(*col(NAVY, 0.55))
    c.fill_preserve()
    halo(c, lw)
    c.set_source_rgba(*col(NAVY))
    c.set_line_width(lw + 1.6)
    c.stroke_preserve()
    c.set_source_rgba(*col(CY))
    c.set_line_width(lw)
    c.stroke()
    stroke_line(c, lw * 1.6, [[(19, 19), (27.5, 27.5)]], CY)
    stroke_line(c, lw * 0.9, [[(9, 13), (17, 13)]] + ([[(13, 9), (13, 17)]] if plus else []), CYH, under=False)


def denied(c, lw, t):
    c.new_path()
    c.arc(16, 16, 10.5, 0, 2 * math.pi)
    halo(c, lw, RED)
    c.set_source_rgba(*col(NAVY))
    c.set_line_width(lw * 1.6 + 1.8)
    c.stroke_preserve()
    c.set_source_rgba(*col(RED))
    c.set_line_width(lw * 1.6)
    c.stroke()
    stroke_line(c, lw * 1.6, [[(8.6, 8.6), (23.4, 23.4)]], RED)


def xcross(c, lw, t):
    stroke_line(c, lw * 1.4, [[(7, 7), (25, 25)], [(25, 7), (7, 25)]])
    square(c, 16, 16, 2)


def pencil(c, lw, t):
    d, p = (1 / math.sqrt(2), -1 / math.sqrt(2)), (1 / math.sqrt(2), 1 / math.sqrt(2))
    T = (4, 28)
    C = (T[0] + d[0] * 6, T[1] + d[1] * 6)
    E = (T[0] + d[0] * 25, T[1] + d[1] * 25)
    w = 3.2
    solid(c, lw, [T, (C[0] + p[0] * w, C[1] + p[1] * w), (E[0] + p[0] * w, E[1] + p[1] * w),
                  (E[0] - p[0] * w, E[1] - p[1] * w), (C[0] - p[0] * w, C[1] - p[1] * w)])
    path(c, [T, (C[0] + p[0] * w, C[1] + p[1] * w), (C[0] - p[0] * w, C[1] - p[1] * w)])
    c.set_source_rgba(*col(RED))
    c.fill()


def question(c, size=14, x=19, y=28.5):
    c.select_font_face(FONT, cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)
    c.set_font_size(size)
    c.move_to(x, y)
    c.text_path("?")
    c.set_source_rgba(*col(NAVY))
    c.set_line_width(2.6)
    c.set_line_join(cairo.LINE_JOIN_ROUND)
    c.stroke_preserve()
    c.set_source_rgba(*col(CYH))
    c.fill()


def badge_box(c, lw):
    path(c, [(17.5, 17.5), (29, 17.5), (29, 29), (17.5, 29)])
    outlined(c, lw * 0.9, NAVY, CY)


def help_(c, lw, t):
    arrow(c, lw, 0.8)
    question(c)


def ask(c, lw, t):
    help_(c, lw, t)


def context(c, lw, t):
    arrow(c, lw, 0.8)
    badge_box(c, lw)
    stroke_line(c, lw * 0.8, [[(20, 21), (26.5, 21)], [(20, 23.3), (26.5, 23.3)], [(20, 25.6), (26.5, 25.6)]], CYH, under=False)


def copy(c, lw, t):
    arrow(c, lw, 0.8)
    badge_box(c, lw)
    stroke_line(c, lw * 1.0, [[(23.25, 20), (23.25, 26.5)], [(20, 23.25), (26.5, 23.25)]], GREEN, under=False)


def link(c, lw, t):
    arrow(c, lw, 0.8)
    badge_box(c, lw)
    stroke_line(c, lw * 0.9, [[(20, 26.5), (26, 20.5)]], YEL, under=False)
    path(c, [(27, 19.5), (27, 25), (21.5, 19.5)])
    c.set_source_rgba(*col(YEL))
    c.fill()


def default(c, lw, t):
    arrow(c, lw)


def pointer(c, lw, t):
    arrow(c, lw, 1.0, fill=CY)


def grabbing(c, lw, t):
    arrow(c, lw, 1.0, fill=RED, tick=CYH)


def right_ptr(c, lw, t):
    c.translate(G, 0)
    c.scale(-1, 1)
    arrow(c, lw)


def vertical_text(c, lw, t):
    rot(c, 90)
    ibeam(c, lw, t)


C16 = (16, 16)
# name -> (draw function, hotspot in grid units, animated frames)
CURSORS = {
    "left_ptr": (default, HOT_ARROW, 1),
    "wayland-cursor": (default, HOT_ARROW, 1),
    "center_ptr": (default, HOT_ARROW, 1),
    "right_ptr": (right_ptr, (G - HOT_ARROW[0], HOT_ARROW[1]), 1),
    "hand1": (pointer, HOT_ARROW, 1),
    "hand2": (pointer, HOT_ARROW, 1),
    "grabbing": (grabbing, HOT_ARROW, 1),
    "xterm": (ibeam, C16, 1),
    "vertical-text": (vertical_text, C16, 1),
    "wait": (wait, C16, 12),
    "left_ptr_watch": (progress, HOT_ARROW, 8),
    "crosshair": (crosshair, C16, 1),
    "cross": (crosshair, C16, 1),
    "tcross": (crosshair, C16, 1),
    "top_tee": (crosshair, C16, 1),
    "bottom_tee": (crosshair, C16, 1),
    "left_tee": (crosshair, C16, 1),
    "right_tee": (crosshair, C16, 1),
    "ul_angle": (crosshair, C16, 1),
    "ur_angle": (crosshair, C16, 1),
    "ll_angle": (crosshair, C16, 1),
    "lr_angle": (crosshair, C16, 1),
    "plus": (cell, C16, 1),
    "dotbox": (cell, C16, 1),
    "move": (move, C16, 1),
    "pointer-move": (move, C16, 1),
    "sb_h_double_arrow": (lambda c, lw, t: double(c, lw, t, 0), C16, 1),
    "sb_v_double_arrow": (lambda c, lw, t: double(c, lw, t, 90), C16, 1),
    "fd_double_arrow": (lambda c, lw, t: double(c, lw, t, 45), C16, 1),
    "bd_double_arrow": (lambda c, lw, t: double(c, lw, t, -45), C16, 1),
    "left_side": (lambda c, lw, t: double(c, lw, t, 0), C16, 1),
    "right_side": (lambda c, lw, t: double(c, lw, t, 0), C16, 1),
    "top_side": (lambda c, lw, t: double(c, lw, t, 90), C16, 1),
    "bottom_side": (lambda c, lw, t: double(c, lw, t, 90), C16, 1),
    "top_left_corner": (lambda c, lw, t: double(c, lw, t, 45), C16, 1),
    "bottom_right_corner": (lambda c, lw, t: double(c, lw, t, 45), C16, 1),
    "top_right_corner": (lambda c, lw, t: double(c, lw, t, -45), C16, 1),
    "bottom_left_corner": (lambda c, lw, t: double(c, lw, t, -45), C16, 1),
    "sb_up_arrow": (lambda c, lw, t: single(c, lw, t, 0), C16, 1),
    "sb_right_arrow": (lambda c, lw, t: single(c, lw, t, 90), C16, 1),
    "sb_down_arrow": (lambda c, lw, t: single(c, lw, t, 180), C16, 1),
    "sb_left_arrow": (lambda c, lw, t: single(c, lw, t, 270), C16, 1),
    "zoom-in": (lambda c, lw, t: zoom(c, lw, t, True), (13, 13), 1),
    "zoom-out": (lambda c, lw, t: zoom(c, lw, t, False), (13, 13), 1),
    "crossed_circle": (denied, C16, 1),
    "circle": (denied, C16, 1),
    "dnd_no_drop": (denied, C16, 1),
    "X_cursor": (xcross, C16, 1),
    "pencil": (pencil, (4, 28), 1),
    "question_arrow": (help_, HOT_ARROW, 1),
    "dnd-ask": (ask, HOT_ARROW, 1),
    "context-menu": (context, HOT_ARROW, 1),
    "copy": (copy, HOT_ARROW, 1),
    "dnd-copy": (copy, HOT_ARROW, 1),
    "link": (link, HOT_ARROW, 1),
    "dnd-link": (link, HOT_ARROW, 1),
}


def render(fn, size, t=0.0):
    surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, size, size)
    c = cairo.Context(surf)
    k = size / G
    c.scale(k, k)
    c.set_antialias(cairo.ANTIALIAS_BEST)
    lw = max(1.5, 1.25 / k)  # never thinner than ~1.25 px
    fn(c, lw, t)
    surf.flush()
    return surf


# ------------------------------------------------------------------------------------------- Xcursor io
IMAGE_CHUNK = 0xFFFD0002


def write(path_, images):
    """images: (nominal size, width, height, xhot, yhot, delay_ms, premultiplied ARGB bytes)."""
    ntoc = len(images)
    pos = 16 + 12 * ntoc
    toc, body = b"", b""
    for sub, w, h, xh, yh, delay, data in images:
        toc += struct.pack("<III", IMAGE_CHUNK, sub, pos + len(body))
        body += struct.pack("<9I", 36, IMAGE_CHUNK, sub, 1, w, h, xh, yh, delay) + data
    with open(path_, "wb") as f:
        f.write(struct.pack("<4sIII", b"Xcur", 16, 0x10000, ntoc) + toc + body)


def frames_for(name):
    fn, hot, nframes = CURSORS[name]
    out = []
    for s in SIZES:
        k = s / G
        xh, yh = min(s - 1, round(hot[0] * k)), min(s - 1, round(hot[1] * k))
        for i in range(nframes):
            surf = render(fn, s, i / nframes)
            out.append((s, s, s, xh, yh, 90 if nframes > 1 else 40, bytes(surf.get_data())))
    return out


def preview(out):
    names = sorted(CURSORS)
    cell_px, cols = 96, 10
    rows = math.ceil(len(names) / cols)
    bgs = [("0b1424", 0), ("c9d3dc", 1)]
    sheet = cairo.ImageSurface(cairo.FORMAT_ARGB32, cols * cell_px, rows * cell_px * 2)
    c = cairo.Context(sheet)
    c.select_font_face("monospace")
    c.set_font_size(8)
    for bg, half in bgs:
        for i, name in enumerate(names):
            x, y = (i % cols) * cell_px, (i // cols) * cell_px + half * rows * cell_px
            c.set_source_rgba(*col(bg))
            c.rectangle(x, y, cell_px, cell_px)
            c.fill()
            c.set_source_surface(render(CURSORS[name][0], 64, 0.02), x + 16, y + 8)
            c.paint()
            c.set_source_rgba(*col("8EA2AE" if half == 0 else "222222"))
            c.move_to(x + 3, y + cell_px - 5)
            c.show_text(name[:16])
    sheet.write_to_png(out)


def main():
    if len(sys.argv) > 2 and sys.argv[1] == "--preview":
        preview(sys.argv[2])
        return
    src, dst = os.path.join(SRC, "cursors"), os.path.join(DST, "cursors")
    os.makedirs(dst, exist_ok=True)
    for name in os.listdir(dst):
        os.remove(os.path.join(dst, name))
    files = links = 0
    for name in sorted(CURSORS):
        write(os.path.join(dst, name), frames_for(name))
        files += 1
    for name in sorted(os.listdir(src)):
        s, d = os.path.join(src, name), os.path.join(dst, name)
        if os.path.islink(s) and not os.path.lexists(d):
            os.symlink(os.readlink(s), d)
            links += 1
    # every real Bibata file must exist in ours
    missing = [n for n in os.listdir(src) if not os.path.islink(os.path.join(src, n)) and not os.path.exists(os.path.join(dst, n))]
    with open(os.path.join(DST, "index.theme"), "w") as f:
        f.write("[Icon Theme]\nName=GitS-Cursors\nComment=Ghost in the Shell: angular cyan neon on navy-black, red eye tick\n")
    print(f"{files} cursors drawn, {links} aliases linked -> {DST}; missing vs Bibata: {missing or 'none'}")


if __name__ == "__main__":
    main()
