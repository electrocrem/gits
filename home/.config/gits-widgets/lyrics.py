"""Synced song lyrics for the player card and the media popup: the line being sung right now.

Lyrics come from lrclib.net (free, no key; only the artist, title, album and length of the track are sent) and are cached in
~/.cache/gits-widgets/lyrics, a miss too (for a day), so a track is looked up once. Fetching runs in a thread: `line()` never
waits and returns "" until the lyrics are there. Only time-synced lyrics are used. GITS_LYRICS=0 turns it off.
"""
import hashlib
import json
import os
import re
import threading
import time
import urllib.error
import urllib.parse
import urllib.request

CACHE = os.path.join(os.environ.get("XDG_CACHE_HOME", os.path.expanduser("~/.cache")), "gits-widgets", "lyrics")
API = "https://lrclib.net/api"
UA = "gits-desktop (https://github.com/electrocrem/gits)"
LRC = re.compile(r"\[(\d+):(\d+(?:\.\d+)?)\]")
ENABLED = os.environ.get("GITS_LYRICS", "1") != "0"


def parse(lrc):
    """'[01:02.50] words' lines -> [(62.5, 'words')], sorted; several stamps on one line each get the words."""
    out = []
    for raw in (lrc or "").splitlines():
        stamps = LRC.findall(raw)
        text = LRC.sub("", raw).strip()
        for m, s in stamps:
            out.append((int(m) * 60 + float(s), text))
    return sorted(out)


def _get(path, params):
    req = urllib.request.Request(f"{API}/{path}?{urllib.parse.urlencode(params)}", headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=8) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return None
        raise


def fetch(artist, title, album, length):
    """[(seconds, line)] for a track ([] when there are no synced lyrics), from the cache or lrclib."""
    key = hashlib.sha1(f"{artist}\0{title}\0{album}\0{round(length or 0)}".encode()).hexdigest()
    path = os.path.join(CACHE, key + ".json")
    try:
        with open(path) as f:
            c = json.load(f)
        if c.get("lines") or time.time() - c.get("t", 0) < 86400:
            return [tuple(x) for x in c.get("lines", [])]
    except (OSError, ValueError):
        pass
    lines = []
    hit = _get("get", {"artist_name": artist, "track_name": title, "album_name": album, "duration": round(length)}) \
        if album and length else None
    if not (hit and hit.get("syncedLyrics")):
        found = _get("search", {"artist_name": artist, "track_name": title}) or []
        near = [x for x in found if x.get("syncedLyrics") and (not length or abs((x.get("duration") or 0) - length) < 4)]
        hit = near[0] if near else next((x for x in found if x.get("syncedLyrics")), None)
    if hit and hit.get("syncedLyrics"):
        lines = parse(hit["syncedLyrics"])
    os.makedirs(CACHE, exist_ok=True)
    with open(path, "w") as f:
        json.dump({"t": time.time(), "lines": lines}, f)
    return lines


class Lyrics:
    """One per view. line(artist, title, album, length_s, pos_s) -> the current line ("" while unknown / instrumental)."""

    def __init__(self):
        self.key, self.lines = None, None

    def line(self, artist, title, album, length, pos):
        if not ENABLED or not title:
            return ""
        if not artist and " - " in title:   # a radio stream: "Artist - Title" in one field
            artist, title = title.split(" - ", 1)
        key = (artist, title)
        if key != self.key:
            self.key, self.lines = key, None
            threading.Thread(target=self._load, args=(key, artist, title, album, length), daemon=True).start()
        if not self.lines:
            return ""
        cur = ""
        for t, text in self.lines:   # a few dozen lines: a plain scan is enough
            if t > pos + 0.25:
                break
            cur = text
        return cur

    def _load(self, key, artist, title, album, length):
        try:
            lines = fetch(artist, title, album, length)
        except Exception:   # offline, lrclib down: no lyrics, never an error in the card
            lines = []
        if self.key == key:
            self.lines = lines
