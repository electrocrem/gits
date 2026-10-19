#!/usr/bin/env python3
"""Synthesises the Ghost in the Shell UI sounds into ./*.wav (pack "terminal": short, bit-crushed blips) and the same melodies
in two more voices, ./soft/*.wav (round sine tones) and ./glass/*.wav (small bells). Pure numpy + wave. `gits-sound pack` picks.

    python3 build.py    # notify login lock unlock plug unplug error focus done shot send touch game battery, for every pack
"""
import os
import wave

import numpy as np

RATE = 44100
HERE = os.path.dirname(os.path.abspath(__file__))


PACKS = {   # waveform per pack (the melodies stay the same), bit-crush, release length
    "terminal": {"map": {}, "crush": 9, "rel": 1.0, "dir": ""},
    "soft": {"map": {"square": "sine", "tri": "sine"}, "crush": None, "rel": 1.5, "dir": "soft"},
    "glass": {"map": {"square": "bell", "tri": "bell", "sine": "bell"}, "crush": None, "rel": 1.8, "dir": "glass"},
}
PACK = PACKS["terminal"]


def tone(freq, dur, kind="square", amp=1.0, glide=None):
    kind = PACK["map"].get(kind, kind)
    dur *= PACK["rel"] if kind != "square" else 1.0
    t = np.arange(int(RATE * dur)) / RATE
    f = np.linspace(freq, glide, len(t)) if glide else np.full(len(t), float(freq))
    ph = 2 * np.pi * np.cumsum(f) / RATE
    if kind == "square":  # band-limited-ish square: first odd harmonics only, so it stays soft
        y = sum(np.sin((2 * k + 1) * ph) / (2 * k + 1) for k in range(4))
    elif kind == "tri":
        y = np.arcsin(np.sin(ph)) * 2 / np.pi
    elif kind == "bell":   # struck-metal partials that die out faster the higher they are
        y = np.sin(ph) + 0.45 * np.sin(2.76 * ph) * np.exp(-t * 18) + 0.25 * np.sin(5.4 * ph) * np.exp(-t * 30)
    else:
        y = np.sin(ph)
    a, r = min(0.004, dur / 4), dur * 0.55  # click-free attack, exponential-ish release
    env = np.minimum(t / a, 1.0) * np.exp(-t / r * 3.2)
    return y * env * amp


def noise(dur, amp=1.0, smooth=3):
    """A shutter-like burst: white noise, a little low-passed, with a fast decay (seeded, so every build is the same)."""
    n = int(RATE * dur)
    y = np.random.default_rng(9).uniform(-1, 1, n)
    y = np.convolve(y, np.ones(smooth) / smooth, mode="same")
    return y * np.exp(-np.arange(n) / RATE / dur * 5) * amp * (0.5 if PACK["crush"] is None else 1.0)


def silence(d):
    return np.zeros(int(RATE * d))


def echo(y, delay=0.09, gain=0.28, n=2):
    out = np.concatenate((y, np.zeros(int(RATE * delay * n))))
    for i in range(1, n + 1):
        k = int(RATE * delay * i)
        out[k:k + len(y)] += y * gain ** i
    return out


def crush(y, bits=9):  # a little bit-crush = the "old terminal" grit
    q = 2 ** (bits - 1)
    return np.round(y * q) / q


def save(name, y, peak=0.55):
    if PACK["crush"]:
        y = crush(y, PACK["crush"])
    y = y / max(np.abs(y).max(), 1e-9) * peak
    n = int(RATE * 0.01)
    y[-n:] *= np.linspace(1, 0, n)
    out = os.path.join(HERE, PACK["dir"])
    os.makedirs(out, exist_ok=True)
    with wave.open(os.path.join(out, name + ".wav"), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(RATE)
        w.writeframes((y * 32767).astype("<i2").tobytes())


def build():
    save("notify", echo(np.concatenate((tone(1568, 0.05, "square"), tone(2093, 0.09, "square", 0.8))), 0.08, 0.25))
    save("plug", np.concatenate((tone(880, 0.05, "tri"), tone(1320, 0.05, "tri"), tone(1760, 0.11, "tri", 0.9))))
    save("unplug", np.concatenate((tone(1320, 0.05, "tri"), tone(880, 0.05, "tri"), tone(587, 0.12, "tri", 0.9))))
    save("lock", echo(np.concatenate((tone(988, 0.05, "square", 0.8), tone(659, 0.05, "square", 0.8),
                                      tone(330, 0.16, "tri", 1.0, glide=247))), 0.1, 0.22))
    save("unlock", echo(np.concatenate((tone(330, 0.05, "tri"), tone(659, 0.05, "square", 0.8),
                                        tone(988, 0.05, "square", 0.9), tone(1319, 0.14, "square", 0.8))), 0.1, 0.22))
    save("error", np.concatenate((tone(220, 0.09, "square"), silence(0.03), tone(196, 0.16, "square", 1.0, glide=150))))
    # login: a rising sweep, then a "system online" chord (root, fifth, octave) with a tail
    sweep = tone(180, 0.32, "tri", 0.6, glide=900)
    chord = sum(tone(f, 0.55, "sine", a) for f, a in ((440, 1.0), (659, 0.7), (880, 0.6)))
    save("login", echo(np.concatenate((sweep, silence(0.04), chord)), 0.14, 0.3, 3), peak=0.5)
    # focus timer: "start" is three rising notes, "done" a soft two-note chime
    save("focus", np.concatenate((tone(660, 0.06, "tri"), tone(880, 0.06, "tri"), tone(1320, 0.14, "tri", 0.9))))
    save("done", echo(np.concatenate((tone(1046, 0.10, "sine"), tone(784, 0.22, "sine", 0.9))), 0.12, 0.3, 3))
    # shot: two shutter clicks; send: a quick rising swoosh; touch: "attention, touch the key" (two pings and a higher one)
    save("shot", np.concatenate((noise(0.035, 1.0, 2), silence(0.045), noise(0.06, 0.8, 4))), peak=0.45)
    save("send", np.concatenate((tone(520, 0.13, "tri", 0.8, glide=1560), tone(2093, 0.08, "sine", 0.6))))
    save("touch", np.concatenate((tone(1760, 0.06, "sine"), silence(0.06), tone(1760, 0.06, "sine"), silence(0.06),
                                  tone(2349, 0.16, "sine"))))
    # game: a power-up arpeggio; battery: a falling two-note warning (the critical one is "error")
    save("game", np.concatenate([tone(f, 0.05, "square", 0.8) for f in (523, 659, 784)] + [tone(1046, 0.16, "square", 0.9)]))
    save("battery", echo(np.concatenate((tone(784, 0.11, "tri"), tone(523, 0.24, "tri", 0.9, glide=494))), 0.1, 0.25))


for PACK in PACKS.values():
    build()
print("wrote", ", ".join(sorted(f[:-4] for f in os.listdir(HERE) if f.endswith(".wav"))), "for", ", ".join(PACKS))
