#!/usr/bin/env python3
"""Ghost in the Shell control panel: a small layer-shell popup under the bar (toggle with `gits-panel`, Super+Shift+C).

Toggles: Wi-Fi, Bluetooth, do-not-disturb, night light, UI sounds, desktop widgets.
Sliders: volume (wpctl), brightness (brightnessctl). Segments: power profile (power-profiles-daemon), battery charge
limit (asusctl, ASUS only). Closes on Escape or when it loses focus. Everything is read/written through the same CLI
tools the bar modules use, so the bar and the panel never disagree for long.
"""
import ast
import json
import math
import operator
import os
import re
import shlex
import shutil
import socket
import subprocess
import sys
import threading
import time
import urllib.parse
import urllib.request

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
gi.require_version("GdkPixbuf", "2.0")
gi.require_version("Gio", "2.0")
from gi.repository import Gdk, GdkPixbuf, Gio, GLib, GLibUnix, Gtk, Pango  # noqa: E402
from gi.repository import Gtk4LayerShell as LS  # noqa: E402
# gtk4-layer-shell only has to be preloaded into THIS process: every child (bash, git, nmcli, hyprctl...) inherited it and loaded GTK's
# libraries for nothing, which made each spawned command several times slower
os.environ.pop("LD_PRELOAD", None)

try:
    from spectrum import StreamSpectrum   # only the radio popup needs these two (numpy, pactl, parec / Pillow, numpy, cairo)
except ImportError:
    StreamSpectrum = None
try:
    import dancer
except ImportError:
    dancer = None

HERE = os.path.dirname(os.path.abspath(__file__))
HOME = os.path.expanduser("~")
STATE = os.environ.get("XDG_STATE_HOME", HOME + "/.local/state")
DEMO = os.environ.get("GITS_PANEL_DEMO") == "1"  # screenshot mode: fixed made-up state, no commands executed


def sh(cmd, timeout=4, real=False):
    """Run a command (list), return stdout ('' on any failure). Screenshot mode returns '' unless the data is not personal (real=True)."""
    if DEMO and not real:
        return ""
    try:
        return subprocess.run(cmd, capture_output=True, text=True, errors="replace", timeout=timeout).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return ""


def fire(cmd):
    """Run a command without waiting."""
    if not DEMO:
        try:
            subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
        except OSError:
            pass


def label(text, css=None, xalign=0.0):
    lb = Gtk.Label(label=text, xalign=xalign)
    for c in (css or "").split():
        lb.add_css_class(c)
    return lb


# ---------------------------------------------------------------------------------------------- state readers
def get_wifi():
    return sh(["nmcli", "radio", "wifi"]) == "enabled"


def get_bt():
    return "Powered: yes" in sh(["bluetoothctl", "show"])


def get_dnd():
    return sh(["dunstctl", "is-paused"]) == "true"


def get_night():
    """Night light is on when hyprsunset's temperature differs from the neutral 6000 K (schedule or manual)."""
    t = sh(["hyprctl", "hyprsunset", "temperature"])
    return t.isdigit() and int(t) != 6000


def get_sounds():
    return not os.path.exists(STATE + "/gits-sounds/off")


def get_widgets():
    try:
        pid = open(os.environ.get("XDG_RUNTIME_DIR", "/tmp") + "/gits-widgets.pid").read().strip()
        return os.path.exists(f"/proc/{int(pid)}")
    except (OSError, ValueError):
        return False


def get_awake():
    """Caffeine: on while the idle unit (hypridle) is stopped (the screen never locks or sleeps by itself)."""
    return subprocess.run(["systemctl", "--user", "is-active", "--quiet", "gits-idle.service"]).returncode != 0 if not DEMO else False


def set_awake():
    fire(["systemctl", "--user", "stop" if not get_awake() else "start", "gits-idle.service"])


def get_airplane():
    rows = sh(["rfkill", "list", "-n", "-o", "SOFT"]).split()
    return bool(rows) and all(r == "blocked" for r in rows)


def get_game():
    try:
        return "workflow=gaming" in open(STATE + "/gits/state").read().split()
    except OSError:
        return False


def get_kbd():
    try:
        base = "/sys/class/leds/asus::kbd_backlight/"
        return int(open(base + "brightness").read()), int(open(base + "max_brightness").read())
    except (OSError, ValueError):
        return None


def get_touchpad():
    return sh(["gits-touchpad", "status"]) != "off"


GLITCH_FLAG = STATE + "/gits-widgets/no-glitch"


def get_glitch():
    return not os.path.exists(GLITCH_FLAG)


def set_glitch():
    if os.path.exists(GLITCH_FLAG):
        os.remove(GLITCH_FLAG)
    else:
        os.makedirs(os.path.dirname(GLITCH_FLAG), exist_ok=True)
        open(GLITCH_FLAG, "w").close()


def get_volume():
    m = re.search(r"([0-9.]+)(\s+\[MUTED\])?", sh(["wpctl", "get-volume", "@DEFAULT_AUDIO_SINK@"]))
    return (round(float(m.group(1)) * 100), bool(m.group(2))) if m else (0, False)


def get_brightness():
    parts = sh(["brightnessctl", "-m"]).split(",")
    try:
        return int(parts[3].rstrip("%"))
    except (IndexError, ValueError):
        return None


def get_profile():
    return sh(["powerprofilesctl", "get"]) or "balanced"


def get_charge_limit():
    m = re.search(r"(\d+)%", sh(["asusctl", "battery", "info"]))
    return int(m.group(1)) if m else None


def battery_line():
    base = "/sys/class/power_supply/BAT0"
    try:
        cap = open(base + "/capacity").read().strip()
        status = open(base + "/status").read().strip()
        watts = int(open(base + "/power_now").read()) / 1e6
        return f"󰁹 {cap}%  {status.lower()}  {watts:.1f} W"
    except (OSError, ValueError):
        return ""


# ---------------------------------------------------------------------------------------------- widgets
class Tile(Gtk.Button):
    """A toggle tile: icon + name + ON/OFF, class `on` when active."""

    def __init__(self, icon, name, getter, setter):
        super().__init__()
        self.add_css_class("tile")
        self.getter, self.setter, self.name = getter, setter, name
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=1)
        self.l_icon = label(icon, "tile-icon")
        self.l_name = label(name, "tile-name")
        self.l_state = label("…", "tile-state")
        for x in (self.l_icon, self.l_name, self.l_state):
            box.append(x)
        self.set_child(box)
        self.set_hexpand(True)
        self.connect("clicked", self._click)

    def show_state(self, on):
        (self.add_css_class if on else self.remove_css_class)("on")
        self.l_state.set_text("ON" if on else "OFF")

    def _click(self, *_):
        if os.environ.get("GITS_PANEL_DEBUG"):
            open(os.environ["GITS_PANEL_DEBUG"], "a").write("tile-click\n")
        self.setter()
        # refresh from the real state a moment later (the command needs time to take effect)
        GLib.timeout_add(350, lambda: threading.Thread(target=lambda: GLib.idle_add(self.show_state, self.getter()),
                                                       daemon=True).start() or False)


class Segments(Gtk.Box):
    """A row of mutually exclusive buttons; `choose(value)` highlights one."""

    def __init__(self, options, on_pick):
        super().__init__(spacing=0)
        self.add_css_class("segs")
        self.btns = {}
        self.set_hexpand(True)
        for text, value in options:
            b = Gtk.Button(label=text)
            b.add_css_class("seg")
            b.set_hexpand(True)
            b.connect("clicked", lambda _b, v=value: on_pick(v))
            self.append(b)
            self.btns[value] = b

    def choose(self, value):
        for v, b in self.btns.items():
            (b.add_css_class if v == value else b.remove_css_class)("on")


class Popup(Gtk.Window):
    """A popup as ONE fullscreen, transparent, keyboard-exclusive layer surface that holds the visible card.

    Why fullscreen: Hyprland routes ALL input to an exclusive-keyboard layer surface, so a separate click catcher below the
    popup never sees a click, and a popup that only covers its own rectangle never sees clicks outside it. As one big surface it
    gets every click: outside the card = close (this also makes a click on the bar button a toggle), Escape = close.
    `left` = None puts the card at the right edge (control panel, notifications), else `left` px from the left edge (media)."""
    CARD_W = 300
    TOP = 58  # below the bar (the surface ignores the bar's exclusive zone, so the bar height is part of the margin)

    def __init__(self, monitor, left=None, center=False):
        super().__init__()
        self.set_decorated(False)
        self.add_css_class("panel-win")
        self.left = left
        self.center = center
        self.hcenter = False   # centred horizontally under the bar (the media popup), instead of hugging a corner
        LS.init_for_window(self)
        LS.set_namespace(self, "gits-panel")
        LS.set_layer(self, LS.Layer.OVERLAY)
        for edge in (LS.Edge.TOP, LS.Edge.BOTTOM, LS.Edge.LEFT, LS.Edge.RIGHT):
            LS.set_anchor(self, edge, True)
        LS.set_exclusive_zone(self, -1)
        LS.set_keyboard_mode(self, LS.KeyboardMode.EXCLUSIVE)
        if monitor is not None:
            LS.set_monitor(self, monitor)
        self.card = None
        key = Gtk.EventControllerKey()
        key.connect("key-pressed", lambda _c, kv, *_: (self.dismiss(), True)[1] if kv == Gdk.KEY_Escape else False)
        self.add_controller(key)
        click = Gtk.GestureClick()
        click.set_button(0)
        click.connect("pressed", self._pressed)
        self.add_controller(click)
        if os.environ.get("GITS_PANEL_DEBUG"):
            GLib.timeout_add(1200, lambda: (open(os.environ["GITS_PANEL_DEBUG"], "a").write(
                f"card {self.card.get_width()}x{self.card.get_height()}\n"), False)[1])

    def set_child(self, card):
        """Called by the subclasses with their card: place it in the corner of the fullscreen surface, inside a stack that plays the
        GitS "power-on" effect: the card opens from a thin line with two glitch flickers while a bright scan line sweeps down it."""
        self.card = card
        card.set_size_request(self.CARD_W, -1)
        scan = Gtk.DrawingArea()
        scan.set_can_target(False)
        scan.set_draw_func(self._draw_scan)
        self.scan = scan
        slow = 10 if os.environ.get("GITS_PANEL_SLOW") else 1
        self.rev = Gtk.Revealer()   # opens the card from the top, like a scan line uncovering it
        self.rev.set_transition_type(Gtk.RevealerTransitionType.SLIDE_UP)
        self.rev.set_transition_duration(self.OPEN_MS * slow)
        self.rev.set_child(card)
        stack = Gtk.Overlay()
        stack.add_css_class("reveal")
        if slow > 1:
            stack.add_css_class("slow")   # 10x slower, for frame-by-frame screenshots
        stack.set_child(self.rev)
        stack.add_overlay(scan)
        self.stack = stack
        stack.set_valign(Gtk.Align.START)
        stack.set_margin_top(self.TOP)
        if self.center:
            stack.set_halign(Gtk.Align.CENTER)
            stack.set_margin_top(110)
        elif self.hcenter:
            stack.set_halign(Gtk.Align.CENTER)
        elif self.left is None:
            stack.set_halign(Gtk.Align.END)
            stack.set_margin_end(8)
        else:
            stack.set_halign(Gtk.Align.START)
            stack.set_margin_start(self.left)
        wrap = Gtk.Box()
        wrap.append(stack)
        super().set_child(wrap)
        self.scan_t0 = None
        self.connect("map", self._on_map)

    # -- the reveal and the scan line at its leading edge
    OPEN_MS, FADE_S = 300, 0.18

    def _on_map(self, *_):
        GLib.idle_add(lambda: (self.rev.set_reveal_child(True), False)[1])
        self.scan.add_tick_callback(self._scan_tick)

    def _scan_tick(self, widget, clock):
        slow = 10 if os.environ.get("GITS_PANEL_SLOW") else 1
        now = clock.get_frame_time() / 1e6
        if self.scan_t0 is None:
            self.scan_t0 = now
        t = now - self.scan_t0
        self.scan_t = t
        widget.queue_draw()
        if t > self.OPEN_MS / 1000 * slow + self.FADE_S * slow:   # done: nothing redraws while the popup just sits there
            self.scan_t = None
            return GLib.SOURCE_REMOVE
        return GLib.SOURCE_CONTINUE

    def _draw_scan(self, area, cr, w, h):
        t = getattr(self, "scan_t", None)
        if t is None:
            return
        import random
        import cairo as _c
        slow = 10 if os.environ.get("GITS_PANEL_SLOW") else 1
        open_s = self.OPEN_MS / 1000 * slow
        fade = 1.0 if t <= open_s else max(0.0, 1 - (t - open_s) / (self.FADE_S * slow))
        y = h - 1          # the drawing area is exactly as tall as the part of the card that is uncovered so far
        # trail: a faint cyan glow above the leading edge
        g = _c.LinearGradient(0, max(y - 46, 0), 0, y)
        g.add_color_stop_rgba(0, 0.18, 0.83, 0.84, 0.0)
        g.add_color_stop_rgba(1, 0.18, 0.83, 0.84, 0.24 * fade)
        cr.set_source(g)
        cr.rectangle(0, max(y - 46, 0), w, min(46, y))
        cr.fill()
        # the line itself: bright white-cyan core with a cyan halo
        cr.set_source_rgba(0.18, 0.83, 0.84, 0.40 * fade)
        cr.rectangle(0, y - 2, w, 4)
        cr.fill()
        cr.set_source_rgba(0.72, 0.99, 1.0, 0.98 * fade)
        cr.rectangle(0, y - 1, w, 1.5)
        cr.fill()
        # glitch: a few displaced slivers right behind the line (cyan, sometimes red)
        rnd = random.Random(int(t * 45 / slow))
        for _ in range(3):
            gy = y - rnd.uniform(4, 34)
            if gy < 0:
                continue
            gw = rnd.uniform(0.15, 0.55) * w
            gx = rnd.uniform(0, w - gw)
            if rnd.random() < 0.4:
                cr.set_source_rgba(0.9, 0.26, 0.17, 0.20 * fade)
            else:
                cr.set_source_rgba(0.18, 0.83, 0.84, 0.24 * fade)
            cr.rectangle(gx, gy, gw, rnd.choice((1, 1, 2, 3)))
            cr.fill()

    # -- closing with a collapse instead of vanishing
    def dismiss(self):
        if getattr(self, "_dismissing", False) or self.card is None:
            return
        self._dismissing = True
        slow = 10 if os.environ.get("GITS_PANEL_SLOW") else 1
        self.stack.add_css_class("closing")
        self.rev.set_transition_duration(140 * slow)
        self.rev.set_reveal_child(False)          # the card folds back up into a line
        GLib.timeout_add(160 * slow, lambda: (Gtk.Window.close(self), False)[1])

    def _pressed(self, gesture, n, x, y):
        if self.card is None:
            return
        ok, rect = self.card.compute_bounds(self)
        if os.environ.get("GITS_PANEL_DEBUG"):
            open(os.environ["GITS_PANEL_DEBUG"], "a").write(f"pressed {x:.0f},{y:.0f} card={rect.get_x():.0f},{rect.get_y():.0f} {rect.get_width():.0f}x{rect.get_height():.0f}\n")
        inside = ok and rect.get_x() <= x <= rect.get_x() + rect.get_width() and rect.get_y() <= y <= rect.get_y() + rect.get_height()
        if not inside:
            self.dismiss()

    def header(self, title):
        head = Gtk.Box(spacing=6)
        head.append(label(title, "tag"))
        sp = Gtk.Box()
        sp.set_hexpand(True)
        head.append(sp)
        head.append(label("▪", "tag-dot"))
        return head


class Panel(Popup):
    def __init__(self, monitor):
        super().__init__(monitor)
        self.quiet = False  # True while we set slider values from the state (no command must fire)
        self.timers = {}

        root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=9)
        root.add_css_class("panel")
        root.append(self.header("CONTROL // 制御"))

        def toggle_cmd(cmd_on_off):
            return lambda: fire(cmd_on_off)

        wifi = Tile("󰖩", "WI-FI", get_wifi, lambda: fire(["nmcli", "radio", "wifi", "off" if get_wifi() else "on"]))
        bt = Tile("󰂯", "BLUETOOTH", get_bt, lambda: fire(["bluetoothctl", "power", "off" if get_bt() else "on"]))
        dnd = Tile("󰂛", "SILENT", get_dnd, lambda: fire(["dunstctl", "set-paused", "toggle"]))
        night = Tile("󰖔", "NIGHT", get_night, lambda: fire(["gits-daynight", "toggle"]))
        snd = Tile("󰝚", "SOUNDS", get_sounds, lambda: fire(["gits-sound", "toggle"]))
        wid = Tile("󰕮", "WIDGETS", get_widgets, lambda: fire([HERE + "/run.sh", "toggle"]))
        awake = Tile("󰅶", "AWAKE", get_awake, set_awake)
        plane = Tile("󰀝", "AIRPLANE", get_airplane, lambda: fire(["rfkill", "unblock" if get_airplane() else "block", "all"]))
        game = Tile("󰊗", "GAME", get_game, lambda: fire(["gits-workflow", "toggle", "gaming"]))
        self.tiles = [wifi, bt, dnd, night, snd, wid, awake, plane, game]
        pad = Tile("󰍽", "TOUCHPAD", get_touchpad, lambda: fire(["gits-touchpad", "toggle"]))
        glitch = Tile("󰘨", "GLITCH", get_glitch, set_glitch)
        rec = Tile("󰑋", "REC", lambda: sh(["gits-rec", "status"]) == "on", lambda: self._later("gits-rec toggle area"))
        focus = Tile("󱎫", "FOCUS", lambda: sh(["gits-focus", "status"]) == "on", lambda: fire(["gits-focus", "toggle"]))
        self.tiles += [pad, glitch, rec, focus]
        for row in (self.tiles[:3], self.tiles[3:6], self.tiles[6:9], self.tiles[9:]):
            r = Gtk.Box(spacing=6, homogeneous=True)
            for t in row:
                r.append(t)
            root.append(r)

        self.vol = self._slider(root, "VOL", self._set_volume)
        self.bri = self._slider(root, "LIGHT", self._set_brightness)

        self.kbd = Segments([("OFF", 0), ("LOW", 1), ("MED", 2), ("HIGH", 3)], self._set_kbd)
        self.kbd_row = self._row(root, "KEYS", self.kbd)
        self.prof = Segments([("PERF", "performance"), ("BAL", "balanced"), ("SAVE", "power-saver")], self._set_profile)
        self.chg = Segments([("60", 60), ("80", 80), ("100", 100)], self._set_charge)
        self._row(root, "POWER", self.prof)
        self.chg_row = self._row(root, "CHARGE", self.chg)

        # tools: close the panel first (it must not end up in the screenshot), then run
        tools = Gtk.Box(spacing=6, homogeneous=True)
        for icon, name, cmd in (("󰄀", "SHOT", "gits-shot area"), ("󰗊", "OCR", "gits-shot ocr"),
                                ("󰈊", "PICK", "hyprpicker -an"), ("󰅍", "CLIP", "gits-panel clip"),
                                ("󰑊", "REC", "gits-rec toggle area")) + ((("󰢮", "ROG", "gits-rog"),) if shutil.which("rog-control-center") and os.path.isdir("/sys/devices/platform/asus-nb-wmi") else ()):
            tools.append(self._action(icon, name, lambda c=cmd: self._later(c)))
        root.append(tools)
        wide = Gtk.Box(spacing=6, homogeneous=True)
        for icon, name, cmd in (("󰤄", "SLEEP TIMERS", "gits-idle menu"), ("󰒓", "ALL SETTINGS", "gits-settings")):
            b = Gtk.Button()
            b.add_css_class("act")
            b.add_css_class("wide")
            bx = Gtk.Box(spacing=8, halign=Gtk.Align.CENTER)
            bx.append(label(icon, "act-icon"))
            bx.append(label(name, "act-name"))
            b.set_child(bx)
            b.connect("clicked", lambda *_, c=cmd: self._later(c))
            wide.append(b)
        root.append(wide)
        # session: lock / sleep / logout run at once, reboot and power off ask twice
        sess = Gtk.Box(spacing=6, homogeneous=True)
        sess.append(self._action("󰌾", "LOCK", lambda: self._later("loginctl lock-session")))
        sess.append(self._action("󰤄", "SLEEP", lambda: self._later("systemctl suspend")))
        sess.append(self._action("󰍃", "LOGOUT", lambda: self._later("gits-exit")))
        sess.append(self._action("󰜉", "REBOOT", lambda: self._later("systemctl reboot"), confirm=True))
        sess.append(self._action("󰐥", "OFF", lambda: self._later("systemctl poweroff"), confirm=True))
        root.append(sess)

        footer = Gtk.Box(spacing=8)
        self.foot = label("", "foot")
        self.foot.set_hexpand(True)
        footer.append(self.foot)
        self.health = Gtk.Button(label="● health…")
        self.health.add_css_class("health")
        self.health.connect("clicked", lambda *_: self._later(
            "kitty --hold sh -c 'gits-doctor; echo; read -rp \"repair what can be repaired (gits-doctor --fix)? [y/N] \" a; [ \"$a\" = y ] && gits-doctor --fix'"))
        footer.append(self.health)
        root.append(footer)
        self.set_child(root)
        threading.Thread(target=self._health, daemon=True).start()

        threading.Thread(target=self._load, daemon=True).start()

    # -- layout helpers
    def _row(self, root, name, widget):
        r = Gtk.Box(spacing=8)
        r.append(label(name, "row-name"))
        r.append(widget)
        root.append(r)
        return r

    def _slider(self, root, name, cb):
        s = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 0, 100, 1)
        s.set_draw_value(False)
        s.set_hexpand(True)
        val = label("", "row-val", 1.0)
        val.set_width_chars(5)
        s.connect("value-changed", lambda sc: self._slider_moved(name, sc, val, cb))
        r = Gtk.Box(spacing=8)
        r.append(label(name, "row-name"))
        r.append(s)
        r.append(val)
        root.append(r)
        s.val_label = val
        return s

    def _slider_moved(self, name, sc, val, cb):
        v = int(sc.get_value())
        val.set_text(f"{v}%")
        if self.quiet:
            return
        if name in self.timers:
            GLib.source_remove(self.timers[name])
        self.timers[name] = GLib.timeout_add(80, lambda: (self.timers.pop(name, None), cb(v), False)[2])  # debounce

    def _health(self):
        """gits-doctor -q takes ~1 s: run it off the UI thread and show the totals as a coloured chip."""
        if DEMO:
            out = "\x1b[0m47 ok, 0 warn, 0 fail"
        else:
            out = sh(["gits-doctor", "-q"], timeout=20)
        import re
        m = re.search(r"(\d+) ok\D+(\d+) warn\D+(\d+) fail", re.sub(r"\x1b\[[0-9;]*m", "", out))
        GLib.idle_add(self._show_health, tuple(int(x) for x in m.groups()) if m else None)

    def _show_health(self, t):
        for c in ("ok", "warn", "bad"):
            self.health.remove_css_class(c)
        if t is None:
            self.health.set_label("● health ?")
            return
        ok, warn, bad = t
        cls = "bad" if bad else ("warn" if warn else "ok")
        self.health.add_css_class(cls)
        self.health.set_label(f"● {bad} fail · {warn} warn" if (bad or warn) else f"● all {ok} checks ok")

    # -- actions
    def _action(self, icon, name, cb, confirm=False):
        b = Gtk.Button()
        b.add_css_class("act")
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=1)
        box.append(label(icon, "act-icon", 0.5))
        lb = label(name, "act-name", 0.5)
        box.append(lb)
        b.set_child(box)
        state = {"armed": None}

        def click(*_):
            if not confirm:
                cb()
                return
            if state["armed"] is None:  # first click: arm, second within 7 s: do it
                b.add_css_class("warn")
                lb.set_text("CONFIRM")
                state["armed"] = GLib.timeout_add(7000, disarm)
            else:
                GLib.source_remove(state["armed"])
                state["armed"] = None
                cb()

        def disarm():
            b.remove_css_class("warn")
            lb.set_text(name)
            state["armed"] = None
            return False

        b.connect("clicked", click)
        return b

    def _later(self, cmd):
        """Close the panel, then run a shell command a moment later (screenshots must not catch the panel)."""
        fire(["sh", "-c", f"sleep 0.45; {cmd}"])
        self.dismiss()

    def _set_kbd(self, n):
        fire(["asusctl", "leds", "set", ["off", "low", "med", "high"][n]])
        self.kbd.choose(n)

    def _set_volume(self, v):
        fire(["wpctl", "set-volume", "@DEFAULT_AUDIO_SINK@", f"{v}%"])

    def _set_brightness(self, v):
        fire(["brightnessctl", "-q", "set", f"{max(v, 1)}%"])

    def _set_profile(self, p):
        fire(["powerprofilesctl", "set", p])
        self.prof.choose(p)
        GLib.timeout_add(600, lambda: (fire(["pkill", "-RTMIN+9", "-x", "waybar"]), False)[1])

    def _set_charge(self, n):
        fire(["asusctl", "battery", "limit", str(n)])
        self.chg.choose(n)

    # -- state
    def _load(self):
        st = {t.name: t.getter() for t in self.tiles}
        if DEMO:
            st = {"WI-FI": True, "BLUETOOTH": True, "SILENT": False, "NIGHT": False, "SOUNDS": True, "WIDGETS": True}
            vol, bri, prof, lim, kbd = (46, False), 82, "balanced", 80, (2, 3)
            st.update({"AWAKE": False, "AIRPLANE": False, "GAME": False, "TOUCHPAD": True, "GLITCH": True, "REC": False, "FOCUS": False})
        else:
            vol, bri, prof, lim, kbd = get_volume(), get_brightness(), get_profile(), get_charge_limit(), get_kbd()
        GLib.idle_add(self._apply, st, vol, bri, prof, lim, kbd, battery_line() or ("󰁹 98%  full  0.0 W" if DEMO else ""))

    def _apply(self, st, vol, bri, prof, lim, kbd, bat):
        for t in self.tiles:
            t.show_state(st.get(t.name, False))
        self.quiet = True
        self.vol.set_value(vol[0])
        self.vol.val_label.set_text("MUTE" if vol[1] else f"{vol[0]}%")
        if bri is None:
            self.bri.set_sensitive(False)
        else:
            self.bri.set_value(bri)
        self.quiet = False
        self.prof.choose(prof)
        if lim is None:
            self.chg_row.set_visible(False)  # not an ASUS laptop
        else:
            self.chg.choose(min((60, 80, 100), key=lambda x: abs(x - lim)))
        if kbd is None:
            self.kbd_row.set_visible(False)
        else:
            self.kbd.choose(kbd[0])
        self.foot.set_text(bat)




def fmt_time(sec):
    sec = int(max(sec, 0))
    return f"{sec // 3600}:{sec % 3600 // 60:02d}:{sec % 60:02d}" if sec >= 3600 else f"{sec // 60}:{sec % 60:02d}"


class CoverArea(Gtk.DrawingArea):
    """Album art in a fixed square, scaled to cover and centre-cropped. A Gtk.Picture reports the picture's own size as its
    natural size, so a big or oddly shaped cover used to stretch the whole popup; this widget never asks for more than `size`."""

    def __init__(self, width, height):
        super().__init__()
        self.size = max(width, height)
        self.pix = None
        self.set_content_width(width)
        self.set_content_height(height)
        self.set_hexpand(False)
        self.set_vexpand(False)
        self.set_halign(Gtk.Align.CENTER)
        self.set_draw_func(self._draw)

    def set_path(self, path):
        try:  # decode at most 2x the display size: enough for a sharp crop, cheap for a 4000 px cover
            self.pix = GdkPixbuf.Pixbuf.new_from_file_at_scale(path, self.size * 2, self.size * 2, True) if path else None
        except GLib.Error:
            self.pix = None
        self.queue_draw()

    def _draw(self, area, cr, w, h):
        if self.pix is None:
            return
        pw, ph = self.pix.get_width(), self.pix.get_height()
        k = max(w / pw, h / ph)
        cr.rectangle(0, 0, w, h)
        cr.clip()
        cr.translate((w - pw * k) / 2, (h - ph * k) / 2)
        cr.scale(k, k)
        Gdk.cairo_set_source_pixbuf(cr, self.pix, 0, 0)
        cr.paint()


class ArtMixin:
    """Cover art for a popup that has `self.cover` (a CoverArea) and `self.art_key`: file:// paths at once, http(s) URLs downloaded
    once into a cache."""
    CACHE = os.path.join(os.environ.get("XDG_CACHE_HOME", HOME + "/.cache"), "gits-widgets", "art")

    def _load_art(self, url):
        if not url:
            self.cover.set_path(None)
            return
        if url.startswith("file://"):
            self._set_cover(urllib.parse.unquote(url[7:]))
            return
        import hashlib
        path = os.path.join(self.CACHE, hashlib.sha1(url.encode()).hexdigest())
        if os.path.exists(path):
            self._set_cover(path)
            return

        def work():
            try:
                os.makedirs(self.CACHE, exist_ok=True)
                req = urllib.request.Request(url, headers={"User-Agent": "gits-panel"})
                with urllib.request.urlopen(req, timeout=8) as r, open(path + ".tmp", "wb") as f:
                    f.write(r.read())
                os.replace(path + ".tmp", path)
                GLib.idle_add(lambda: (self.art_key == url and self._set_cover(path), False)[1])
            except (OSError, ValueError):
                pass

        threading.Thread(target=work, daemon=True).start()

    def _set_cover(self, path):
        self.cover.set_path(path)


class PlayerPage(ArtMixin, Gtk.Box):
    """One page of the media carousel: an MPRIS player (playerctl -p NAME): cover, title, seek bar, transport, shuffle/repeat, player volume."""

    def __init__(self, name):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=7)
        self.name = name
        self.alive = True
        self.quiet = False
        self.art_key = None
        self.length = 0.0
        self.seek_timer = None
        self.cover = CoverArea(274, 250)  # fills the card's inner width (304 - padding - frame), fixed height
        self.cover.add_css_class("cover")
        frame = Gtk.Box()
        frame.add_css_class("cover-frame")
        frame.append(self.cover)
        ov = Gtk.Overlay()
        ov.set_child(frame)
        self.nosig = label("NO SIGNAL", "nosig", 0.5)
        self.nosig.set_halign(Gtk.Align.CENTER)
        self.nosig.set_valign(Gtk.Align.CENTER)
        ov.add_overlay(self.nosig)
        self.append(ov)

        self.title = label("—", "m-title")
        self.title.set_ellipsize(Pango.EllipsizeMode.END)
        self.title.set_max_width_chars(30)
        self.artist = label("", "m-artist")
        self.artist.set_ellipsize(Pango.EllipsizeMode.END)
        self.artist.set_max_width_chars(34)
        self.append(self.title)
        self.append(self.artist)

        self.seek = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 0, 100, 1)
        self.seek.set_draw_value(False)
        self.seek.set_hexpand(True)
        self.seek.connect("value-changed", self._seek_moved)
        self.append(self.seek)
        times = Gtk.Box()
        self.t_pos, self.t_len = label("0:00", "m-time"), label("0:00", "m-time", 1.0)
        self.t_len.set_hexpand(True)
        times.append(self.t_pos)
        times.append(self.t_len)
        self.append(times)

        ctl = Gtk.Box(spacing=6, homogeneous=True)
        def btn(text, cb, css="ctl"):
            b = Gtk.Button(label=text)
            for c in css.split():
                b.add_css_class(c)
            b.connect("clicked", lambda *_: cb())
            ctl.append(b)
            return b
        self.b_shuf = btn("󰒟", lambda: self._pc("shuffle", "Toggle"))
        btn("󰒮", lambda: self._pc("previous"))
        self.b_play = btn("󰐊", lambda: self._pc("play-pause"), "ctl big")
        btn("󰒭", lambda: self._pc("next"))
        self.b_loop = btn("󰑖", self._cycle_loop)
        self.append(ctl)

        vrow = Gtk.Box(spacing=8)
        vrow.append(label("VOL", "row-name"))
        self.vol = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 0, 100, 1)
        self.vol.set_draw_value(False)
        self.vol.set_hexpand(True)
        self.vol.connect("value-changed", self._vol_moved)
        vrow.append(self.vol)
        self.l_vol = label("", "row-val", 1.0)
        self.l_vol.set_width_chars(5)
        vrow.append(self.l_vol)
        self.vol_row = vrow
        self.append(vrow)
        self.connect("map", lambda *_: self.refresh())
        self.refresh()
        GLib.timeout_add_seconds(1, self._auto)

    def _auto(self):
        if self.get_mapped():   # only the visible page polls
            self.refresh()
        return self.alive

    def shutdown(self):
        self.alive = False

    # -- playerctl helpers
    def _pcout(self, *args):
        return sh(["playerctl", "-p", self.name, *args], timeout=2.5)

    def _pc(self, *args):
        fire(["playerctl", "-p", self.name, *args])
        GLib.timeout_add(250, lambda: (self.refresh(), False)[1])

    def _cycle_loop(self):
        nxt = {"None": "Playlist", "Playlist": "Track", "Track": "None"}
        self._pc("loop", nxt.get(self._pcout("loop"), "None"))

    def _seek_moved(self, sc):
        if self.quiet:
            return
        v = sc.get_value()
        self.t_pos.set_text(fmt_time(v))
        if self.seek_timer:
            GLib.source_remove(self.seek_timer)
        self.seek_timer = GLib.timeout_add(120, lambda: (setattr(self, "seek_timer", None), fire(["playerctl", "-p", self.name, "position", f"{v:.1f}"]), False)[2])

    def _vol_moved(self, sc):
        v = int(sc.get_value())
        self.l_vol.set_text(f"{v}%")
        if not self.quiet:
            fire(["playerctl", "-p", self.name, "volume", f"{v / 100:.2f}"])

    # -- state
    def refresh(self):
        threading.Thread(target=self._fetch, daemon=True).start()

    def _fetch(self):
        if DEMO and self.name == "spotify":
            data = ["Playing", "Lain Iwakura", "Serial Experiments Lain - Duvet", ("file://" + os.environ["GITS_PANEL_ART"]) if os.environ.get("GITS_PANEL_ART") else "", str(232 * 10**6), str(84 * 10**6),
                    "spotify", "On", "None", "0.62"]
        elif DEMO:
            data = ["Paused", "", "Wired ambient mix (10 hours)", "", str(36000 * 10**6), str(725 * 10**6), "firefox", "Off", "None", "1.00"]
        else:
            fmt = "\t".join(["{{status}}", "{{artist}}", "{{title}}", "{{mpris:artUrl}}", "{{mpris:length}}", "{{position}}",
                            "{{playerName}}"])
            out = self._pcout("metadata", "--format", fmt)
            parts = out.split("\t")
            data = parts + [self._pcout("shuffle"), self._pcout("loop"), self._pcout("volume")] if len(parts) == 7 else None
        GLib.idle_add(self._show, data)

    def _show(self, d):
        self.nosig.set_visible(d is None or not d[3])   # no player, or a player without cover art
        self.nosig.set_text("NO SIGNAL" if d is None else "NO COVER")
        (self.nosig.remove_css_class if d is None else self.nosig.add_css_class)("dim")
        if d is None:
            self.title.set_text("NO PLAYER")
            self.artist.set_text("start something to play")
            self.cover.set_path(None)
            self.art_key = None
            return
        status, artist, title, art, length, pos, name, shuf, loop, vol = d
        self.title.set_text(title or "—")
        self.artist.set_text(artist)
        self.b_play.set_label("󰏤" if status == "Playing" else "󰐊")
        (self.b_shuf.add_css_class if shuf == "On" else self.b_shuf.remove_css_class)("on")
        self.b_loop.set_label("󰑘" if loop == "Track" else "󰑖")
        (self.b_loop.add_css_class if loop in ("Track", "Playlist") else self.b_loop.remove_css_class)("on")
        try:
            self.length, ps = float(length or 0) / 1e6, float(pos or 0) / 1e6
        except ValueError:
            self.length = ps = 0.0
        self.quiet = True
        self.seek.set_range(0, max(self.length, 1))
        if self.seek_timer is None:
            self.seek.set_value(ps)
        self.t_pos.set_text(fmt_time(ps))
        self.t_len.set_text(fmt_time(self.length))
        self.seek.set_sensitive(self.length > 0)
        try:
            self.vol.set_value(float(vol) * 100)
            self.l_vol.set_text(f"{float(vol) * 100:.0f}%")
            self.vol_row.set_visible(True)
        except ValueError:
            self.vol_row.set_visible(False)  # this player has no volume control
        self.quiet = False
        if art != self.art_key:
            self.art_key = art
            self._load_art(art)




def mpv_ipc(sock, command, timeout=0.6):
    """One command to mpv's JSON IPC socket: the reply's data, or None when mpv is not there / does not answer."""
    try:
        c = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        c.settimeout(timeout)
        c.connect(sock)
        c.sendall((json.dumps({"command": command}) + "\n").encode())
        buf = b""
        while True:
            chunk = c.recv(4096)
            if not chunk:
                break
            buf += chunk
            for line in buf.split(b"\n")[:-1]:   # events come between the reply and us: skip everything without "error"
                r = json.loads(line)
                if "error" in r:
                    c.close()
                    return r.get("data") if r["error"] == "success" else None
            buf = buf.split(b"\n")[-1]
    except (OSError, ValueError):
        pass
    return None


class RadioPage(ArtMixin, Gtk.Box):
    """The last page of the media carousel: the web radio (gits-radio; DATAMOSH unless GITS_RADIO_API / GITS_RADIO_STREAM say otherwise): a stage
    where Lain dances on the live spectrum of the radio's own stream, what is on air with its cover, listeners, tune in / out, volume. The radio
    runs in the user unit gits-radio, so it keeps playing when the popup closes. Lain: GITS_RADIO_LAIN=holo (default) | color | off."""
    RUN = os.path.join(os.environ.get("XDG_RUNTIME_DIR", "/tmp"), "gits-radio")
    API = os.environ.get("GITS_RADIO_API", "https://radio.datamosh.ru/api/nowplaying/datamosh_radio")
    NAME = os.environ.get("GITS_RADIO_NAME", "DATAMOSH")
    LAIN = os.environ.get("GITS_RADIO_LAIN", "holo").lower()
    STAGE_H = 150      # logical px
    SPRITE_H = 116     # Lain: leaves room above her for the jump and the zoom of a beat
    SPEED = float(os.environ.get("GITS_RADIO_LAIN_SPEED", "1") or 1)   # 1 = lively, 0.5 = calm, 1.5 = frantic
    FLASH = os.environ.get("GITS_RADIO_FLASH", "1") != "0"   # the stage flashing on the beats; 0 = off (for anyone who dislikes flicker)
    SEG, SGAP = 3, 1   # LED segment height / gap of the spectrum, px
    # as #hex so a colour theme (gits-theme) recolours them; cairo wants 0..1 floats
    CY, CYB, RED, FG = (tuple(int(h[i:i + 2], 16) / 255 for i in (1, 3, 5)) for h in ("#2ED3D7", "#8CF2F7", "#F04F4F", "#DBF0F5"))

    def __init__(self):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=7)
        self.alive = True
        self.state = "OFF AIR"
        self.quiet = False
        self.art_key = None
        self.running, self.paused = DEMO, False
        self.api, self.api_at, self.api_mono = None, -100.0, 0.0
        self.polling = False
        self.fast = None
        n = StreamSpectrum.BANDS if StreamSpectrum else 24
        self.level, self.peak, self.hold = [0.0] * n, [0.0] * n, [0] * n
        self.demo_t = 0.0
        self.spec = None
        self.dance, self.phase, self.energy = [], 0.0, 0.0
        self.pulse, self.t = 0.0, 0.0   # a beat "kick" (1 -> 0) and the dance clock
        self.seen_beats, self.rings = 0, []   # beats already answered; the shock waves running over the floor (birth time, strength)
        if StreamSpectrum is not None and not DEMO:
            self.spec = StreamSpectrum(os.path.join(self.RUN, "mpv.pid"), self.NAME)
            self.spec.start()
        if dancer is not None and self.LAIN != "off":
            threading.Thread(target=self._load_dancer, daemon=True).start()

        self.da = Gtk.DrawingArea()   # the stage: spectrum bars behind, Lain in front
        self.da.set_content_height(self.STAGE_H)
        self.da.set_hexpand(True)
        self.da.set_draw_func(self._draw)
        self.append(self.da)

        info = Gtk.Box(spacing=10)
        self.cover = CoverArea(66, 66)
        self.cover.add_css_class("cover")
        frame = Gtk.Box()
        frame.add_css_class("cover-frame")
        frame.set_valign(Gtk.Align.START)
        frame.append(self.cover)
        info.append(frame)
        text = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=3)
        text.set_hexpand(True)
        text.set_valign(Gtk.Align.CENTER)
        self.l_station = label(self.NAME.upper(), "m-time")
        self.title = label("—", "m-title")
        self.title.set_ellipsize(Pango.EllipsizeMode.END)
        self.title.set_max_width_chars(22)
        self.artist = label("", "m-artist")
        self.artist.set_ellipsize(Pango.EllipsizeMode.END)
        self.artist.set_max_width_chars(24)
        for w in (self.l_station, self.title, self.artist):
            text.append(w)
        info.append(text)
        self.append(info)

        self.prog = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 0, 100, 1)
        self.prog.set_draw_value(False)
        self.prog.set_hexpand(True)
        self.prog.set_can_target(False)   # a live stream cannot be seeked: show the progress, ignore the pointer
        self.append(self.prog)
        times = Gtk.Box()
        self.t_pos, self.t_len = label("0:00", "m-time"), label("0:00", "m-time", 1.0)
        self.t_len.set_hexpand(True)
        times.append(self.t_pos)
        times.append(self.t_len)
        self.append(times)
        self.l_next = label("", "m-time")
        self.l_next.set_ellipsize(Pango.EllipsizeMode.END)
        self.l_next.set_max_width_chars(38)
        self.append(self.l_next)

        ctl = Gtk.Box(spacing=6, homogeneous=True)
        self.b_power = Gtk.Button(label="󰐥")
        self.b_power.add_css_class("ctl")
        self.b_power.add_css_class("big")
        self.b_power.set_tooltip_text("tune in / switch off")
        self.b_power.connect("clicked", lambda *_: self._power())
        self.b_pause = Gtk.Button(label="󰏤")
        self.b_pause.add_css_class("ctl")
        self.b_pause.connect("clicked", lambda *_: self._pause())
        ctl.append(self.b_power)
        ctl.append(self.b_pause)
        self.append(ctl)

        lrow = Gtk.Box(spacing=8)
        lrow.append(label("LISTENERS", "row-name"))
        self.l_listen = label("–", "row-val", 1.0)
        self.l_listen.set_hexpand(True)
        lrow.append(self.l_listen)
        self.append(lrow)

        vrow = Gtk.Box(spacing=8)
        vrow.append(label("VOL", "row-name"))
        self.vol = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 0, 100, 1)
        self.vol.set_draw_value(False)
        self.vol.set_hexpand(True)
        self.vol.connect("value-changed", self._vol_moved)
        vrow.append(self.vol)
        self.l_vol = label("", "row-val", 1.0)
        self.l_vol.set_width_chars(5)
        vrow.append(self.l_vol)
        self.append(vrow)
        self._render()
        self._tick()
        GLib.timeout_add_seconds(1, self._tick)

    def _load_dancer(self):
        frames = dancer.load(self.SPRITE_H, "color" if self.LAIN == "color" else "holo")   # ~1.5 s the first time, cached afterwards
        GLib.idle_add(self._dancer_ready, frames)

    def _dancer_ready(self, frames):
        self.dance = frames
        self.da.queue_draw()
        return False

    # -- radio control (gits-radio does the work; the popup only asks)
    def _sock(self):
        return os.path.join(self.RUN, "mpv.sock")

    def _power(self):
        fire(["gits-radio", "stop" if self.running else "start"])
        GLib.timeout_add(1600, lambda: (self._tick(), False)[1])

    def _pause(self):
        fire(["gits-radio", "playpause"])
        GLib.timeout_add(350, lambda: (self._tick(), False)[1])

    def _vol_moved(self, sc):
        v = int(sc.get_value())
        self.l_vol.set_text(f"{v}%")
        if not self.quiet and not DEMO:
            threading.Thread(target=mpv_ipc, args=(self._sock(), ["set_property", "volume", v]), daemon=True).start()

    # -- state, once a second
    def _tick(self):
        if not self.polling:
            self.polling = True
            threading.Thread(target=self._poll, daemon=True).start()
        return self.alive

    def _poll(self):
        try:
            if DEMO:
                GLib.idle_add(self._apply_state, True, False, 70.0)
                if self.api is None:
                    GLib.idle_add(self._apply_api, {"station": {"name": "DATAMOSH RADIO"}, "listeners": {"current": 7}, "playing_next": {"song": {"artist": "Wired Angel", "title": "Protocol 7"}},
                                                    "now_playing": {"elapsed": 84, "duration": 232, "song": {"artist": "Lain Iwakura", "title": "Duvet (breakcore rework)",
                                                                                                             "art": ("file://" + os.environ["GITS_PANEL_ART"]) if os.environ.get("GITS_PANEL_ART") else ""}}})
                return
            vol = mpv_ipc(self._sock(), ["get_property", "volume"])
            running = vol is not None
            if os.environ.get("GITS_PANEL_DEBUG_FRAMES"):
                open(os.environ["GITS_PANEL_DEBUG_FRAMES"], "a").write(f"poll vol={vol!r} sock_exists={os.path.exists(self._sock())} spec={self.spec is not None}\n")
            paused = running and mpv_ipc(self._sock(), ["get_property", "pause"]) is True
            GLib.idle_add(self._apply_state, running, paused, vol)
            if time.monotonic() - self.api_at > 3.0:
                self.api_at = time.monotonic()
                try:
                    req = urllib.request.Request(f"{self.API}?_={int(time.time())}", headers={"User-Agent": "gits-panel", "Cache-Control": "no-cache"})
                    with urllib.request.urlopen(req, timeout=4) as r:
                        GLib.idle_add(self._apply_api, json.loads(r.read().decode()))
                except (OSError, ValueError):
                    pass
        finally:
            self.polling = False

    def _apply_state(self, running, paused, vol):
        self.running, self.paused = running, paused
        self.state = "PAUSED" if paused else "ON AIR" if running else "OFF AIR"
        self.b_power.set_label("󰓛" if running else "󰐥")
        self.b_pause.set_label("󰐊" if paused else "󰏤")
        self.b_pause.set_sensitive(running)
        if vol is not None:
            self.quiet = True
            self.vol.set_value(float(vol))
            self.l_vol.set_text(f"{float(vol):.0f}%")
            self.quiet = False
        self.vol.set_sensitive(vol is not None)
        if (running or any(v > 0.01 for v in self.level)) and self.fast is None:
            self.fast = GLib.timeout_add(33, self._frame)
        self.da.queue_draw()   # she dims when the radio is off, the pose stays when it is paused
        self._render()
        return False

    def _apply_api(self, d):
        self.api, self.api_mono = d, time.monotonic()
        self._render()
        return False

    def _render(self):
        d = self.api
        name = ((d or {}).get("station") or {}).get("name", self.NAME).upper()
        self.l_station.set_text(f"{name} · {self.state}")
        if not d:
            self.title.set_text("—" if self.running else "OFF AIR")
            self.artist.set_text("" if self.running else "press 󰐥 to tune in")
            return
        song = (d.get("now_playing") or {}).get("song") or {}
        self.title.set_text(song.get("title") or "—")
        self.artist.set_text(song.get("artist") or "")
        nxt = ((d.get("playing_next") or {}).get("song") or {})
        self.l_next.set_text(f"NEXT  {nxt.get('artist', '')} - {nxt.get('title', '')}" if nxt.get("title") else "")
        self.l_listen.set_text(str((d.get("listeners") or {}).get("current", "–")))
        np_ = d.get("now_playing") or {}
        ln = float(np_.get("duration") or 0)
        ps = float(np_.get("elapsed") or 0) + (time.monotonic() - self.api_mono if not DEMO else 0)
        ps = min(ps, ln) if ln else ps
        self.prog.set_range(0, max(ln, 1))
        self.prog.set_value(ps)
        self.t_pos.set_text(fmt_time(ps))
        self.t_len.set_text(fmt_time(ln))
        art = song.get("art") or ""
        if art != self.art_key:
            self.art_key = art or None
            if art:
                self._load_art(art)
            else:
                self.cover.set_path(None)

    # -- the stage: LED spectrum bars behind, Lain in front
    def _target(self):
        n = len(self.level)
        if DEMO:
            self.demo_t += 0.033
            t = self.demo_t
            return [max(0.04, min(1.0, 0.72 * math.exp(-((i - 3 - 2.5 * math.sin(t * 1.3)) / 6) ** 2)
                                  + 0.28 * abs(math.sin(t * 2.1 + i * 0.55)) * (1 - i / (n * 1.4))
                                  + 0.12 * abs(math.sin(t * 9 + i * 1.7)))) for i in range(n)]
        if self.spec is None or not self.running:
            return [0.0] * n
        return list(self.spec.bands)

    def _frame(self):
        moving = False
        for i, tv in enumerate(self._target()):
            lv = self.level[i]
            lv = lv + (tv - lv) * 0.6 if tv > lv else max(tv, lv - 0.045)
            self.level[i] = lv
            if lv >= self.peak[i]:
                self.peak[i], self.hold[i] = lv, 12
            elif self.hold[i] > 0:
                self.hold[i] -= 1
            else:
                self.peak[i] = max(0.0, self.peak[i] - 0.02)
            moving = moving or lv > 0.01 or self.peak[i] > 0.01
        bass = sum(self.level[:8]) / 8
        self.energy = self.energy + (bass - self.energy) * (0.5 if bass > self.energy else 0.15)
        if self.spec is not None and self.spec.beats != self.seen_beats:   # the spectrum thread heard a beat
            self.seen_beats = self.spec.beats
            self._kick(self.spec.kick)
        elif DEMO and int(self.t / 0.42) != int((self.t - 0.033) / 0.42) and self.running:   # the demo has a steady made-up beat
            self._kick(0.8)
        self.pulse *= 0.86
        if os.environ.get("GITS_PANEL_DEBUG_FRAMES"):
            open(os.environ["GITS_PANEL_DEBUG_FRAMES"], "a").write(f"{time.monotonic():.3f} {self.pulse:.3f} {self.energy:.3f} {max(self.level[:4]):.3f}\n")
        if self.running and not self.paused and self.dance:
            self.t += 0.033
            self.phase += 0.033 * self.SPEED * min(30.0, 10.0 + 16.0 * self.energy + 12.0 * self.pulse)   # 10 frames a second at rest, up to 30 on a loud beat
            if os.environ.get("GITS_PANEL_DEBUG") and int(self.t * 30) % 30 == 0:
                open(os.environ["GITS_PANEL_DEBUG"], "a").write(f"dance phase={self.phase:.1f} energy={self.energy:.2f} beats={self.seen_beats}\n")
        self.da.queue_draw()
        if not moving and not self.running:
            self.fast = None
            return False
        return True

    def _kick(self, strength):
        self.pulse = max(self.pulse, 0.6 + 0.4 * strength)
        self.rings.append((time.monotonic(), strength))
        del self.rings[:-4]

    def _draw(self, area, cr, w, h):
        n = len(self.level)
        gap = 1.5
        bw = (w - gap * (n - 1)) / n
        pitch = self.SEG + self.SGAP
        rows = max(int(h * 0.55 // pitch), 1)   # the bars are the floor and the backdrop, not the whole stage
        if self.FLASH and self.running and self.pulse > 0.02:   # the whole stage flashes on a beat: the one thing that cannot be missed
            cr.rectangle(0, 0, w, h)
            cr.set_source_rgba(*self.CY, 0.30 * self.pulse ** 1.4)
            cr.fill()
        for i in range(n):   # faint baseline dots: alive even when silent
            cr.set_source_rgba(*self.CY, 0.22)
            cr.rectangle(i * (bw + gap), h - self.SEG, bw, self.SEG)
        cr.fill()
        lit = {self.CY: [], self.CYB: [], self.RED: [], self.FG: []}
        for i in range(n):
            x = i * (bw + gap)
            lv = self.level[i]
            if i < 6:   # the bass bars are sustained most of the time: on a beat they punch to the top and fall back between the beats
                lv = max(lv * (0.55 if self.running else 1.0), self.pulse * (1.0 - 0.09 * i))
            k = int(lv * rows)
            for r in range(k):
                frac = (r + 1) / rows
                lit[self.RED if frac > 0.86 else (self.CYB if frac > 0.55 else self.CY)].append((x, h - (r + 1) * pitch + self.SGAP))
            pk = int(self.peak[i] * rows)
            if pk > k:
                lit[self.FG].append((x, h - pk * pitch + self.SGAP))
        for col, alpha in ((self.CY, 0.45), (self.CYB, 0.7), (self.RED, 0.85), (self.FG, 0.8)):
            for x, y in lit[col]:
                cr.rectangle(x, y, bw, self.SEG)
            cr.set_source_rgba(*col, alpha)
            cr.fill()
        if not self.dance:
            return
        frame = self.dance[int(self.phase) % len(self.dance)]
        fw, fh = frame.get_width() / 2, frame.get_height() / 2
        zoom = 1 + 0.12 * self.pulse                                               # pumps up on every beat
        sx, sy = zoom * (1 - 0.03 * self.pulse), zoom * (1 + 0.05 * self.pulse)
        hop = 3 * self.energy + 12 * self.pulse                                    # and jumps
        sway = 6 * math.sin(self.t * 2.4) * (0.35 + self.energy)                   # and rocks from side to side
        x, y = (w - fw * sx) / 2 + sway, h - fh * sy - hop
        alpha = 1.0 if self.running else 0.3
        cr.save()   # a soft light on the floor under her feet, pulsing with the bass
        cr.translate(w / 2, h - 4)
        cr.scale(1, 0.16)
        g = cairo.RadialGradient(0, 0, 4, 0, 0, 66)
        k = (0.30 + 0.45 * self.energy + 0.6 * self.pulse) * (1.0 if self.running else 0.3)
        g.add_color_stop_rgba(0, *self.CYB, k)
        g.add_color_stop_rgba(1, *self.CY, 0.0)
        cr.set_source(g)
        cr.arc(0, 0, 66, 0, 2 * math.pi)
        cr.fill()
        cr.restore()
        now = time.monotonic()
        for born, st in self.rings:   # a shock wave runs over the floor on every beat
            age = (now - born) / 0.5
            if age >= 1:
                continue
            cr.save()
            cr.translate(w / 2, h - 5)
            cr.scale(1, 0.16)
            cr.arc(0, 0, 14 + 128 * age, 0, 2 * math.pi)
            cr.restore()   # the path stays an ellipse, the stroke below has a uniform width
            cr.set_source_rgba(*self.CYB, 0.95 * (1 - age) * (0.6 + 0.4 * st))
            cr.set_line_width(2.6)
            cr.stroke()
        cr.save()
        cr.translate(x, y)
        cr.scale(0.5 * sx, 0.5 * sy)
        cr.set_source_surface(frame, 0, 0)
        cr.paint_with_alpha(alpha)
        cr.restore()

    def shutdown(self):
        self.alive = False
        if self.spec is not None:
            self.spec.stop()


class MediaPopup(Popup):
    """The media popup is a carousel: one page per MPRIS player (Spotify, a browser tab, mpv...), then the web radio (RadioPage), so any sound
    source is one step away. Switch with the arrows, the dots, Left / Right, or a two-finger swipe on the touchpad. `start`: "auto" opens on the
    player the bar follows (a playing one wins), "radio" opens on the radio (Super+R)."""
    RADIO_URL = os.environ.get("GITS_RADIO_STREAM", "https://radio.datamosh.ru/listen/datamosh_radio/radio.mp3")

    def __init__(self, monitor, start="auto"):
        super().__init__(monitor)
        self.hcenter = True   # opened from the bar or by Super+Shift+M: always in the middle, never wherever the pointer happens to be
        self.CARD_W = 304
        self.pages = {}    # name -> page widget ("radio" is the radio page)
        self.order = []    # names in navigation order: players (in the order they appeared), radio last
        self.current = None
        self.scanning = False
        self.scroll_acc, self.scroll_t = 0.0, 0.0
        self.radio_name = None
        self.missing = {}   # name -> consecutive scans in which the player was not seen
        root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=7)
        root.add_css_class("panel")
        head = Gtk.Box(spacing=2)
        head.append(label("MEDIA.LINK // 音", "tag"))
        sp = Gtk.Box()
        sp.set_hexpand(True)
        head.append(sp)
        self.b_prev = Gtk.Button(label="‹")
        self.b_prev.add_css_class("navbtn")
        self.b_prev.connect("clicked", lambda *_: self.go(-1))
        self.l_src = label("", "src")
        self.l_src.set_width_chars(9)
        self.l_src.set_xalign(0.5)
        self.b_next = Gtk.Button(label="›")
        self.b_next.add_css_class("navbtn")
        self.b_next.connect("clicked", lambda *_: self.go(1))
        for w in (self.b_prev, self.l_src, self.b_next):
            head.append(w)
        root.append(head)
        self.deck = Gtk.Stack()
        self.deck.set_transition_duration(230)
        self.deck.set_hhomogeneous(True)
        self.deck.set_vhomogeneous(False)      # the card takes the height of the page it shows
        self.deck.set_interpolate_size(True)
        root.append(self.deck)
        self.dots = Gtk.Box(spacing=0)
        self.dots.set_halign(Gtk.Align.CENTER)
        root.append(self.dots)
        self.set_child(root)

        self._add("radio", RadioPage())
        self._apply_players(self._scan(), start=start)

        keys = Gtk.EventControllerKey()
        keys.connect("key-pressed", self._key)
        self.add_controller(keys)
        scroll = Gtk.EventControllerScroll.new(Gtk.EventControllerScrollFlags.HORIZONTAL)
        scroll.connect("scroll", self._scrolled)
        self.add_controller(scroll)
        GLib.timeout_add_seconds(1, self._tick)

    # -- players
    def _scan(self):
        """{player name: (status, title, url)} for every MPRIS player."""
        if DEMO:
            return {"spotify": ("Playing", "Serial Experiments Lain - Duvet", ""), "firefox.instance_1": ("Paused", "Wired ambient mix (10 hours)", "")}
        out = {}
        for name in sh(["playerctl", "-l"], timeout=2).splitlines():
            line = sh(["playerctl", "-p", name, "metadata", "--format", "{{status}}\t{{title}}\t{{xesam:url}}"], timeout=2)
            st, _, rest = line.partition("\t")
            title, _, url = rest.partition("\t")
            out[name] = (st, title, url)
        return out

    def _tick(self):
        if not self.scanning:
            self.scanning = True
            def work():
                try:
                    GLib.idle_add(self._apply_players, self._scan())
                finally:
                    self.scanning = False
            threading.Thread(target=work, daemon=True).start()
        return True

    @staticmethod
    def source_name(name):
        if name == "radio":
            return "RADIO"
        parts = name.split(".")
        if parts[0] in ("org", "com", "io", "net") and len(parts) > 1:   # reverse-DNS names: org.telegram.desktop -> telegram, org.mozilla.firefox -> firefox
            base = parts[-2] if parts[-1] in ("desktop", "app", "player", "client", "mediaplayer", "instance") and len(parts) > 2 else parts[-1]
        else:
            base = parts[0]
        return base.upper()[:10]

    def _apply_players(self, scan, start=None):
        names, radio = [], None
        for name, (st, title, url) in scan.items():
            if url and url == self.RADIO_URL:   # the radio's own MPRIS entry is the radio page, not one more player
                radio = name
                continue
            if st in ("Playing", "Paused"):   # a stopped player (an idle chat app that still remembers a title) is not a source
                names.append(name)
        new = sorted((n for n in names if n not in self.pages), key=lambda n: (scan[n][0] != "Playing", n))
        for n in names:
            self.missing.pop(n, None)
        for n in [n for n in self.order if n != "radio" and n not in names]:
            self.missing[n] = self.missing.get(n, 0) + 1   # one failed or slow scan must not make a page vanish and come back at the end
        gone = [n for n, c in self.missing.items() if c >= 3]
        for n in gone:
            self.missing.pop(n, None)
            self._remove(n)
        keep = [n for n in self.order if n != "radio" and (n in names or n in self.missing)]
        for n in new:
            self._add(n, PlayerPage(n))
        self.radio_name = radio
        order = keep + new + ["radio"]
        if order != self.order:
            self.order = order
        if self.current is None or self.current not in self.pages:
            target = "radio"
            if start != "radio":
                picked = "spotify" if DEMO else sh(["gits-media", "pick"], timeout=2)
                if picked in self.pages:
                    target = picked
                elif picked and picked == radio:
                    target = "radio"
                elif len(self.order) > 1:
                    target = self.order[0]
            self.select(target, animate=False)
        self._chrome()
        return False

    def _add(self, name, page):
        self.pages[name] = page
        self.deck.add_named(page, name)

    def _remove(self, name):
        page = self.pages.pop(name, None)
        if page is None:
            return
        if self.current == name:   # step to a neighbour first, so the page does not just vanish under the pointer
            i = self.order.index(name) if name in self.order else 0
            rest = [n for n in self.order if n != name]
            self.order = rest
            self.select(rest[min(i, len(rest) - 1)] if rest else "radio")
        page.shutdown()
        GLib.timeout_add(400, lambda: (self.deck.remove(page), False)[1])

    # -- navigation
    def select(self, name, animate=True):
        if name not in self.pages or name == self.current:
            return
        forward = True
        if self.current in self.order and name in self.order:
            forward = self.order.index(name) > self.order.index(self.current)
        kind = Gtk.StackTransitionType.NONE if not animate else (Gtk.StackTransitionType.SLIDE_LEFT if forward else Gtk.StackTransitionType.SLIDE_RIGHT)
        self.current = name
        self.deck.set_visible_child_full(name, kind)
        self._chrome()

    def go(self, delta):
        if len(self.order) < 2 or self.current not in self.order:
            return
        self.select(self.order[(self.order.index(self.current) + delta) % len(self.order)])

    def _key(self, _c, kv, *_):
        if kv in (Gdk.KEY_Left, Gdk.KEY_Right):
            self.go(-1 if kv == Gdk.KEY_Left else 1)
            return True
        return False

    def _scrolled(self, _c, dx, _dy):
        now = time.monotonic()
        if now - self.scroll_t > 0.5:   # a new gesture
            self.scroll_acc = 0.0
        self.scroll_t = now
        self.scroll_acc += dx
        if abs(self.scroll_acc) > 1.5:
            self.go(1 if self.scroll_acc > 0 else -1)
            self.scroll_acc = -100.0   # one page per gesture
        return True

    def _chrome(self):
        """The source name, the arrows and the dots follow the pages."""
        self.l_src.set_text(self.source_name(self.current) if self.current else "")
        many = len(self.order) > 1
        self.b_prev.set_sensitive(many)
        self.b_next.set_sensitive(many)
        key = (tuple(self.order), self.current)
        if key == getattr(self, "_dots_key", None):
            return
        self._dots_key = key
        while (c := self.dots.get_first_child()) is not None:
            self.dots.remove(c)
        for name in self.order:
            b = Gtk.Button(label="󰐹" if name == "radio" else "●")
            b.add_css_class("dotbtn")
            if name == self.current:
                b.add_css_class("on")
            b.connect("clicked", lambda _b, n=name: self.select(n))
            self.dots.append(b)

    def shutdown(self):
        for page in self.pages.values():
            page.shutdown()


def fmt_age(sec):
    sec = int(max(sec, 0))
    if sec < 60:
        return "now"
    if sec < 3600:
        return f"{sec // 60}m"
    if sec < 86400:
        return f"{sec // 3600}h"
    return f"{sec // 86400}d"


def clean_body(text):
    import html
    text = html.unescape(html.unescape(text or ""))          # KDE Connect escapes twice
    text = re.sub(r"(?i)<br\s*/?>", " ", text)
    text = re.sub(r"<[^>]+>", "", text)
    return re.sub(r"\s+", " ", text).strip()[:160]


class NotifyPopup(Popup):
    """Notification centre: the dunst history (newest first) with per-entry delete, clear all and do-not-disturb."""

    def __init__(self, monitor):
        super().__init__(monitor)
        self.CARD_W = 340
        root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        root.add_css_class("panel")
        root.append(self.header("NOTIFY // 通知"))

        top = Gtk.Box(spacing=6, homogeneous=True)
        self.dnd = Tile("󰂛", "SILENT", get_dnd, lambda: fire(["dunstctl", "set-paused", "toggle"]))
        top.append(self.dnd)
        clr = Gtk.Button()
        clr.add_css_class("tile")
        cb = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=1)
        cb.append(label("󰎟", "tile-icon"))
        cb.append(label("CLEAR ALL", "tile-name"))
        self.l_count = label("", "tile-state")
        cb.append(self.l_count)
        clr.set_child(cb)
        clr.connect("clicked", self._clear)
        top.append(clr)
        root.append(top)

        self.scroll = Gtk.ScrolledWindow()
        self.scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        self.scroll.set_propagate_natural_height(True)
        self.scroll.set_max_content_height(400)
        self.scroll.set_min_content_height(60)
        self.list = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.scroll.set_child(self.list)
        root.append(self.scroll)
        self.empty = label("NO NOTIFICATIONS", "nosig dim", 0.5)
        self.empty.set_margin_top(14)
        self.empty.set_margin_bottom(14)
        root.append(self.empty)
        self.set_child(root)
        threading.Thread(target=self._load, daemon=True).start()

    def _load(self):
        import json
        import time
        if DEMO:
            now = time.monotonic() * 1e6
            items = [(1, "Telegram Desktop", "Section 9 // chat", "meeting moved to 15:00, bring the report", 120, "NORMAL"),
                     (2, "Phone", "Alex", "are you coming tonight?", 900, "LOW"),
                     (3, "GitS", "Battery Low", "Battery is at 19%. Connect the charger.", 3600 * 3, "CRITICAL"),
                     (4, "Spotify", "Now playing", "Lain Iwakura - Duvet", 3600 * 9, "LOW")]
            data = [(i, a, sm, b, age, u) for i, a, sm, b, age, u in items]
        else:
            try:
                d = json.loads(sh(["dunstctl", "history"]) or "{}").get("data", [[]])[0]
            except (ValueError, IndexError):
                d = []
            now = time.monotonic() * 1e6
            data = [(n["id"]["data"], n["appname"]["data"], n["summary"]["data"], clean_body(n["body"]["data"]),
                     (now - n["timestamp"]["data"]) / 1e6, n["urgency"]["data"]) for n in d]
        GLib.idle_add(self._show, data, get_dnd())

    def _show(self, data, dnd):
        self.dnd.show_state(dnd)
        while (c := self.list.get_first_child()) is not None:
            self.list.remove(c)
        for nid, app, summary, body, age, urg in data:
            self.list.append(self._row(nid, app, summary, body, age, urg))
        self._count()

    def _row(self, nid, app, summary, body, age, urg):
        row = Gtk.Box(spacing=8)
        row.add_css_class("nrow")
        if urg == "CRITICAL":
            row.add_css_class("crit")
        col = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=1)
        col.set_hexpand(True)
        top = Gtk.Box()
        top.append(label(app.upper()[:22], "n-app"))
        t = label(fmt_age(age), "n-age", 1.0)
        t.set_hexpand(True)
        top.append(t)
        col.append(top)
        s = label(summary or "—", "n-sum")
        s.set_ellipsize(Pango.EllipsizeMode.END)
        s.set_max_width_chars(34)
        col.append(s)
        if body:
            b = label(body, "n-body")
            b.set_wrap(True)
            b.set_lines(2)
            b.set_ellipsize(Pango.EllipsizeMode.END)
            b.set_max_width_chars(38)
            col.append(b)
        row.append(col)
        x = Gtk.Button(label="✕")
        x.add_css_class("n-x")
        x.set_valign(Gtk.Align.START)
        x.connect("clicked", lambda *_: (fire(["dunstctl", "history-rm", str(nid)]), self.list.remove(row), self._count()))
        row.append(x)
        return row

    def _count(self):
        n, c = 0, self.list.get_first_child()
        while c is not None:
            n, c = n + 1, c.get_next_sibling()
        self.l_count.set_text(f"{n} stored")
        self.empty.set_visible(n == 0)
        self.scroll.set_visible(n > 0)

    def _clear(self, *_):
        fire(["dunstctl", "history-clear"])
        while (c := self.list.get_first_child()) is not None:
            self.list.remove(c)
        self._count()


class MenuPopup(Popup):
    """A list menu in the GitS style (replaces rofi for gits-wifi / gits-bt / gits-perf / the notification action menu, because
    rofi cannot be closed by clicking away). Lines come from stdin; the choice goes to stdout (its index, or the line, or the typed
    text in password mode). Exit status 1 = cancelled. Type to filter, Up/Down + Enter or click to choose, Esc / click outside cancels."""
    CARD_W = 460

    def __init__(self, monitor, title, tag, mode, lines):
        super().__init__(monitor, center=True)
        self.mode, self.lines, self.result = mode, lines, None
        root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        root.add_css_class("panel")
        head = Gtk.Box(spacing=6)
        head.append(label(title, "m-head"))
        sp = Gtk.Box()
        sp.set_hexpand(True)
        head.append(sp)
        head.append(label(tag, "m-tag"))
        root.append(head)
        self.entry = Gtk.Entry()
        self.entry.add_css_class("m-entry")
        self.entry.set_placeholder_text("password_" if mode == "password" else "filter_")
        root.append(self.entry)
        if mode == "password":
            self.entry.set_visibility(False)
            self.entry.connect("activate", lambda *_: self._finish(self.entry.get_text()))
        else:
            self.box = Gtk.ListBox()
            self.box.set_selection_mode(Gtk.SelectionMode.SINGLE)
            self.box.set_activate_on_single_click(True)
            self.rows = []
            for i, ln in enumerate(lines):
                row = Gtk.ListBoxRow()
                row.add_css_class("mrow")
                row.idx, row.text = i, ln
                lb = label(ln, "mrow-text")
                lb.set_ellipsize(Pango.EllipsizeMode.END)
                row.set_child(lb)
                self.box.append(row)
                self.rows.append(row)
            self.box.set_filter_func(lambda row: self.entry.get_text().lower() in row.text.lower())
            self.box.connect("row-activated", lambda _b, row: self._finish(row.idx))
            self.entry.connect("changed", self._filtered)
            self.entry.connect("activate", lambda *_: self._activate_selected())
            sc = Gtk.ScrolledWindow()
            sc.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
            sc.set_propagate_natural_height(True)
            sc.set_max_content_height(440)
            sc.set_child(self.box)
            root.append(sc)
            keys = Gtk.EventControllerKey()
            keys.connect("key-pressed", self._key)
            self.entry.add_controller(keys)
            vis = self._visible()
            if vis:
                self.box.select_row(vis[0])
        self.set_child(root)
        GLib.idle_add(lambda: (self.entry.grab_focus(), False)[1])

    def _visible(self):
        q = self.entry.get_text().lower()
        return [r for r in self.rows if q in r.text.lower()]

    def _filtered(self, *_):
        self.box.invalidate_filter()
        vis = self._visible()
        if vis:
            self.box.select_row(vis[0])

    def _key(self, _c, kv, *_):
        if kv in (Gdk.KEY_Down, Gdk.KEY_Up):
            vis = self._visible()
            cur = self.box.get_selected_row()
            if vis:
                i = vis.index(cur) if cur in vis else -1
                i = (i + (1 if kv == Gdk.KEY_Down else -1)) % len(vis)
                self.box.select_row(vis[i])
                vis[i].grab_focus()   # scrolls it into view
                self.entry.grab_focus()
            return True
        return False

    def _activate_selected(self):
        row = self.box.get_selected_row()
        if row is not None:
            self._finish(row.idx)

    def _finish(self, value):
        self.result = value
        self.dismiss()


def theme_info():
    """`gits-theme info`: themes with their effective colours and your options, the mascots, the current theme."""
    try:
        return json.loads(sh(["gits-theme", "info"], timeout=8, real=True) or "{}")
    except ValueError:
        return {}


def lighter(hexc, k=0.45):
    c = [int(hexc[i:i + 2], 16) for i in (1, 3, 5)]
    return "#%02X%02X%02X" % tuple(round(v + (255 - v) * k) for v in c)


def thumb(path, w, h):
    """A picture decoded small and cut to exactly w x h (cover), as a texture; None if it cannot be read."""
    try:
        pb = GdkPixbuf.Pixbuf.new_from_file_at_scale(path, w * 3, h * 3, True)
        k = max(w / pb.get_width(), h / pb.get_height())
        pb = pb.scale_simple(max(w, round(pb.get_width() * k)), max(h, round(pb.get_height() * k)), GdkPixbuf.InterpType.BILINEAR)
        return Gdk.Texture.new_for_pixbuf(pb.new_subpixbuf((pb.get_width() - w) // 2, (pb.get_height() - h) // 2, w, h))
    except GLib.Error:
        return None


class AppearancePopup(Popup):
    """Appearance (gits-panel appearance, Super+I -> Appearance): the colour theme, your own accent on top of it, the lock-screen
    mascot and the wallpaper, in one place. Theme / accent / mascot are applied together with APPLY (one recolouring, `gits-theme
    option` + `set`); a wallpaper is shown at once (gits-wall remembers it for the current theme)."""
    CARD_W = 860
    SWATCH = ("bg", "surface", "fg", "accent", "accent_bright", "accent_2", "red", "green", "yellow", "violet")
    PREVIEW = (352, 198)   # the big preview beside the wallpaper grid
    # written without "#" on purpose: gits-theme recolours every #RRGGBB in this file, and these must stay what they say
    ACCENTS = tuple((n, "#" + c) for n, c in (("CYAN", "2ED3D7"), ("LAVENDER", "B79CFF"), ("MATRIX", "3BFF8E"), ("MAGENTA", "FF2E97"),
                                              ("AMBER", "FFB000"), ("RED", "E5432B"), ("BLUE", "459BF1"), ("CREAM", "E8DCCB")))

    def __init__(self, monitor):
        super().__init__(monitor, center=True)
        self.info = theme_info()
        self.themes = {t["id"]: t for t in self.info.get("themes", [])}
        self.cur = self.info.get("current", "gits")
        self.sel = self.cur if self.cur in self.themes else next(iter(self.themes), "gits")
        root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        root.add_css_class("panel")
        head = Gtk.Box(spacing=6)
        head.append(label("\U000F03D8  APPEARANCE", "m-head"))
        sp = Gtk.Box()
        sp.set_hexpand(True)
        head.append(sp)
        head.append(label("// 外観", "m-tag"))
        root.append(head)
        # themes
        root.append(label("THEME", "ap-sec"))
        row = Gtk.Box(spacing=8)
        self.cards = {}
        for tid, t in self.themes.items():
            row.append(self._theme_card(tid, t))
        root.append(row)
        # accent
        root.append(label("ACCENT  ·  rings, borders, icons, the selection", "ap-sec"))
        arow = Gtk.Box(spacing=6)
        self.chips = {}
        self.chip_default = self._chip("THEME", None)
        arow.append(self.chip_default)
        for name, c in self.ACCENTS:
            arow.append(self._chip(name, c))
        self.hex = Gtk.Entry()
        self.hex.set_placeholder_text("#RRGGBB")
        self.hex.set_max_width_chars(8)
        self.hex.set_width_chars(8)
        self.hex.add_css_class("ap-hex")
        self.hex.connect("activate", self._hex_entered)
        arow.append(self.hex)
        root.append(arow)
        # mascot
        root.append(label("LOCK SCREEN MASCOT", "ap-sec"))
        mrow = Gtk.Box(spacing=6)
        self.mascots = {}
        for m in self.info.get("mascots", []):
            b = Gtk.Button(label=m.upper())
            b.add_css_class("ap-toggle")
            b.connect("clicked", lambda _b, m=m: self._pick_mascot(m))
            self.mascots[m] = b
            mrow.append(b)
        root.append(mrow)
        # radio dancer
        root.append(label("RADIO DANCER", "ap-sec"))
        drow = Gtk.Box(spacing=6)
        self.dancers = {}
        for d in [{"id": "", "name": "theme"}] + self.info.get("dancers", []):
            b = Gtk.Button(label=d["name"].upper())
            b.add_css_class("ap-toggle")
            b.connect("clicked", lambda _b, i=d["id"]: self._pick_dancer(i))
            self.dancers[d["id"]] = b
            drow.append(b)
        root.append(drow)
        # wallpaper
        root.append(label("WALLPAPER  ·  for the theme selected above; shown at once when it is the current one", "ap-sec"))
        self.walls = Gtk.FlowBox()
        self.walls.set_selection_mode(Gtk.SelectionMode.NONE)
        self.walls.set_max_children_per_line(4)
        self.walls.set_min_children_per_line(4)
        self.walls.set_row_spacing(6)
        self.walls.set_column_spacing(6)
        sc = Gtk.ScrolledWindow()
        sc.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        sc.set_min_content_height(250)
        sc.set_max_content_height(250)
        sc.set_child(self.walls)
        sc.set_hexpand(True)
        wrow = Gtk.Box(spacing=10)
        wrow.append(sc)
        # the big preview: whatever the pointer is over, else the wallpaper the selected theme would show
        pv = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        self.preview = Gtk.Picture()
        self.preview.set_size_request(*self.PREVIEW)
        self.preview.add_css_class("th-thumb")
        self.preview_name = label("", "th-status")
        self.preview_name.set_ellipsize(Pango.EllipsizeMode.MIDDLE)
        self.preview_name.set_max_width_chars(40)
        pv.append(self.preview)
        pv.append(self.preview_name)
        pv.append(label("hover to preview · click to choose", "th-status"))
        wrow.append(pv)
        root.append(wrow)
        self._previews = {}
        self.wall_buttons = {}
        self.walls_of = dict(self.info.get("wallpapers", {}))   # the wallpaper each theme remembers (gits-wall --theme)
        files = [f for f in sh(["gits-wall", "--list"], real=True).split("\n") if f]
        for f in files:
            b = Gtk.Button()
            b.add_css_class("ap-wall")
            b.set_tooltip_text(os.path.basename(f))
            pic = Gtk.Picture()
            pic.set_size_request(118, 66)
            b.set_child(pic)
            b.connect("clicked", lambda _b, f=f: self._pick_wall(f))
            hover = Gtk.EventControllerMotion()
            hover.connect("enter", lambda *_a, f=f: self._preview(f))
            hover.connect("leave", lambda *_a: self._preview(None))
            b.add_controller(hover)
            self.walls.append(b)
            self.wall_buttons[f] = (b, pic)
        self._pending = list(files)
        GLib.idle_add(self._load_thumbs)   # a few thumbnails per idle turn: the popup opens at once, pictures fill in
        # footer
        foot = Gtk.Box(spacing=8)
        self.status = label("", "th-status")
        self.status.set_hexpand(True)
        foot.append(self.status)
        reset = Gtk.Button(label="RESET THEME OPTIONS")
        reset.add_css_class("ap-toggle")
        reset.connect("clicked", lambda _b: self._reset())
        foot.append(reset)
        self.apply_btn = Gtk.Button(label="APPLY")
        self.apply_btn.add_css_class("ap-apply")
        self.apply_btn.connect("clicked", lambda _b: self._apply())
        foot.append(self.apply_btn)
        root.append(foot)
        self.set_child(root)
        self._select_theme(self.sel)

    # -- building blocks
    def _theme_card(self, tid, t):
        btn = Gtk.Button()
        btn.add_css_class("theme-card")
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        pic = Gtk.Picture()
        pic.set_size_request(176, 99)
        pic.add_css_class("th-thumb")
        wall = t.get("wallpaper", "")
        path = wall if os.path.isabs(wall) else os.path.join(HOME, ".local/share/gits/wallpapers", wall)
        tex = thumb(path, 176, 99) if wall and os.path.exists(path) else None
        if tex:
            pic.set_paintable(tex)
        box.append(pic)
        top = Gtk.Box(spacing=4)
        nm = label(t["name"].upper(), "th-name")
        nm.set_ellipsize(Pango.EllipsizeMode.END)
        nm.set_max_width_chars(16)
        nm.set_hexpand(True)
        top.append(nm)
        if tid == self.cur:
            top.append(label("ACTIVE", "th-active"))
        box.append(top)
        da = Gtk.DrawingArea()
        da.set_content_height(10)
        da.set_draw_func(lambda _a, cr, w, h, tid=tid: self._draw_swatch(cr, w, h, self.themes[tid]["roles"]))
        box.append(da)
        btn.set_child(box)
        btn.connect("clicked", lambda _b: self._select_theme(tid))
        self.cards[tid] = (btn, da)
        return btn

    def _draw_swatch(self, cr, w, h, roles):
        cols = [roles[k] for k in self.SWATCH if k in roles]
        n = max(len(cols), 1)
        for i, c in enumerate(cols):
            cr.set_source_rgb(*(int(c[j:j + 2], 16) / 255 for j in (1, 3, 5)))
            cr.rectangle(i * w / n, 0, w / n - 2, h)
            cr.fill()

    def _chip(self, name, colour):
        b = Gtk.Button()
        b.add_css_class("ap-chip")
        box = Gtk.Box(spacing=5)
        da = Gtk.DrawingArea()
        da.set_content_width(14)
        da.set_content_height(14)

        def draw(_a, cr, w, h):
            c = colour or self.themes.get(self.sel, {}).get("theme_roles", {}).get("accent", "#888888")
            cr.set_source_rgb(*(int(c[j:j + 2], 16) / 255 for j in (1, 3, 5)))
            cr.rectangle(0, 0, w, h)
            cr.fill()
        da.set_draw_func(draw)
        box.append(da)
        box.append(label(name, "ap-chip-name"))
        b.set_child(box)
        b.da = da
        b.connect("clicked", lambda _b: self._pick_accent(colour))
        self.chips[colour] = b
        return b

    # -- choices
    def _select_theme(self, tid):
        self.sel = tid
        for k, (b, _d) in self.cards.items():
            (b.add_css_class if k == tid else b.remove_css_class)("sel")
        t = self.themes.get(tid, {})
        self.accent = t.get("user", {}).get("accent")          # None = the theme's own
        self.mascot = t.get("mascot", "tachikoma")
        self.dancer = t.get("user", {}).get("dancer", "")     # "" = the theme's own
        self._show_wall()
        self.chip_default.da.queue_draw()
        self._show_choices()

    def _show_choices(self):
        for c, b in self.chips.items():
            (b.add_css_class if c == self.accent else b.remove_css_class)("sel")
        if self.accent and self.accent not in self.chips:
            self.hex.set_text(self.accent)
        for m, b in self.mascots.items():
            (b.add_css_class if m == self.mascot else b.remove_css_class)("sel")
        for d, b in self.dancers.items():
            (b.add_css_class if d == self.dancer else b.remove_css_class)("sel")
        t = self.themes.get(self.sel, {})
        changed = (self.sel != self.cur or self.accent != t.get("user", {}).get("accent") or self.mascot != t.get("mascot", "tachikoma")
                   or self.dancer != t.get("user", {}).get("dancer", ""))
        self.status.set_text(("APPLY: " + t.get("name", self.sel)) if changed else t.get("description", ""))

    def _pick_accent(self, colour):
        self.accent = colour
        self.hex.set_text("")
        self._show_choices()

    def _hex_entered(self, entry):
        v = entry.get_text().strip()
        v = v if v.startswith("#") else "#" + v
        if re.fullmatch(r"#[0-9A-Fa-f]{6}", v):
            self.accent = v.upper()
            self._show_choices()
        else:
            self.status.set_text("a colour is #RRGGBB")

    def _pick_mascot(self, m):
        self.mascot = m
        self._show_choices()

    def _pick_dancer(self, d):
        self.dancer = d
        self._show_choices()

    def _theme_wall(self):
        t = self.themes.get(self.sel, {})
        own = t.get("wallpaper", "")
        own = own if os.path.isabs(own) else os.path.join(HOME, ".local/share/gits/wallpapers", own)
        return self.walls_of.get(self.sel) or own

    def _show_wall(self):
        """Mark the wallpaper the selected theme would show: the one it remembers, else its own."""
        want = self._theme_wall()
        for k, (b, _p) in getattr(self, "wall_buttons", {}).items():
            (b.add_css_class if k == want else b.remove_css_class)("sel")
        if hasattr(self, "preview"):
            self._preview(None)

    def _preview(self, f):
        """Show f big (None: the selected theme's wallpaper). Decoded once per picture, at the preview's size."""
        f = f or self._theme_wall()
        if not f or not os.path.exists(f):
            return
        if f not in self._previews:
            self._previews[f] = thumb(f, *self.PREVIEW)
        if self._previews[f]:
            self.preview.set_paintable(self._previews[f])
        self.preview_name.set_text(os.path.basename(f))

    def _pick_wall(self, f):
        fire(["gits-wall", "--theme", self.sel, f])   # shown at once if the selected theme is the current one
        self.walls_of[self.sel] = f
        self._show_wall()
        t = self.themes.get(self.sel, {})
        self.status.set_text(f"wallpaper for {t.get('name', self.sel)}: " + os.path.basename(f))

    def _load_thumbs(self):
        for _ in range(3):
            if not self._pending:
                return False
            f = self._pending.pop(0)
            tex = thumb(f, 118, 66)
            if tex:
                self.wall_buttons[f][1].set_paintable(tex)
        return True

    # -- doing it
    def _run(self, cmds, msg):
        for b in list(self.chips.values()) + [self.apply_btn]:
            b.set_sensitive(False)
        self.status.set_text(msg)

        def work():
            for c in cmds:
                sh(c, timeout=120)
            GLib.idle_add(lambda: (self.dismiss(), False)[1])
        threading.Thread(target=work, daemon=True).start()

    def _apply(self):
        t, tid = self.themes.get(self.sel, {}), self.sel
        cmds = []
        if self.accent and self.accent != t.get("theme_roles", {}).get("accent"):
            cmds += [["gits-theme", "option", tid, "accent", self.accent],
                     ["gits-theme", "option", tid, "accent_bright", lighter(self.accent)]]
        else:
            cmds += [["gits-theme", "option", tid, "accent"], ["gits-theme", "option", tid, "accent_bright"]]
        # the theme's own mascot: no option of yours; another one: remembered in the theme's .user file
        cmds.append(["gits-theme", "option", tid, "mascot"] + ([] if self.mascot == t.get("theme_mascot") else [self.mascot]))
        cmds.append(["gits-theme", "option", tid, "dancer"] + ([self.dancer] if self.dancer else []))
        cmds.append(["gits-theme", "set", tid])
        self._run(cmds, "APPLYING " + t.get("name", tid).upper() + " …")

    def _reset(self):
        self._run([["gits-theme", "option", self.sel, "--reset"], ["gits-theme", "set", self.sel]],
                  "FORGETTING YOUR OPTIONS FOR " + self.themes.get(self.sel, {}).get("name", self.sel).upper() + " …")


class MixerPopup(Popup):
    """Sound mixer: master volume + mute of the default output, a button per output device, and one slider per application that
    is playing (streams of one app are grouped). Refreshes every 1.5 s while open (apps come and go)."""
    CARD_W = 340

    def __init__(self, monitor, left):
        super().__init__(monitor, left)
        self.CARD_W = 340
        self.apps = {}        # app name -> dict(ids, slider, val label, mute button, touched)
        self.sig = None       # what the app list looked like last time (rebuild only on a change)
        self.quiet = False
        self.timers = {}
        root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        root.add_css_class("panel")
        root.append(self.header("MIXER // 音量"))
        self.out_row = Gtk.Box(spacing=6, homogeneous=True)
        root.append(self.out_row)
        mrow = Gtk.Box(spacing=8)
        mrow.append(label("MASTER", "row-name"))
        self.master = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 0, 100, 1)
        self.master.set_draw_value(False)
        self.master.set_hexpand(True)
        self.master.connect("value-changed", lambda sc: self._moved("master", sc, self.l_master, lambda v: self._run(["pactl", "set-sink-volume", "@DEFAULT_SINK@", f"{v}%"])))
        mrow.append(self.master)
        self.l_master = label("", "row-val", 1.0)
        self.l_master.set_width_chars(5)
        mrow.append(self.l_master)
        self.b_mute = Gtk.Button(label="󰕾")
        self.b_mute.add_css_class("ctl")
        self.b_mute.connect("clicked", lambda *_: (self._run(["pactl", "set-sink-mute", "@DEFAULT_SINK@", "toggle"]), GLib.timeout_add(250, lambda: (self.refresh(), False)[1])))
        mrow.append(self.b_mute)
        root.append(mrow)
        root.append(label("APPLICATIONS", "tile-state"))
        self.app_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        root.append(self.app_box)
        self.empty = label("nothing is playing", "nosig dim", 0.5)
        root.append(self.empty)
        self.set_child(root)
        self.refresh()
        GLib.timeout_add(1500, lambda: (self.refresh(), True)[1])

    @staticmethod
    def _run(cmd):
        fire(cmd)

    def _moved(self, key, sc, val, cb):
        v = int(sc.get_value())
        val.set_text(f"{v}%")
        if self.quiet:
            return
        if key in self.timers:
            GLib.source_remove(self.timers[key])
        self.timers[key] = GLib.timeout_add(80, lambda: (self.timers.pop(key, None), cb(v), False)[2])

    def refresh(self):
        threading.Thread(target=self._fetch, daemon=True).start()

    def _fetch(self):
        import json
        if DEMO:
            data = {"sinks": [("speakers", "SPEAKERS", False), ("bt", "WH-1000XM5", True)], "master": (46, False),
                    "apps": [("SPOTIFY", [1], 72, False), ("ZEN", [2], 40, False), ("TELEGRAM", [3], 100, True)]}
            GLib.idle_add(self._show, data)
            return
        def jl(*args):
            try:
                return json.loads(sh(["pactl", "--format=json", *args]) or "[]")
            except ValueError:
                return []
        default = sh(["pactl", "get-default-sink"])
        sinks = [(x["name"], x.get("description", x["name"]), x["name"] == default) for x in jl("list", "sinks")]
        grouped = {}
        for st in jl("list", "sink-inputs"):
            pr = st.get("properties", {})
            name = (pr.get("application.name") or pr.get("application.process.binary") or pr.get("media.name") or "app").upper()
            vols = list((st.get("volume") or {}).values())
            pct = int(vols[0]["value_percent"].rstrip("%")) if vols else 100
            g = grouped.setdefault(name, [[], pct, bool(st.get("mute"))])
            g[0].append(st["index"])
        m = get_volume()
        GLib.idle_add(self._show, {"sinks": sinks, "master": m, "apps": [(n, g[0], g[1], g[2]) for n, g in sorted(grouped.items())]})

    def _short(self, desc):
        d = desc.upper()
        return "BLUETOOTH" if "BLUE" in d or "WH-" in d else ("SPEAKERS" if "ANALOG" in d or "SPEAKER" in d or "HD AUDIO" in d else d[:14])

    def _show(self, d):
        self.quiet = True
        while (c := self.out_row.get_first_child()) is not None:
            self.out_row.remove(c)
        for name, desc, is_def in d["sinks"]:
            b = Gtk.Button(label=self._short(desc))
            b.add_css_class("seg")
            if is_def:
                b.add_css_class("on")
            b.connect("clicked", lambda _b, n=name: self._set_sink(n))
            self.out_row.append(b)
        vol, muted = d["master"]
        self.master.set_value(vol)
        self.l_master.set_text("MUTE" if muted else f"{vol}%")
        self.b_mute.set_label("󰝟" if muted else "󰕾")
        sig = [(n, tuple(ids)) for n, ids, _v, _m in d["apps"]]
        if sig != self.sig:
            self.sig = sig
            while (c := self.app_box.get_first_child()) is not None:
                self.app_box.remove(c)
            self.apps = {}
            for name, ids, pct, mute in d["apps"]:
                row = Gtk.Box(spacing=8)
                nm = label(name[:12], "row-name")
                nm.set_size_request(74, -1)
                row.append(nm)
                sc = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 0, 100, 1)
                sc.set_draw_value(False)
                sc.set_hexpand(True)
                vl = label("", "row-val", 1.0)
                vl.set_width_chars(5)
                sc.connect("value-changed", lambda w, ids=ids, vl=vl, n=name: self._moved("app" + n, w, vl, lambda v: [self._run(["pactl", "set-sink-input-volume", str(i), f"{v}%"]) for i in ids]))
                mb = Gtk.Button(label="󰕾")
                mb.add_css_class("ctl")
                mb.connect("clicked", lambda _b, ids=ids: ([self._run(["pactl", "set-sink-input-mute", str(i), "toggle"]) for i in ids], GLib.timeout_add(250, lambda: (self.refresh(), False)[1])))
                for w in (sc, vl, mb):
                    row.append(w)
                self.app_box.append(row)
                self.apps[name] = (sc, vl, mb)
        for name, ids, pct, mute in d["apps"]:
            sc, vl, mb = self.apps[name]
            if name not in self.timers and "app" + name not in self.timers:
                sc.set_value(pct)
            vl.set_text("MUTE" if mute else f"{pct}%")
            mb.set_label("󰝟" if mute else "󰕾")
        self.empty.set_visible(not d["apps"])
        self.quiet = False

    def _set_sink(self, name):
        def work():
            subprocess.run(["pactl", "set-default-sink", name])
            for line in sh(["pactl", "list", "short", "sink-inputs"]).splitlines():
                subprocess.run(["pactl", "move-sink-input", line.split()[0], name])   # streams follow the new output
            GLib.idle_add(self.refresh)
        if not DEMO:
            threading.Thread(target=work, daemon=True).start()


class NotePopup(Popup):
    """Quick capture: one line into ~/notes/inbox.md (GITS_NOTES to change), with a timestamp. Enter saves and closes, Esc cancels.
    The last few notes are shown underneath so you can see what is already there."""
    CARD_W = 480

    def __init__(self, monitor):
        super().__init__(monitor, center=True)
        self.path = os.environ.get("GITS_NOTES") or os.path.join(HOME, "notes", "inbox.md")
        root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        root.add_css_class("panel")
        head = Gtk.Box(spacing=6)
        head.append(label("NOTE // 記録", "m-head"))
        sp = Gtk.Box()
        sp.set_hexpand(True)
        head.append(sp)
        self.l_hint = label("Enter: save · Esc: cancel", "m-tag")
        head.append(self.l_hint)
        root.append(head)
        self.entry = Gtk.Entry()
        self.entry.add_css_class("m-entry")
        self.entry.set_placeholder_text("type a note (#tags are fine)_")
        self.entry.connect("activate", self._save)
        root.append(self.entry)
        for ln in self._recent(3):
            lb = label(ln, "n-body")
            lb.set_ellipsize(Pango.EllipsizeMode.END)
            lb.set_max_width_chars(60)
            root.append(lb)
        self.l_path = label("~/notes/inbox.md" if DEMO else self.path.replace(HOME, "~"), "foot")
        root.append(self.l_path)
        self.set_child(root)
        GLib.idle_add(lambda: (self.entry.grab_focus(), False)[1])
        auto = os.environ.get("GITS_PANEL_AUTOTEXT")   # test hook: type a note and press Enter
        if auto:
            GLib.timeout_add(900, lambda: (self.entry.set_text(auto), self._save(), False)[2])

    def _recent(self, n):
        try:
            lines = [ln.rstrip("\n") for ln in open(self.path, encoding="utf-8") if ln.strip()]
        except OSError:
            return []
        return [ln[2:] if ln.startswith("- ") else ln for ln in lines[-n:]]

    def _save(self, *_):
        import time
        text = self.entry.get_text().strip()
        if not text:
            return
        if not DEMO:
            os.makedirs(os.path.dirname(self.path), exist_ok=True)
            with open(self.path, "a", encoding="utf-8") as f:
                f.write(f"- {time.strftime('%Y-%m-%d %H:%M')}  {text}\n")
        self.l_hint.set_text("saved")
        self.entry.set_sensitive(False)
        GLib.timeout_add(380, lambda: (self.dismiss(), False)[1])


# ---------------------------------------------------------------------------------------------- launcher / command palette
def fuzzy(q, text):
    """Match score of query q in text, 0 = no match: prefix > word start > substring > letters in order."""
    q, t = q.lower(), text.lower()
    if not q:
        return 1.0
    if t.startswith(q):
        return 100 - min(len(t) - len(q), 40) * 0.3
    if any(w.startswith(q) for w in re.split(r"[\s\-_./]+", t) if w):
        return 80 - min(len(t), 60) * 0.2
    if q in t:
        return 60 - min(t.index(q), 30) * 0.5
    it = iter(t)
    if len(q) >= 2 and all(c in it for c in q):
        return 30 - min(len(t), 60) * 0.2
    return 0.0


_BIN = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul, ast.Div: operator.truediv,
        ast.FloorDiv: operator.floordiv, ast.Mod: operator.mod, ast.Pow: operator.pow}
_FUN = {"sqrt": math.sqrt, "sin": math.sin, "cos": math.cos, "tan": math.tan, "log": math.log10, "ln": math.log,
        "abs": abs, "round": round}
_CONST = {"pi": math.pi, "e": math.e}


def calc(expr):
    """A safe pocket calculator: numbers, + - * / // % ** ^ ( ), sqrt sin cos tan log ln abs round, pi e. None if it is not maths."""
    expr = expr.strip().replace("^", "**").replace(",", ".")
    if not expr or not re.fullmatch(r"[0-9a-z_+\-*/%().\s]+", expr) or not re.search(r"\d|pi|\be\b", expr):
        return None
    if not re.search(r"[+\-*/%]|sqrt|sin|cos|tan|log|ln|abs|round", expr):
        return None   # a bare number is not worth a row

    def ev(n):
        if isinstance(n, ast.Expression):
            return ev(n.body)
        if isinstance(n, ast.Constant) and isinstance(n.value, (int, float)):
            return n.value
        if isinstance(n, ast.Name) and n.id in _CONST:
            return _CONST[n.id]
        if isinstance(n, ast.UnaryOp) and isinstance(n.op, (ast.UAdd, ast.USub)):
            v = ev(n.operand)
            return v if isinstance(n.op, ast.UAdd) else -v
        if isinstance(n, ast.BinOp) and type(n.op) in _BIN:
            a, b = ev(n.left), ev(n.right)
            if isinstance(n.op, ast.Pow) and abs(b) > 1000:
                raise ValueError("exponent too large")
            return _BIN[type(n.op)](a, b)
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id in _FUN and len(n.args) == 1 and not n.keywords:
            return _FUN[n.func.id](ev(n.args[0]))
        raise ValueError("not maths")
    try:
        v = ev(ast.parse(expr, mode="eval"))
    except (ValueError, SyntaxError, ZeroDivisionError, OverflowError, TypeError):
        return None
    if isinstance(v, float) and v == int(v) and abs(v) < 1e15:
        v = int(v)
    return f"{v:.10g}" if isinstance(v, float) else str(v)


class Item:
    def __init__(self, kind, title, sub="", icon=None, glyph="󰀻", match="", act=None, weight=1.0, ident=None):
        self.kind, self.title, self.sub, self.icon, self.glyph = kind, title, sub, icon, glyph
        self.match, self.act, self.weight, self.ident = match or title, act, weight, ident


# screenshot mode (GITS_PANEL_DEMO=1): nothing personal from the clipboard, the windows or the project list
DEMO_CLIPS = ["sudo pacman -S --needed hyprland waybar dunst kitty", "https://github.com/electrocrem/gits",
              "meeting moved: Section 9 sync on Friday 15:00", "[[ binary data 118 KiB png 1920x1200 ]]", "#2ed3d7",
              "git commit -m \"Installer: hook user.zsh into .zshrc\"", "ssh -L 8080:localhost:80 puppet-master"]
DEMO_WINDOWS = [("Neovim - install.sh", "kitty", "1"), ("Ghost in the Shell - Zen", "zen", "2"), ("Section 9 // chat", "org.telegram.desktop", "3"),
                ("btop", "kitty", "1"), ("Steam", "steam", "5"), ("Dolphin - Downloads", "org.kde.dolphin", "4")]
DEMO_PROJECTS = [("gits", "~/gits", "git"), ("puppet-master", "~/src/puppet-master", "git"), ("tachikoma", "~/src/tachikoma", "godot"),
                 ("laughing-man", "~/src/laughing-man", "git")]


class LauncherPopup(Popup):
    """Command palette: apps (with icons, most used first), settings, projects, open windows, notes, a calculator and a web search
    in one field. mode "clip" is the clipboard history (cliphist) instead. Enter runs, Up/Down select, Esc / click outside close."""
    CARD_W = 580
    USAGE = os.path.join(STATE, "gits-launcher", "usage.json")
    # the plain list modes: one source of rows, fuzzy filter, Enter runs the row (everything but "launch")
    TITLES = {"clip": "CLIPBOARD // 貼付", "windows": "WINDOWS // 窓", "emoji": "EMOJI // 絵文字", "keys": "KEY BINDINGS // 鍵"}
    PLACEHOLDERS = {"clip": "search the clipboard history_", "windows": "jump to a window_", "emoji": "search by name: smile, fire, arrow..._",
                    "keys": "search a key or an action_"}

    def __init__(self, monitor, mode="launch"):
        super().__init__(monitor, center=True)
        self.mode = mode
        self.dry = os.environ.get("GITS_LAUNCH_DRYRUN")
        root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        root.add_css_class("panel")
        head = Gtk.Box(spacing=6)
        head.append(label(self.TITLES.get(mode, "LAUNCH // 起動"), "m-head"))
        sp = Gtk.Box()
        sp.set_hexpand(True)
        head.append(sp)
        self.l_hint = label("Enter: copy · Esc: close" if mode == "emoji" else "Esc: close" if mode == "keys" else "Enter: run · Esc: close", "m-tag")
        head.append(self.l_hint)
        root.append(head)
        self.entry = Gtk.Entry()
        self.entry.add_css_class("m-entry")
        self.entry.set_placeholder_text(self.PLACEHOLDERS.get(mode, "apps, settings, projects, windows, notes... or 2+2_"))
        self.entry.connect("changed", lambda *_: self._refresh())
        self.entry.connect("activate", lambda *_: self._activate())
        keys = Gtk.EventControllerKey()
        keys.connect("key-pressed", self._key)
        self.entry.add_controller(keys)
        root.append(self.entry)
        self.box = Gtk.ListBox()
        self.box.set_selection_mode(Gtk.SelectionMode.SINGLE)
        self.box.set_activate_on_single_click(True)
        self.box.connect("row-activated", lambda _b, row: self._run(row.item))
        sc = Gtk.ScrolledWindow()
        sc.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        sc.set_propagate_natural_height(True)
        sc.set_max_content_height(470)
        sc.set_child(self.box)
        root.append(sc)
        self.set_child(root)
        import time as _t
        _t0 = _t.time()
        self.usage = {} if DEMO else self._load_usage()
        self.items = self._gather()
        _t1 = _t.time()
        self._refresh()
        if os.environ.get("GITS_PANEL_DEBUG"):
            open(os.environ["GITS_PANEL_DEBUG"], "a").write(f"launcher: gather {_t1 - _t0:.2f}s, first list {_t.time() - _t1:.2f}s, {len(self.items)} items\n")
        GLib.idle_add(lambda: (self.entry.grab_focus(), False)[1])
        auto = os.environ.get("GITS_PANEL_AUTOTEXT")   # test / screenshot hooks
        if auto:
            GLib.timeout_add(900, lambda: (self.entry.set_text(auto), False)[1])
            if os.environ.get("GITS_PANEL_AUTOENTER"):
                GLib.timeout_add(1600, lambda: (self._activate(), False)[1])

    # -- data
    def _load_usage(self):
        try:
            return json.load(open(self.USAGE))
        except (OSError, ValueError):
            return {}

    def _gather(self):
        items = []
        if self.mode == "clip":
            rows = [f"{i}\t{t}" for i, t in enumerate(DEMO_CLIPS, 1)] if DEMO else sh(["cliphist", "list"], timeout=3).splitlines()[:80]
            for ln in rows:
                cid, _, text = ln.partition("\t")
                binary = text.startswith("[[ binary data")
                items.append(Item("clip", text.replace("[[ binary data ", "image ").rstrip(" ]]") if binary else " ".join(text.split())[:110],
                                  "image" if binary else f"{len(text)} chars", glyph="󰋩" if binary else "󰅍",
                                  match=text, act=("clip", cid), ident=cid))
            return items
        if self.mode == "windows" and DEMO:
            for i, (t, c, ws) in enumerate(DEMO_WINDOWS):
                items.append(Item("win", t, f"{c} · workspace {ws}", glyph="󰖯", match=f"{t} {c}", act=("win", str(i)), ident=str(i)))
            return items
        if self.mode == "windows":
            try:
                cl = [c for c in json.loads(sh(["hyprctl", "clients", "-j"]) or "[]") if c.get("mapped") and c.get("workspace", {}).get("id") is not None]
            except ValueError:
                cl = []
            for c in sorted(cl, key=lambda c: c.get("focusHistoryID", 99)):   # most recently used first; the current window is skipped
                if c.get("focusHistoryID") == 0 and len(cl) > 1:
                    continue
                ws = c["workspace"].get("name", "")
                ws = "scratchpad" if ws.startswith("special:") else f"workspace {ws}"
                items.append(Item("win", (c.get("title") or c.get("class") or "?")[:80], f"{c.get('class', '')} · {ws}", glyph="󰖯",
                                  match=f"{c.get('title', '')} {c.get('class', '')}", act=("win", c["address"]), ident=c["address"]))
            return items
        if self.mode == "emoji":
            import unicodedata
            for lo, hi in ((0x1F600, 0x1F64F), (0x1F300, 0x1F5FF), (0x1F650, 0x1FAFF), (0x2190, 0x21FF), (0x2600, 0x27BF), (0x2B00, 0x2BFF)):   # faces first
                for cp in range(lo, hi + 1):
                    ch = chr(cp)
                    if unicodedata.category(ch) not in ("So", "Sm"):
                        continue
                    name = unicodedata.name(ch, "").lower()
                    if name:
                        items.append(Item("emoji", name, f"U+{cp:04X}", glyph=ch, match=name, act=("copy", ch), ident=name))
            return items
        if self.mode == "keys":
            names = {64: "SUPER", 4: "CTRL", 8: "ALT", 1: "SHIFT"}
            try:
                binds = json.loads(sh(["hyprctl", "binds", "-j"], real=True) or "[]")
            except ValueError:
                binds = []
            for b in binds:
                if not b.get("has_description") or b.get("mouse"):
                    continue
                mods = [n for bit, n in names.items() if b.get("modmask", 0) & bit]
                combo = " + ".join(mods + [b.get("key", "")])
                grp, _, what = b["description"].partition("] ")
                items.append(Item("key", what or grp, f"{combo}   {grp.lstrip('[')}" if what else combo, glyph="󰌌",
                                  match=f"{what} {grp} {combo}", act=("none", ""), ident=combo))
            items.sort(key=lambda it: it.sub.rpartition("   ")[2] + it.title)
            return items
        for a in Gio.AppInfo.get_all():
            if not a.should_show():
                continue
            kw = " ".join(a.get_keywords() or []) if hasattr(a, "get_keywords") else ""
            gen = a.get_generic_name() if hasattr(a, "get_generic_name") else ""
            items.append(Item("app", a.get_name(), a.get_description() or gen or "", icon=a.get_icon(), glyph="󰀻",
                              match=f"{a.get_name()} {gen or ''} {kw}", act=("app", a.get_id() or ""), ident=a.get_id()))
        for row in sh(["gits-settings", "--list"], timeout=3, real=True).splitlines():
            lab, _, cmd = row.partition("\t")
            m = re.match(r"^(\S)\s+(.*)$", lab)
            items.append(Item("set", m.group(2) if m else lab, "settings", glyph=m.group(1) if m else "󰒓", act=("sh", cmd), weight=0.9))
        prj_rows = [f"{n}\t{d.replace('~', HOME)}\t{k}" for n, d, k in DEMO_PROJECTS] if DEMO else sh(["gits-project", "--tsv"], timeout=4).splitlines()
        for row in prj_rows:
            name, _, rest = row.partition("\t")
            d, _, kind = rest.partition("\t")
            items.append(Item("prj", name, d.replace(HOME, "~"), glyph="󰊗" if kind == "godot" else "", match=f"{name} {d}", act=("prj", d), weight=0.95))
        try:
            cls = [{"mapped": True, "title": t, "class": c, "address": str(i)} for i, (t, c, _) in enumerate(DEMO_WINDOWS)] if DEMO \
                else json.loads(sh(["hyprctl", "clients", "-j"]) or "[]")
            for c in cls:
                if c.get("mapped") and c.get("title"):
                    items.append(Item("win", c["title"][:80], c.get("class", ""), glyph="󰖯", match=f"{c['title']} {c.get('class', '')}",
                                      act=("win", c["address"]), weight=1.1))
        except ValueError:
            pass
        notes = os.environ.get("GITS_NOTES") or os.path.join(HOME, "notes", "inbox.md")
        try:
            for ln in [x.rstrip("\n") for x in open(notes, encoding="utf-8") if x.strip()][-40:]:
                t = re.sub(r"^- \d{4}-\d{2}-\d{2} \d{2}:\d{2} +", "", ln)
                items.append(Item("note", t[:100], "note (Enter copies it)", glyph="󰎞", act=("copy", t), weight=0.7))
        except OSError:
            pass
        return items

    def _frecency(self, ident):
        u = self.usage.get(ident or "")
        if not u:
            return 1.0
        import time
        recent = 0.3 if time.time() - u.get("t", 0) < 3 * 86400 else 0.0
        return 1.0 + min(math.log1p(u.get("n", 0)), 3.0) * 0.35 + recent

    def _search(self, q):
        if self.mode in self.TITLES:
            if not q.strip():
                return self.items[:12]
            scored = [(fuzzy(q.strip(), it.match), it) for it in self.items]
            return [it for sc, it in sorted(scored, key=lambda x: -x[0]) if sc > 0][:12]
        q = q.strip()
        if not q:
            apps = [it for it in self.items if it.kind == "app"]
            used = sorted((it for it in apps if it.ident in self.usage), key=lambda it: -self._frecency(it.ident))[:8]
            return used or sorted(apps, key=lambda it: it.title.lower())[:8]
        res = []
        r = calc(q)
        if r is not None:
            res.append((1e6, Item("calc", f"= {r}", q, glyph="󰃬", act=("copy", r))))
        for it in self.items:
            sc = fuzzy(q, it.match)
            if it.kind == "note" and len(q) < 3:
                sc = 0
            if sc > 0:
                res.append((sc * it.weight * (self._frecency(it.ident) if it.kind == "app" else 1.0), it))
        res = [it for _, it in sorted(res, key=lambda x: -x[0])][:9]
        res.append(Item("web", f"Search the web for \"{q}\"", "opens the browser", glyph="󰖟", act=("web", q)))
        return res

    # -- list
    def _refresh(self):
        while (c := self.box.get_first_child()) is not None:
            self.box.remove(c)
        rows = self._search(self.entry.get_text())
        tags = {"app": "APP", "set": "SETTINGS", "prj": "PROJECT", "win": "WINDOW", "note": "NOTE", "calc": "CALC", "web": "WEB", "clip": "", "emoji": "", "key": ""}
        for it in rows:
            row = Gtk.ListBoxRow()
            row.add_css_class("lrow")
            row.item = it
            h = Gtk.Box(spacing=10)
            if it.icon is not None:
                img = Gtk.Image.new_from_gicon(it.icon)
                img.set_pixel_size(28)
                if os.environ.get("GITS_ICON_TINT") != "0":   # app logos in the cyan phosphor tone; GITS_ICON_TINT=0 keeps their colours
                    img.add_css_class("l-icon")
                h.append(img)
            else:
                g = label(it.glyph, "l-glyph", 0.5)
                g.set_size_request(28, -1)
                h.append(g)
            col = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
            col.set_hexpand(True)
            t = label(it.title, "l-title")
            t.set_ellipsize(Pango.EllipsizeMode.END)
            t.set_max_width_chars(48)
            col.append(t)
            if it.sub:
                sub = label(it.sub, "l-sub")
                sub.set_ellipsize(Pango.EllipsizeMode.END)
                sub.set_max_width_chars(58)
                col.append(sub)
            h.append(col)
            if tags.get(it.kind):
                h.append(label(tags[it.kind], "l-tag", 1.0))
            row.set_child(h)
            self.box.append(row)
        first = self.box.get_row_at_index(0)
        if first is not None:
            self.box.select_row(first)

    def _key(self, _c, kv, state, *_):
        if kv in (Gdk.KEY_Down, Gdk.KEY_Up) or (state & Gdk.ModifierType.CONTROL_MASK and kv in (Gdk.KEY_n, Gdk.KEY_p)):
            down = kv in (Gdk.KEY_Down, Gdk.KEY_n)
            cur = self.box.get_selected_row()
            i = (cur.get_index() if cur else -1) + (1 if down else -1)
            n = 0
            while self.box.get_row_at_index(n) is not None:
                n += 1
            if n:
                row = self.box.get_row_at_index(i % n)
                self.box.select_row(row)
                row.grab_focus()
                self.entry.grab_focus()
            return True
        return False

    def _activate(self):
        row = self.box.get_selected_row()
        if row is not None:
            self._run(row.item)

    # -- actions
    def _run(self, it):
        kind, arg = it.act
        cmd = None
        if kind == "app":
            u = self.usage.setdefault(it.ident, {"n": 0, "t": 0})
            import time
            u["n"], u["t"] = u["n"] + 1, time.time()
            if not self.dry:
                os.makedirs(os.path.dirname(self.USAGE), exist_ok=True)
                json.dump(self.usage, open(self.USAGE, "w"))
            cmd = ["gtk-launch", arg if arg.endswith(".desktop") else arg + ".desktop"]   # full id: org.telegram.desktop would lose its tail
        elif kind == "sh":
            cmd = ["bash", "-c", arg]
        elif kind == "prj":
            cmd = ["gits-project", "--open", arg]
        elif kind == "win":
            cmd = ["hyprctl", "dispatch", f'hl.dsp.focus({{ window = "address:{arg}" }})']
        elif kind == "copy":
            cmd = ["bash", "-c", f"printf %s {shlex.quote(arg)} | wl-copy && notify-send -a 'GitS Notify' -t 2500 'Copied' {shlex.quote(arg[:80])}"]
        elif kind == "web":
            import urllib.parse
            cmd = ["xdg-open", "https://duckduckgo.com/?q=" + urllib.parse.quote_plus(arg)]
        elif kind == "clip":
            cmd = ["bash", "-c", f"cliphist decode {shlex.quote(arg)} | wl-copy"]
        if cmd:
            if self.dry:
                open(self.dry, "a").write(f"{kind}\t{it.title}\t{shlex.join(cmd)}\n")
            else:   # a moment later: the popup still holds the keyboard, a new window would not get focus
                fire(["sh", "-c", "sleep 0.25; exec " + shlex.join(cmd)])
        self.dismiss()


def main():
    if not LS.is_supported():
        print("gits-panel: no layer-shell support", file=sys.stderr)
        return 1
    Gtk.init()
    css = Gtk.CssProvider()
    css.load_from_path(os.path.join(HERE, "panel.css"))
    Gtk.StyleContext.add_provider_for_display(Gdk.Display.get_default(), css, Gtk.STYLE_PROVIDER_PRIORITY_USER)
    # no monitor given = the compositor opens the popup on the focused one (where the bar was clicked / the key was pressed);
    # GITS_PANEL_MONITOR=<connector> pins every popup to one screen instead
    mons = Gdk.Display.get_default().get_monitors()
    want = os.environ.get("GITS_PANEL_MONITOR", "")
    mon = None
    for i in range(mons.get_n_items()):
        m = mons.get_item(i)
        if want and (m.get_connector() or "") == want:
            mon = m
            break
    loop = GLib.MainLoop()
    mode = (sys.argv[1:] or ["control"])[0]
    if mode == "menu":
        title, tag, kind = (sys.argv[2:5] + ["", "", "line"])[:3]
        lines = [] if kind == "password" else [ln.rstrip("\n") for ln in sys.stdin.read().split("\n") if ln.strip()]
        win = MenuPopup(mon, title, tag, kind, lines)
        win.connect("close-request", lambda *_: (loop.quit(), False)[1])
        win.present()
        for sig in (2, 15):
            GLibUnix.signal_add(GLib.PRIORITY_DEFAULT, sig, lambda: (loop.quit(), False)[1])
        loop.run()
        if win.result is None:
            return 1
        print(win.lines[win.result] if kind == "line" else win.result)
        return 0
    if mode == "notify":
        win = NotifyPopup(mon)
    elif mode in ("launch", "clip", "windows", "emoji", "keys"):
        win = LauncherPopup(mon, mode)
    elif mode == "note":
        win = NotePopup(mon)
    elif mode in ("appearance", "themes"):
        win = AppearancePopup(mon)
    elif mode == "mixer":
        cx = int(sh(["hyprctl", "cursorpos"]).split(",")[0] or 640) if not DEMO else 700
        width = mon.get_geometry().width if mon else 1280
        win = MixerPopup(mon, max(8, min(cx - 170, width - 348)))
    elif mode == "media":
        win = MediaPopup(mon)
    elif mode == "radio":
        win = MediaPopup(mon, start="radio")
    else:
        win = Panel(mon)
    win.connect("close-request", lambda *_: (loop.quit(), False)[1])
    win.present()
    for sig in (2, 15):
        GLibUnix.signal_add(GLib.PRIORITY_DEFAULT, sig, lambda: (loop.quit(), False)[1])
    loop.run()
    getattr(win, "shutdown", lambda: None)()   # e.g. the radio popup's parec
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
