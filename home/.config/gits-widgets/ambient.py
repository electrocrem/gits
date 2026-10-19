#!/usr/bin/env python3
"""GitS sound bars on the desktop: while something plays, a spectrum along the bottom edge of the wallpaper, in the theme's colours
(gits-ambient.service; gits-ambient on / off, Super+I -> Desktop sound bars).

The default output's monitor (parec) -> 48 bands (numpy FFT), bass in the middle, treble at both ends, falling peak caps. It only
runs while you can see it: the main monitor's workspace has no windows, the laptop is on AC power and the gaming workflow is off;
otherwise parec is stopped and nothing redraws. A BACKGROUND layer (above the wallpaper, below the desktop cards), drawn with GSK on
the integrated GPU (Mesa only: the NVIDIA card is never opened), ~30 fps. Off: ~/.local/state/gits/ambient.json {"spectrum": false}.
"""
import json
import os
import select
import socket
import subprocess
import sys
import threading
import time

_LS = "/usr/lib/libgtk4-layer-shell.so"
if os.path.exists(_LS) and _LS not in os.environ.get("LD_PRELOAD", ""):
    os.environ["LD_PRELOAD"] = (_LS + " " + os.environ.get("LD_PRELOAD", "")).strip()
    os.execv(sys.executable, [sys.executable, os.path.abspath(__file__), *sys.argv[1:]])
os.environ.pop("LD_PRELOAD", None)
# GPU drawing, but on the integrated GPU: only Mesa's EGL, so the NVIDIA card of a hybrid laptop is never opened (and stays asleep)
_MESA = "/usr/share/glvnd/egl_vendor.d/50_mesa.json"
if os.path.exists(_MESA):
    os.environ.setdefault("__EGL_VENDOR_LIBRARY_FILENAMES", _MESA)
    os.environ.setdefault("GSK_RENDERER", "gl")
else:
    os.environ.setdefault("GSK_RENDERER", "cairo")

import cairo  # noqa: E402
import gi  # noqa: E402

gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")
gi.require_version("Graphene", "1.0")
gi.require_version("Gtk4LayerShell", "1.0")
from gi.repository import Gdk, GLib, GLibUnix, Graphene, Gtk  # noqa: E402
from gi.repository import Gtk4LayerShell as LS  # noqa: E402

HOME = os.path.expanduser("~")
RUN = os.environ.get("XDG_RUNTIME_DIR", "/tmp")
STATE = os.path.join(os.environ.get("XDG_STATE_HOME", os.path.join(HOME, ".local", "state")), "gits")
CONF = os.path.join(STATE, "ambient.json")
FPS = 30

# palette (= the GitS theme; gits-theme recolours these literals)
CY, CYB = "#2ED3D7", "#5EF1F5"

_rgba = {}


def col(h, a=1.0):
    k = (h, round(a, 3))
    c = _rgba.get(k)
    if c is None:
        c = Gdk.RGBA()
        c.parse(h)
        c.alpha = max(0.0, min(1.0, a))
        if len(_rgba) > 4000:
            _rgba.clear()
        _rgba[k] = c
    return c


def rect(x, y, w, h):
    return Graphene.Rect().init(x, y, w, h)


def conf():
    c = {"spectrum": True}
    try:
        c.update(json.load(open(CONF)))
    except (OSError, ValueError):
        pass
    return c


# ------------------------------------------------------------------------------------------------ sound
class Spectrum(threading.Thread):
    """The default output's monitor (parec) -> BANDS levels 0..1 (numpy FFT). Runs only while the scene is live."""
    RATE, N, BANDS, HOP = 44100, 2048, 48, 1024

    def __init__(self):
        super().__init__(daemon=True)
        import numpy as np
        self.np = np
        self.bands = np.zeros(self.BANDS)
        self.loud = 0.0
        self.on = threading.Event()
        edges = np.geomspace(40, 16000, self.BANDS + 1) * self.N / self.RATE
        self.lo = np.maximum(np.floor(edges[:-1]).astype(int), 1)
        self.hi = np.maximum(np.ceil(edges[1:]).astype(int), self.lo + 1)
        self.win = np.hanning(self.N)
        self.tilt = np.linspace(0, 12, self.BANDS)

    def run(self):
        np = self.np
        while True:
            self.on.wait()
            sink = subprocess.run(["pactl", "get-default-sink"], capture_output=True, text=True).stdout.strip()
            if not sink:
                time.sleep(3)
                continue
            try:
                p = subprocess.Popen(["parec", "-d", sink + ".monitor", "--format=s16le", f"--rate={self.RATE}", "--channels=1",
                                      "--latency-msec=30"], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
            except OSError:
                time.sleep(10)
                continue
            buf, pend, fd, started = np.zeros(self.N), b"", p.stdout.fileno(), time.monotonic()
            while self.on.is_set() and p.poll() is None and time.monotonic() - started < 60:   # re-check the sink every minute
                if not select.select([fd], [], [], 1.0)[0]:
                    continue
                pend += os.read(fd, 8192)
                while len(pend) >= self.HOP * 2:
                    x = np.frombuffer(pend[:self.HOP * 2], dtype="<i2").astype(np.float64) / 32768.0
                    pend = pend[self.HOP * 2:]
                    buf = np.concatenate((buf[self.HOP:], x))
                    mag = np.abs(np.fft.rfft(buf * self.win)) / (self.N / 4)
                    db = 20 * np.log10(np.array([mag[a:b].max() for a, b in zip(self.lo, self.hi)]) + 1e-9)
                    self.bands = np.clip((db + self.tilt + 70) / 60, 0, 1)
                    self.loud = float(np.sqrt(np.mean(x * x)))
            p.kill()
            p.wait()
            if not self.on.is_set():
                self.bands = np.zeros(self.BANDS)
                self.loud = 0.0



# ------------------------------------------------------------------------------------------------ the bars
class Bars(Gtk.Widget):
    __gtype_name__ = "GitsAmbientBars"

    def __init__(self, app):
        super().__init__()
        self.app = app
        self.levels = [0.0] * Spectrum.BANDS
        self.peaks = [0.0] * Spectrum.BANDS

    def step(self, dt):
        sp = self.app.spectrum
        if sp is None:
            return
        bands = sp.bands
        for i in range(len(self.levels)):
            self.levels[i] += (float(bands[i]) - self.levels[i]) * min(1.0, dt * 14)
            self.peaks[i] = max(self.levels[i], self.peaks[i] - dt * 0.5)

    def do_snapshot(self, s):
        w, h = self.get_width(), self.get_height()
        if w <= 0 or not self.app.live or max(self.peaks) < 0.03:
            return
        n = len(self.levels)
        span = w * 0.56
        x0, bw = (w - span) / 2, span / n
        hmax, base = h * 0.11, h - 4
        half = n // 2
        bar, cap = col(CY, 0.20), col(CYB, 0.55)
        for i in range(n):
            j = min(n - 1, (i - half) * 2 if i >= half else (half - 1 - i) * 2 + 1)   # bass in the middle, treble at both ends
            v, pk = self.levels[j], self.peaks[j]
            x = x0 + i * bw
            if v * hmax > 1:
                s.append_color(bar, rect(x + 1, base - v * hmax, bw - 2, v * hmax))
            if pk > 0.03:
                s.append_color(cap, rect(x + 1, base - pk * hmax - 3, bw - 2, 2))


# ------------------------------------------------------------------------------------------------ app
class App:
    def __init__(self):
        self.c = conf()
        self.spectrum = None
        self.live = False
        self.visible = True
        self.tick_id = None
        self.last_frame = 0.0
        self.loop = GLib.MainLoop()

    def pick_monitor(self):
        mons = Gdk.Display.get_default().get_monitors()
        items = [mons.get_item(i) for i in range(mons.get_n_items())]
        want = os.environ.get("GITS_WIDGETS_MONITOR") or os.environ.get("GITS_MAIN_MONITOR", "")
        if not items:
            return None

        def rank(m):
            conn, g = m.get_connector() or "", m.get_geometry()
            return (0 if want and conn == want else 1 if not want and conn.startswith("eDP") else 2, -g.width * g.height, g.x)
        return min(items, key=rank)

    def start(self):
        Gtk.init()
        css = Gtk.CssProvider()
        css.load_from_string("window.amb { background: transparent; }")
        Gtk.StyleContext.add_provider_for_display(Gdk.Display.get_default(), css, Gtk.STYLE_PROVIDER_PRIORITY_USER)
        mon = self.pick_monitor()
        self.conn = mon.get_connector() if mon else ""
        self.win = Gtk.Window()
        LS.init_for_window(self.win)
        LS.set_namespace(self.win, "gits-ambient")
        LS.set_layer(self.win, LS.Layer.BACKGROUND)
        for e in (LS.Edge.TOP, LS.Edge.BOTTOM, LS.Edge.LEFT, LS.Edge.RIGHT):
            LS.set_anchor(self.win, e, True)
        LS.set_exclusive_zone(self.win, -1)
        LS.set_keyboard_mode(self.win, LS.KeyboardMode.NONE)
        if mon is not None:
            LS.set_monitor(self.win, mon)
        self.win.set_decorated(False)
        self.win.add_css_class("amb")
        self.win.connect("map", lambda *_: self.win.get_surface().set_input_region(cairo.Region()))   # clicks go through
        self.bars = Bars(self)
        self.win.set_child(self.bars)
        self.win.present()
        threading.Thread(target=self.listen, daemon=True).start()
        GLib.timeout_add_seconds(5, lambda: (self.update_live(), True)[1])   # AC plugged in, away flag gone, ...
        GLibUnix.signal_add(GLib.PRIORITY_DEFAULT, 1, lambda: (self.reconf(), True)[1])   # SIGHUP: settings changed
        for sig in (2, 15):
            GLibUnix.signal_add(GLib.PRIORITY_DEFAULT, sig, lambda: (self.loop.quit(), False)[1])
        with open(os.path.join(RUN, "gits-ambient.pid"), "w") as f:
            f.write(str(os.getpid()))
        self.recheck()
        self.loop.run()

    def reconf(self):
        self.c = conf()
        self.update_live()

    def listen(self):
        """Hyprland's events: whether the main monitor shows an empty workspace (the bars can be seen) after every change."""
        sig = os.environ.get("HYPRLAND_INSTANCE_SIGNATURE", "")
        path = os.path.join(RUN, "hypr", sig, ".socket2.sock")
        evs = (b"workspace>>", b"openwindow>>", b"closewindow>>", b"movewindow>>", b"activespecial>>", b"changefloatingmode>>",
               b"fullscreen>>", b"focusedmon>>")
        while True:
            try:
                sk = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
                sk.connect(path)
                buf = b""
                while True:
                    chunk = sk.recv(4096)
                    if not chunk:
                        break
                    buf += chunk
                    *lines, buf = buf.split(b"\n")
                    if any(ln.startswith(evs) for ln in lines):
                        GLib.idle_add(self.recheck)
            except OSError:
                pass
            time.sleep(3)

    def recheck(self):
        try:
            mons = json.loads(subprocess.run(["hyprctl", "monitors", "-j"], capture_output=True, text=True, timeout=2).stdout)
            wss = json.loads(subprocess.run(["hyprctl", "workspaces", "-j"], capture_output=True, text=True, timeout=2).stdout)
        except (OSError, ValueError, subprocess.TimeoutExpired):
            return False
        m = next((m for m in mons if m.get("name") == self.conn), mons[0] if mons else {})
        ids = {(m.get("activeWorkspace") or {}).get("id"), (m.get("specialWorkspace") or {}).get("id") or None} - {None, 0}
        self.visible = not any(w.get("windows", 0) for w in wss if w.get("id") in ids)
        self.update_live()
        return False

    @staticmethod
    def blocked():
        try:
            if "workflow=gaming" in open(os.path.join(STATE, "state")).read().split():
                return True
        except OSError:
            pass
        return os.path.exists(os.path.join(RUN, "gits-away"))

    @staticmethod
    def on_ac():
        for d in os.listdir("/sys/class/power_supply"):
            try:
                if open(f"/sys/class/power_supply/{d}/type").read().strip() == "Mains":
                    return open(f"/sys/class/power_supply/{d}/online").read().strip() == "1"
            except OSError:
                pass
        return True   # a desktop PC

    def update_live(self):
        want = self.c.get("spectrum", True) and self.visible and self.on_ac() and not self.blocked()
        if want:
            if self.spectrum is None:
                try:
                    self.spectrum = Spectrum()
                    self.spectrum.start()
                except ImportError:   # no numpy
                    return
            self.spectrum.on.set()
        elif self.spectrum is not None:
            self.spectrum.on.clear()
        if want == self.live:
            return
        self.live = want
        if want:
            self.last_frame = 0.0
            self.tick_id = self.bars.add_tick_callback(self.tick)
        elif self.tick_id is not None:
            self.bars.remove_tick_callback(self.tick_id)
            self.tick_id = None
            self.bars.queue_draw()   # an empty last frame

    def tick(self, widget, clock):
        now = clock.get_frame_time() / 1e6
        if now - self.last_frame < 1 / FPS - 0.004:
            return True
        dt = min(0.1, now - self.last_frame) if self.last_frame else 1 / FPS
        self.last_frame = now
        self.bars.step(dt)
        widget.queue_draw()
        return True


def main():
    if not LS.is_supported():
        print("gits-ambient: no layer-shell support", file=sys.stderr)
        return 1
    App().start()
    return 0


if __name__ == "__main__":
    sys.exit(main())
