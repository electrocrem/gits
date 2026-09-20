#!/usr/bin/env python3
"""Ghost in the Shell on-screen display for volume / brightness / microphone (a tiny resident layer-shell daemon).

Feed it with `gits-osd volume 46 [muted]` (writes a line into $XDG_RUNTIME_DIR/gits-osd.fifo). The window appears at the bottom
centre, shows a segmented LED bar and hides itself 1.4 s after the last event. Hidden = unmapped: it costs nothing.
`GITS_OSD_DEMO=kind:pct[:muted]` shows one frame and stays (for screenshots)."""
import math
import os
import sys

_LS_LIB = "/usr/lib/libgtk4-layer-shell.so"
if os.path.exists(_LS_LIB) and _LS_LIB not in os.environ.get("LD_PRELOAD", ""):
    os.environ["LD_PRELOAD"] = (_LS_LIB + " " + os.environ.get("LD_PRELOAD", "")).strip()
    os.execv(sys.executable, [sys.executable, os.path.abspath(__file__), *sys.argv[1:]])
os.environ.setdefault("GSK_RENDERER", "cairo")
os.environ.setdefault("GDK_BACKEND", "wayland")
os.environ["GTK_THEME"] = "Adwaita:dark"

import cairo
import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")
gi.require_version("Gtk4LayerShell", "1.0")
from gi.repository import Gdk, GLib, GLibUnix, Gtk  # noqa: E402
from gi.repository import Gtk4LayerShell as LS  # noqa: E402

FIFO = os.path.join(os.environ.get("XDG_RUNTIME_DIR", "/tmp"), "gits-osd.fifo")
FONT = "JetBrainsMono Nerd Font"
BG, CY, CYB, FG, DIM, RED = "#060A14", "#2ED3D7", "#5EF1F5", "#C8F4FF", "#596977", "#E5432B"
W, H, SEGS = 330, 58, 26
KINDS = {  # kind -> (title, kanji, icon by state)
    "volume": ("VOLUME", "音量", "󰕿", "󰖀", "󰕾", "󰝟"),
    "brightness": ("BRIGHTNESS", "輝度", "󰃞", "󰃟", "󰃠", "󰃞"),
    "mic": ("MICROPHONE", "録音", "󰍬", "󰍬", "󰍬", "󰍭"),
    "kbd": ("KEYBOARD", "鍵盤", "󰌌", "󰌌", "󰌌", "󰌌"),
}
KBD_LEVELS = ["OFF", "LOW", "MED", "HIGH"]


def rgba(h, a=1.0):
    h = h.lstrip("#")
    return int(h[0:2], 16) / 255, int(h[2:4], 16) / 255, int(h[4:6], 16) / 255, a


def text(cr, s, x, y, size, color, bold=False, align="left", alpha=1.0, spacing=0.0, family=FONT):
    cr.select_font_face(family, cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD if bold else cairo.FONT_WEIGHT_NORMAL)
    cr.set_font_size(size)
    if spacing:
        # letter-spacing by hand (cairo has none)
        total = sum(cr.text_extents(c).x_advance + spacing for c in s)
        x = x - total if align == "right" else x
        for c in s:
            cr.set_source_rgba(*rgba(color, alpha))
            cr.move_to(x, y)
            cr.show_text(c)
            x += cr.text_extents(c).x_advance + spacing
        cr.new_path()
        return
    ext = cr.text_extents(s)
    if align == "right":
        x -= ext.x_advance
    elif align == "center":
        x -= ext.x_advance / 2
    cr.set_source_rgba(*rgba(color, alpha))
    cr.move_to(x, y)
    cr.show_text(s)
    cr.new_path()


class Osd(Gtk.Window):
    def __init__(self, monitor):
        super().__init__()
        self.set_decorated(False)
        self.set_resizable(False)
        self.set_default_size(W, H)
        self.add_css_class("osd")
        LS.init_for_window(self)
        LS.set_namespace(self, "gits-osd")
        LS.set_layer(self, LS.Layer.OVERLAY)
        LS.set_anchor(self, LS.Edge.BOTTOM, True)
        LS.set_margin(self, LS.Edge.BOTTOM, 96)
        LS.set_keyboard_mode(self, LS.KeyboardMode.NONE)
        LS.set_exclusive_zone(self, -1)
        if monitor is not None:
            LS.set_monitor(self, monitor)
        self.kind, self.pct, self.muted, self.label = "volume", 0, False, None
        self.da = Gtk.DrawingArea()
        self.da.set_content_width(W)
        self.da.set_content_height(H)
        self.da.set_draw_func(self._draw)
        self.set_child(self.da)
        self.hide_id = None
        self.connect("map", lambda *_: self.get_surface().set_input_region(cairo.Region()))  # never steals clicks

    def show_state(self, kind, pct, muted, sticky=False, label=None):
        self.kind, self.pct, self.muted, self.label = kind, max(0, min(100, pct)), muted, label
        self.da.queue_draw()
        self.present()
        if self.hide_id:
            GLib.source_remove(self.hide_id)
            self.hide_id = None
        if not sticky:
            self.hide_id = GLib.timeout_add(1400, self._hide)

    def _hide(self):
        self.hide_id = None
        self.set_visible(False)
        return False

    def _draw(self, area, cr, w, h):
        cr.set_operator(cairo.OPERATOR_CLEAR)
        cr.paint()
        cr.set_operator(cairo.OPERATOR_OVER)
        title, kanji, i_lo, i_mid, i_hi, i_mute = KINDS[self.kind]
        col = RED if self.muted else CY
        cr.set_source_rgba(*rgba(BG, 0.96))
        cr.rectangle(0, 0, w, h)
        cr.fill()
        cr.set_source_rgba(*rgba(col, 0.5))
        cr.set_line_width(1)
        cr.rectangle(0.5, 0.5, w - 1, h - 1)
        cr.stroke()
        cr.set_source_rgba(*rgba(col))
        cr.rectangle(0, 0, 3, h)
        cr.fill()
        icon = i_mute if self.muted else (i_lo if self.pct < 34 else i_mid if self.pct < 67 else i_hi)
        text(cr, icon, 20, 38, 24, RED if self.muted else CYB)
        text(cr, title, 62, 21, 9, DIM, bold=True, spacing=2)
        text(cr, kanji, 62 + len(title) * 8.3 + 6, 21, 9, DIM, family="Noto Sans CJK JP")
        bx, by, bw, bh = 62, 30, w - 62 - 74, 14
        n, gap = SEGS, 2
        sw = (bw - gap * (n - 1)) / n
        lit = 0 if self.muted else round(self.pct / 100 * n)
        for i in range(n):
            frac = (i + 1) / n
            if self.muted:
                c, alpha = RED, 0.16
            else:
                c = RED if (frac > 0.9 and self.kind == "volume") else (CYB if frac > 0.55 else CY)
                alpha = 0.95 if i < lit else 0.16
            cr.set_source_rgba(*rgba(c, alpha))
            cr.rectangle(bx + i * (sw + gap), by, sw, bh)
            cr.fill()
        label = "MUTED" if self.muted else (self.label or f"{self.pct}%")
        text(cr, label, w - 14, 43, 17 if not (self.muted or self.label) else 13, RED if self.muted else FG, bold=True, align="right")


class Daemon:
    def __init__(self):
        mons = Gdk.Display.get_default().get_monitors()
        mon = None
        for i in range(mons.get_n_items()):
            m = mons.get_item(i)
            if mon is None:
                mon = m
            if (m.get_connector() or "").startswith("eDP"):
                mon = m
                break
        self.win = Osd(mon)
        self.buf = ""
        try:
            os.mkfifo(FIFO, 0o600)
        except FileExistsError:
            pass
        self.fd = os.open(FIFO, os.O_RDWR | os.O_NONBLOCK)  # RDWR: writers never block, no EOF storms
        GLib.io_add_watch(self.fd, GLib.PRIORITY_DEFAULT, GLib.IOCondition.IN, self._readable)
        # keyboard backlight: whoever changes it (Fn keys via asusd, asusctl, ROG Control Center) - watch sysfs, 3 reads/s
        self.kbd = {}
        GLib.timeout_add(350, self._poll_kbd)

    def _poll_kbd(self):
        import glob
        for d in glob.glob("/sys/class/leds/*kbd_backlight"):
            try:
                v = int(open(d + "/brightness").read())
                mx = max(int(open(d + "/max_brightness").read()), 1)
            except (OSError, ValueError):
                continue
            old = self.kbd.get(d)
            self.kbd[d] = v
            if old is not None and old != v:
                label = KBD_LEVELS[v] if mx == 3 and 0 <= v <= 3 else None
                self.win.show_state("kbd", round(v / mx * 100), False, label=label)
        return True

    def _readable(self, fd, cond):
        try:
            self.buf += os.read(fd, 4096).decode("utf-8", "replace")
        except OSError:
            return True
        *lines, self.buf = self.buf.split("\n")
        for ln in lines[-3:]:  # a burst of key repeats: only the newest matter
            parts = ln.split()
            if len(parts) >= 2 and parts[0] in KINDS:
                try:
                    self.win.show_state(parts[0], int(float(parts[1])), len(parts) > 2 and parts[2] in ("1", "muted"))
                except ValueError:
                    pass
        return True


def main():
    if not LS.is_supported():
        return 1
    Gtk.init()
    loop = GLib.MainLoop()
    demo = os.environ.get("GITS_OSD_DEMO")
    d = Daemon()
    if demo:
        p = demo.split(":")
        d.win.show_state(p[0], int(p[1]), len(p) > 2 and p[2] == "muted", sticky=True)
    for sig in (2, 15):
        GLibUnix.signal_add(GLib.PRIORITY_DEFAULT, sig, lambda: (loop.quit(), False)[1])
    loop.run()
    try:
        os.unlink(FIFO)
    except OSError:
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
