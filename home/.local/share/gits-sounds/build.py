#!/usr/bin/env python3
"""Synthesises the Ghost in the Shell UI sounds (short, soft terminal blips) into ./*.wav. Pure numpy + wave.

    python3 build.py            # writes notify, login, lock, unlock, plug, unplug, error next to this file
"""
import os
import wave

import numpy as np

RATE = 44100
HERE = os.path.dirname(os.path.abspath(__file__))


def tone(freq, dur, kind="square", amp=1.0, glide=None):
    t = np.arange(int(RATE * dur)) / RATE
    f = np.linspace(freq, glide, len(t)) if glide else np.full(len(t), float(freq))
    ph = 2 * np.pi * np.cumsum(f) / RATE
    if kind == "square":  # band-limited-ish square: first odd harmonics only, so it stays soft
        y = sum(np.sin((2 * k + 1) * ph) / (2 * k + 1) for k in range(4))
    elif kind == "tri":
        y = np.arcsin(np.sin(ph)) * 2 / np.pi
    else:
        y = np.sin(ph)
    a, r = min(0.004, dur / 4), dur * 0.55  # click-free attack, exponential-ish release
    env = np.minimum(t / a, 1.0) * np.exp(-t / r * 3.2)
    return y * env * amp


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
    y = crush(y)
    y = y / max(np.abs(y).max(), 1e-9) * peak
    n = int(RATE * 0.01)
    y[-n:] *= np.linspace(1, 0, n)
    with wave.open(os.path.join(HERE, name + ".wav"), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(RATE)
        w.writeframes((y * 32767).astype("<i2").tobytes())


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
print("wrote", ", ".join(sorted(f for f in os.listdir(HERE) if f.endswith(".wav"))))
