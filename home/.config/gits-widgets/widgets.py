#!/usr/bin/env python3
"""Ghost in the Shell desktop widgets.

GTK4 + gtk4-layer-shell, one process, one layer-shell window per card on the BOTTOM layer (above the
wallpaper, below every window; BACKGROUND would be covered by a later-started wallpaper daemon). Cards: clock, calendar, media player (playerctl), weather (wttr.in),
battery, CPU/RAM/SSD rings, CPU/RAM history graph, network throughput, audio spectrum (parec + numpy), to-do list.

Env: GITS_WEATHER_LOCATION  city for wttr.in (default: auto-detect by IP; "off" disables the request)
     GITS_WIDGETS_MONITOR   connector name to place the cards on (default: the main monitor, as in hypr/gits/monitors.lua:
                            GITS_MAIN_MONITOR, else a laptop panel (eDP), else the largest one)
     GITS_WIDGETS_GLITCH    0 = no wallpaper glitch bursts (default: on, only while on AC power)
     GITS_WIDGETS_DEMO      1 = screenshot mode: made-up SSID/IP and to-do items, throw-away state and cache dirs
                            (your to-do file and weather cache are neither read nor written)
"""
import calendar
import collections
import datetime
import glob
import hashlib
import json
import math
import os
import random
import re
import select
import subprocess
import threading
import time
import sys
import urllib.parse
import urllib.request

# gtk4-layer-shell has to be loaded before libwayland-client, i.e. before GTK is imported: re-exec with LD_PRELOAD
_LS_LIB = "/usr/lib/libgtk4-layer-shell.so"
if os.path.exists(_LS_LIB) and _LS_LIB not in os.environ.get("LD_PRELOAD", ""):
    os.environ["LD_PRELOAD"] = (_LS_LIB + " " + os.environ.get("LD_PRELOAD", "")).strip()
    os.execv(sys.executable, [sys.executable, os.path.abspath(__file__), *sys.argv[1:]])

# small static widgets: never wake the discrete GPU for them
os.environ.setdefault("GSK_RENDERER", "cairo")
os.environ.setdefault("GDK_BACKEND", "wayland")
# the cards bring their own CSS: skip loading the 160 KB generated "Wallbash-Gtk" theme (it also used to hang GTK 4.22 when
# gtk-4.0/settings.ini had prefer-dark-theme, see docs/PITFALLS.md; fixed system-wide, this stays as a startup saving)
os.environ["GTK_THEME"] = "Adwaita:dark"

import cairo
import gi
import psutil

try:
    import numpy as np
except ImportError:  # the audio card is skipped
    np = None

gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")
gi.require_version("Gtk4LayerShell", "1.0")
from gi.repository import Gdk, GLib, GLibUnix, Gtk, Pango  # noqa: E402
from gi.repository import Gtk4LayerShell as LS  # noqa: E402
# gtk4-layer-shell only has to be preloaded into THIS process: every child (bash, git, nmcli, hyprctl...) inherited it and loaded GTK's
# libraries for nothing, which made each spawned command several times slower
os.environ.pop("LD_PRELOAD", None)

HERE = os.path.dirname(os.path.abspath(__file__))
STATE_DIR = os.path.join(os.environ.get("XDG_STATE_HOME", os.path.expanduser("~/.local/state")), "gits-widgets")
CACHE_DIR = os.path.join(os.environ.get("XDG_CACHE_HOME", os.path.expanduser("~/.cache")), "gits-widgets")
DEMO = os.environ.get("GITS_WIDGETS_DEMO") == "1"
if DEMO:
    import tempfile
    STATE_DIR = CACHE_DIR = tempfile.mkdtemp(prefix="gits-widgets-demo-")
FONT = "JetBrainsMono Nerd Font"

# palette (= the kitty colours of the GitS theme)
BG, CY, CYB, FG = "#060A14", "#2ED3D7", "#5EF1F5", "#C8F4FF"
MID, DIM, RED, NAVY = "#9FC5D6", "#596977", "#E5432B", "#0C1A33"

DAYS = ["MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN"]
MONTHS = ["JANUARY", "FEBRUARY", "MARCH", "APRIL", "MAY", "JUNE", "JULY", "AUGUST", "SEPTEMBER", "OCTOBER",
          "NOVEMBER", "DECEMBER"]
MON3 = [m[:3] for m in MONTHS]
KANJI_DAY = ["月", "火", "水", "木", "金", "土", "日"]


def rgba(h, a=1.0):
    h = h.lstrip("#")
    return int(h[0:2], 16) / 255, int(h[2:4], 16) / 255, int(h[4:6], 16) / 255, a


def setc(cr, h, a=1.0):
    cr.set_source_rgba(*rgba(h, a))


def label(text="", css=None, xalign=0.0, ellipsize=False):
    lb = Gtk.Label(label=text, xalign=xalign)
    if css:
        for c in css.split():
            lb.add_css_class(c)
    if ellipsize:
        lb.set_ellipsize(Pango.EllipsizeMode.END)
    return lb


def draw_text(cr, text, x, y, size, color, bold=False, align="left", alpha=1.0):
    cr.select_font_face(FONT, cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD if bold else cairo.FONT_WEIGHT_NORMAL)
    cr.set_font_size(size)
    ext = cr.text_extents(text)
    if align == "center":
        x -= ext.width / 2 + ext.x_bearing
    elif align == "right":
        x -= ext.width + ext.x_bearing
    setc(cr, color, alpha)
    cr.move_to(x, y)
    cr.show_text(text)
    cr.new_path()  # show_text leaves a current point: the next arc would be joined to it by a line


# --------------------------------------------------------------------------------------------- shared data
class Stats:
    """CPU / RAM / disk numbers, refreshed every 2 s, with a short history for the graph."""
    N = 60

    def __init__(self):
        self.cpu = self.ram = self.ssd = 0.0
        self.ram_used = 0.0
        self.cpu_hist = collections.deque([0.0] * self.N, maxlen=self.N)
        self.ram_hist = collections.deque([0.0] * self.N, maxlen=self.N)
        psutil.cpu_percent(None)
        self.refresh()

    def refresh(self):
        self.cpu = psutil.cpu_percent(None)
        vm = psutil.virtual_memory()
        self.ram, self.ram_used = vm.percent, (vm.total - vm.available) / 2**30
        try:
            self.ssd = psutil.disk_usage("/").percent
        except OSError:
            pass
        self.cpu_hist.append(self.cpu)
        self.ram_hist.append(self.ram)


# --------------------------------------------------------------------------------------------- card window
class Card(Gtk.Window):
    """A borderless layer-shell window: `tag` header line + `self.body` box."""

    def __init__(self, app, tag, w, h, x, y, right=False, keyboard=False, monitor=None):
        super().__init__()
        self.set_decorated(False)
        self.set_resizable(False)
        self.set_default_size(w, h)
        self.add_css_class("gw")
        LS.init_for_window(self)
        LS.set_namespace(self, "gits-widgets")
        # BOTTOM, not BACKGROUND: layers of one level stack by creation order, so a wallpaper daemon (awww) that
        # starts after us covers every card on BACKGROUND (only the to-do, on BOTTOM, stayed visible). BOTTOM is
        # always above the wallpaper and below all windows. The to-do entry also needs keyboard focus, which
        # compositors only hand to layers above BACKGROUND.
        LS.set_layer(self, LS.Layer.BOTTOM)
        LS.set_anchor(self, LS.Edge.TOP, True)
        LS.set_anchor(self, LS.Edge.RIGHT if right else LS.Edge.LEFT, True)
        LS.set_margin(self, LS.Edge.TOP, y)
        LS.set_margin(self, LS.Edge.RIGHT if right else LS.Edge.LEFT, x)
        LS.set_keyboard_mode(self, LS.KeyboardMode.ON_DEMAND if keyboard else LS.KeyboardMode.NONE)
        if monitor is not None:
            LS.set_monitor(self, monitor)

        card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        card.add_css_class("card")
        card.set_hexpand(True)
        card.set_vexpand(True)
        head = Gtk.Box(spacing=6)
        head.append(label(tag, "tag"))
        spacer = Gtk.Box()
        spacer.set_hexpand(True)
        head.append(spacer)
        head.append(label("▪", "tag-dot"))
        card.append(head)
        self.body = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        self.body.set_vexpand(True)
        card.append(self.body)
        self.set_child(card)
        self.tick = None  # optional per-second / per-2s refresh hook

    def area(self, draw, w=-1, h=-1):
        da = Gtk.DrawingArea()
        da.set_content_width(max(w, 0))
        da.set_content_height(max(h, 0))
        da.set_draw_func(draw)
        return da


# --------------------------------------------------------------------------------------------- clock
class ClockCard(Card):
    def __init__(self, app, **kw):
        super().__init__(app, "SYS.CLOCK // 時計", **kw)
        self.hh = label("00", "clock-h", 0.5)
        self.mm = label("00", "clock-m", 0.5)
        self.date = label("", "clock-date", 0.5)
        self.kanji = label("", "clock-kanji", 0.5)
        self.sec = 0
        for wdg in (self.hh, self.mm):
            self.body.append(wdg)
        self.secbar = self.area(self._draw_sec, -1, 3)
        self.secbar.set_margin_top(4)
        self.secbar.set_margin_bottom(2)
        self.body.append(self.secbar)
        self.body.append(self.date)
        self.update()

    def _draw_sec(self, area, cr, w, h):
        setc(cr, CY, 0.18)
        cr.rectangle(0, 0, w, h)
        cr.fill()
        setc(cr, CY)
        cr.rectangle(0, 0, w * self.sec / 60.0, h)
        cr.fill()

    def update(self):
        n = datetime.datetime.now()
        self.hh.set_text(f"{n.hour:02d}")
        self.mm.set_text(f"{n.minute:02d}")
        self.date.set_text(f"{DAYS[n.weekday()]} {KANJI_DAY[n.weekday()]}  {n.day:02d} {MON3[n.month - 1]}")
        self.sec = n.second
        self.secbar.queue_draw()


# --------------------------------------------------------------------------------------------- calendar
class CalendarCard(Card):
    def __init__(self, app, **kw):
        super().__init__(app, "SYS.CAL // 暦", **kw)
        today = datetime.date.today()
        self.year, self.month, self.today = today.year, today.month, today
        nav = Gtk.Box(spacing=4)
        self.title = label("", "cal-title")
        self.title.set_hexpand(True)
        prev, nxt = Gtk.Button(label="‹"), Gtk.Button(label="›")
        for b, d in ((prev, -1), (nxt, 1)):
            b.add_css_class("flat-btn")
            b.set_focusable(False)
            b.connect("clicked", lambda _b, d=d: self.shift(d))
        nav.append(self.title)
        nav.append(prev)
        nav.append(nxt)
        self.body.append(nav)
        self.grid = Gtk.Grid(column_homogeneous=True, row_homogeneous=True, row_spacing=1, column_spacing=1)
        self.grid.set_vexpand(True)
        self.body.append(self.grid)
        self.build()

    def shift(self, d):
        m = self.month - 1 + d
        self.year += m // 12
        self.month = m % 12 + 1
        self.build()

    def build(self):
        child = self.grid.get_first_child()
        while child:
            nxt = child.get_next_sibling()
            self.grid.remove(child)
            child = nxt
        self.title.set_text(f"{MONTHS[self.month - 1]} {self.year}")
        for c, d in enumerate("MTWTFSS"):
            self.grid.attach(label(d, "cal-dow", 0.5), c, 0, 1, 1)
        weeks = calendar.Calendar(0).monthdatescalendar(self.year, self.month)
        while len(weeks) < 6:
            weeks.append([weeks[-1][-1] + datetime.timedelta(days=i + 1) for i in range(7)])
        for r, week in enumerate(weeks):
            for c, day in enumerate(week):
                lb = label(str(day.day), "cal-day", 0.5)
                if day.month != self.month:
                    lb.add_css_class("cal-out")
                if day == self.today:
                    lb.add_css_class("cal-today")
                elif c >= 5:
                    lb.add_css_class("cal-we")
                self.grid.attach(lb, c, r + 1, 1, 1)

    def update(self):
        t = datetime.date.today()
        if t != self.today:  # midnight passed
            self.today = t
            self.year, self.month = t.year, t.month
            self.build()


# --------------------------------------------------------------------------------------------- media
class IconButton(Gtk.DrawingArea):
    """Flat square button whose glyph is drawn with cairo (no dependency on icon fonts)."""

    def __init__(self, kind, on_click, size=(38, 30)):
        super().__init__()
        self.kind, self.hover, self.active = kind, False, True
        self.set_content_width(size[0])
        self.set_content_height(size[1])
        self.set_draw_func(self._draw)
        click = Gtk.GestureClick()
        click.connect("released", lambda *_: self.active and on_click())
        self.add_controller(click)
        motion = Gtk.EventControllerMotion()
        motion.connect("enter", lambda *_: self._hover(True))
        motion.connect("leave", lambda *_: self._hover(False))
        self.add_controller(motion)
        self.set_cursor(Gdk.Cursor.new_from_name("pointer"))

    def _hover(self, v):
        self.hover = v
        self.queue_draw()

    def _draw(self, area, cr, w, h):
        col = CYB if self.hover else CY
        a = 1.0 if self.active else 0.3
        setc(cr, col, a * (0.9 if self.hover else 0.55))
        cr.set_line_width(1)
        cr.rectangle(0.5, 0.5, w - 1, h - 1)
        cr.stroke()
        if self.hover and self.active:
            setc(cr, CY, 0.14)
            cr.rectangle(1, 1, w - 2, h - 2)
            cr.fill()
        setc(cr, col, a)
        cx, cy, s = w / 2, h / 2, 6.0
        k = self.kind
        if k == "play":
            cr.move_to(cx - s * 0.7, cy - s)
            cr.line_to(cx + s * 0.9, cy)
            cr.line_to(cx - s * 0.7, cy + s)
            cr.close_path()
            cr.fill()
        elif k == "pause":
            cr.rectangle(cx - s * 0.8, cy - s, s * 0.6, s * 2)
            cr.rectangle(cx + s * 0.2, cy - s, s * 0.6, s * 2)
            cr.fill()
        else:
            d = -1 if k == "prev" else 1
            for off in (-s * 0.55, s * 0.55):
                x0 = cx + off * 0.8
                cr.move_to(x0 - d * s * 0.5, cy - s * 0.85)
                cr.line_to(x0 + d * s * 0.5, cy)
                cr.line_to(x0 - d * s * 0.5, cy + s * 0.85)
                cr.close_path()
                cr.fill()
            bx = cx + d * (s * 1.35)
            cr.rectangle(bx - 0.75 if d > 0 else bx - 0.75, cy - s * 0.85, 1.5, s * 1.7)
            cr.fill()


def fmt_time(sec):
    sec = max(0, int(sec))
    return f"{sec // 60}:{sec % 60:02d}"


class MediaCard(Card):
    COVER = 200

    def __init__(self, app, **kw):
        super().__init__(app, "MEDIA.LINK // 音", **kw)
        self.cover = Gtk.Picture()
        self.cover.set_content_fit(Gtk.ContentFit.COVER)
        self.cover.set_can_shrink(True)
        self.cover.set_size_request(self.COVER, self.COVER)
        self.cover.add_css_class("cover")
        frame = Gtk.Box()
        frame.add_css_class("cover-frame")
        frame.set_halign(Gtk.Align.CENTER)
        frame.append(self.cover)
        self.nosig = label("NO SIGNAL", "nosig", 0.5)
        ov = Gtk.Overlay()
        ov.set_child(frame)
        self.nosig.set_halign(Gtk.Align.CENTER)
        self.nosig.set_valign(Gtk.Align.CENTER)
        ov.add_overlay(self.nosig)
        self.body.append(ov)
        self.title = label("—", "m-title", ellipsize=True)
        self.artist = label("", "m-artist", ellipsize=True)
        self.body.append(self.title)
        self.body.append(self.artist)
        self.frac, self.playing = 0.0, False
        self.prog = self.area(self._draw_prog, -1, 10)
        self.prog.set_margin_top(4)
        self.body.append(self.prog)
        times = Gtk.Box()
        self.t_pos, self.t_len = label("0:00", "m-time"), label("0:00", "m-time", 1.0)
        self.t_len.set_hexpand(True)
        times.append(self.t_pos)
        times.append(self.t_len)
        self.body.append(times)
        ctl = Gtk.Box(spacing=8, halign=Gtk.Align.CENTER)
        ctl.set_margin_top(4)
        self.b_prev = IconButton("prev", lambda: self.pc("previous"))
        self.b_play = IconButton("play", lambda: self.pc("play-pause"), size=(56, 30))
        self.b_next = IconButton("next", lambda: self.pc("next"))
        for b in (self.b_prev, self.b_play, self.b_next):
            ctl.append(b)
        self.body.append(ctl)
        self.art_key = None
        self.update()

    def pc(self, cmd):
        subprocess.Popen(["gits-media", cmd], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        GLib.timeout_add(250, lambda: (self.update(), False)[1])

    def _draw_prog(self, area, cr, w, h):
        y = h / 2
        setc(cr, CY, 0.2)
        cr.set_line_width(2)
        cr.move_to(0, y)
        cr.line_to(w, y)
        cr.stroke()
        setc(cr, CY)
        cr.move_to(0, y)
        cr.line_to(w * self.frac, y)
        cr.stroke()
        setc(cr, CYB)
        cr.rectangle(min(max(w * self.frac - 2, 0), w - 4), 1, 4, h - 2)
        cr.fill()

    def query(self):
        if DEMO:   # a made-up track (cover from GITS_WIDGETS_ART) so the screenshots show the card in use
            art = os.environ.get("GITS_WIDGETS_ART", "")
            return ["Playing", "Lain Iwakura", "Serial Experiments Lain - Duvet", ("file://" + art) if art else "", "232000000", "84000000"]
        fmt = "\t".join(["{{status}}", "{{artist}}", "{{title}}", "{{mpris:artUrl}}", "{{mpris:length}}",
                         "{{position}}"])
        try:
            out = subprocess.run(["gits-media", "metadata", "--format", fmt], capture_output=True, text=True,
                                 timeout=1.5).stdout.rstrip("\n")
        except (OSError, subprocess.TimeoutExpired):
            return None
        parts = out.split("\t")
        return parts if len(parts) == 6 else None

    def update(self):
        p = self.query()
        live = p is not None
        for b in (self.b_prev, self.b_play, self.b_next):
            b.active = live
            b.queue_draw()
        self.nosig.set_visible(not live)
        if not live:
            self.title.set_text("NO PLAYER")
            self.artist.set_text("start something to play")
            self.frac, self.playing = 0.0, False
            self.cover.set_paintable(None)
            self.art_key = None
            self.t_pos.set_text("0:00")
            self.t_len.set_text("0:00")
            self.b_play.kind = "play"
            self.prog.queue_draw()
            self.b_play.queue_draw()
            return
        status, artist, title, art, length, pos = p
        self.title.set_text(title or "—")
        self.artist.set_text(artist)
        self.playing = status == "Playing"
        self.b_play.kind = "pause" if self.playing else "play"
        self.b_play.queue_draw()
        try:
            ln, ps = float(length or 0) / 1e6, float(pos or 0) / 1e6
        except ValueError:
            ln = ps = 0.0
        self.frac = min(1.0, ps / ln) if ln > 0 else 0.0
        self.t_pos.set_text(fmt_time(ps))
        self.t_len.set_text(fmt_time(ln))
        self.prog.queue_draw()
        if art != self.art_key:
            self.art_key = art
            self.load_art(art)

    def load_art(self, url):
        if not url:
            self.cover.set_paintable(None)
            return
        if url.startswith("file://"):
            self.set_cover(urllib.parse.unquote(url[7:]))
            return
        path = os.path.join(CACHE_DIR, "art", hashlib.sha1(url.encode()).hexdigest())
        if os.path.exists(path):
            self.set_cover(path)
            return

        def work():
            try:
                os.makedirs(os.path.dirname(path), exist_ok=True)
                req = urllib.request.Request(url, headers={"User-Agent": "gits-widgets"})
                with urllib.request.urlopen(req, timeout=8) as r, open(path + ".tmp", "wb") as f:
                    f.write(r.read())
                os.replace(path + ".tmp", path)
                GLib.idle_add(lambda: (self.art_key == url and self.set_cover(path), False)[1])
            except (OSError, ValueError):
                pass

        threading.Thread(target=work, daemon=True).start()

    def set_cover(self, path):
        try:
            self.cover.set_paintable(Gdk.Texture.new_from_filename(path))
        except GLib.Error:
            self.cover.set_paintable(None)


# --------------------------------------------------------------------------------------------- weather
class WeatherCard(Card):
    REFRESH_S = 900

    def __init__(self, app, **kw):
        super().__init__(app, "ATMOS // 天気", **kw)
        self.loc_cfg = os.environ.get("GITS_WEATHER_LOCATION", "")
        row = Gtk.Box(spacing=14)
        self.temp = label("--°", "w-temp")
        col = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, valign=Gtk.Align.CENTER)
        self.cond = label("NO DATA", "w-cond", ellipsize=True)
        self.meta = label("", "w-meta", ellipsize=True)
        col.append(self.cond)
        row.append(self.temp)
        row.append(col)
        self.body.append(row)
        self.body.append(self.meta)
        self.cache = os.path.join(CACHE_DIR, "weather.json")
        self.last_fetch = 0.0
        self.fetching = False
        try:
            with open(self.cache) as f:
                self.show(json.load(f), stale=True)
        except (OSError, ValueError):
            pass
        self.update()

    def show(self, d, stale=False):
        self.temp.set_text(d["t"])
        self.cond.set_text(d["c"].upper())
        self.meta.set_text(("OFFLINE · " if stale else "") + d["m"])

    def update(self):
        now = GLib.get_monotonic_time() / 1e6
        if self.loc_cfg.lower() == "off" or self.fetching or now - self.last_fetch < self.REFRESH_S:
            return
        self.fetching, self.last_fetch = True, now

        def work():
            data = None
            try:
                url = "https://wttr.in/" + urllib.parse.quote(self.loc_cfg) + "?format=%t|%C|%l|%h|%w"
                req = urllib.request.Request(url, headers={"User-Agent": "curl/8"})
                with urllib.request.urlopen(req, timeout=10) as r:
                    txt = r.read().decode("utf-8", "replace").strip()
                m = re.match(r"^([+-]?\d+)\s*°?[CF]\|([^|]+)\|([^|]*)\|([^|]*)\|([^|]*)$", txt)
                if m:
                    t, c, loc, hum, wind = m.groups()
                    meta = " · ".join(x for x in (loc.split(",")[0].strip(), f"HUM {hum.strip()}",
                                                  f"WIND {wind.strip().lstrip('↑↓←→↖↗↘↙')}") if x)
                    data = {"t": f"{int(t)}°", "c": c.strip(), "m": meta}
                    os.makedirs(CACHE_DIR, exist_ok=True)
                    with open(self.cache, "w") as f:
                        json.dump(data, f)
            except (OSError, ValueError):
                pass

            def done():
                self.fetching = False
                if data:
                    self.show(data)
                else:
                    self.last_fetch = now - self.REFRESH_S + 60  # retry in a minute
                return False

            GLib.idle_add(done)

        threading.Thread(target=work, daemon=True).start()


# --------------------------------------------------------------------------------------------- battery
class BatteryCard(Card):
    def __init__(self, app, bat, **kw):
        super().__init__(app, "POWER.CELL // 電池", **kw)
        self.bat = bat
        self.pct, self.status = 0, ""
        top = Gtk.Box()
        self.big = label("0%", "b-big")
        self.big.set_hexpand(True)
        self.state = label("", "b-state", 1.0)
        self.state.set_valign(Gtk.Align.START)
        top.append(self.big)
        top.append(self.state)
        self.body.append(top)
        self.bar = self.area(self._draw, -1, 8)
        self.body.append(self.bar)
        self.update()

    def read(self, name):
        try:
            with open(os.path.join(self.bat, name)) as f:
                return f.read().strip()
        except OSError:
            return ""

    def update(self):
        self.pct = int(self.read("capacity") or 0)
        self.status = self.read("status")
        low = self.pct <= 20 and self.status == "Discharging"
        self.big.set_text(f"{self.pct}%")
        self.state.set_text({"Full": "FULLY CHARGED", "Charging": "CHARGING ↑", "Discharging": "ON BATTERY",
                             "Not charging": "PLUGGED IN"}.get(self.status, self.status.upper()))
        (self.big.add_css_class if low else self.big.remove_css_class)("low")
        self.bar.queue_draw()

    def _draw(self, area, cr, w, h):
        n, gap = 24, 2
        sw = (w - gap * (n - 1)) / n
        low = self.pct <= 20 and self.status == "Discharging"
        for i in range(n):
            filled = (i + 0.5) / n * 100 <= self.pct
            if filled:
                setc(cr, RED if low else CY)
            else:
                setc(cr, CY, 0.16)
            cr.rectangle(i * (sw + gap), 0, sw, h)
            cr.fill()


# --------------------------------------------------------------------------------------------- rings + graph
class RingsCard(Card):
    def __init__(self, app, stats, **kw):
        super().__init__(app, "SYS.LOAD // 負荷", **kw)
        self.stats = stats
        self.da = self.area(self._draw)
        self.da.set_hexpand(True)
        self.da.set_vexpand(True)
        self.body.append(self.da)

    def update(self):
        self.da.queue_draw()

    def _draw(self, area, cr, w, h):
        s = self.stats
        items = (("CPU", s.cpu), ("RAM", s.ram), ("SSD", s.ssd))
        cell = w / 3
        r = min(cell / 2 - 10, (h - 22) / 2)
        a0, sweep = math.radians(135), math.radians(270)
        for i, (name, v) in enumerate(items):
            cx, cy = cell * i + cell / 2, r + 5
            cr.set_line_width(5)
            cr.set_line_cap(cairo.LINE_CAP_BUTT)
            setc(cr, CY, 0.16)
            cr.arc(cx, cy, r, a0, a0 + sweep)
            cr.stroke()
            setc(cr, RED if v >= 85 else CY)
            cr.arc(cx, cy, r, a0, a0 + sweep * min(v, 100) / 100)
            cr.stroke()
            setc(cr, CYB, 0.5)  # inner hairline ring
            cr.set_line_width(1)
            cr.arc(cx, cy, r - 6, 0, 2 * math.pi)
            cr.stroke()
            draw_text(cr, f"{v:.0f}%", cx, cy + 4.5, 13, FG, bold=True, align="center")
            draw_text(cr, name, cx, h - 3, 9, DIM, bold=True, align="center")


class GraphCard(Card):
    def __init__(self, app, stats, **kw):
        super().__init__(app, "SYS.TRACE // 履歴", **kw)
        self.stats = stats
        head = Gtk.Box(spacing=12)
        self.l_cpu, self.l_ram = label("CPU 0%", "g-cpu"), label("RAM 0%", "g-ram")
        self.l_used = label("", "g-used", 1.0)
        self.l_used.set_hexpand(True)
        for x in (self.l_cpu, self.l_ram, self.l_used):
            head.append(x)
        self.body.append(head)
        self.da = self.area(self._draw)
        self.da.set_vexpand(True)
        self.body.append(self.da)

    def update(self):
        s = self.stats
        self.l_cpu.set_text(f"CPU {s.cpu:.0f}%")
        self.l_ram.set_text(f"RAM {s.ram:.0f}%")
        self.l_used.set_text(f"{s.ram_used:.1f} GB")
        self.da.queue_draw()

    def _draw(self, area, cr, w, h):
        setc(cr, CY, 0.12)  # grid
        cr.set_line_width(1)
        cr.set_dash([2, 3])
        for f in (0.25, 0.5, 0.75):
            y = round(h * f) + 0.5
            cr.move_to(0, y)
            cr.line_to(w, y)
        cr.stroke()
        cr.set_dash([])

        def pts(hist):
            n = len(hist)
            return [(i * w / (n - 1), h - 1 - (h - 3) * min(v, 100) / 100) for i, v in enumerate(hist)]

        ram = pts(self.stats.ram_hist)
        setc(cr, FG, 0.75)
        cr.set_line_width(1)
        cr.set_dash([4, 3])
        cr.move_to(*ram[0])
        for p in ram[1:]:
            cr.line_to(*p)
        cr.stroke()
        cr.set_dash([])
        cpu = pts(self.stats.cpu_hist)
        cr.move_to(cpu[0][0], h)
        for p in cpu:
            cr.line_to(*p)
        cr.line_to(cpu[-1][0], h)
        cr.close_path()
        setc(cr, CY, 0.2)
        cr.fill()
        cr.set_line_width(1.5)
        setc(cr, CYB)
        cr.move_to(*cpu[0])
        for p in cpu[1:]:
            cr.line_to(*p)
        cr.stroke()


# --------------------------------------------------------------------------------------------- audio spectrum
class Spectrum(threading.Thread):
    """Records the default sink's monitor with `parec` and turns it into BANDS log-spaced levels (0..1).

    No cava needed: mono s16le -> Hann-windowed FFT (numpy). Follows default-sink changes (headphones on/off).
    Only reads what is already playing; when nothing plays the stream is just silence and the card goes idle."""
    RATE, N, BANDS = 44100, 2048, 32
    HOP = 1024  # samples per read = 23 ms

    def __init__(self):
        super().__init__(daemon=True)
        self.bands = np.zeros(self.BANDS)
        self.db = -90.0
        self.sink = ""
        self.last_sound = 0.0  # monotonic time of the last audible frame
        self._quit = False
        edges = np.geomspace(45, 15000, self.BANDS + 1) * self.N / self.RATE
        self._lo = np.maximum(np.floor(edges[:-1]).astype(int), 1)
        self._hi = np.maximum(np.ceil(edges[1:]).astype(int), self._lo + 1)
        self._win = np.hanning(self.N)
        self._tilt = np.linspace(0, 12, self.BANDS)  # music falls ~3 dB/octave: lift the top so it is not always flat

    @staticmethod
    def default_sink():
        try:
            return subprocess.run(["pactl", "get-default-sink"], capture_output=True, text=True, timeout=3).stdout.strip()
        except (OSError, subprocess.SubprocessError):
            return ""

    def stop(self):
        self._quit = True

    def run(self):
        while not self._quit:
            sink = self.default_sink()
            if not sink:
                time.sleep(3)
                continue
            self.sink = sink
            try:
                proc = subprocess.Popen(
                    ["parec", "-d", sink + ".monitor", "--format=s16le", f"--rate={self.RATE}", "--channels=1",
                     "--latency-msec=25"], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
            except OSError:
                time.sleep(5)
                continue
            try:
                self._pump(proc)
            finally:
                proc.kill()
                proc.wait()

    def _pump(self, proc):
        fd = proc.stdout.fileno()
        buf = np.zeros(self.N)
        pending = b""
        next_check = time.monotonic() + 4
        while not self._quit and proc.poll() is None:
            if time.monotonic() > next_check:
                if self.default_sink() != self.sink:
                    return
                next_check = time.monotonic() + 4
            if not select.select([fd], [], [], 1.0)[0]:
                continue
            chunk = os.read(fd, 8192)
            if not chunk:
                return
            pending += chunk
            need = self.HOP * 2
            while len(pending) >= need:
                x = np.frombuffer(pending[:need], dtype="<i2").astype(np.float64) / 32768.0
                pending = pending[need:]
                buf = np.concatenate((buf[self.HOP:], x))
                self._analyse(buf, x)

    def _analyse(self, buf, x):
        rms = float(np.sqrt(np.mean(x * x)))
        self.db = 20 * math.log10(rms + 1e-9)
        if self.db > -70:
            self.last_sound = time.monotonic()
        mag = np.abs(np.fft.rfft(buf * self._win)) / (self.N / 4)
        db = 20 * np.log10(np.array([mag[lo:hi].max() for lo, hi in zip(self._lo, self._hi)]) + 1e-9)
        self.bands = np.clip((db + self._tilt + 72) / 62, 0, 1)


class AudioCard(Card):
    """LED-style spectrum analyser with peak caps. Animates at 30 fps only while sound plays."""
    SEG, SGAP = 3, 1  # LED segment height / gap, px

    def __init__(self, app, **kw):
        super().__init__(app, "AUDIO.SPECTRUM // 音声", **kw)
        n = Spectrum.BANDS
        self.spec = None
        self.level = [0.0] * n
        self.peak = [0.0] * n
        self.peak_hold = [0] * n
        self.demo_t = 0.0
        self.fast = None  # GLib source id of the 30 fps timer while animating
        head = Gtk.Box(spacing=12)
        self.l_src = label("NO SIGNAL", "au-src")
        self.l_src.set_hexpand(True)
        self.l_db = label("", "au-db", 1.0)
        head.append(self.l_src)
        head.append(self.l_db)
        self.body.append(head)
        self.da = self.area(self._draw)
        self.da.set_vexpand(True)
        self.body.append(self.da)
        if not DEMO:
            self.spec = Spectrum()
            self.spec.start()
        GLib.timeout_add(250, self._watch)

    @staticmethod
    def _name(sink):
        s = sink.lower()
        if "bluez" in s:
            return "BLUETOOTH"
        if "hdmi" in s or "displayport" in s:
            return "HDMI"
        if "usb" in s:
            return "USB.AUDIO"
        return "SPEAKERS" if s else "NO SINK"

    def _active(self):
        if DEMO:
            return True
        return self.spec is not None and time.monotonic() - self.spec.last_sound < 2.5

    def _watch(self):
        """Cheap 4 Hz check: start the fast timer when sound appears, refresh the labels."""
        active = self._active()
        if self.spec is not None:
            self.l_src.set_text(self._name(self.spec.sink) if active else "NO SIGNAL")
            self.l_db.set_text(f"{self.spec.db:+.0f} dB" if active else "")
        elif DEMO:
            self.l_src.set_text("BLUETOOTH")
            self.l_db.set_text("-14 dB")
        if (active or any(v > 0.01 for v in self.level) or any(v > 0.01 for v in self.peak)) and self.fast is None:
            self.fast = GLib.timeout_add(33, self._frame)
        return True

    def _target(self):
        if DEMO:  # made-up but plausible: bass hump, wandering mids, sparkly highs
            self.demo_t += 0.033
            t = self.demo_t
            n = Spectrum.BANDS
            return [max(0.04, min(1.0, 0.72 * math.exp(-((i - 4 - 3 * math.sin(t * 1.3)) / 7) ** 2)
                                  + 0.28 * abs(math.sin(t * 2.1 + i * 0.55)) * (1 - i / (n * 1.4))
                                  + 0.12 * abs(math.sin(t * 9 + i * 1.7)))) for i in range(n)]
        if self.spec is None or not self._active():
            return [0.0] * Spectrum.BANDS
        return [float(v) for v in self.spec.bands]

    def _frame(self):
        target = self._target()
        moving = False
        for i, tv in enumerate(target):
            lv = self.level[i]
            lv = lv + (tv - lv) * 0.6 if tv > lv else max(tv, lv - 0.045)  # fast attack, slow fall
            self.level[i] = lv
            if lv >= self.peak[i]:
                self.peak[i], self.peak_hold[i] = lv, 12
            elif self.peak_hold[i] > 0:
                self.peak_hold[i] -= 1
            else:
                self.peak[i] = max(0.0, self.peak[i] - 0.02)
            moving = moving or lv > 0.01 or self.peak[i] > 0.01
        self.da.queue_draw()
        if not moving and not self._active():
            self.fast = None
            return False
        return True

    def _draw(self, area, cr, w, h):
        n = Spectrum.BANDS
        gap = 1.5
        bw = (w - gap * (n - 1)) / n
        pitch = self.SEG + self.SGAP
        rows = max(int(h // pitch), 1)
        y0 = h - rows * pitch + self.SGAP  # snap the bottom to the segment grid
        cr.set_line_width(1)
        # faint baseline dots: the card looks alive even when nothing plays
        for i in range(n):
            setc(cr, CY, 0.22)
            cr.rectangle(i * (bw + gap), h - self.SEG, bw, self.SEG)
        cr.fill()
        lit = {CY: [], CYB: [], RED: [], FG: []}
        for i in range(n):
            x = i * (bw + gap)
            k = int(self.level[i] * rows)
            for r in range(k):
                frac = (r + 1) / rows
                col = RED if frac > 0.86 else (CYB if frac > 0.55 else CY)
                lit[col].append((x, h - (r + 1) * pitch + self.SGAP))
            pk = int(self.peak[i] * rows)
            if pk > k:
                lit[FG].append((x, h - pk * pitch + self.SGAP))
        for col, alpha in ((CY, 0.55), (CYB, 0.85), (RED, 0.95), (FG, 0.9)):
            for x, y in lit[col]:
                cr.rectangle(x, y, bw, self.SEG)
            setc(cr, col, alpha)
            cr.fill()

    def shutdown(self):
        if self.spec is not None:
            self.spec.stop()


# --------------------------------------------------------------------------------------------- glitch layer
class GlitchLayer(Gtk.Window):
    """Rare, brief "signal loss" bursts over the wallpaper: a fullscreen transparent click-through layer on BOTTOM.

    Every 20-50 s, for ~0.3 s: a few thin horizontal bands with an RGB split. Nothing is drawn (and nothing repaints)
    in between. Skipped while the laptop runs on battery."""

    def __init__(self, monitor=None):
        super().__init__()
        self.set_decorated(False)
        self.add_css_class("gw")
        LS.init_for_window(self)
        LS.set_namespace(self, "gits-glitch")
        LS.set_layer(self, LS.Layer.BOTTOM)
        for edge in (LS.Edge.TOP, LS.Edge.BOTTOM, LS.Edge.LEFT, LS.Edge.RIGHT):
            LS.set_anchor(self, edge, True)
        LS.set_exclusive_zone(self, -1)  # ignore the bar's reserved area: cover the whole output
        LS.set_keyboard_mode(self, LS.KeyboardMode.NONE)
        if monitor is not None:
            LS.set_monitor(self, monitor)
        self.bands = []
        self.frames = 0
        self.da = Gtk.DrawingArea()
        self.da.set_draw_func(self._draw)
        self.set_child(self.da)
        self.connect("map", lambda *_: self.get_surface().set_input_region(cairo.Region()))  # clicks pass through
        GLib.timeout_add(int(random.uniform(8, 20) * 1000), self._maybe_burst)

    @staticmethod
    def _on_battery():
        b = psutil.sensors_battery()
        return b is not None and b.power_plugged is False

    def _maybe_burst(self):
        if not self._on_battery() and not os.path.exists(os.path.join(STATE_DIR, "no-glitch")):
            self.frames = 7
            GLib.timeout_add(45, self._frame)
        GLib.timeout_add(int(random.uniform(20, 50) * 1000), self._maybe_burst)
        return False

    def _frame(self):
        w, h = self.da.get_width(), self.da.get_height()
        self.frames -= 1
        self.bands = []
        if self.frames > 0 and w > 0 and h > 0:
            for _ in range(random.randint(3, 8)):
                bh = random.choice((1, 1, 2, 2, 3, 5, 9, 18, 34))
                bw = random.uniform(0.15, 1.0) * w
                self.bands.append((random.uniform(0, w - bw), random.uniform(0, h), bw, bh, random.uniform(3, 14),
                                   random.random()))
        self.da.queue_draw()
        return self.frames > 0

    def _draw(self, area, cr, w, h):
        cr.set_operator(cairo.OPERATOR_CLEAR)
        cr.paint()
        cr.set_operator(cairo.OPERATOR_OVER)
        for x, y, bw, bh, dx, r in self.bands:
            setc(cr, RED, 0.16)  # RGB split: red one way, cyan the other, a pale core between
            cr.rectangle(x - dx, y, bw, bh)
            cr.fill()
            setc(cr, CY, 0.22)
            cr.rectangle(x + dx, y, bw, bh)
            cr.fill()
            if r > 0.6:
                setc(cr, FG, 0.28)
                cr.rectangle(x, y + bh * 0.35, bw * 0.6, max(1, bh * 0.3))
                cr.fill()


# --------------------------------------------------------------------------------------------- network
def human_rate(bps):
    for unit, div in (("GB/s", 2**30), ("MB/s", 2**20), ("KB/s", 2**10)):
        if bps >= div:
            v = bps / div
            return f"{v:.1f} {unit}" if v < 100 else f"{v:.0f} {unit}"
    return f"{bps:.0f} B/s"


class NetCard(Card):
    """Throughput (psutil deltas every 2 s), plus SSID / signal / IP looked up off the main thread every 10 s."""
    SKIP = ("lo", "docker", "veth", "br-", "virbr", "vboxnet")

    def __init__(self, app, **kw):
        super().__init__(app, "NET.LINK // 通信", **kw)
        self.down = collections.deque([0.0] * Stats.N, maxlen=Stats.N)
        self.up = collections.deque([0.0] * Stats.N, maxlen=Stats.N)
        self.last = None  # (monotonic, rx, tx)
        self.info, self.info_at, self.looking = "NO LINK", 0.0, False
        row = Gtk.Box(spacing=8)
        self.l_down = label("↓ 0 B/s", "n-down")
        self.l_up = label("↑ 0 B/s", "n-up", 1.0)
        self.l_down.set_hexpand(True)
        row.append(self.l_down)
        row.append(self.l_up)
        self.body.append(row)
        self.l_meta = label("", "n-meta", ellipsize=True)
        self.body.append(self.l_meta)
        self.da = self.area(self._draw)
        self.da.set_vexpand(True)
        self.body.append(self.da)
        self.update()

    def _totals(self):
        rx = tx = 0
        for name, c in psutil.net_io_counters(pernic=True).items():
            if not name.startswith(self.SKIP):
                rx, tx = rx + c.bytes_recv, tx + c.bytes_sent
        return rx, tx

    def _lookup(self):
        """SSID + signal from NetworkManager, else the busiest interface's IPv4 address."""
        def work():
            info = "NO LINK"
            if DEMO:
                GLib.idle_add(lambda: (setattr(self, "info", "SECTION9 · 87% · 10.9.0.5"), setattr(self, "looking", False),
                                       self.l_meta.set_text("SECTION9 · 87% · 10.9.0.5"), False)[-1])
                return
            try:
                out = subprocess.run(["nmcli", "-t", "-f", "ACTIVE,SSID,SIGNAL", "dev", "wifi"],
                                     capture_output=True, text=True, timeout=4).stdout
                wifi = next((ln.split(":") for ln in out.splitlines() if ln.startswith("yes:")), None)
                ip = ""
                stats = psutil.net_if_stats()
                for name, addrs in psutil.net_if_addrs().items():
                    if name.startswith(self.SKIP) or not stats.get(name, None) or not stats[name].isup:
                        continue
                    v4 = next((a.address for a in addrs if a.family.name == "AF_INET"), "")
                    if v4 and (not ip or name.startswith(("wl", "en", "tun", "wg"))):
                        ip = v4
                parts = []
                if wifi and len(wifi) >= 3:
                    parts += [wifi[-2].upper() or "WIFI", f"{wifi[-1]}%"]
                if ip:
                    parts.append(ip)
                if parts:
                    info = " · ".join(parts)
            except (OSError, subprocess.SubprocessError, ValueError):
                pass

            def done():
                self.info, self.looking = info, False
                self.l_meta.set_text(info)
                return False

            GLib.idle_add(done)

        self.looking = True
        threading.Thread(target=work, daemon=True).start()

    def update(self):
        now = GLib.get_monotonic_time() / 1e6
        rx, tx = self._totals()
        if self.last:
            dt = max(now - self.last[0], 0.1)
            self.down.append(max(rx - self.last[1], 0) / dt)
            self.up.append(max(tx - self.last[2], 0) / dt)
        self.last = (now, rx, tx)
        self.l_down.set_text("↓ " + human_rate(self.down[-1]))
        self.l_up.set_text("↑ " + human_rate(self.up[-1]))
        if not self.looking and now - self.info_at > 10:
            self.info_at = now
            self._lookup()
        self.da.queue_draw()

    def _draw(self, area, cr, w, h):
        peak = max(max(self.down), max(self.up), 100 * 1024)  # floor: idle noise stays flat
        n = len(self.down)
        setc(cr, CY, 0.12)
        cr.set_line_width(1)
        cr.set_dash([2, 3])
        y = round(h / 2) + 0.5
        cr.move_to(0, y)
        cr.line_to(w, y)
        cr.stroke()
        cr.set_dash([])

        def pts(hist):
            return [(i * w / (n - 1), h - 1 - (h - 3) * v / peak) for i, v in enumerate(hist)]

        up = pts(self.up)
        setc(cr, FG, 0.75)
        cr.set_dash([4, 3])
        cr.move_to(*up[0])
        for p in up[1:]:
            cr.line_to(*p)
        cr.stroke()
        cr.set_dash([])
        dn = pts(self.down)
        cr.move_to(dn[0][0], h)
        for p in dn:
            cr.line_to(*p)
        cr.line_to(dn[-1][0], h)
        cr.close_path()
        setc(cr, CY, 0.2)
        cr.fill()
        cr.set_line_width(1.5)
        setc(cr, CYB)
        cr.move_to(*dn[0])
        for p in dn[1:]:
            cr.line_to(*p)
        cr.stroke()


# --------------------------------------------------------------------------------------------- to-do
class TodoCard(Card):
    def __init__(self, app, **kw):
        super().__init__(app, "TASK.QUEUE // 任務", keyboard=True, **kw)
        self.path = os.path.join(STATE_DIR, "todo.json")
        self.items = []
        try:
            with open(self.path) as f:
                self.items = [{"t": str(i["t"]), "d": bool(i["d"])} for i in json.load(f)]
        except (OSError, ValueError, KeyError, TypeError):
            pass
        if DEMO:
            self.items = [{"t": "Trace the Puppet Master", "d": False}, {"t": "Patch the mainframe", "d": True},
                          {"t": "Water the ferns", "d": False}]
        self.count = label("", "t-count")
        self.body.append(self.count)
        self.rows = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        sc = Gtk.ScrolledWindow()
        sc.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        sc.set_vexpand(True)
        sc.set_child(self.rows)
        self.body.append(sc)
        self.entry = Gtk.Entry(placeholder_text="+ add an item")
        self.entry.add_css_class("t-entry")
        self.entry.connect("activate", self.add)
        self.body.append(self.entry)
        self.render()

    def save(self):
        try:
            os.makedirs(STATE_DIR, exist_ok=True)
            with open(self.path + ".tmp", "w") as f:
                json.dump(self.items, f, ensure_ascii=False, indent=1)
            os.replace(self.path + ".tmp", self.path)
        except OSError:
            pass

    def add(self, entry):
        t = entry.get_text().strip()
        if t:
            self.items.append({"t": t, "d": False})
            entry.set_text("")
            self.save()
            self.render()

    def toggle(self, i):
        self.items[i]["d"] = not self.items[i]["d"]
        self.save()
        self.render()

    def remove(self, i):
        del self.items[i]
        self.save()
        self.render()

    def render(self):
        child = self.rows.get_first_child()
        while child:
            nxt = child.get_next_sibling()
            self.rows.remove(child)
            child = nxt
        done = sum(1 for i in self.items if i["d"])
        self.count.set_text(f"{done} OF {len(self.items)} DONE" if self.items else "QUEUE EMPTY")
        for idx, it in enumerate(self.items):
            row = Gtk.Box(spacing=8)
            row.add_css_class("t-row")
            box = Gtk.DrawingArea()
            box.set_content_width(14)
            box.set_content_height(14)
            box.set_valign(Gtk.Align.CENTER)
            box.set_draw_func(self._draw_box, it["d"])
            box.set_cursor(Gdk.Cursor.new_from_name("pointer"))
            g = Gtk.GestureClick()
            g.connect("released", lambda *_, idx=idx: self.toggle(idx))
            box.add_controller(g)
            text = label(it["t"], "t-text t-done" if it["d"] else "t-text", ellipsize=True)
            text.set_hexpand(True)
            x = label("×", "t-x", 0.5)
            x.set_cursor(Gdk.Cursor.new_from_name("pointer"))
            g2 = Gtk.GestureClick()
            g2.connect("released", lambda *_, idx=idx: self.remove(idx))
            x.add_controller(g2)
            for wdg in (box, text, x):
                row.append(wdg)
            self.rows.append(row)

    @staticmethod
    def _draw_box(area, cr, w, h, done):
        setc(cr, CY, 0.9)
        cr.set_line_width(1)
        cr.rectangle(0.5, 0.5, w - 1, h - 1)
        cr.stroke()
        if done:
            setc(cr, CY)
            cr.rectangle(3, 3, w - 6, h - 6)
            cr.fill()


# --------------------------------------------------------------------------------------------- application
class App:
    """Plain windows + GLib main loop (a Gtk.Application blocks on its D-Bus registration in this session)."""

    def __init__(self):
        self.cards = []
        self.stats = None
        self.loop = GLib.MainLoop()

    def pick_monitor(self):
        """The main monitor, chosen like hypr/gits/monitors.lua does: named one, else eDP, else the largest (ties: leftmost)."""
        mons = Gdk.Display.get_default().get_monitors()
        want = os.environ.get("GITS_WIDGETS_MONITOR") or os.environ.get("GITS_MAIN_MONITOR", "")
        items = [mons.get_item(i) for i in range(mons.get_n_items())]
        if not items:
            return None

        def rank(m):
            conn, g = m.get_connector() or "", m.get_geometry()
            return (0 if want and conn == want else 1 if not want and conn.startswith("eDP") else 2, -g.width * g.height, g.x)
        return min(items, key=rank)

    def start(self):
        css = Gtk.CssProvider()
        css.load_from_path(os.path.join(HERE, "style.css"))
        Gtk.StyleContext.add_provider_for_display(Gdk.Display.get_default(), css,
                                                  Gtk.STYLE_PROVIDER_PRIORITY_USER)
        mon = self.pick_monitor()
        self.stats = Stats()
        if not DEMO and os.environ.get("GITS_WIDGETS_GLITCH", "1") != "0":
            self.cards.append(GlitchLayer(mon))  # first: layers of one level stack by creation order, cards go on top
        m, gap, top = 20, 12, 14  # screen margin, gap between cards, distance below the bar
        LW, MW, RW = 220, 236, 264  # left / middle / right column widths

        def add(cls, x, y, w, h, right=False, **kw):
            c = cls(self, x=x, y=y, w=w, h=h, right=right, monitor=mon, **kw)
            self.cards.append(c)
            return c

        y = top
        add(ClockCard, m, y, LW, 226)
        y += 226 + gap
        add(CalendarCard, m, y, LW, 236)
        if np is not None:
            y += 236 + gap
            add(AudioCard, m, y, LW, 160)
        x2 = m + LW + gap
        y = top
        add(MediaCard, x2, y, MW, 372)
        y += 372 + gap
        add(WeatherCard, x2, y, MW, 108)
        y += 108 + gap
        add(NetCard, x2, y, MW, 132)
        y = top
        bats = sorted(glob.glob("/sys/class/power_supply/BAT*"))
        if bats:
            add(BatteryCard, m, y, RW, 92, right=True, bat=bats[0])
            y += 92 + gap
        add(RingsCard, m, y, RW, 132, right=True, stats=self.stats)
        y += 132 + gap
        add(GraphCard, m, y, RW, 132, right=True, stats=self.stats)
        y += 132 + gap
        add(TodoCard, m, y, RW, 250, right=True)

        for c in self.cards:
            c.present()
        GLib.timeout_add_seconds(1, self.tick1)
        GLib.timeout_add_seconds(2, self.tick2)

    def tick1(self):
        for c in self.cards:
            if isinstance(c, (ClockCard, CalendarCard, MediaCard)):
                c.update()
        return True

    def tick2(self):
        self.stats.refresh()
        for c in self.cards:
            if isinstance(c, (RingsCard, GraphCard, BatteryCard, WeatherCard, NetCard)):
                c.update()
        return True


def main():
    if not LS.is_supported():
        print("gits-widgets: compositor has no wlr-layer-shell (or gtk4-layer-shell was not preloaded)", file=sys.stderr)
        return 1
    app = App()
    app.start()
    for sig in (2, 15):  # SIGINT, SIGTERM
        GLibUnix.signal_add(GLib.PRIORITY_DEFAULT, sig, lambda: (app.loop.quit(), False)[1])
    app.loop.run()
    for c in app.cards:
        getattr(c, "shutdown", lambda: None)()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
