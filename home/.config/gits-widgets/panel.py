#!/usr/bin/env python3
"""Ghost in the Shell control panel: a small layer-shell popup under the bar (toggle with `gits-panel`, Super+Shift+C).

Toggles: Wi-Fi, Bluetooth, do-not-disturb, night light, UI sounds, desktop widgets.
Sliders: volume (wpctl), brightness (brightnessctl). Segments: power profile (power-profiles-daemon), battery charge
limit (asusctl, ASUS only). Closes on Escape or when it loses focus. Everything is read/written through the same CLI
tools the bar modules use, so the bar and the panel never disagree for long.
"""
import os
import re
import subprocess
import sys
import threading
import urllib.parse
import urllib.request

_LS_LIB = "/usr/lib/libgtk4-layer-shell.so"
if os.path.exists(_LS_LIB) and _LS_LIB not in os.environ.get("LD_PRELOAD", ""):
    os.environ["LD_PRELOAD"] = (_LS_LIB + " " + os.environ.get("LD_PRELOAD", "")).strip()
    os.execv(sys.executable, [sys.executable, os.path.abspath(__file__), *sys.argv[1:]])
os.environ.setdefault("GSK_RENDERER", "cairo")
os.environ.setdefault("GDK_BACKEND", "wayland")
os.environ["GTK_THEME"] = "Adwaita:dark"

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")
gi.require_version("Gtk4LayerShell", "1.0")
gi.require_version("GdkPixbuf", "2.0")
from gi.repository import Gdk, GdkPixbuf, GLib, GLibUnix, Gtk, Pango  # noqa: E402
from gi.repository import Gtk4LayerShell as LS  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
HOME = os.path.expanduser("~")
STATE = os.environ.get("XDG_STATE_HOME", HOME + "/.local/state")
DEMO = os.environ.get("GITS_PANEL_DEMO") == "1"  # screenshot mode: fixed made-up state, no commands executed


def sh(cmd, timeout=4):
    """Run a command (list), return stdout ('' on any failure)."""
    if DEMO:
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
    try:
        return open(STATE + "/hyde/hyprsunset").read().strip().split("|")[2] == "1"
    except (OSError, IndexError):
        return False


def get_sounds():
    return not os.path.exists(STATE + "/gits-sounds/off")


def get_widgets():
    try:
        pid = open(os.environ.get("XDG_RUNTIME_DIR", "/tmp") + "/gits-widgets.pid").read().strip()
        return os.path.exists(f"/proc/{int(pid)}")
    except (OSError, ValueError):
        return False


def get_awake():
    """Caffeine: on while hypridle is stopped (the screen never locks or sleeps by itself)."""
    return subprocess.run(["pgrep", "-x", "hypridle"], capture_output=True).returncode != 0 if not DEMO else False


def set_awake():
    if subprocess.run(["pgrep", "-x", "hypridle"], capture_output=True).returncode == 0:
        subprocess.run(["pkill", "-x", "hypridle"])
    else:
        fire(["setsid", "-f", "hypridle"])


def get_airplane():
    rows = sh(["rfkill", "list", "-n", "-o", "SOFT"]).split()
    return bool(rows) and all(r == "blocked" for r in rows)


def get_game():
    try:
        return 'HYPR_WORKFLOW="gaming"' in open(STATE + "/hyde/staterc").read()
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
        night = Tile("󰖔", "NIGHT", get_night, lambda: fire(["hyde-shell", "hyprsunset", "-t", "-q"]))
        snd = Tile("󰝚", "SOUNDS", get_sounds, lambda: fire(["gits-sound", "toggle"]))
        wid = Tile("󰕮", "WIDGETS", get_widgets, lambda: fire([HERE + "/run.sh", "toggle"]))
        awake = Tile("󰅶", "AWAKE", get_awake, set_awake)
        plane = Tile("󰀝", "AIRPLANE", get_airplane, lambda: fire(["rfkill", "unblock" if get_airplane() else "block", "all"]))
        game = Tile("󰊗", "GAME", get_game, lambda: fire(["hyde-shell", "workflows", "--set", "01-default" if get_game() else "gaming"]))
        self.tiles = [wifi, bt, dnd, night, snd, wid, awake, plane, game]
        pad = Tile("󰍽", "TOUCHPAD", get_touchpad, lambda: fire(["gits-touchpad", "toggle"]))
        glitch = Tile("󰘨", "GLITCH", get_glitch, set_glitch)
        rec = Tile("󰑋", "REC", lambda: sh(["gits-rec", "status"]) == "on", lambda: self._later("gits-rec toggle area"))
        self.tiles += [pad, glitch, rec]
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
        for icon, name, cmd in (("󰄀", "SHOT", "hyde-shell screenshot s"), ("󰗊", "OCR", "hyde-shell screenshot sc"),
                                ("󰈊", "PICK", "hyprpicker -an"), ("󰅍", "CLIP", "hyde-shell cliphist -c"),
                                ("󰢮", "ROG", "gits-rog")):
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
        # session: lock / sleep run at once, the destructive three ask twice
        sess = Gtk.Box(spacing=6, homogeneous=True)
        sess.append(self._action("󰌾", "LOCK", lambda: self._later("loginctl lock-session")))
        sess.append(self._action("󰤄", "SLEEP", lambda: self._later("systemctl suspend")))
        sess.append(self._action("󰍃", "LOGOUT", lambda: self._later("hyprctl dispatch 'hl.dsp.exit()'"), confirm=True))
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
            out = "\x1b[0m50 ok, 1 warn, 0 fail"
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
            if state["armed"] is None:  # first click: arm, second within 3 s: do it
                b.add_css_class("warn")
                lb.set_text("SURE?")
                state["armed"] = GLib.timeout_add(3000, disarm)
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
            st.update({"AWAKE": False, "AIRPLANE": False, "GAME": False, "TOUCHPAD": True, "GLITCH": True, "REC": False})
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


class MediaPopup(Popup):
    """Player popup (MPRIS through playerctl): cover, title, seek bar, transport, shuffle/repeat, player volume."""
    CACHE = os.path.join(os.environ.get("XDG_CACHE_HOME", HOME + "/.cache"), "gits-widgets", "art")

    def __init__(self, monitor, left):
        super().__init__(monitor, left)
        self.CARD_W = 304
        self.quiet = False
        self.art_key = None
        self.length = 0.0
        self.seek_timer = None
        root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=7)
        root.add_css_class("panel")
        head = self.header("MEDIA.LINK // 音")
        root.append(head)

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
        root.append(ov)

        self.title = label("—", "m-title")
        self.title.set_ellipsize(Pango.EllipsizeMode.END)
        self.title.set_max_width_chars(30)
        self.artist = label("", "m-artist")
        self.artist.set_ellipsize(Pango.EllipsizeMode.END)
        self.artist.set_max_width_chars(34)
        root.append(self.title)
        root.append(self.artist)

        self.seek = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 0, 100, 1)
        self.seek.set_draw_value(False)
        self.seek.set_hexpand(True)
        self.seek.connect("value-changed", self._seek_moved)
        root.append(self.seek)
        times = Gtk.Box()
        self.t_pos, self.t_len = label("0:00", "m-time"), label("0:00", "m-time", 1.0)
        self.t_len.set_hexpand(True)
        times.append(self.t_pos)
        times.append(self.t_len)
        root.append(times)

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
        root.append(ctl)

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
        root.append(vrow)
        self.set_child(root)

        self.refresh()
        GLib.timeout_add_seconds(1, lambda: (self.refresh(), True)[1])

    # -- playerctl helpers
    @staticmethod
    def _pcout(*args):
        return sh(["gits-media", *args], timeout=2.5)

    def _pc(self, *args):
        fire(["gits-media", *args])
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
        self.seek_timer = GLib.timeout_add(120, lambda: (setattr(self, "seek_timer", None), fire(["gits-media", "position", f"{v:.1f}"]), False)[2])

    def _vol_moved(self, sc):
        v = int(sc.get_value())
        self.l_vol.set_text(f"{v}%")
        if not self.quiet:
            fire(["gits-media", "volume", f"{v / 100:.2f}"])

    # -- state
    def refresh(self):
        threading.Thread(target=self._fetch, daemon=True).start()

    def _fetch(self):
        if DEMO:
            data = ["Playing", "Lain Iwakura", "Serial Experiments Lain - Duvet", ("file://" + os.environ["GITS_PANEL_ART"]) if os.environ.get("GITS_PANEL_ART") else "", str(232 * 10**6), str(84 * 10**6),
                    "spotify", "On", "None", "0.62"]
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
                     (3, "HyDE Power", "Battery Low", "Battery is at 19%. Connect the charger.", 3600 * 3, "CRITICAL"),
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


def main():
    if not LS.is_supported():
        print("gits-panel: no layer-shell support", file=sys.stderr)
        return 1
    Gtk.init()
    css = Gtk.CssProvider()
    css.load_from_path(os.path.join(HERE, "panel.css"))
    Gtk.StyleContext.add_provider_for_display(Gdk.Display.get_default(), css, Gtk.STYLE_PROVIDER_PRIORITY_USER)
    mons = Gdk.Display.get_default().get_monitors()
    mon = None
    for i in range(mons.get_n_items()):
        m = mons.get_item(i)
        if mon is None:
            mon = m
        if (m.get_connector() or "").startswith("eDP"):
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
    elif mode == "mixer":
        cx = int(sh(["hyprctl", "cursorpos"]).split(",")[0] or 640) if not DEMO else 700
        width = mon.get_geometry().width if mon else 1280
        win = MixerPopup(mon, max(8, min(cx - 170, width - 348)))
    elif mode == "media":
        cx = int(sh(["hyprctl", "cursorpos"]).split(",")[0] or 640) if not DEMO else 700  # logical px: under the clicked bar module
        width = mon.get_geometry().width if mon else 1280
        win = MediaPopup(mon, max(8, min(cx - 150, width - 308)))
    else:
        win = Panel(mon)
    win.connect("close-request", lambda *_: (loop.quit(), False)[1])
    win.present()
    for sig in (2, 15):
        GLibUnix.signal_add(GLib.PRIORITY_DEFAULT, sig, lambda: (loop.quit(), False)[1])
    loop.run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
