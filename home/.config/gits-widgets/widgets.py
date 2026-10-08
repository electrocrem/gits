#!/usr/bin/env python3
"""Ghost in the Shell desktop widgets.

GTK4 + gtk4-layer-shell, one process, one layer-shell window per card on the BOTTOM layer (above the
wallpaper, below every window; BACKGROUND would be covered by a later-started wallpaper daemon). Cards: clock, calendar, media player (playerctl), weather (wttr.in),
battery, CPU/RAM/SSD rings, CPU/RAM history graph, network throughput, audio spectrum (parec + numpy), to-do list, a journal feed
(SYS.LOG), a home server over ssh with its services, torrents (qBittorrent) and streams (Jellyfin).

Env: GITS_WEATHER_LOCATION  city for wttr.in (default: auto-detect by IP; "off" disables the request)
     GITS_WIDGETS_MONITOR   connector name to place the cards on (default: the main monitor, as in hypr/gits/monitors.lua:
                            GITS_MAIN_MONITOR, else a laptop panel (eDP), else the largest one)
     GITS_WIDGETS_GLITCH    0 = no wallpaper glitch bursts (default: on, only while on AC power)
     GITS_WIDGETS_SECOND    0 = nothing on the other monitors (default: clock, calendar, system rings / graph, network,
                            GPU, disks and the busiest processes there)
     GITS_SERVER            ssh destination of a home server (a Host from ~/.ssh/config or user@host; key login, python3 on it):
                            adds the NODE.LINK card with its CPU / RAM / temperature, disks and Docker containers, SERVICES
                            (container lights, Pi-hole) and, when set up in ~/.config/gits/server.env on the server (see
                            SERVER_PROBE), TORRENT.LINK and NOW.WATCHING (default: none)
     GITS_SERVER_NAME       the name on that card (default: the server's hostname)
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
# --------------------------------------------------------------------------------------------- gpu / disks / top (the other monitors)
def draw_meter(cr, x, y, w, h, frac, hot=False):
    """A thin segmented bar, like the battery one."""
    n, gap = max(int(w // 9), 4), 2
    sw = (w - gap * (n - 1)) / n
    for i in range(n):
        if (i + 0.5) / n <= frac:
            setc(cr, RED if hot else CY)
        else:
            setc(cr, CY, 0.16)
        cr.rectangle(x + i * (sw + gap), y, sw, h)
        cr.fill()


def gpu_sample():
    """(name, temp °C, load %, vram used MiB, vram total MiB, watts) of the NVIDIA card while it is awake, else of an AMD GPU
    from sysfs; None without either. An asleep dGPU is not queried: nvidia-smi would wake it (as in waybar's gits-gpu.sh)."""
    for d in glob.glob("/sys/bus/pci/devices/*"):
        try:
            with open(d + "/vendor") as f, open(d + "/class") as g:
                if f.read().strip() != "0x10de" or not g.read().startswith("0x03"):
                    continue
            with open(d + "/power/runtime_status") as f:
                if f.read().strip() != "active":
                    break
            out = subprocess.run(["nvidia-smi", "--query-gpu=name,temperature.gpu,utilization.gpu,memory.used,memory.total,power.draw",
                                  "--format=csv,noheader,nounits"], capture_output=True, text=True, timeout=4).stdout
            name, *nums = [x.strip() for x in out.splitlines()[0].split(",")]
            t, u, mu, mt, pw = (float(x) if x.replace(".", "", 1).isdigit() else 0.0 for x in nums)
            return name.replace("NVIDIA GeForce ", ""), t, u, mu, mt, pw
        except (OSError, subprocess.SubprocessError, IndexError, ValueError):
            break
    for dev in glob.glob("/sys/class/drm/card*/device"):
        try:
            with open(dev + "/gpu_busy_percent") as f:
                u = float(f.read())
            rd = lambda n: float(open(os.path.join(dev, n)).read()) / 2**20
            mu, mt = rd("mem_info_vram_used"), rd("mem_info_vram_total")
            t = 0.0
            for h in glob.glob(dev + "/hwmon/hwmon*/temp1_input"):
                t = float(open(h).read()) / 1000
            return "RADEON", t, u, mu, mt, 0.0
        except (OSError, ValueError):
            continue
    return None


class GpuCard(Card):
    def __init__(self, app, **kw):
        super().__init__(app, "GPU.CORE // 演算", **kw)
        self.data, self.busy = None, False
        self.load = collections.deque([0.0] * Stats.N, maxlen=Stats.N)
        head = Gtk.Box(spacing=8)
        self.l_name = label("GPU ASLEEP", "g-cpu", ellipsize=True)
        self.l_name.set_hexpand(True)
        self.l_temp = label("", "g-ram", 1.0)
        head.append(self.l_name)
        head.append(self.l_temp)
        self.body.append(head)
        self.l_meta = label("", "n-meta")
        self.body.append(self.l_meta)
        self.da = self.area(self._draw)
        self.da.set_vexpand(True)
        self.body.append(self.da)
        self.update()

    def update(self):
        if self.busy:
            return
        self.busy = True

        def work():
            d = gpu_sample()

            def done():
                self.data, self.busy = d, False
                self.load.append(d[2] if d else 0.0)
                if d:
                    name, t, u, mu, mt, pw = d
                    self.l_name.set_text(f"{name.upper()}  {u:.0f}%")
                    self.l_temp.set_text(f"{t:.0f}°C")
                    self.l_meta.set_text(f"VRAM {mu / 1024:.1f}/{mt / 1024:.0f} GB" + (f" · {pw:.0f} W" if pw else ""))
                else:
                    self.l_name.set_text("GPU ASLEEP")
                    self.l_temp.set_text("")
                    self.l_meta.set_text("not polled: that would wake it")
                self.da.queue_draw()
                return False

            GLib.idle_add(done)

        threading.Thread(target=work, daemon=True).start()

    def _draw(self, area, cr, w, h):
        d = self.data
        draw_meter(cr, 0, 0, w, 5, (d[3] / d[4]) if d and d[4] else 0.0, hot=bool(d) and d[4] and d[3] / d[4] > 0.9)
        gh = h - 10
        hist = list(self.load)
        pts = [(i * w / (len(hist) - 1), h - 1 - (gh - 2) * min(v, 100) / 100) for i, v in enumerate(hist)]
        cr.move_to(pts[0][0], h)
        for p in pts:
            cr.line_to(*p)
        cr.line_to(pts[-1][0], h)
        cr.close_path()
        setc(cr, CY, 0.2)
        cr.fill()
        cr.set_line_width(1.5)
        setc(cr, RED if d and d[1] >= 85 else CYB)
        cr.move_to(*pts[0])
        for p in pts[1:]:
            cr.line_to(*p)
        cr.stroke()


class DiskCard(Card):
    """Real filesystems (one row per device, btrfs subvolumes folded) with a fill bar, plus read / write speed."""
    FS = ("ext4", "btrfs", "xfs", "f2fs", "ntfs", "ntfs3", "exfat", "vfat", "zfs", "bcachefs")

    def __init__(self, app, **kw):
        super().__init__(app, "STORAGE // 記憶", **kw)
        self.rows, self.last = [], None
        row = Gtk.Box(spacing=8)
        self.l_read = label("R 0 B/s", "n-down")
        self.l_read.set_hexpand(True)
        self.l_write = label("W 0 B/s", "n-up", 1.0)
        row.append(self.l_read)
        row.append(self.l_write)
        self.body.append(row)
        self.da = self.area(self._draw)
        self.da.set_vexpand(True)
        self.body.append(self.da)
        self.update()

    def update(self):
        rows, seen = [], set()
        for p in psutil.disk_partitions(all=False):
            if p.fstype not in self.FS or p.device in seen or p.mountpoint.startswith(("/boot", "/efi", "/snap", "/var/lib")):
                continue
            seen.add(p.device)
            try:
                u = psutil.disk_usage(p.mountpoint)
            except OSError:
                continue
            if u.total >= 2**30:
                rows.append((p.mountpoint, u.percent, u.free / 2**30))
        self.rows = sorted(rows, key=lambda r: (r[0] != "/", r[0]))[:4]
        io, now = psutil.disk_io_counters(), time.monotonic()
        if io and self.last:
            dt = max(now - self.last[0], 0.1)
            self.l_read.set_text("R " + human_rate((io.read_bytes - self.last[1]) / dt))
            self.l_write.set_text("W " + human_rate((io.write_bytes - self.last[2]) / dt))
        if io:
            self.last = (now, io.read_bytes, io.write_bytes)
        self.da.queue_draw()

    def _draw(self, area, cr, w, h):
        if not self.rows:
            return
        step = h / len(self.rows)
        for i, (mnt, pct, free) in enumerate(self.rows):
            y = i * step
            name = mnt if len(mnt) <= 14 else "…" + mnt[-13:]
            draw_text(cr, name.upper(), 0, y + 10, 9, FG, bold=True)
            draw_text(cr, f"{pct:.0f}% · {free:.0f}G FREE", w, y + 10, 9, DIM, bold=True, align="right")
            draw_meter(cr, 0, y + 15, w, 5, pct / 100, hot=pct >= 90)


class TopCard(Card):
    """The busiest processes by CPU (share of the whole machine), refreshed off the main thread."""
    N = 5

    def __init__(self, app, **kw):
        super().__init__(app, "PROC.TOP // 処理", **kw)
        self.rows, self.busy = [], False
        self.ncpu = psutil.cpu_count() or 1
        self.da = self.area(self._draw)
        self.da.set_vexpand(True)
        self.body.append(self.da)
        self.update()

    def update(self):
        if self.busy:
            return
        self.busy = True

        def work():
            rows = []
            for p in psutil.process_iter(["name", "memory_info"]):  # process_iter keeps the Process objects: cpu_percent has a baseline
                try:
                    c = p.cpu_percent(None) / self.ncpu
                    rows.append((c, p.info["name"] or "?", (p.info["memory_info"].rss if p.info["memory_info"] else 0) / 2**20))
                except (psutil.Error, OSError):
                    pass
            rows.sort(reverse=True)

            def done():
                self.rows, self.busy = rows[:self.N], False
                self.da.queue_draw()
                return False

            GLib.idle_add(done)

        threading.Thread(target=work, daemon=True).start()

    def _draw(self, area, cr, w, h):
        step = h / self.N
        for i, (c, name, mem) in enumerate(self.rows):
            y = i * step + step / 2 + 4
            setc(cr, RED if c >= 50 else CY, 0.14 + 0.5 * min(c, 100) / 100)
            cr.rectangle(0, y - 11, w * min(c, 100) / 100, 15)
            cr.fill()
            draw_text(cr, name[:18].upper(), 4, y, 10, FG if i == 0 else MID, bold=i == 0)
            draw_text(cr, f"{c:4.1f}%  {mem:5.0f}M", w - 4, y, 10, CYB if i == 0 else DIM, bold=True, align="right")


# --------------------------------------------------------------------------------------------- remote server (GITS_SERVER)
# Sent to the server over ssh and run there by `python3 -` (stdlib only, nothing is installed): one JSON line every 2 s.
# Docker is polled every 10 s with `docker`, else `sudo -n docker`; without either the card just has no container line.
# Optional services, read from ~/.config/gits/server.env ON THE SERVER (KEY=value lines; the secrets never leave it):
#   GITS_QBIT_URL=http://localhost:8080   [GITS_QBIT_USER, GITS_QBIT_PASS]   -> TORRENT.LINK
#   GITS_JELLYFIN_URL=http://localhost:8096   GITS_JELLYFIN_KEY=<api key>   -> NOW.WATCHING
#   GITS_PIHOLE_URL=http://localhost   GITS_PIHOLE_PASS or GITS_PIHOLE_PASS_FILE (Pi-hole v6; its cli_pw works) -> SERVICES
# A service that is not configured sends null and its card stays hidden.
SERVER_PROBE = r'''
import http.cookiejar, json, os, subprocess, time, urllib.error, urllib.parse, urllib.request
FS = {"ext4", "btrfs", "xfs", "f2fs", "vfat", "exfat", "ntfs3", "zfs", "bcachefs"}
SKIP = ("lo", "docker", "veth", "br-", "virbr")
def cpu():
    with open("/proc/stat") as f:
        v = [int(x) for x in f.readline().split()[1:]]
    return sum(v), v[3] + v[4]
def net():
    rx = tx = 0
    with open("/proc/net/dev") as f:
        for ln in f.readlines()[2:]:
            name, rest = ln.split(":", 1)
            if not name.strip().startswith(SKIP):
                c = rest.split()
                rx, tx = rx + int(c[0]), tx + int(c[8])
    return rx, tx
def run(cmd):
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
        return p.stdout if p.returncode == 0 else None
    except (OSError, subprocess.SubprocessError):
        return None
def slow():
    fmt = "{{.Names}}\t{{.State}}\t{{.Status}}"
    out = run(["docker", "ps", "-a", "--format", fmt])
    if out is None:
        out = run(["sudo", "-n", "docker", "ps", "-a", "--format", fmt])
    dk = None
    if out is not None:  # [name, state, health]: health is healthy / unhealthy / starting / "" (no healthcheck)
        dk = []
        for ln in out.splitlines():
            c = ln.split("\t")
            if len(c) == 3:
                h = next((x for x in ("unhealthy", "healthy", "starting") if "(" + x in c[2]), "")
                dk.append([c[0], c[1], h])
        dk.sort()
    th = run(["vcgencmd", "get_throttled"])
    return dk, (th.strip().split("=")[-1] if th else None)
ENV = {}
try:
    with open(os.path.expanduser("~/.config/gits/server.env")) as f:
        for ln in f:
            ln = ln.strip()
            if ln and not ln.startswith("#") and "=" in ln:
                k, v = ln.split("=", 1)
                ENV[k.strip()] = v.strip().strip("\"'")
except OSError:
    pass
def fetch(url, data=None, headers=None, opener=None, method=None):
    req = urllib.request.Request(url, data=data, headers=headers or {}, method=method)
    with (opener.open(req, timeout=4) if opener else urllib.request.urlopen(req, timeout=4)) as r:
        body = r.read()
    return json.loads(body) if body[:1] in (b"{", b"[") else body.decode("utf-8", "replace")
QB = ENV.get("GITS_QBIT_URL", "").rstrip("/")
qb_jar = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
DL = ("downloading", "forcedDL", "metaDL", "forcedMetaDL", "stalledDL", "queuedDL", "checkingDL", "allocating")
def qbit():
    for attempt in (0, 1):
        try:
            info = fetch(QB + "/api/v2/transfer/info", opener=qb_jar)
            ts = fetch(QB + "/api/v2/torrents/info?sort=added_on&reverse=true", opener=qb_jar)
            break
        except urllib.error.HTTPError as e:
            if e.code not in (401, 403) or attempt or not ENV.get("GITS_QBIT_USER"):
                return {"error": "HTTP %d" % e.code}
            try:
                fetch(QB + "/api/v2/auth/login", opener=qb_jar, headers={"Referer": QB}, data=urllib.parse.urlencode(
                    {"username": ENV["GITS_QBIT_USER"], "password": ENV.get("GITS_QBIT_PASS", "")}).encode())
            except (OSError, ValueError):
                return {"error": "LOGIN FAILED"}
        except (OSError, ValueError):
            return {"error": "NO ANSWER"}
    ts.sort(key=lambda t: (t.get("state") not in DL, t.get("dlspeed", 0) <= 0, -t.get("added_on", 0)))  # moving ones first
    return {"dl": info.get("dl_info_speed", 0), "up": info.get("up_info_speed", 0),
            "n": len(ts), "active": sum(t.get("state") in DL for t in ts),
            "seed": sum(t.get("state") in ("uploading", "stalledUP", "forcedUP") for t in ts),
            "list": [[t.get("name", ""), t.get("progress", 0), t.get("dlspeed", 0), t.get("eta", 0), t.get("state", ""),
                      t.get("size", 0)] for t in ts[:5]]}
JF, JK = ENV.get("GITS_JELLYFIN_URL", "").rstrip("/"), ENV.get("GITS_JELLYFIN_KEY", "")
jf = {"user": None, "latest": []}
def jellyfin(with_latest):
    h = {"Authorization": 'MediaBrowser Token="%s"' % JK}
    try:
        playing = []
        for se in fetch(JF + "/Sessions?activeWithinSeconds=960", headers=h):
            it = se.get("NowPlayingItem")
            if not it:
                continue
            ps = se.get("PlayState") or {}
            title = it.get("Name", "")
            if it.get("SeriesName"):
                title = "%s · S%02dE%02d" % (it["SeriesName"], it.get("ParentIndexNumber") or 0, it.get("IndexNumber") or 0)
            playing.append([se.get("UserName") or "?", title, se.get("DeviceName") or se.get("Client") or "",
                            (ps.get("PositionTicks") or 0) / 1e7, (it.get("RunTimeTicks") or 0) / 1e7, bool(ps.get("IsPaused"))])
        if with_latest:
            if jf["user"] is None:
                users = fetch(JF + "/Users", headers=h)
                jf["user"] = next((u["Id"] for u in users if (u.get("Policy") or {}).get("IsAdministrator")),
                                  users[0]["Id"] if users else "")
            items = fetch(JF + "/Items/Latest?" + urllib.parse.urlencode({"userId": jf["user"], "limit": 6}), headers=h)
            jf["latest"] = [[i.get("SeriesName") or i.get("Name", ""), i.get("Type", ""), i.get("ProductionYear") or ""]
                            for i in items]
        return {"playing": playing, "latest": jf["latest"]}
    except urllib.error.HTTPError as e:
        return {"error": "HTTP %d" % e.code}
    except (OSError, ValueError, KeyError, IndexError):
        return {"error": "NO ANSWER"}
PH = ENV.get("GITS_PIHOLE_URL", "").rstrip("/")
ph = {"sid": None}
def pihole():
    for attempt in (0, 1):
        try:
            q = fetch(PH + "/api/stats/summary", headers={"X-FTL-SID": ph["sid"]} if ph["sid"] else {})["queries"]
            return {"total": q["total"], "blocked": q["blocked"], "pct": q["percent_blocked"]}
        except urllib.error.HTTPError as e:
            if e.code != 401 or attempt:
                return {"error": "HTTP %d" % e.code}
            pw = ENV.get("GITS_PIHOLE_PASS", "")
            try:
                if not pw and ENV.get("GITS_PIHOLE_PASS_FILE"):
                    with open(os.path.expanduser(ENV["GITS_PIHOLE_PASS_FILE"])) as f:
                        pw = f.read().strip()
                r = fetch(PH + "/api/auth", data=json.dumps({"password": pw}).encode(), headers={"Content-Type": "application/json"})
                ph["sid"] = (r.get("session") or {}).get("sid")
            except (OSError, ValueError, AttributeError):
                return {"error": "LOGIN FAILED"}
        except (OSError, ValueError, KeyError, TypeError):
            return {"error": "NO ANSWER"}
host = os.uname().nodename
t0, i0 = cpu()
n0, s0 = net(), time.monotonic()
docker, throttled, k = None, None, 0
torrents = media = dns = None
while True:
    time.sleep(2)
    if k % 5 == 0:
        docker, throttled = slow()
    if QB and k % 2 == 0:
        torrents = qbit()
    if JF and JK and k % 3 == 0:
        media = jellyfin(k % 30 == 0)
    if PH and k % 15 == 0:
        dns = pihole()
    k += 1
    t, i = cpu()
    c = 100 * (1 - (i - i0) / max(t - t0, 1))
    t0, i0 = t, i
    n, s = net(), time.monotonic()
    rx, tx = (max(n[0] - n0[0], 0) / (s - s0), max(n[1] - n0[1], 0) / (s - s0))
    n0, s0 = n, s
    mem = {}
    with open("/proc/meminfo") as f:
        for ln in f:
            key, val = ln.split(":")
            mem[key] = int(val.split()[0])
    try:
        with open("/sys/class/thermal/thermal_zone0/temp") as f:
            temp = int(f.read()) / 1000
    except (OSError, ValueError):
        temp = None
    with open("/proc/uptime") as f:
        up = float(f.read().split()[0])
    disks, seen = [], set()
    with open("/proc/mounts") as f:
        for ln in f:
            dev, mnt, fs = ln.split()[:3]
            mnt = mnt.replace("\\040", " ")
            if fs not in FS or dev in seen or mnt.startswith(("/boot", "/efi", "/snap", "/var/lib")):
                continue
            seen.add(dev)
            st = os.statvfs(mnt)
            total, free = st.f_blocks * st.f_frsize, st.f_bavail * st.f_frsize
            if total >= 2**30:
                disks.append([mnt, total, free])
    print(json.dumps({"host": host, "cpu": c, "ram": 100 * (1 - mem["MemAvailable"] / mem["MemTotal"]),
                      "ram_total": mem["MemTotal"] * 1024, "temp": temp, "up": up, "load": os.getloadavg()[0],
                      "rx": rx, "tx": tx, "disks": disks, "docker": docker, "throttled": throttled,
                      "qbit": torrents, "jellyfin": media, "pihole": dns}), flush=True)
'''


def fmt_uptime(sec):
    d, h, m = int(sec // 86400), int(sec % 86400 // 3600), int(sec % 3600 // 60)
    return f"{d}D {h:02d}H" if d else f"{h}H {m:02d}M"


class ServerLink(threading.Thread):
    """One long-lived `ssh <dest> python3 -` streaming SERVER_PROBE lines; reconnects with a growing pause."""

    def __init__(self, dest):
        super().__init__(daemon=True)
        self.dest = dest
        self.data, self.seen, self.error = None, 0.0, "CONNECTING"
        self.cpu_hist = collections.deque([0.0] * Stats.N, maxlen=Stats.N)
        self.proc, self._quit = None, False

    def stop(self):
        self._quit = True
        if self.proc:
            self.proc.kill()

    def run(self):
        pause = 5
        while not self._quit:
            try:
                self.proc = subprocess.Popen(
                    ["ssh", "-T", "-o", "BatchMode=yes", "-o", "ConnectTimeout=6", "-o", "ServerAliveInterval=5",
                     "-o", "ServerAliveCountMax=2", self.dest, "python3", "-u", "-"],
                    stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                self.proc.stdin.write(SERVER_PROBE)
                self.proc.stdin.close()
                for line in self.proc.stdout:
                    try:
                        d = json.loads(line)
                    except ValueError:
                        continue
                    self.cpu_hist.append(d["cpu"])
                    self.data, self.seen, self.error, pause = d, time.monotonic(), "", 5
                err = self.proc.stderr.read().strip().splitlines()
                self.proc.wait()
                self.error = (err[-1] if err else f"ssh exited {self.proc.returncode}")[:60]
            except OSError as e:
                self.error = str(e)[:60]
            if self._quit:
                return
            time.sleep(pause)
            pause = min(pause * 2, 60)

    def online(self):
        return self.data is not None and time.monotonic() - self.seen < 8


class ServerCard(Card):
    """A home server over ssh (GITS_SERVER): CPU / RAM / temperature rings, a CPU trace, disks, Docker containers.

    Undervoltage / throttling (Raspberry Pi `vcgencmd get_throttled` != 0x0) turns the status red."""

    def __init__(self, app, dest, link, **kw):
        super().__init__(app, "NODE.LINK // 端末", **kw)
        self.link = link
        head = Gtk.Box(spacing=8)
        self.l_name = label(os.environ.get("GITS_SERVER_NAME", "") or dest.split("@")[-1].upper(), "n-down", ellipsize=True)
        self.l_name.set_hexpand(True)
        self.l_state = label("LINKING", "s-state", 1.0)
        head.append(self.l_name)
        head.append(self.l_state)
        self.body.append(head)
        self.l_meta = label("", "n-meta", ellipsize=True)
        self.body.append(self.l_meta)
        self.da = self.area(self._draw)
        self.da.set_vexpand(True)
        self.body.append(self.da)
        self.l_docker = label("", "s-docker", ellipsize=True)
        self.body.append(self.l_docker)
        self.update()

    def _state(self):
        """(data or None, online, error, cpu history)"""
        if DEMO:
            t = time.monotonic()
            hist = [18 + 9 * math.sin((t - 2 * (Stats.N - i)) / 3) for i in range(Stats.N)]
            return demo_server(), True, "", hist
        ln = self.link
        return ln.data, ln.online(), ln.error, list(ln.cpu_hist)

    def update(self):
        d, online, err, _ = self._state()
        warn = online and d.get("throttled") not in (None, "0x0")
        self.l_state.set_text("UNDERVOLT" if warn else "ONLINE" if online else "OFFLINE")
        (self.l_state.add_css_class if warn or not online else self.l_state.remove_css_class)("bad")
        if d and not os.environ.get("GITS_SERVER_NAME"):
            self.l_name.set_text(d["host"].upper())
        if online:
            self.l_meta.set_text(f"UP {fmt_uptime(d['up'])} · ↓{human_rate(d['rx'])} ↑{human_rate(d['tx'])}")
        else:
            self.l_meta.set_text(err.upper() if err else "NO SIGNAL")
        dk = d.get("docker") if d else None
        if online and dk is not None:
            down = [e[0] for e in dk if e[1] != "running"]
            up = len(dk) - len(down)
            self.l_docker.set_text(f"DOCKER {up}/{len(dk)} UP" + (" · DOWN: " + ", ".join(down).upper() if down else ""))
            (self.l_docker.add_css_class if down else self.l_docker.remove_css_class)("bad")
        else:
            self.l_docker.set_text("")
        self.da.queue_draw()

    def _draw(self, area, cr, w, h):
        d, online, _, hist = self._state()
        a = 1.0 if online else 0.35  # a lost link keeps the last numbers, dimmed
        temp = (d or {}).get("temp")
        items = (("CPU", (d or {}).get("cpu", 0.0), f"{(d or {}).get('cpu', 0.0):.0f}%", 85),
                 ("RAM", (d or {}).get("ram", 0.0), f"{(d or {}).get('ram', 0.0):.0f}%", 85),
                 ("TEMP", (temp or 0.0) / 90 * 100, f"{temp:.0f}°" if temp is not None else "--", 75 / 90 * 100))
        cell = w / 3
        r = min(cell / 2 - 10, 26)
        a0, sweep = math.radians(135), math.radians(270)
        for i, (name, v, txt, hot) in enumerate(items):
            cx, cy = cell * i + cell / 2, r + 3
            cr.set_line_width(4)
            setc(cr, CY, 0.16)
            cr.arc(cx, cy, r, a0, a0 + sweep)
            cr.stroke()
            setc(cr, RED if v >= hot else CY, a)
            cr.arc(cx, cy, r, a0, a0 + sweep * min(max(v, 0), 100) / 100)
            cr.stroke()
            draw_text(cr, txt, cx, cy + 4, 11, FG, bold=True, align="center", alpha=a)
            draw_text(cr, name, cx, cy + r + 8, 8, DIM, bold=True, align="center")
        # CPU trace
        gy, gh = 2 * r + 20, 26
        pts = [(i * w / (len(hist) - 1), gy + gh - 1 - (gh - 2) * min(v, 100) / 100) for i, v in enumerate(hist)]
        cr.move_to(pts[0][0], gy + gh)
        for p in pts:
            cr.line_to(*p)
        cr.line_to(pts[-1][0], gy + gh)
        cr.close_path()
        setc(cr, CY, 0.18 * a)
        cr.fill()
        cr.set_line_width(1.2)
        setc(cr, CYB, a)
        cr.move_to(*pts[0])
        for p in pts[1:]:
            cr.line_to(*p)
        cr.stroke()
        # disks
        disks = (d or {}).get("disks") or []
        y = gy + gh + 8
        step = min(24, (h - y) / max(len(disks), 1))
        for mnt, total, free in disks[:max(int((h - y) // 20), 0)]:
            pct = 100 * (1 - free / total) if total else 0
            name = mnt if len(mnt) <= 12 else "…" + mnt[-11:]
            draw_text(cr, name.upper(), 0, y + 9, 9, FG, bold=True, alpha=a)
            draw_text(cr, f"{pct:.0f}% · {free / 2**30:.0f}G FREE", w, y + 9, 9, DIM, bold=True, align="right")
            draw_meter(cr, 0, y + 13, w, 4, pct / 100, hot=pct >= 90)
            y += step



def demo_server():
    """Made-up server data for GITS_WIDGETS_DEMO (screenshots)."""
    t = time.monotonic()
    names = ["filebrowser", "homepage", "jellyfin", "navidrome", "pihole", "portainer", "qbittorrent", "syncthing",
             "uptime-kuma", "vaultwarden"]
    return {"host": "tachikoma", "cpu": 18 + 9 * math.sin(t / 3), "ram": 47.0, "ram_total": 4 * 2**30, "temp": 51.0,
            "up": 3 * 86400 + 5 * 3600, "load": 0.42, "rx": 310e3, "tx": 42e3, "throttled": "0x0",
            "disks": [["/", 62e9, 41e9], ["/mnt/media", 1e12, 850e9], ["/mnt/backup", 235e9, 233e9]],
            "docker": [[n, "running", "healthy" if i % 3 else ""] for i, n in enumerate(names)],
            "qbit": {"dl": 12.4e6, "up": 830e3, "n": 14, "active": 2, "seed": 11,
                     "list": [["Ghost in the Shell - Stand Alone Complex S01 [BD 1080p]", 0.62, 9.1e6, 1260, "downloading", 38e9],
                              ["Kenji Kawai - Ghost in the Shell OST [FLAC]", 0.88, 3.3e6, 95, "downloading", 410e6],
                              ["Serial Experiments Lain [BD 1080p]", 1.0, 0, 8640000, "stalledUP", 21e9],
                              ["Akira (1988) [BD 1080p]", 1.0, 0, 8640000, "stalledUP", 12e9]]},
            "jellyfin": {"playing": [["motoko", "Ghost in the Shell · S01E03", "Living room TV", 812 + t % 600, 1450, False]],
                         "latest": [["Serial Experiments Lain", "Series", 1998], ["Akira", "Movie", 1988],
                                    ["Patlabor 2", "Movie", 1993], ["Ergo Proxy", "Series", 2006]]},
            "pihole": {"total": 18422, "blocked": 2311, "pct": 12.5}}


def clip(cr, text, maxw, size, bold=False):
    """`text` shortened with … to fit `maxw` pixels at this font size."""
    cr.select_font_face(FONT, cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD if bold else cairo.FONT_WEIGHT_NORMAL)
    cr.set_font_size(size)
    if cr.text_extents(text).x_advance <= maxw:
        return text
    while text and cr.text_extents(text + "…").x_advance > maxw:
        text = text[:-1]
    return text.rstrip() + "…"


class ServerFeed(Card):
    """A card fed by the shared ServerLink; hidden until the server reports its part (`key`) - unconfigured = never shown."""
    key = ""

    def __init__(self, app, tag, link, **kw):
        super().__init__(app, tag, **kw)
        self.link = link
        self.wait_data = True

    def feed(self):
        """(this card's part of the data or None, link online)"""
        if DEMO:
            return demo_server().get(self.key), True
        d = self.link.data if self.link else None
        return (d or {}).get(self.key), bool(self.link and self.link.online())

    def update(self):
        part, _ = self.feed()
        if (part is not None) != self.get_visible():
            self.set_visible(part is not None)
        if part is not None:
            self.refresh(part)

    def refresh(self, part):
        self.da.queue_draw()


def fmt_eta(sec):
    if sec <= 0 or sec >= 8640000:
        return "∞"
    return f"{sec // 3600}H{sec % 3600 // 60:02d}" if sec >= 3600 else f"{sec // 60}M{sec % 60:02d}"


class TorrentCard(ServerFeed):
    """qBittorrent on the server: total speed, counts, the moving torrents first with progress and ETA."""
    key = "qbit"

    def __init__(self, app, link, **kw):
        super().__init__(app, "TORRENT.LINK // 急流", link, **kw)
        row = Gtk.Box(spacing=8)
        self.l_dl = label("↓ 0 B/s", "n-down")
        self.l_dl.set_hexpand(True)
        self.l_up = label("↑ 0 B/s", "n-up", 1.0)
        row.append(self.l_dl)
        row.append(self.l_up)
        self.body.append(row)
        self.l_meta = label("", "n-meta", ellipsize=True)
        self.body.append(self.l_meta)
        self.da = self.area(self._draw)
        self.da.set_vexpand(True)
        self.body.append(self.da)
        self.update()

    def refresh(self, q):
        if q.get("error"):
            self.l_dl.set_text("QBITTORRENT")
            self.l_up.set_text("")
            self.l_meta.set_text(q["error"])
        else:
            self.l_dl.set_text("↓ " + human_rate(q["dl"]))
            self.l_up.set_text("↑ " + human_rate(q["up"]))
            self.l_meta.set_text(f"{q['active']} DL · {q['seed']} SEED · {q['n']} TOTAL")
        self.da.queue_draw()

    def _draw(self, area, cr, w, h):
        q, online = self.feed()
        rows = (q or {}).get("list") or []
        if not rows:
            draw_text(cr, "NO TORRENTS", 0, 12, 9, DIM, bold=True)
            return
        a = 1.0 if online else 0.35
        step = 25
        n = min(len(rows), max(int(h // step), 1))
        for i, (name, prog, speed, eta, state, size) in enumerate(rows[:n]):
            y = i * step
            done = prog >= 1
            tail = "DONE" if done else f"{prog * 100:.0f}% · {fmt_eta(eta)}"
            draw_text(cr, tail, w, y + 10, 9, CYB if speed > 0 else DIM, bold=True, align="right", alpha=a)
            cr.select_font_face(FONT, cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)
            cr.set_font_size(9)
            room = w - cr.text_extents(tail).x_advance - 10
            draw_text(cr, clip(cr, name, room, 9, bold=True), 0, y + 10, 9, FG if speed > 0 else MID, bold=True, alpha=a)
            draw_meter(cr, 0, y + 15, w, 4, prog, hot=state in ("error", "missingFiles"))


def fmt_hms(sec):
    sec = int(sec)
    return f"{sec // 3600}:{sec % 3600 // 60:02d}:{sec % 60:02d}" if sec >= 3600 else f"{sec // 60}:{sec % 60:02d}"


class WatchCard(ServerFeed):
    """Jellyfin on the server: who is watching what (with progress), then the newest additions."""
    key = "jellyfin"

    def __init__(self, app, link, **kw):
        super().__init__(app, "NOW.WATCHING // 視聴", link, **kw)
        self.da = self.area(self._draw)
        self.da.set_vexpand(True)
        self.body.append(self.da)
        self.update()

    def _draw(self, area, cr, w, h):
        j, online = self.feed()
        j = j or {}
        a = 1.0 if online else 0.35
        if j.get("error"):
            draw_text(cr, "JELLYFIN · " + j["error"], 0, 12, 9, RED, bold=True)
            return
        y = 0
        playing = j.get("playing") or []
        if not playing:
            draw_text(cr, "NO ACTIVE STREAMS", 0, y + 12, 9, DIM, bold=True)
            y += 24
        for user, title, dev, pos, total, paused in playing[:2]:
            draw_text(cr, "󰏤" if paused else "󰐊", 0, y + 13, 12, RED if paused else CYB, alpha=a)
            draw_text(cr, clip(cr, title.upper(), w - 18, 11, bold=True), 18, y + 13, 11, FG, bold=True, alpha=a)
            draw_text(cr, clip(cr, f"{user} · {dev}".upper(), w * 0.6, 8, bold=True), 18, y + 27, 8, DIM, bold=True)
            draw_text(cr, f"{fmt_hms(pos)} / {fmt_hms(total)}", w, y + 27, 8, MID, bold=True, align="right")
            draw_meter(cr, 18, y + 32, w - 18, 4, pos / total if total else 0)
            y += 46
        latest = j.get("latest") or []
        if not latest or y > h - 30:
            return
        draw_text(cr, "RECENTLY ADDED", 0, y + 10, 8, DIM, bold=True)
        y += 16
        for name, kind, year in latest:
            if y + 14 > h:
                break
            right = f"{'TV' if kind == 'Series' else 'FILM' if kind == 'Movie' else kind.upper()[:5]} {year}".strip()
            draw_text(cr, right, w, y + 10, 8, DIM, bold=True, align="right")
            cr.select_font_face(FONT, cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_NORMAL)
            cr.set_font_size(8)
            room = w - cr.text_extents(right).x_advance - 12
            setc(cr, CY)
            cr.rectangle(0, y + 5, 3, 3)
            cr.fill()
            draw_text(cr, clip(cr, name.upper(), room - 8, 10), 8, y + 10, 10, MID, alpha=a)
            y += 16


class ServicesCard(ServerFeed):
    """Every Docker container on the server as a status light, plus the Pi-hole blocking figures when configured."""
    key = "docker"

    def __init__(self, app, link, **kw):
        super().__init__(app, "SERVICES // 稼働", link, **kw)
        self.l_sum = label("", "n-meta", ellipsize=True)
        self.body.append(self.l_sum)
        self.da = self.area(self._draw)
        self.da.set_vexpand(True)
        self.body.append(self.da)
        self.update()

    def refresh(self, dk):
        bad = [e for e in dk if e[1] != "running" or e[2] == "unhealthy"]
        self.l_sum.set_text(f"{len(dk) - len(bad)}/{len(dk)} NOMINAL" + (f" · {len(bad)} FAULT" if bad else ""))
        (self.l_sum.add_css_class if bad else self.l_sum.remove_css_class)("bad")
        self.da.queue_draw()

    def _draw(self, area, cr, w, h):
        dk, online = self.feed()
        dk = dk or []
        pi = (demo_server() if DEMO else (self.link.data if self.link else None) or {}).get("pihole")
        a = 1.0 if online else 0.35
        foot = 34 if pi else 0
        cols = 2
        rows = max((len(dk) + cols - 1) // cols, 1)
        step = min(17, (h - foot) / rows)
        cw = w / cols
        blink = int(time.monotonic()) % 2 == 0
        for i, (name, state, health) in enumerate(dk):
            x, y = (i // rows) * cw, (i % rows) * step
            if state != "running" or health == "unhealthy":
                col, fill = RED, True
            elif health == "starting":
                col, fill = CY, blink
            else:
                col, fill = CYB if health == "healthy" else CY, True
            setc(cr, col, a if fill else 0.3)
            cr.arc(x + 4, y + 7, 3.2, 0, 2 * math.pi)
            cr.fill() if fill else cr.stroke()
            draw_text(cr, clip(cr, name.upper(), cw - 18, 9), x + 13, y + 10, 9,
                      RED if col == RED else FG if health == "healthy" else MID, alpha=a)
        if pi:
            y = h - foot + 6
            if pi.get("error"):
                draw_text(cr, "PI-HOLE · " + pi["error"], 0, y + 10, 9, RED, bold=True)
                return
            draw_text(cr, "PI-HOLE", 0, y + 10, 9, FG, bold=True, alpha=a)
            draw_text(cr, f"{pi['blocked']:,} / {pi['total']:,} BLOCKED · {pi['pct']:.1f}%".replace(",", " "), w, y + 10, 9, DIM,
                      bold=True, align="right")
            draw_meter(cr, 0, y + 15, w, 4, min(pi["pct"] / 100 * 4, 1))  # 25 % blocked fills the bar


# --------------------------------------------------------------------------------------------- local journal
class SysLog(threading.Thread):
    """`journalctl -f` as JSON: warnings and errors, USB plug / unplug, ssh logins. Repeats fold into one line with a count."""
    USB_NEW = re.compile(r"^usb (\S+): Product: (.+)$")
    USB_GONE = re.compile(r"^usb (\S+): USB disconnect")
    SSH = re.compile(r"^Accepted \S+ for (\S+) from (\S+)")

    def __init__(self):
        super().__init__(daemon=True)
        self.lines = collections.deque(maxlen=40)  # [time, source, text, level, count, key]
        self.lock = threading.Lock()
        self.proc, self.stamp = None, 0

    def stop(self):
        if self.proc:
            self.proc.kill()

    def pick(self, e):
        msg = e.get("MESSAGE")
        if not isinstance(msg, str):
            return None
        prio = int(e.get("PRIORITY", 6))
        src = os.path.basename(e.get("SYSLOG_IDENTIFIER") or e.get("_COMM") or "?").lower()
        m = self.USB_NEW.match(msg)
        if m:
            return "usb", "+ " + m.group(2), "event"
        m = self.USB_GONE.match(msg)
        if m:
            return "usb", "- " + m.group(1) + " unplugged", "event"
        m = self.SSH.match(msg)
        if m and src.startswith("sshd"):
            return "ssh", f"login {m.group(1)} from {m.group(2)}", "event"
        if prio <= 4:
            return src, msg, "err" if prio <= 3 else "warn"
        return None

    def run(self):
        while True:
            try:
                self.proc = subprocess.Popen(["journalctl", "-f", "-n", "2000", "-o", "json", "--no-pager"],
                                             stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)
                for line in self.proc.stdout:
                    try:
                        e = json.loads(line)
                    except ValueError:
                        continue
                    got = self.pick(e)
                    if not got:
                        continue
                    src, text, level = got
                    text = " ".join(text.split())
                    ts = time.strftime("%H:%M:%S", time.localtime(int(e.get("__REALTIME_TIMESTAMP", 0)) / 1e6))
                    key = (src, re.sub(r"\d+", "#", text)[:60])
                    with self.lock:  # a repeat of one of the last few lines moves it down with a higher count
                        old = next((x for x in list(self.lines)[-4:] if x[5] == key), None)
                        if old:
                            self.lines.remove(old)
                            old[0], old[4] = ts, old[4] + 1
                            self.lines.append(old)
                        else:
                            self.lines.append([ts, src, text, level, 1, key])
                        self.stamp += 1
                self.proc.wait()
            except OSError:
                return
            time.sleep(10)

    def snapshot(self):
        with self.lock:
            return self.stamp, [list(x) for x in self.lines]


class LogCard(Card):
    """SYS.LOG: the local journal as a terminal feed (newest at the bottom)."""

    def __init__(self, app, **kw):
        super().__init__(app, "SYS.LOG // 記録", **kw)
        self.feed, self.seen = None, -1
        if DEMO:
            self.demo = [["22:41:07", "kernel", "+ Elements 25A2", "event", 1],
                         ["22:41:09", "ssh", "login crem from 192.168.50.20", "event", 1],
                         ["22:43:30", "kernel", "x86/split lock detection: #DB: took a bus_lock trap", "warn", 38],
                         ["22:47:12", "systemd", "pi-backup.service: Failed with result 'exit-code'.", "err", 1],
                         ["22:52:03", "kernel", "- 8-3.2 unplugged", "event", 1]]
        else:
            self.feed = SysLog()
            self.feed.start()
        self.da = self.area(self._draw)
        self.da.set_vexpand(True)
        self.body.append(self.da)

    def update(self):
        if self.feed and self.feed.stamp != self.seen:
            self.seen = self.feed.stamp
            self.da.queue_draw()

    def _draw(self, area, cr, w, h):
        lines = self.demo if DEMO else self.feed.snapshot()[1]
        lh = 16
        n = max(int(h // lh), 1)
        lines = lines[-n:]
        if not lines:
            draw_text(cr, "NO EVENTS", 0, 12, 9, DIM, bold=True)
            return
        y = h - len(lines) * lh
        for i, (ts, src, text, level, count, *_) in enumerate(lines):
            yy = y + i * lh + 11
            age = 0.55 + 0.45 * (i + 1) / len(lines)  # older lines fade
            col = RED if level == "err" else CYB if level == "event" else MID
            draw_text(cr, ts, 0, yy, 9, DIM, alpha=age)
            tag = src[:8].upper()
            draw_text(cr, tag, 52, yy, 9, col, bold=True, alpha=age)
            tail = f" ×{count}" if count > 1 else ""
            x = 102
            if tail:
                draw_text(cr, tail, w, yy, 9, DIM, bold=True, align="right", alpha=age)
                cr.select_font_face(FONT, cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)
                cr.set_font_size(9)
            room = w - x - (cr.text_extents(tail).x_advance + 6 if tail else 0)
            draw_text(cr, clip(cr, text, room, 9), x, yy, 9, FG if level != "warn" else MID, alpha=age)

    def shutdown(self):
        if self.feed:
            self.feed.stop()


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
# --------------------------------------------------------------------------------------------- notes + focus, updates, bluetooth
UPDATE_CMD, BT_CMD = ["gits-update"], ["gits-bt"]   # what the bar runs on a click on its updates / Bluetooth module


class BackgroundPoll(threading.Thread):
    """Runs `fn` every `every` s off the main thread; the card reads `value` (None until the first answer)."""

    def __init__(self, fn, every):
        super().__init__(daemon=True)
        self.fn, self.every, self.value = fn, every, None
        self.start()

    def run(self):
        while True:
            try:
                self.value = self.fn()
            except Exception:   # a tool that is missing or hangs must never kill the widgets
                pass
            time.sleep(self.every)


def clickable(card, fn):
    g = Gtk.GestureClick()
    g.connect("released", lambda *_: fn())
    card.add_controller(g)


class NotesCard(Card):
    """The latest quick notes (gits-note, ~/notes/inbox.md) and the focus timer (gits-focus). Click: the note popup; the timer line
    starts / stops the timer."""
    N = 5

    def __init__(self, app, **kw):
        super().__init__(app, "MEMO // 記録", **kw)
        self.file = os.environ.get("GITS_NOTES", os.path.expanduser("~/notes/inbox.md"))
        self.focus_state = os.path.join(os.environ.get("XDG_STATE_HOME", os.path.expanduser("~/.local/state")), "gits-focus", "state")
        self.notes, self.focus = [], None
        self.da = self.area(self._draw)
        self.da.set_vexpand(True)
        self.body.append(self.da)
        self.l_focus = label("", "n-down")
        self.body.append(self.l_focus)
        g = Gtk.GestureClick()
        g.connect("released", lambda _g, _n, x, y: self._click(y))
        self.add_controller(g)
        self.update()

    def _click(self, y):
        if y > self.get_height() - 30:
            subprocess.Popen(["gits-focus", "toggle"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
        else:
            subprocess.Popen(["gits-panel", "note"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)

    def update(self):
        notes = []
        if DEMO:
            notes = ["call the section chief", "dive log: 2501", "buy thermoptic batteries"]
        else:
            try:
                with open(self.file, errors="replace") as f:
                    for line in f:
                        t = re.sub(r"^\s*[-*]\s*(\[[ x]\]\s*)?(\d{4}-\d\d-\d\d \d\d:\d\d\s*)?", "", line.rstrip())
                        if t and not t.startswith("#"):
                            notes.append(t)
            except OSError:
                pass
        self.notes = notes[-self.N:][::-1]
        st = {}
        try:
            with open(self.focus_state) as f:
                st = dict(l.strip().split("=", 1) for l in f if "=" in l)
        except OSError:
            pass
        if st.get("end", "").isdigit():
            left = max(0, int(st["end"]) - int(time.time()))
            phase = "FOCUS" if st.get("phase") == "work" else "BREAK"
            self.l_focus.set_text(f"◉ {phase} {left // 60:02d}:{left % 60:02d} · ROUND {int(st.get('round', 0) or 0) + 1}")
        else:
            self.l_focus.set_text("○ FOCUS TIMER · CLICK TO START")
        self.da.queue_draw()

    def _draw(self, area, cr, w, h):
        if not self.notes:
            draw_text(cr, "NO NOTES · SUPER+N", 0, 14, 9, DIM, bold=True)
            return
        step = min(22, h / self.N)
        for i, t in enumerate(self.notes):
            y = i * step + 13
            draw_text(cr, "›", 0, y, 10, CY, bold=True)
            draw_text(cr, clip(cr, t, w - 14, 10), 12, y, 10, FG if i == 0 else MID, bold=i == 0)


def updates_probe():
    out = subprocess.run(["gits-update", "--check"], capture_output=True, text=True, timeout=180).stdout
    m = re.search(r"repo:\s*(\d+).*?aur:\s*(\d+)", out.replace("\n", " "))
    repo, aur = (int(m.group(1)), int(m.group(2))) if m else (0, 0)
    flat = 0
    try:
        fo = subprocess.run(["flatpak", "remote-ls", "--updates", "--columns=application"], capture_output=True, text=True, timeout=60).stdout
        flat = len([l for l in fo.splitlines() if l.strip()])
    except (OSError, subprocess.SubprocessError):
        pass
    return repo, aur, flat


class UpdatesCard(Card):
    """Pending updates (pacman repos, AUR, Flatpak; checked every 30 min), uptime and kernel. Click: gits-update."""

    def __init__(self, app, **kw):
        super().__init__(app, "SYS.PATCH // 更新", **kw)
        self.poll = None if DEMO else BackgroundPoll(updates_probe, 1800)
        top = Gtk.Box()
        self.big = label("…", "b-big")
        self.big.set_hexpand(True)
        self.state = label("", "b-state", 1.0)
        self.state.set_valign(Gtk.Align.START)
        top.append(self.big)
        top.append(self.state)
        self.body.append(top)
        self.l_src = label("", "n-up")
        self.body.append(self.l_src)
        self.l_up = label("", "n-down")
        self.body.append(self.l_up)
        clickable(self, lambda: subprocess.Popen(UPDATE_CMD, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True))
        self.update()

    def update(self):
        v = (12, 3, 1) if DEMO else (self.poll.value if self.poll else None)
        if v is None:
            self.big.set_text("…")
            self.state.set_text("CHECKING")
            self.l_src.set_text("")
        else:
            n = sum(v)
            self.big.set_text(str(n))
            self.state.set_text("PENDING" if n else "UP TO DATE")
            self.l_src.set_text(f"REPO {v[0]} · AUR {v[1]} · FLATPAK {v[2]}")
        try:
            with open("/proc/uptime") as f:
                up = int(float(f.read().split()[0]))
        except OSError:
            up = 0
        self.l_up.set_text(f"UP {fmt_uptime(up)} · LINUX {os.uname().release.split('-')[0]}")


def bt_probe():
    devs = []
    out = subprocess.run(["bluetoothctl", "devices", "Connected"], capture_output=True, text=True, timeout=10).stdout
    for line in out.splitlines():
        parts = line.split(" ", 2)
        if len(parts) < 3 or parts[0] != "Device":
            continue
        info = subprocess.run(["bluetoothctl", "info", parts[1]], capture_output=True, text=True, timeout=10).stdout
        bat = re.search(r"Battery Percentage:.*\((\d+)\)", info)
        icon = re.search(r"Icon:\s*(\S+)", info)
        devs.append((parts[2], int(bat.group(1)) if bat else None, icon.group(1) if icon else ""))
    try:   # phones over KDE Connect
        ids = subprocess.run(["kdeconnect-cli", "-a", "--id-name-only"], capture_output=True, text=True, timeout=10).stdout
        for line in ids.splitlines():
            did, _, name = line.partition(" ")
            if not did or " " in did:
                continue
            r = subprocess.run(["gdbus", "call", "--session", "--dest", "org.kde.kdeconnect", "--object-path",
                                f"/modules/kdeconnect/devices/{did}/battery", "--method", "org.freedesktop.DBus.Properties.Get",
                                "org.kde.kdeconnect.device.battery", "charge"], capture_output=True, text=True, timeout=10).stdout
            m = re.search(r"(\d+)", r)
            devs.append((name, int(m.group(1)) if m else None, "phone"))
    except (OSError, subprocess.SubprocessError):
        pass
    return devs


class BluetoothCard(Card):
    """Connected Bluetooth devices and phones (KDE Connect) with their battery. Click: the Bluetooth menu."""
    ICONS = {"audio-headset": "\U000F02CB", "audio-headphones": "\U000F02CB", "input-mouse": "\U000F037D", "input-keyboard": "\U000F030C",
             "input-gaming": "\U000F0297", "phone": "\U000F011C", "audio-card": "\U000F04C3"}

    def __init__(self, app, **kw):
        super().__init__(app, "BT.LINK // 無線", **kw)
        self.poll = None if DEMO else BackgroundPoll(bt_probe, 30)
        self.da = self.area(self._draw)
        self.da.set_vexpand(True)
        self.body.append(self.da)
        clickable(self, lambda: subprocess.Popen(BT_CMD, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True))
        self.update()

    def update(self):
        self.da.queue_draw()

    def _draw(self, area, cr, w, h):
        devs = [("WH-1000XM", 80, "audio-headset"), ("LOGI M650", 100, "input-mouse")] if DEMO else (self.poll.value if self.poll else None)
        if devs is None:
            draw_text(cr, "SCANNING…", 0, 14, 9, DIM, bold=True)
            return
        if not devs:
            draw_text(cr, "NOTHING CONNECTED", 0, 14, 9, DIM, bold=True)
            return
        step = min(30, h / max(1, len(devs)))
        for i, (name, bat, icon) in enumerate(devs[:4]):
            y = i * step
            draw_text(cr, self.ICONS.get(icon, "\U000F00AF"), 0, y + 12, 11, CY)
            draw_text(cr, clip(cr, name.upper(), w - 70, 9, True), 18, y + 12, 9, FG, bold=True)
            if bat is not None:
                draw_text(cr, f"{bat}%", w, y + 12, 9, RED if bat <= 15 else MID, bold=True, align="right")
                draw_meter(cr, 18, y + 17, w - 18, 4, bat / 100, hot=bat <= 15)


BAR_H = 26   # the bar's exclusive zone (waybar height 24 + its border)
WIDGETS_CONF = os.path.join(os.environ.get("XDG_CONFIG_HOME", os.path.expanduser("~/.config")), "gits", "widgets.conf")
WIDGETS_OFF = {"gpu", "disks", "top"}   # off by default on the main monitor (the second monitor shows them); the menu turns them on


def widget_choice():
    """(on, off) card ids from ~/.config/gits/widgets.conf (`ID = on|off` lines, written by the desktop menu); unlisted ones keep their
    default: on, except WIDGETS_OFF."""
    on, off = set(), set(WIDGETS_OFF)
    try:
        with open(WIDGETS_CONF) as f:
            for line in f:
                k, _, v = line.partition("=")
                k, v = k.strip(), v.split("#")[0].strip().lower()
                if k and not k.startswith("#") and v in ("on", "off"):
                    (on if v == "on" else off).add(k)
                    (off if v == "on" else on).discard(k)
    except OSError:
        pass
    return on, off


class App:
    """Plain windows + GLib main loop (a Gtk.Application blocks on its D-Bus registration in this session)."""

    def __init__(self):
        self.cards = []
        self.stats = None
        self.link = None
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
        hidden = widget_choice()[1]

        def add(cls, x, y, w, h, right=False, **kw):
            c = cls(self, x=x, y=y, w=w, h=h, right=right, monitor=mon, **kw)
            self.cards.append(c)
            return c

        server = os.environ.get("GITS_SERVER", "")
        self.link = None
        if DEMO or (server and server.lower() != "off"):
            if not DEMO:
                self.link = ServerLink(server)
                self.link.start()
        # every card the main monitor may show: (id, class, side, preferred column, width, height, kwargs); `widget_choice` (the
        # desktop menu, ~/.config/gits/widgets.conf) says which are on. They stack down their column and a card that does not fit
        # the screen's height goes to the next column inward, so nothing ends up below the screen edge.
        bats = sorted(glob.glob("/sys/class/power_supply/BAT*"))
        has_gpu = gpu_sample() is not None
        many = mon is not None and Gdk.Display.get_default().get_monitors().get_n_items() > 1
        plan = [("clock", ClockCard, "L", 0, LW, 226, {}),
                ("calendar", CalendarCard, "L", 0, LW, 236, {})]
        if np is not None:
            plan.append(("spectrum", AudioCard, "L", 0, LW, 160, {}))
        if not (many and os.environ.get("GITS_WIDGETS_SECOND", "1") != "0"):   # with a second monitor SYS.LOG lives there
            plan.append(("log", LogCard, "L", 0, LW, 300, {}))
        plan += [("media", MediaCard, "L", 1, MW, 372, {}),
                 ("weather", WeatherCard, "L", 1, MW, 108, {}),
                 ("net", NetCard, "L", 1, MW, 132, {})]
        if DEMO or self.link:
            plan += [("server", ServerCard, "L", 1, MW, 262, {"dest": server or "tachikoma", "link": self.link}),
                     ("services", ServicesCard, "L", 1, MW, 236, {"link": self.link})]
        plan += [("notes", NotesCard, "L", 0, LW, 170, {})]
        if bats:
            plan.append(("battery", BatteryCard, "R", 0, RW, 92, {"bat": bats[0]}))
        plan += [("rings", RingsCard, "R", 0, RW, 132, {"stats": self.stats}),
                 ("graph", GraphCard, "R", 0, RW, 132, {"stats": self.stats}),
                 ("todo", TodoCard, "R", 0, RW, 250, {})]
        if DEMO or self.link:
            plan += [("torrents", TorrentCard, "R", 0, RW, 196, {"link": self.link}),
                     ("watching", WatchCard, "R", 0, RW, 214, {"link": self.link})]
        plan += [("updates", UpdatesCard, "R", 0, RW, 110, {}),
                 ("bluetooth", BluetoothCard, "R", 0, RW, 120, {})]
        if has_gpu:
            plan.append(("gpu", GpuCard, "R", 0, RW, 132, {}))
        plan += [("disks", DiskCard, "R", 0, RW, 150, {}), ("top", TopCard, "R", 0, RW, 150, {})]
        room = (mon.get_geometry().height if mon is not None else 1080) - BAR_H - top - m
        for side in "LR":
            cols = []   # [width, used height, [(card...)]]
            for wid, cls, sd, pref, w, h, kw in plan:
                if sd != side or wid in hidden:
                    continue
                ci = pref
                while True:
                    while len(cols) <= ci:
                        cols.append([0, 0, []])
                    col = cols[ci]
                    need = h if not col[2] else col[1] + gap + h
                    if need <= room or not col[2]:
                        col[0], col[1] = max(col[0], w), need
                        col[2].append((cls, w, h, kw))
                        break
                    ci += 1
            x = m
            for cw, _, items in cols:
                if not items:
                    continue
                y = top
                for cls, w, h, kw in items:
                    add(cls, x, y, w, h, right=side == "R", **kw)
                    y += h + gap
                x += cw + gap
        log_home = None  # SYS.LOG: under the calendar of the second monitor, else in the main monitor's plan above

        # every other monitor: a smaller set without the cards that run their own threads (player, audio spectrum, to-do)
        if os.environ.get("GITS_WIDGETS_SECOND", "1") != "0" and mon is not None:
            mons = Gdk.Display.get_default().get_monitors()
            for other in (mons.get_item(i) for i in range(mons.get_n_items())):
                if other == mon:
                    continue
                def add2(cls, x, y, w, h, right=False, **kw):
                    c = cls(self, x=x, y=y, w=w, h=h, right=right, monitor=other, **kw)
                    self.cards.append(c)
                y = top
                add2(ClockCard, m, y, LW, 226)
                add2(CalendarCard, m, y + 226 + gap, LW, 236)
                if log_home is None:
                    log_home = other
                    add2(LogCard, m, y + 226 + gap + 236 + gap, LW + gap + MW, 300)
                y = top
                add2(RingsCard, m, y, RW, 132, right=True, stats=self.stats)
                y += 132 + gap
                add2(GraphCard, m, y, RW, 132, right=True, stats=self.stats)
                y += 132 + gap
                add2(NetCard, m, y, RW, 132, right=True)
                x2, y = m + LW + gap, top  # the middle column: what the main screen does not show
                if gpu_sample() is not None or any(open(v).read().strip() == "0x10de" for v in glob.glob("/sys/bus/pci/devices/*/vendor")):
                    add2(GpuCard, x2, y, MW, 132)
                    y += 132 + gap
                add2(DiskCard, x2, y, MW, 150)
                y += 150 + gap
                add2(TopCard, x2, y, MW, 150)


        for c in self.cards:
            if not getattr(c, "wait_data", False):
                c.present()
        GLib.timeout_add_seconds(1, self.tick1)
        GLib.timeout_add_seconds(2, self.tick2)

    def tick1(self):
        for c in self.cards:
            if isinstance(c, (ClockCard, CalendarCard, MediaCard, LogCard, NotesCard)):
                c.update()
        return True

    def tick2(self):
        self.stats.refresh()
        for c in self.cards:
            if isinstance(c, (RingsCard, GraphCard, BatteryCard, WeatherCard, NetCard, GpuCard, DiskCard, TopCard, ServerCard,
                              ServerFeed, UpdatesCard, BluetoothCard)):
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
    if app.link:
        app.link.stop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
