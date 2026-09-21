"""Spectrum of ONE audio stream (the radio's mpv), not of everything the machine plays.

    tap = StreamSpectrum(pid_file)      # pid_file holds the pid of the mpv (gits-radio writes it)
    tap.start()                         # a daemon thread: finds mpv's sink input with pactl, records it with `parec --monitor-stream`
    tap.bands                           # BANDS floats 0..1, low to high pitch; all zero while nothing plays
    tap.beats, tap.kick                 # count of detected beats (it goes up by one per beat) and the strength 0.4..1 of the last one
    tap.stop()                          # kills parec (call it when the popup closes)

The stream is not there for a moment after mpv starts, and it vanishes when mpv stops: the thread keeps looking, so the popup can
be open across both. Needs numpy, pactl and parec; `tap.error` is set if they are missing.
"""
import json
import os
import select
import subprocess
import threading
import time

import numpy as np

RATE = 44100
HOP = 2205        # 50 ms of mono s16 per update
WINDOW = 4096     # FFT size
LOW, HIGH = 45.0, 16000.0


def _pactl(*args):
    try:
        return json.loads(subprocess.run(["pactl", "--format=json", *args], capture_output=True, text=True, timeout=3).stdout or "[]")
    except (OSError, ValueError, subprocess.SubprocessError):
        return None


def find_stream(pid):
    """(sink-input index, monitor source) of the process, None while it is not playing, False if pactl cannot be used."""
    inputs = _pactl("list", "sink-inputs")
    if inputs is None:
        return False
    for si in inputs:
        if str(si.get("properties", {}).get("application.process.id", "")) == str(pid):
            for sink in _pactl("list", "sinks") or []:
                if sink.get("index") == si.get("sink"):
                    return si["index"], sink["name"] + ".monitor"
    return None


class StreamSpectrum(threading.Thread):
    BANDS = 24

    def __init__(self, pid_file):
        super().__init__(daemon=True)
        self.pid_file = pid_file
        self.bands = [0.0] * self.BANDS
        self.error = ""
        self.beats, self.kick = 0, 0.0
        self.proc = None
        self._halt = threading.Event()
        edges = np.geomspace(LOW, HIGH, self.BANDS + 1)
        freqs = np.fft.rfftfreq(WINDOW, 1 / RATE)
        self.lo = np.searchsorted(freqs, edges[:-1])
        self.hi = np.maximum(np.searchsorted(freqs, edges[1:]), self.lo + 1)
        self.tilt = (np.sqrt(edges[:-1] * edges[1:]) / 800.0) ** 0.45   # music falls off with pitch: lift the highs
        self.win = np.hanning(WINDOW)

    def stop(self):
        self._halt.set()
        proc = self.proc
        if proc is not None:
            try:
                proc.kill()
            except OSError:
                pass

    def _pid(self):
        try:
            with open(self.pid_file) as f:
                pid = int(f.read().strip())
            os.kill(pid, 0)
            return pid
        except (OSError, ValueError):
            return None

    def run(self):
        while not self._halt.is_set():
            pid = self._pid()
            found = find_stream(pid) if pid else None
            if found is False:
                self.error = "no pactl"
                return
            if found:
                self._capture(pid, *found)
            self.bands = [0.0] * self.BANDS
            self._halt.wait(0.8)

    def _capture(self, pid, index, monitor):
        try:
            self.proc = subprocess.Popen(["parec", "--format=s16le", f"--rate={RATE}", "--channels=1", "--latency-msec=40",
                                          f"--device={monitor}", f"--monitor-stream={index}"],
                                         stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        except OSError:
            self.error = "no parec"
            self._halt.set()
            return
        proc = self.proc
        fd = proc.stdout.fileno()
        buf = np.zeros(WINDOW)
        raw = b""
        shown = np.zeros(self.BANDS)
        ref = 1.0
        prev = np.zeros(self.BANDS)
        fluxes = []            # recent spectral flux: the sum of the rises of the low and mid bands from one 50 ms step to the next
        last_beat = 0.0
        last = time.monotonic()
        try:
            while not self._halt.is_set() and proc.poll() is None and self._pid() == pid:
                ready, _, _ = select.select([fd], [], [], 0.12)
                if ready:
                    chunk = os.read(fd, 8192)
                    if not chunk:
                        break
                    raw += chunk
                now = time.monotonic()
                if len(raw) >= HOP * 2:
                    take, raw = raw[:HOP * 2], raw[HOP * 2:]
                    buf = np.concatenate([buf[HOP:], np.frombuffer(take, dtype="<i2").astype(float) / 32768])
                    mag = np.abs(np.fft.rfft(buf * self.win))
                    level = np.array([mag[a:b].max() for a, b in zip(self.lo, self.hi)]) * self.tilt
                    ref = max(ref * 0.985, level.max(), 1.0)                # automatic gain, half-life ~2 s
                    fresh = np.clip(level / ref, 0, 1) ** 0.65
                    shown = np.maximum(fresh, shown * 0.80)
                    flux = float(np.maximum(fresh[:12] - prev[:12], 0).sum())
                    prev = fresh
                    if len(fluxes) >= 4:                            # a beat = the flux jumps above its own recent mean + 1 sigma (tuned on breakcore: ~2.4 a second)
                        m, sd = float(np.mean(fluxes)), float(np.std(fluxes))
                        if flux > m + sd and flux > 0.12 and now - last_beat > 0.15:
                            self.kick = min(1.0, 0.4 + 0.6 * (flux - m) / max(3 * sd, 0.2))
                            self.beats += 1
                            last_beat = now
                    fluxes.append(flux)
                    del fluxes[:-30]                                # the last 1.5 s
                    last = now
                elif now - last > 0.15:                                      # nothing arrives (paused): let the bars sink
                    shown = shown * 0.85
                    last = now
                else:
                    continue
                self.bands = [float(v) for v in shown]
        finally:
            proc.kill()
            proc.wait()
            self.proc = None
