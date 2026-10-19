#!/usr/bin/env python3
"""The screensaver (gits-saver): "diving into the net" — digital rain of half-width katakana and digits in the colours of the
current theme (read from style.css, which gits-theme recolours), a slow scan line and a big clock in the middle. One full-screen
overlay per monitor; any key, click or mouse movement ends it (hypridle's on-resume runs `gits-saver stop` too).
Cheap: every glyph is drawn once into a small surface per brightness step and only copied afterwards, ~20 frames a second.
"""
import math
import os
import random
import re
import sys
import time

_LS = "/usr/lib/libgtk4-layer-shell.so"
if os.path.exists(_LS) and _LS not in os.environ.get("LD_PRELOAD", ""):
    os.environ["LD_PRELOAD"] = (_LS + " " + os.environ.get("LD_PRELOAD", "")).strip()
    os.execv(sys.executable, [sys.executable, os.path.abspath(__file__), *sys.argv[1:]])
os.environ.pop("LD_PRELOAD", None)
os.environ.setdefault("GSK_RENDERER", "cairo")   # stay on the iGPU (hybrid laptops)

import cairo  # noqa: E402
import gi  # noqa: E402

gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")
gi.require_version("Gtk4LayerShell", "1.0")
from gi.repository import Gdk, GLib, GLibUnix, Gtk  # noqa: E402
from gi.repository import Gtk4LayerShell as LS  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
GLYPHS = "ｱｲｳｴｵｶｷｸｹｺｻｼｽｾｿﾀﾁﾂﾃﾄﾅﾆﾇﾈﾉﾊﾋﾌﾍﾎﾏﾐﾑﾒﾓﾔﾕﾖﾗﾘﾙﾚﾛﾜﾝ0123456789ABCDEF"
CELL, FPS = 20, 15
FONT = "Noto Sans Mono CJK JP"   # has the katakana / kanji (JetBrains Mono does not)


def palette():
    """(background, accent, bright, red) from the widgets' style.css (@define-color bg / cy / cyb / red)."""
    want = {"bg": "#060A14", "cy": "#2ED3D7", "cyb": "#5EF1F5", "red": "#E5432B"}
    try:
        for name, hexv in re.findall(r"@define-color\s+(\w+)\s+(#[0-9A-Fa-f]{6})", open(os.path.join(HERE, "style.css")).read()):
            if name in want:
                want[name] = hexv
    except OSError:
        pass
    rgb = lambda h: tuple(int(h[i:i + 2], 16) / 255 for i in (1, 3, 5))
    return rgb(want["bg"]), rgb(want["cy"]), rgb(want["cyb"]), rgb(want["red"])


class Rain(Gtk.DrawingArea):
    """The classic way: a persistent buffer that fades a little every frame, and only the falling heads are drawn into it."""

    def __init__(self, scale):
        super().__init__()
        self.bg, self.cy, self.cyb, self.red = palette()
        self.scale, self.cols, self.atlas, self.buf = scale, [], {}, None
        self.t0 = time.monotonic()
        self.set_draw_func(self.draw)
        GLib.timeout_add(1000 // FPS, self.tick)

    def glyph(self, ch, bright, red=False):
        key = (ch, bright, red)
        s = self.atlas.get(key)
        if s is None:
            px = int(CELL * self.scale)
            s = cairo.ImageSurface(cairo.FORMAT_ARGB32, px, px)
            cr = cairo.Context(s)
            cr.scale(self.scale, self.scale)
            cr.set_source_rgb(*self.bg)   # opaque cell: drawing it replaces whatever was there
            cr.paint()
            cr.set_source_rgb(*(self.red if red else self.cyb if bright else self.cy))
            cr.select_font_face(FONT, cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)
            cr.set_font_size(CELL * 0.78)
            ext = cr.text_extents(ch)
            cr.move_to((CELL - ext.x_advance) / 2, CELL * 0.82)
            cr.show_text(ch)
            self.atlas[key] = s
        return s

    def setup(self, w, h):
        px, py = int(w * self.scale), int(h * self.scale)
        if self.buf is not None and (self.buf.get_width(), self.buf.get_height()) == (px, py):
            return
        self.buf = cairo.ImageSurface(cairo.FORMAT_RGB24, px, py)
        cr = cairo.Context(self.buf)
        cr.set_source_rgb(*self.bg)
        cr.paint()
        self.rows = int(h // CELL) + 1
        self.cols = [self.new_drop(fresh=True) for _ in range(int(w // CELL) + 1)]

    def new_drop(self, fresh=False):
        return {"y": random.uniform(-self.rows, self.rows / 2 if fresh else 0), "speed": random.uniform(0.3, 0.9), "row": None,
                "ch": random.choice(GLYPHS), "red": random.random() < 0.04}

    def tick(self):
        if self.buf is None:
            self.queue_draw()
            return True
        cr = cairo.Context(self.buf)
        cr.set_source_rgba(*self.bg, 0.075)   # the fade that makes the trails
        cr.paint()
        px = CELL * self.scale
        for x, c in enumerate(self.cols):
            c["y"] += c["speed"]
            row = int(c["y"])
            if row != c["row"]:
                if c["row"] is not None and 0 <= c["row"] < self.rows:   # the old head turns into trail colour
                    cr.set_source_surface(self.glyph(c["ch"], False), x * px, c["row"] * px)
                    cr.paint()
                c["row"], c["ch"] = row, random.choice(GLYPHS)
                if 0 <= row < self.rows:
                    cr.set_source_surface(self.glyph(c["ch"], True, c["red"]), x * px, row * px)
                    cr.paint()
            if row > self.rows + 4:
                c.update(self.new_drop())
        self.queue_draw()
        return True

    def draw(self, _a, cr, w, h):
        self.setup(w, h)
        cr.save()
        cr.scale(1 / self.scale, 1 / self.scale)
        pat = cairo.SurfacePattern(self.buf)
        pat.set_filter(cairo.FILTER_NEAREST)   # 1:1 after the device scale: no smoothing pass over the whole screen
        cr.set_source(pat)
        cr.paint()
        cr.restore()
        t = time.monotonic() - self.t0
        sy = (t * 60) % (h + 200) - 100   # the scan line
        g = cairo.LinearGradient(0, sy - 60, 0, sy + 4)
        g.add_color_stop_rgba(0, *self.cy, 0)
        g.add_color_stop_rgba(1, *self.cy, 0.10)
        cr.set_source(g)
        cr.rectangle(0, sy - 60, w, 64)
        cr.fill()
        # the centre: a big clock, the date and an idle tag (no names: it fits every theme)
        clock, sub = time.strftime("%H:%M"), time.strftime("%A  %d %B").upper() + "   //   IDLE · 待機中"
        cr.select_font_face(FONT, cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)
        cr.set_font_size(96)
        e = cr.text_extents(clock)
        cr.set_font_size(13)
        e2 = cr.text_extents(sub)
        bw = max(e.x_advance, e2.x_advance) + 64
        px, py = (w - e.x_advance) / 2, h / 2 + 24
        cr.set_source_rgba(*self.bg, 0.85)
        cr.rectangle((w - bw) / 2, py - 104, bw, 160)
        cr.fill()
        cr.set_source_rgba(*self.cy, 0.6)
        cr.rectangle((w - bw) / 2, py - 104, bw, 1)
        cr.rectangle((w - bw) / 2, py + 55, bw, 1)
        cr.fill()
        cr.set_font_size(96)
        if random.random() < 0.05:   # a glitch now and then
            cr.set_source_rgba(*self.red, 0.8)
            cr.move_to(px + random.uniform(-5, 5), py)
            cr.show_text(clock)
        cr.set_source_rgb(*self.cyb)
        cr.move_to(px, py)
        cr.show_text(clock)
        cr.set_font_size(13)
        cr.set_source_rgba(*self.cy, 0.75 + 0.25 * math.sin(t * 3))
        cr.move_to((w - e2.x_advance) / 2, py + 36)
        cr.show_text(sub)


def main():
    Gtk.init()
    loop = GLib.MainLoop()
    started = time.monotonic()
    quit_ = lambda *_: (loop.quit(), True)[1] if time.monotonic() - started > 0.8 else False   # ignore the input that is still settling
    mons = Gdk.Display.get_default().get_monitors()
    wins = []
    for i in range(mons.get_n_items()):
        mon = mons.get_item(i)
        win = Gtk.Window()
        LS.init_for_window(win)
        LS.set_namespace(win, "gits-saver")
        LS.set_layer(win, LS.Layer.OVERLAY)
        LS.set_monitor(win, mon)
        for edge in (LS.Edge.TOP, LS.Edge.BOTTOM, LS.Edge.LEFT, LS.Edge.RIGHT):
            LS.set_anchor(win, edge, True)
        LS.set_exclusive_zone(win, -1)
        LS.set_keyboard_mode(win, LS.KeyboardMode.EXCLUSIVE)
        win.set_child(Rain(mon.get_scale_factor()))
        win.set_cursor(Gdk.Cursor.new_from_name("none", None))   # no pointer over the rain
        keys = Gtk.EventControllerKey()
        keys.connect("key-pressed", quit_)
        win.add_controller(keys)
        click = Gtk.GestureClick()
        click.connect("pressed", quit_)
        win.add_controller(click)
        motion = Gtk.EventControllerMotion()
        last = {}

        def moved(_c, x, y, last=last):
            if "p" in last and math.hypot(x - last["p"][0], y - last["p"][1]) > 12:
                quit_()
            last.setdefault("p", (x, y))
        motion.connect("motion", moved)
        win.add_controller(motion)
        win.present()
        wins.append(win)
    for sig in (2, 15):
        GLibUnix.signal_add(GLib.PRIORITY_DEFAULT, sig, lambda: (loop.quit(), False)[1])
    loop.run()
    return 0


if __name__ == "__main__":
    sys.exit(main())
