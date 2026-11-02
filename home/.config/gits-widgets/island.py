#!/usr/bin/env python3
"""GitS dynamic island: the middle of the bar as one living shape (gits-island.service; `gits-island on|off`).

With nothing to show it is not there at all (the bar keeps its own clock and player). A live status puts it inside the bar, at the
bar's height, as chips next to the clock and the track: screen recording (click = stop), the focus timer, a reminder due within 10 minutes, "touch the YubiKey" while sudo / polkit /
the lock screen waits for it, and anything a tool pushes with `gits-island activity`. It grows ~20 px below the bar for a moment to show:
  * the OSD (volume, brightness, microphone, keyboard backlight, layout): osd.py hands its events here while the island runs
  * notifications of low / normal urgency (dunst rules in dunstrc.d/70-gits-island.conf, switched on by this daemon while it runs and
    off when it stops; critical ones and ones with buttons stay dunst popups). Hover = keep it, click = open it in dunst (with its
    actions), right click = dismiss.
Click it (or `gits-island expand`) = the media card (cover, progress, prev / play / next; click the bar to seek) or, with nothing playing, the date.
Middle click = play / pause, scroll = previous / next track (scroll on the volume OSD = volume). It leaves 1 s after the pointer does.

One window per monitor on the OVERLAY layer (above the bar), transparent outside the shape, which is also the only place it takes
clicks. Over a fullscreen window only the OSD and notifications show. Super+I -> Dynamic island / `gits-island off`: OSD and popups as before. Fed through $XDG_RUNTIME_DIR/gits-island.fifo, one JSON object
per line (gits-island writes them). Off: ~/.local/state/gits/island.json {"on": false}."""
import glob
import hashlib
import json
import math
import os
import socket
import subprocess
import sys
import threading
import time

_LS_LIB = "/usr/lib/libgtk4-layer-shell.so"
if os.path.exists(_LS_LIB) and _LS_LIB not in os.environ.get("LD_PRELOAD", ""):
    os.environ["LD_PRELOAD"] = (_LS_LIB + " " + os.environ.get("LD_PRELOAD", "")).strip()
    os.execv(sys.executable, [sys.executable, os.path.abspath(__file__), *sys.argv[1:]])
os.environ.pop("LD_PRELOAD", None)   # children (playerctl, gits-* tools) must not load GTK for nothing
os.environ.setdefault("GSK_RENDERER", "cairo")
os.environ.setdefault("GDK_BACKEND", "wayland")
os.environ["GTK_THEME"] = "Adwaita:dark"

import cairo  # noqa: E402
import gi  # noqa: E402

gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")
gi.require_version("GdkPixbuf", "2.0")
gi.require_version("Pango", "1.0")
gi.require_version("PangoCairo", "1.0")
gi.require_version("Gtk4LayerShell", "1.0")
from gi.repository import Gdk, GdkPixbuf, Gio, GLib, GLibUnix, Gtk, Pango, PangoCairo  # noqa: E402
from gi.repository import Gtk4LayerShell as LS  # noqa: E402

HOME = os.path.expanduser("~")
RUN = os.environ.get("XDG_RUNTIME_DIR", "/tmp")
STATE = os.environ.get("XDG_STATE_HOME", os.path.join(HOME, ".local", "state"))
CACHE = os.path.join(os.environ.get("XDG_CACHE_HOME", os.path.join(HOME, ".cache")), "gits-island")
CONF = os.path.join(STATE, "gits", "island.json")
FIFO = os.path.join(RUN, "gits-island.fifo")
PIDFILE = os.path.join(RUN, "gits-island.pid")
DUNST_RULES = ("gits-island-low", "gits-island-normal")

# palette (= the GitS theme; gits-theme recolours these literals)
BG, CY, CYB, FG, DIM, RED = "#060A14", "#2ED3D7", "#5EF1F5", "#C8F4FF", "#596977", "#E5432B"
FONT = "JetBrainsMono Nerd Font, Noto Sans CJK JP"

WIN_W, WIN_H = 600, 176      # the surface; the shape inside it grows and shrinks, the rest is transparent and click-through
BAR_H = 25                   # the bar (24 px + its 1 px bottom line): the resting shape hangs a little below it
REST_H = BAR_H               # with a live status the island sits inside the bar, it does not hang below it
OSD_SIZE = (360, 46)         # the shapes that grow out of the bar stay short: ~20 px below it
NOTE_SIZE = (480, 50)
CARD_SIZE = (520, 128)
DATE_SIZE = (360, 66)
OSD_TIME, NOTE_TIME, NOTE_TIME_LOW, LEAVE_TIME = 1.4, 4.5, 3.0, 1.0

OSD_KINDS = {  # kind -> (title, kanji, icon low / mid / high / muted)
    "volume": ("VOLUME", "音量", "󰕿", "󰖀", "󰕾", "󰝟"),
    "brightness": ("BRIGHTNESS", "輝度", "󰃞", "󰃟", "󰃠", "󰃞"),
    "mic": ("MICROPHONE", "録音", "󰍬", "󰍬", "󰍬", "󰍭"),
    "kbd": ("KEYBOARD", "鍵盤", "󰌌", "󰌌", "󰌌", "󰌌"),
    "touchpad": ("TOUCHPAD", "触摸", "󰍽", "󰍽", "󰍽", "󰍽"),
    "layout": ("LAYOUT", "配列", "󰌌", "󰌌", "󰌌", "󰌌"),
}

_rgba = {}


def rgba(h, a=1.0):
    c = _rgba.get(h)
    if c is None:
        s = h.lstrip("#")
        c = _rgba[h] = (int(s[0:2], 16) / 255, int(s[2:4], 16) / 255, int(s[4:6], 16) / 255)
    return (*c, a)


def spawn(*cmd):
    try:
        pid, *_ = GLib.spawn_async(list(cmd), flags=GLib.SpawnFlags.SEARCH_PATH | GLib.SpawnFlags.DO_NOT_REAP_CHILD)
        GLib.child_watch_add(GLib.PRIORITY_DEFAULT, pid, lambda *_: None)
    except GLib.Error:
        pass


def conf_on():
    try:
        return json.load(open(CONF)).get("on", True) is not False
    except (OSError, ValueError, AttributeError):
        return True


def fmt_time(s):
    s = max(0, int(s))
    return f"{s // 3600}:{s % 3600 // 60:02d}:{s % 60:02d}" if s >= 3600 else f"{s // 60}:{s % 60:02d}"


# ------------------------------------------------------------------------------------------------ text
_fonts = {}


def font(size, bold=False):
    k = (size, bold)
    d = _fonts.get(k)
    if d is None:
        d = _fonts[k] = Pango.FontDescription.from_string(f"{FONT} {'Bold' if bold else ''}")
        d.set_absolute_size(size * Pango.SCALE)
    return d


_measure_cr = cairo.Context(cairo.ImageSurface(cairo.FORMAT_ARGB32, 4, 4))


def make_layout(cr, s, size, bold=False, width=None, spacing=0, lines=1):
    lay = PangoCairo.create_layout(cr)
    lay.set_font_description(font(size, bold))
    lay.set_text(s or "", -1)
    if spacing:
        attrs = Pango.AttrList()
        attrs.insert(Pango.attr_letter_spacing_new(int(spacing * Pango.SCALE)))
        lay.set_attributes(attrs)
    if width:
        lay.set_width(int(width * Pango.SCALE))
        lay.set_ellipsize(Pango.EllipsizeMode.END)
        if lines > 1:
            lay.set_wrap(Pango.WrapMode.WORD_CHAR)
            lay.set_height(-lines)
    return lay


def text_w(s, size, bold=False, spacing=0):
    return make_layout(_measure_cr, s, size, bold, spacing=spacing).get_pixel_size()[0]


def text(cr, s, x, y, size, color, alpha=1.0, bold=False, width=None, align="left", spacing=0, lines=1):
    """Draw s with its top-left at (x, y) (align right / center: x is that edge / the centre). Returns its pixel width."""
    lay = make_layout(cr, s, size, bold, width, spacing, lines)
    w, h = lay.get_pixel_size()
    if align == "right":
        x -= w
    elif align == "center":
        x -= w / 2
    cr.set_source_rgba(*rgba(color, alpha))
    cr.move_to(x, y)
    PangoCairo.show_layout(cr, lay)
    cr.new_path()
    return w


def strip_markup(s):
    import html
    import re
    return html.unescape(re.sub(r"<[^>]*>", "", s or "")).strip()


# ------------------------------------------------------------------------------------------------ hyprland
def hypr(cmd):
    sig = os.environ.get("HYPRLAND_INSTANCE_SIGNATURE")
    if not sig:
        return None
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
            s.settimeout(0.5)
            s.connect(os.path.join(RUN, "hypr", sig, ".socket.sock"))
            s.sendall(cmd.encode())
            data = b""
            while chunk := s.recv(65536):
                data += chunk
        return json.loads(data)
    except (OSError, ValueError):
        return None


def focused_connector():
    mons = hypr("j/monitors") or []
    return next((m["name"] for m in mons if m.get("focused")), None)


def fullscreen_connectors():
    """Monitors whose visible workspace has a fullscreen window."""
    mons, wss = hypr("j/monitors") or [], hypr("j/workspaces") or []
    full = {w["id"] for w in wss if w.get("hasfullscreen")}
    out = set()
    for m in mons:
        ids = {(m.get("activeWorkspace") or {}).get("id"), (m.get("specialWorkspace") or {}).get("id")}
        if ids & full:
            out.add(m["name"])
    return out


class HyprEvents(threading.Thread):
    """socket2 listener: calls back (in the GTK thread) when fullscreen state could have changed."""
    WATCH = ("fullscreen", "workspace", "workspacev2", "focusedmon", "focusedmonv2", "closewindow", "movewindow",
             "movewindowv2", "openwindow", "activespecial", "monitoradded", "monitorremoved")

    def __init__(self, cb):
        super().__init__(daemon=True)
        self.cb = cb

    def run(self):
        sig = os.environ.get("HYPRLAND_INSTANCE_SIGNATURE")
        if not sig:
            return
        path = os.path.join(RUN, "hypr", sig, ".socket2.sock")
        while True:
            try:
                with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
                    s.connect(path)
                    buf = b""
                    while chunk := s.recv(4096):
                        buf += chunk
                        *lines, buf = buf.split(b"\n")
                        if any(ln.split(b">>", 1)[0].decode(errors="replace") in self.WATCH for ln in lines):
                            GLib.idle_add(self.cb)
            except OSError:
                pass
            time.sleep(2)


# ------------------------------------------------------------------------------------------------ media (MPRIS over D-Bus)
MPRIS = "org.mpris.MediaPlayer2."
PLAYER_IF = "org.mpris.MediaPlayer2.Player"
OBJ = "/org/mpris/MediaPlayer2"


class Media:
    """Every MPRIS player on the session bus; `current()` follows the same rule as gits-media: a playing one wins, else the one that
    played last."""

    def __init__(self, changed):
        self.changed = changed
        self.bus = Gio.bus_get_sync(Gio.BusType.SESSION)
        self.players = {}     # bus name -> dict
        self.owners = {}      # unique name -> bus name
        self.last = self._read_last()
        self.bus.signal_subscribe("org.freedesktop.DBus", "org.freedesktop.DBus", "NameOwnerChanged", "/org/freedesktop/DBus",
                                  None, Gio.DBusSignalFlags.NONE, self._owner_changed)
        self.bus.signal_subscribe(None, "org.freedesktop.DBus.Properties", "PropertiesChanged", OBJ, None,
                                  Gio.DBusSignalFlags.NONE, self._props_changed)
        self.bus.signal_subscribe(None, PLAYER_IF, "Seeked", OBJ, None, Gio.DBusSignalFlags.NONE, self._props_changed)
        try:
            names = self.bus.call_sync("org.freedesktop.DBus", "/org/freedesktop/DBus", "org.freedesktop.DBus", "ListNames", None,
                                       GLib.VariantType("(as)"), Gio.DBusCallFlags.NONE, 2000, None).unpack()[0]
        except GLib.Error:
            names = []
        for n in names:
            if self._wanted(n):
                try:
                    owner = self.bus.call_sync("org.freedesktop.DBus", "/org/freedesktop/DBus", "org.freedesktop.DBus", "GetNameOwner",
                                               GLib.Variant("(s)", (n,)), GLib.VariantType("(s)"), Gio.DBusCallFlags.NONE, 1000,
                                               None).unpack()[0]
                except GLib.Error:
                    continue
                self._add(n, owner)

    @staticmethod
    def _wanted(name):
        return name.startswith(MPRIS) and not name.startswith(MPRIS + "playerctld")   # playerctld only mirrors the others

    @staticmethod
    def _read_last():
        try:
            return open(os.path.join(STATE, "gits-media", "last")).read().strip()
        except OSError:
            return ""

    def _add(self, name, owner):
        self.owners[owner] = name
        self.players[name] = {"name": name, "short": name[len(MPRIS):], "status": "Stopped", "since": 0.0, "pos": 0, "pos_t": 0.0,
                              "rate": 1.0, "length": 0, "title": "", "artist": "", "album": "", "art": "", "trackid": "/"}
        self.refresh(name)

    def _owner_changed(self, _c, _s, _p, _i, _sig, params):
        name, old, new = params.unpack()
        if not self._wanted(name):
            return
        self.owners.pop(old, None)
        if new:
            self._add(name, new)
        else:
            self.players.pop(name, None)
            self.changed()

    def _props_changed(self, _c, sender, *_):
        name = self.owners.get(sender)
        if name:
            self.refresh(name)

    def refresh(self, name):
        self.bus.call(name, OBJ, "org.freedesktop.DBus.Properties", "GetAll", GLib.Variant("(s)", (PLAYER_IF,)),
                      GLib.VariantType("(a{sv})"), Gio.DBusCallFlags.NONE, 2000, None, self._got, name)

    def _got(self, bus, res, name):
        try:
            props = bus.call_finish(res).unpack()[0]
        except GLib.Error:
            return
        p = self.players.get(name)
        if p is None:
            return
        md = props.get("Metadata") or {}
        status = props.get("PlaybackStatus", p["status"])
        if status == "Playing" and p["status"] != "Playing":
            p["since"] = time.monotonic()
        artists = md.get("xesam:artist") or []
        p.update(status=status, title=str(md.get("xesam:title") or ""), album=str(md.get("xesam:album") or ""),
                 artist=", ".join(artists) if isinstance(artists, list) else str(artists), art=str(md.get("mpris:artUrl") or ""),
                 length=int(md.get("mpris:length") or 0), trackid=str(md.get("mpris:trackid") or "/"),
                 rate=float(props.get("Rate", 1.0) or 1.0))
        if "Position" in props:
            p["pos"], p["pos_t"] = int(props["Position"]), time.monotonic()
        if status == "Playing" and self.last != p["short"]:
            self.last = p["short"]
            try:
                os.makedirs(os.path.join(STATE, "gits-media"), exist_ok=True)
                with open(os.path.join(STATE, "gits-media", "last"), "w") as f:
                    f.write(self.last + "\n")
            except OSError:
                pass
        self.changed()

    def current(self):
        ps = [p for p in self.players.values() if p["title"] or p["status"] == "Playing"]
        playing = [p for p in ps if p["status"] == "Playing"]
        if playing:
            return max(playing, key=lambda p: p["since"])
        live = [p for p in ps if p["status"] != "Stopped"]
        return next((p for p in live if p["short"] == self.last), live[0] if live else None)

    @staticmethod
    def position(p):
        pos = p["pos"]
        if p["status"] == "Playing":
            pos += (time.monotonic() - p["pos_t"]) * 1e6 * p["rate"]
        return max(0, min(pos, p["length"])) if p["length"] else max(0, pos)

    def call(self, p, method, args=None):
        if p:
            self.bus.call(p["name"], OBJ, PLAYER_IF, method, args, None, Gio.DBusCallFlags.NONE, 2000, None, None)

    def seek(self, p, frac):
        if p and p["length"] and p["trackid"].startswith("/"):
            us = int(p["length"] * max(0.0, min(1.0, frac)))
            self.call(p, "SetPosition", GLib.Variant("(ox)", (p["trackid"], us)))
            p["pos"], p["pos_t"] = us, time.monotonic()


class Art:
    """Cover art (file:// or http(s), downloaded once into ~/.cache/gits-island) as a pixbuf, loaded in a thread."""

    def __init__(self, changed):
        self.changed = changed
        self.url, self.pix, self.busy = None, None, set()

    def get(self, url):
        if url != self.url:
            self.url, self.pix = url, None
            if url and url not in self.busy:
                self.busy.add(url)
                threading.Thread(target=self._load, args=(url,), daemon=True).start()
        return self.pix

    def _load(self, url):
        path = None
        try:
            if url.startswith("file://"):
                from urllib.parse import unquote, urlparse
                path = unquote(urlparse(url).path)
            elif url.startswith(("http://", "https://")):
                import urllib.request
                os.makedirs(CACHE, exist_ok=True)
                path = os.path.join(CACHE, hashlib.sha1(url.encode()).hexdigest())
                if not os.path.exists(path):
                    with urllib.request.urlopen(url, timeout=6) as r, open(path + ".part", "wb") as f:
                        f.write(r.read(4 << 20))
                    os.replace(path + ".part", path)
                    old = sorted(glob.glob(os.path.join(CACHE, "*")), key=os.path.getmtime)[:-60]   # keep the last 60 covers
                    for o in old:
                        os.unlink(o)
            pix = GdkPixbuf.Pixbuf.new_from_file_at_scale(path, 192, 192, True) if path else None
        except Exception:  # noqa: BLE001 - any broken cover just means no cover
            pix = None
        GLib.idle_add(self._done, url, pix)

    def _done(self, url, pix):
        self.busy.discard(url)
        if url == self.url:
            self.pix = pix
            self.changed()
        return False


# ------------------------------------------------------------------------------------------------ live statuses
class Activities:
    """Chips at rest: polled once a second from the state files the tools already write (no changes needed in them)."""

    def __init__(self):
        self.pushed = {}      # id -> {"icon", "text", "until", "color"}
        self._rem = (0, [])   # (mtime, reminders)

    def push(self, msg):
        aid = str(msg.get("id") or "x")
        if msg.get("clear"):
            self.pushed.pop(aid, None)
            return
        ttl = float(msg.get("ttl") or 0)
        self.pushed[aid] = {"icon": msg.get("icon") or "󰋼", "text": str(msg.get("text") or "")[:60],
                            "until": time.time() + ttl if ttl > 0 else 0, "color": RED if msg.get("alert") else CY,
                            "action": msg.get("action")}

    @staticmethod
    def _alive(pidfile, needle):
        try:
            pid = int(open(pidfile).read().strip())
            return needle in open(f"/proc/{pid}/cmdline", "rb").read().decode(errors="replace")
        except (OSError, ValueError):
            return False

    def _reminders(self):
        f = os.path.join(os.environ.get("XDG_DATA_HOME", os.path.join(HOME, ".local", "share")), "gits", "reminders.json")
        try:
            m = os.path.getmtime(f)
        except OSError:
            return []
        if m != self._rem[0]:
            try:
                self._rem = (m, json.load(open(f)))
            except (OSError, ValueError):
                self._rem = (m, [])
        return self._rem[1]

    def chips(self):
        """[(icon, text, colour, pulse, action argv or None)], most urgent first."""
        now = time.time()
        out = []
        uid = os.getuid()
        if os.path.exists(f"/run/gits-u2f-{uid}.id") or os.path.exists(os.path.join(RUN, "gits-u2f")):
            out.append(("󰌆", "TOUCH KEY", CYB, True, None))
        if self._alive(os.path.join(RUN, "gits-rec.pid"), "wf-recorder"):
            try:
                t0 = int(open(os.path.join(RUN, "gits-rec.info")).read().split("\n")[1])
            except (OSError, ValueError, IndexError):
                t0 = now
            out.append(("󰑋", "REC " + fmt_time(now - t0), RED, False, ["gits-rec", "stop"]))
        fs = os.path.join(STATE, "gits-focus", "state")
        if os.path.exists(fs) and self._alive(os.path.join(RUN, "gits-focus.pid"), "gits-focus"):
            kv = dict(ln.split("=", 1) for ln in open(fs).read().splitlines() if "=" in ln)
            try:
                left = int(kv.get("end", 0)) - now
                work = kv.get("phase") == "work"
                out.append(("󰔛" if work else "󰾨", ("FOCUS " if work else "BREAK ") + fmt_time(left), CY if work else DIM, False,
                            ["gits-focus", "menu"]))
            except ValueError:
                pass
        soon = [r for r in self._reminders() if 0 <= r.get("at", 0) - now <= 600]
        if soon:
            r = min(soon, key=lambda r: r["at"])
            out.append(("󰀠", f"{max(1, round((r['at'] - now) / 60))}m {r.get('text', '')}"[:28], CY, False, ["gits-remind", "menu"]))
        for k, a in list(self.pushed.items()):
            if a["until"] and a["until"] < now:
                del self.pushed[k]
                continue
            act = a["action"].split() if isinstance(a.get("action"), str) else a.get("action")
            out.append((a["icon"], a["text"], a["color"], False, act))
        return out


# ------------------------------------------------------------------------------------------------ the window
def shape_path(cr, x, y, w, h):
    """The island: square top (it continues the bar), cut corners below (the GitS chamfer)."""
    c = min(10.0, h / 3, w / 6)
    cr.move_to(x, y)
    cr.line_to(x + w, y)
    cr.line_to(x + w, y + h - c)
    cr.line_to(x + w - c, y + h)
    cr.line_to(x + c, y + h)
    cr.line_to(x, y + h - c)
    cr.close_path()


class IslandWindow(Gtk.Window):
    def __init__(self, island, monitor):
        super().__init__()
        self.island, self.monitor = island, monitor
        self.connector = monitor.get_connector() if monitor else None
        self.set_decorated(False)
        self.set_resizable(False)
        self.set_default_size(WIN_W, WIN_H)
        LS.init_for_window(self)
        LS.set_namespace(self, "gits-island")
        LS.set_layer(self, LS.Layer.OVERLAY)
        LS.set_anchor(self, LS.Edge.TOP, True)
        LS.set_keyboard_mode(self, LS.KeyboardMode.NONE)
        LS.set_exclusive_zone(self, -1)
        if monitor is not None:
            LS.set_monitor(self, monitor)
        self.cur_w, self.cur_h = 0.0, 0.0
        self.kind, self.drawn_kind = "none", "none"
        self.expanded = False
        self.hover = False
        self.leave_id = None
        self.tick_id = None
        self.last_t = 0.0
        self.zones = []          # [(x0, y0, x1, y1, callable)] of the last frame
        self.region = None
        self.da = Gtk.DrawingArea()
        self.da.set_content_width(WIN_W)
        self.da.set_content_height(WIN_H)
        self.da.set_draw_func(self._draw)
        self.set_child(self.da)
        click = Gtk.GestureClick(button=0)
        click.connect("released", self._click)
        self.da.add_controller(click)
        scroll = Gtk.EventControllerScroll(flags=Gtk.EventControllerScrollFlags.VERTICAL | Gtk.EventControllerScrollFlags.DISCRETE)
        scroll.connect("scroll", self._scroll)
        self.da.add_controller(scroll)
        motion = Gtk.EventControllerMotion()
        motion.connect("enter", self._enter)
        motion.connect("leave", self._leave)
        self.da.add_controller(motion)
        self.connect("map", lambda *_: self._set_region(0, 0, 0, 0))
        self.present()

    # -- what to show
    def target(self):
        isl = self.island
        t = isl.transient
        if t and (t["connector"] in (None, self.connector) or self.connector is None):
            if t["kind"] == "osd":
                return "osd", OSD_SIZE
            return "note", NOTE_SIZE
        if self.expanded:
            return ("card", CARD_SIZE) if isl.media.current() else ("date", DATE_SIZE)
        if self.connector in isl.fullscreen or not isl.chips:
            return "none", (0, 0)   # nothing to say: no island at all, the bar shows its own clock and player
        return "rest", (isl.rest_width(), REST_H)

    def update(self):
        kind, (tw, th) = self.target()
        if kind != self.kind:
            self.kind = kind
        self.tw, self.th = tw, th
        if self.tick_id is None and (abs(tw - self.cur_w) > 0.5 or abs(th - self.cur_h) > 0.5):
            self.last_t = 0.0
            self.tick_id = self.da.add_tick_callback(self._tick)
        self.da.queue_draw()

    def _tick(self, widget, clock):
        t = clock.get_frame_time() / 1e6
        dt = min(0.05, t - self.last_t) if self.last_t else 1 / 60
        self.last_t = t
        k = 1 - math.exp(-dt * 16)
        self.cur_w += (self.tw - self.cur_w) * k
        self.cur_h += (self.th - self.cur_h) * k
        done = abs(self.tw - self.cur_w) < 0.5 and abs(self.th - self.cur_h) < 0.5
        if done:
            self.cur_w, self.cur_h = float(self.tw), float(self.th)
        x = (WIN_W - self.cur_w) / 2
        self._set_region(x, 0, self.cur_w, self.cur_h)
        self.da.queue_draw()
        if done:
            self.tick_id = None
            return GLib.SOURCE_REMOVE
        return GLib.SOURCE_CONTINUE

    def _set_region(self, x, y, w, h):
        r = (int(x), int(y), int(math.ceil(w)), int(math.ceil(h)))
        if r == self.region:
            return
        surf = self.get_surface()
        if surf is None:
            return
        self.region = r
        surf.set_input_region(cairo.Region(cairo.RectangleInt(*r)) if r[2] > 0 and r[3] > 0 else cairo.Region())

    # -- pointer
    def _enter(self, *_):
        self.hover = True
        if self.leave_id:
            GLib.source_remove(self.leave_id)
            self.leave_id = None
        self.island.hold(True)

    def _leave(self, *_):
        self.hover = False
        self.island.hold(False)
        if self.expanded and not self.leave_id:
            self.leave_id = GLib.timeout_add(int(LEAVE_TIME * 1000), self._collapse)

    def _collapse(self):
        self.leave_id = None
        self.expanded = False
        self.update()
        return False

    def _click(self, gesture, n, x, y):
        btn = gesture.get_current_button()
        isl = self.island
        if self.kind == "note":
            note = isl.transient.get("note") if isl.transient else None
            if btn == 1 and note:
                spawn("dunstctl", "history-pop", str(note["id"]))
            isl.next_note()
            return
        if btn == 2:
            isl.media.call(isl.media.current(), "PlayPause")
            return
        if btn == 3:
            spawn("gits-panel", "media")
            return
        for x0, y0, x1, y1, fn in self.zones:
            if x0 <= x <= x1 and y0 <= y <= y1:
                fn(x, x0, x1)
                return
        if self.kind in ("rest", "card", "date"):
            self.expanded = not self.expanded
            self.update()

    def _scroll(self, ctl, dx, dy):
        isl = self.island
        if isl.transient and isl.transient["kind"] == "osd" and isl.transient["osd"]["kind"] in ("volume", "brightness"):
            k = isl.transient["osd"]["kind"]
            spawn("gits-vol" if k == "volume" else "gits-bright", "down" if dy > 0 else "up")
            return True
        p = isl.media.current()
        if p:
            isl.media.call(p, "Next" if dy > 0 else "Previous")
        return True

    # -- drawing
    def _draw(self, area, cr, w, h):
        cr.set_operator(cairo.OPERATOR_CLEAR)
        cr.paint()
        cr.set_operator(cairo.OPERATOR_OVER)
        self.zones = []
        sw, sh = self.cur_w, self.cur_h
        if sw < 2 or sh < 2:
            return
        x0 = (WIN_W - sw) / 2
        shape_path(cr, x0, 0, sw, sh)
        cr.set_source_rgba(*rgba(BG, 0.97))
        cr.fill()
        # a frame below the bar's height (the bar's own bottom line runs through the top), brighter in the middle
        accent = RED if self.kind == "osd" and self.island.transient and self.island.transient["osd"].get("muted") else CY
        cr.set_line_width(1)
        c = min(10.0, sh / 3, sw / 6)
        cr.move_to(x0 + 0.5, BAR_H if sh > BAR_H else sh)
        cr.line_to(x0 + 0.5, sh - c)
        cr.line_to(x0 + c, sh - 0.5)
        cr.line_to(x0 + sw - c, sh - 0.5)
        cr.line_to(x0 + sw - 0.5, sh - c)
        cr.line_to(x0 + sw - 0.5, BAR_H if sh > BAR_H else sh)
        cr.set_source_rgba(*rgba(accent, 0.55))
        cr.stroke()
        cr.set_source_rgba(*rgba(CYB if accent == CY else accent, 0.9))
        cr.rectangle(x0 + sw * 0.35, sh - 1.5, sw * 0.3, 1.5)
        cr.fill()
        # the content fades in as the shape reaches its size (the morph)
        off = abs(self.tw - sw) / 40 + abs(self.th - sh) / 16
        alpha = max(0.0, min(1.0, 1 - off))
        if alpha <= 0.02:
            return
        cr.save()
        shape_path(cr, x0, 0, sw, sh)
        cr.clip()
        cr.push_group()
        getattr(self, "_draw_" + self.kind, lambda *a: None)(cr, x0, sw, sh)
        cr.pop_group_to_source()
        cr.paint_with_alpha(alpha)
        cr.restore()

    def _draw_rest(self, cr, x0, w, h):
        isl = self.island
        x = x0 + 14
        y = 4
        now = time.time()
        for icon, label, col, pulse, action in isl.chips:
            a = 0.45 + 0.55 * abs(math.sin(now * 3)) if pulse else 1.0
            cw = text(cr, f"{icon} {label}", x, y, 11, col, alpha=a, bold=True)
            if action:
                self.zones.append((x - 4, 0, x + cw + 4, h, lambda *_ , act=action: spawn(*act)))
            x += cw + 10
            cr.set_source_rgba(*rgba(DIM, 0.6))
            cr.rectangle(x - 5, 6, 1, 13)
            cr.fill()
        cw = text(cr, time.strftime("%H:%M:%S"), x, y, 11, CY, bold=True, spacing=1)
        x += cw
        p = isl.media.current()
        if p:
            x += 10
            cr.set_source_rgba(*rgba(DIM, 0.6))
            cr.rectangle(x - 5, 6, 1, 13)
            cr.fill()
            playing = p["status"] == "Playing"
            for i in range(3):   # the equalizer: three bars, still while paused
                v = 0.35 + 0.65 * abs(math.sin(now * (5.1 + i * 1.7) + i * 1.3)) if playing else 0.3
                bh = 3 + 9 * v
                cr.set_source_rgba(*rgba(CY, 1.0 if playing else 0.5))
                cr.rectangle(x + i * 4, 18 - bh, 2.5, bh)
                cr.fill()
            x += 18
            line = (p["artist"] + " – " if p["artist"] else "") + p["title"]
            text(cr, line, x, y, 11, CY, alpha=1.0 if playing else 0.6, bold=True, width=x0 + w - 14 - x)

    def _draw_card(self, cr, x0, w, h):
        isl = self.island
        p = isl.media.current()
        if not p:
            return
        pad = 14
        ax, ay, asz = x0 + pad, BAR_H + 3, h - BAR_H - 3 - 10
        pix = isl.art.get(p["art"])
        cr.save()
        cr.rectangle(ax, ay, asz, asz)
        if pix:
            cr.clip()
            sc = asz / max(pix.get_width(), pix.get_height())
            cr.translate(ax + (asz - pix.get_width() * sc) / 2, ay + (asz - pix.get_height() * sc) / 2)
            cr.scale(sc, sc)
            Gdk.cairo_set_source_pixbuf(cr, pix, 0, 0)
            cr.paint()
        else:
            cr.set_source_rgba(*rgba(CY, 0.08))
            cr.fill()
            text(cr, "󰎆", ax + asz / 2, ay + asz / 2 - 18, 30, CY, alpha=0.5, align="center")
        cr.restore()
        cr.set_source_rgba(*rgba(CY, 0.5))
        cr.set_line_width(1)
        cr.rectangle(ax + 0.5, ay + 0.5, asz - 1, asz - 1)
        cr.stroke()
        self.zones.append((ax, ay, ax + asz, ay + asz, lambda *_: spawn("gits-panel", "media")))
        tx = ax + asz + 14
        tw = x0 + w - pad - tx
        # top line (in the bar's height): clock left, player right
        text(cr, time.strftime("%H:%M:%S"), x0 + pad, 6, 11, CY, bold=True, spacing=1)
        text(cr, p["short"].split(".")[0].upper(), x0 + w - pad, 7, 9, DIM, bold=True, align="right", spacing=2)
        text(cr, p["title"] or "—", tx, ay - 2, 14, FG, bold=True, width=tw)
        text(cr, p["artist"] or "unknown artist", tx, ay + 18, 11, CY, bold=True, width=tw)
        if p["album"]:
            text(cr, p["album"], tx, ay + 34, 9, DIM, width=tw)
        # progress: segments like the OSD, click to seek
        by = ay + 54
        segs, gap = 40, 2
        sw = (tw - gap * (segs - 1)) / segs
        frac = Media.position(p) / p["length"] if p["length"] else 0
        lit = frac * segs
        for i in range(segs):
            a = 0.95 if i + 1 <= lit else (0.16 + 0.79 * (lit - i) if i < lit else 0.16)
            cr.set_source_rgba(*rgba(CYB if i + 1 <= lit else CY, a))
            cr.rectangle(tx + i * (sw + gap), by, sw, 5)
            cr.fill()
        self.zones.append((tx, by - 6, tx + tw, by + 11, lambda x, a, b: (isl.media.seek(p, (x - a) / (b - a)), self.update())))
        ry = by + 10
        text(cr, fmt_time(Media.position(p) / 1e6), tx, ry, 9, DIM, bold=True)
        if p["length"]:
            text(cr, fmt_time(p["length"] / 1e6), tx + tw, ry, 9, DIM, bold=True, align="right")
        # buttons
        cx = tx + tw / 2
        for dx, icon, method, size in ((-46, "󰒮", "Previous", 16), (0, "󰏤" if p["status"] == "Playing" else "󰐊", "PlayPause", 22),
                                       (46, "󰒭", "Next", 16)):
            text(cr, icon, cx + dx, ry + (0 if size > 16 else 3), size, CYB if method == "PlayPause" else CY, align="center")
            self.zones.append((cx + dx - 18, ry - 4, cx + dx + 18, ry + 28,
                               lambda *_, m=method: (isl.media.call(p, m), GLib.timeout_add(150, lambda: (self.update(), False)[1]))))

    def _draw_date(self, cr, x0, w, h):
        text(cr, "NO SIGNAL", x0 + w / 2, 6, 9, DIM, bold=True, align="center", spacing=3)
        text(cr, time.strftime("%H:%M:%S"), x0 + w / 2, BAR_H, 18, FG, bold=True, align="center", spacing=2)
        text(cr, time.strftime("%A  //  %d %B %Y").upper(), x0 + w / 2, BAR_H + 24, 9, CY, bold=True, align="center", spacing=1)

    def _draw_osd(self, cr, x0, w, h):
        o = self.island.transient["osd"]
        kind, pct, muted, label = o["kind"], o["pct"], o["muted"], o.get("label")
        title, kanji, i_lo, i_mid, i_hi, i_mute = OSD_KINDS.get(kind, OSD_KINDS["volume"])
        icon = i_mute if muted else (i_lo if pct < 34 else i_mid if pct < 67 else i_hi)
        text(cr, icon, x0 + 26, h / 2 - 12, 20, RED if muted else CYB, align="center")
        tw = text(cr, title, x0 + 50, 6, 8, DIM, bold=True, spacing=2)
        text(cr, kanji, x0 + 50 + tw + 8, 5, 8, DIM)
        bx, by, bw, bh = x0 + 50, 25, w - 50 - 66, 10
        if kind == "layout":
            codes = [c for c in (label or "").split(",") if c] or ["??"]
            cur = min(pct, len(codes) - 1)
            gap = 4
            cw = (bw - gap * (len(codes) - 1)) / len(codes)
            for i, code in enumerate(codes):
                x = bx + i * (cw + gap)
                if i == cur:
                    cr.set_source_rgba(*rgba(CY, 0.95))
                    cr.rectangle(x, by, cw, bh)
                    cr.fill()
                else:
                    cr.set_source_rgba(*rgba(CY, 0.35))
                    cr.set_line_width(1)
                    cr.rectangle(x + 0.5, by + 0.5, cw - 1, bh - 1)
                    cr.stroke()
                text(cr, code, x + cw / 2, by - 1, 8, BG if i == cur else DIM, bold=True, align="center")
            text(cr, codes[cur], x0 + w - 14, h / 2 - 10, 14, FG, bold=True, align="right")
            return
        n, gap = 26, 2
        sw = (bw - gap * (n - 1)) / n
        lit = 0 if muted else round(pct / 100 * n)
        for i in range(n):
            frac = (i + 1) / n
            if muted:
                c, a = RED, 0.16
            else:
                c = RED if (frac > 0.9 and kind == "volume") else (CYB if frac > 0.55 else CY)
                a = 0.95 if i < lit else 0.16
            cr.set_source_rgba(*rgba(c, a))
            cr.rectangle(bx + i * (sw + gap), by, sw, bh)
            cr.fill()
        big = not (muted or label)
        text(cr, label or ("MUTED" if muted else f"{pct}%"), x0 + w - 14, h / 2 - (10 if big else 7), 14 if big else 11,
             RED if muted else FG, bold=True, align="right")

    def _draw_note(self, cr, x0, w, h):
        isl = self.island
        n = isl.transient["note"]
        low = n.get("urgency") == "LOW"
        cr.set_source_rgba(*rgba(DIM if low else CY))
        cr.rectangle(x0, 0, 3, h)
        cr.fill()
        ix, iy, isz = x0 + 14, (h - 28) / 2, 28
        pix = isl.icon(n.get("icon"))
        if pix:
            sc = isz / max(pix.get_width(), pix.get_height())
            cr.save()
            cr.translate(ix + (isz - pix.get_width() * sc) / 2, iy + (isz - pix.get_height() * sc) / 2)
            cr.scale(sc, sc)
            Gdk.cairo_set_source_pixbuf(cr, pix, 0, 0)
            cr.paint()
            cr.restore()
        else:
            text(cr, "󰂚", ix + isz / 2, iy + 2, 20, DIM if low else CYB, align="center")
        tx = ix + isz + 12
        tw = x0 + w - 16 - tx
        more = len(isl.notes)
        if more:
            mw = text(cr, f"+{more}", x0 + w - 14, 6, 9, DIM, bold=True, align="right")
            tw0 = tw - mw - 8
        else:
            tw0 = tw
        app = n.get("app") or ""
        head = (app.upper() + "  //  " if app and app not in ("GitS Notify", "notify-send") else "") + (n.get("summary") or "")
        text(cr, head, tx, 5, 11, FG if not low else DIM, bold=True, width=tw0)
        text(cr, (n.get("body") or "").replace("\n", "  "), tx, 25, 10, CY if not low else DIM, width=tw)
        if n.get("progress", -1) >= 0:
            frac = max(0, min(100, n["progress"])) / 100
            cr.set_source_rgba(*rgba(CY, 0.16))
            cr.rectangle(tx, h - 7, tw, 3)
            cr.fill()
            cr.set_source_rgba(*rgba(CYB, 0.95))
            cr.rectangle(tx, h - 7, tw * frac, 3)
            cr.fill()


# ------------------------------------------------------------------------------------------------ the daemon
class Island:
    def __init__(self):
        self.windows = {}
        self.transient = None   # {"kind": "osd"|"note", "connector", "until", "osd"/"note"}
        self.notes = []         # waiting notifications
        self.holding = 0
        self.fullscreen = set()
        self.chips = []
        self._rest_cache = (None, 0)
        self._icons = {}
        self.media = Media(self.changed)
        self.art = Art(self.changed)
        self.acts = Activities()
        self.display = Gdk.Display.get_default()
        css = Gtk.CssProvider()   # the window itself is see-through: only the shape is drawn
        css.load_from_string("window, window.background { background: transparent; box-shadow: none; }")
        Gtk.StyleContext.add_provider_for_display(self.display, css, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
        self.monitors = self.display.get_monitors()
        self.monitors.connect("items-changed", lambda *_: GLib.timeout_add(500, self._sync_windows))
        self._sync_windows()
        self._fifo()
        HyprEvents(self._fs_changed).start()
        self._fs_changed()
        self._second()
        GLib.timeout_add(80, self._anim)
        self.dunst(True)
        Gio.bus_watch_name(Gio.BusType.SESSION, "org.freedesktop.Notifications", Gio.BusNameWatcherFlags.NONE,
                           lambda *_: GLib.timeout_add(1500, lambda: (self.dunst(True), False)[1]), None)

    # -- monitors
    def _sync_windows(self):
        seen = set()
        for i in range(self.monitors.get_n_items()):
            m = self.monitors.get_item(i)
            key = m.get_connector()
            seen.add(key)
            if key not in self.windows:
                self.windows[key] = IslandWindow(self, m)
        for key in list(self.windows):
            if key not in seen:
                self.windows.pop(key).destroy()
        self.changed()
        return False

    def _fs_changed(self):
        fs = fullscreen_connectors()
        if fs != self.fullscreen:
            self.fullscreen = fs
            self.changed()
        return False

    # -- state changes
    def changed(self):
        self._rest_cache = (None, 0)
        for w in self.windows.values():
            w.update()

    def rest_width(self):
        p = self.media.current()
        key = (tuple((c[0], c[1]) for c in self.chips), p and (p["artist"], p["title"]))
        if self._rest_cache[0] == key:
            return self._rest_cache[1]
        w = 28 + text_w("00:00:00", 11, True, spacing=1)
        for icon, label, *_ in self.chips:
            w += text_w(f"{icon} {label}", 11, True) + 10
        if p:
            line = (p["artist"] + " – " if p["artist"] else "") + p["title"]
            w += 10 + 18 + min(300, text_w(line, 11, True))
        w = int(min(WIN_W - 20, w))
        self._rest_cache = (key, w)
        return w

    def _second(self):
        chips = self.acts.chips()
        if [c[:2] for c in chips] != [c[:2] for c in self.chips]:
            self.chips = chips
            self.changed()
        else:
            self.chips = chips
        t = self.transient
        if t and not self.holding and time.monotonic() >= t["until"]:
            self.next_note() if t["kind"] == "note" else self._end_transient()
        for w in self.windows.values():
            w.da.queue_draw()
        GLib.timeout_add(1000 - int(time.time() * 1000) % 1000 + 5, self._second)   # on the second, for the clock
        return False

    def _anim(self):
        """Equalizer / pulse frames: only redraw resting islands that have something moving."""
        p = self.media.current()
        moving = (p and p["status"] == "Playing") or any(c[3] for c in self.chips)
        if moving:
            for w in self.windows.values():
                if w.kind == "rest" and w.tick_id is None:
                    w.da.queue_draw()
        return True

    def hold(self, on):
        self.holding = max(0, self.holding + (1 if on else -1))
        if not on and self.transient:
            self.transient["until"] = max(self.transient["until"], time.monotonic() + 1.2)

    def _end_transient(self):
        self.transient = None
        self.changed()

    def show_osd(self, msg):
        try:
            pct = int(float(msg.get("pct", 0)))
        except (TypeError, ValueError):
            pct = 0
        o = {"kind": msg.get("kind", "volume"), "pct": max(0, min(100, pct)), "muted": bool(msg.get("muted")) and msg.get("kind") != "layout",
             "label": msg.get("label") or None}
        t = self.transient
        if t and t["kind"] == "note":
            self.notes.insert(0, t["note"])   # the notification comes back after the OSD
        conn = t["connector"] if t and t["kind"] == "osd" else focused_connector()
        self.transient = {"kind": "osd", "osd": o, "connector": conn, "until": time.monotonic() + OSD_TIME}
        self.changed()

    def add_note(self, n):
        t = self.transient
        if t and t["kind"] == "note" and t["note"]["id"] == n["id"]:
            t["note"] = n
            t["until"] = time.monotonic() + (NOTE_TIME_LOW if n.get("urgency") == "LOW" else NOTE_TIME)
            self.changed()
            return
        for i, q in enumerate(self.notes):
            if q["id"] == n["id"]:
                self.notes[i] = n
                return
        self.notes = (self.notes + [n])[-8:]
        if not t:
            self.next_note()

    def next_note(self):
        if not self.notes:
            self._end_transient()
            return
        n = self.notes.pop(0)
        self.transient = {"kind": "note", "note": n, "connector": focused_connector(),
                          "until": time.monotonic() + (NOTE_TIME_LOW if n.get("urgency") == "LOW" else NOTE_TIME)}
        self.changed()

    def icon(self, path):
        if not path or not os.path.isfile(path):
            return None
        if path not in self._icons:
            try:
                self._icons[path] = GdkPixbuf.Pixbuf.new_from_file_at_scale(path, 80, 80, True)
            except GLib.Error:
                self._icons[path] = None
            if len(self._icons) > 64:
                self._icons.pop(next(iter(self._icons)))
        return self._icons[path]

    # -- input
    def _fifo(self):
        try:
            os.mkfifo(FIFO, 0o600)
        except FileExistsError:
            pass
        self.fd = os.open(FIFO, os.O_RDWR | os.O_NONBLOCK)
        self.buf = b""
        GLib.io_add_watch(self.fd, GLib.PRIORITY_DEFAULT, GLib.IOCondition.IN, self._readable)

    def _readable(self, fd, cond):
        try:
            self.buf += os.read(fd, 65536)
        except OSError:
            return True
        *lines, self.buf = self.buf.split(b"\n")
        osd = None
        for ln in lines:
            try:
                m = json.loads(ln)
            except ValueError:
                continue
            t = m.get("t")
            if t == "osd":
                osd = m   # a burst of key repeats: only the newest
            elif t == "note":
                self.add_note(m)
            elif t == "expand":   # gits-island expand: the card on the focused monitor (or back)
                win = self.windows.get(focused_connector()) or next(iter(self.windows.values()), None)
                if win:
                    win.expanded = not win.expanded
                    win.update()
                    if win.expanded and not win.hover:   # opened from the keyboard: it leaves by itself unless the pointer comes
                        win.leave_id = win.leave_id or GLib.timeout_add(4000, win._collapse)
            elif t == "activity":
                self.acts.push(m)
                self.chips = self.acts.chips()
                self.changed()
        if osd:
            self.show_osd(osd)
        return True

    def dunst(self, on):
        for r in DUNST_RULES:
            spawn("dunstctl", "rule", r, "enable" if on else "disable")
        return False


def main():
    if not conf_on():
        return 0
    if not LS.is_supported():
        print("gits-island: the compositor has no layer-shell", file=sys.stderr)
        return 1
    Gtk.init()
    loop = GLib.MainLoop()
    with open(PIDFILE, "w") as f:
        f.write(str(os.getpid()))
    isl = Island()
    for sig in (2, 15):
        GLibUnix.signal_add(GLib.PRIORITY_DEFAULT, sig, lambda: (loop.quit(), False)[1])
    loop.run()
    subprocess.run(["dunstctl", "rule", DUNST_RULES[0], "disable"], capture_output=True, timeout=3)
    subprocess.run(["dunstctl", "rule", DUNST_RULES[1], "disable"], capture_output=True, timeout=3)
    del isl
    for f in (FIFO, PIDFILE):
        try:
            os.unlink(f)
        except OSError:
            pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
