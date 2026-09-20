#!/usr/bin/env python3
"""Build GitS-Icons: Tela-circle-grey with cyan folders.

Only the "places" icons (folders, home, desktop, ...) are recoloured; everything else is inherited, so the theme is
small (well under 2 MB) and follows updates of the base theme after a rebuild.

    ./build.py                      # ~/.local/share/icons/GitS-Icons from Tela-circle-grey
    ./build.py --base Tela-circle-blue --out /tmp/x
"""
import argparse, configparser, os, re, shutil, sys

ap = argparse.ArgumentParser()
ap.add_argument("--base", default="Tela-circle-grey")
ap.add_argument("--out", default=os.path.expanduser("~/.local/share/icons/GitS-Icons"))
ap.add_argument("--name", default="GitS-Icons")
a = ap.parse_args()

src = next((d for d in (os.path.expanduser(f"~/.local/share/icons/{a.base}"), f"/usr/share/icons/{a.base}") if os.path.isdir(d)), None)
if not src:
    sys.exit(f"base icon theme '{a.base}' not found (pacman -S tela-circle-icon-theme-all or the AUR package)")

# base grey -> GitS palette (kitty.theme): folder body, folder shadow/text tone, dark accent
MAP = {"#bdbdbd": "#2ab7bd", "#727272": "#14707a", "#333333": "#0c1a33", "#9e9e9e": "#1f8f97", "#616161": "#0f5a63"}
pat = re.compile("|".join(re.escape(k) for k in MAP), re.I)

if os.path.isdir(a.out):
    shutil.rmtree(a.out)
sec = configparser.ConfigParser(interpolation=None, strict=False)
sec.optionxform = str
sec.read(os.path.join(src, "index.theme"))

dirs, files, links = [], 0, 0
aliases = {}  # alias name -> target, over all sizes
for d in sorted(os.listdir(src)):
    pdir = os.path.join(src, d, "places")
    if not os.path.isdir(pdir) or d.startswith("symbolic"):
        continue
    out = os.path.join(a.out, d, "places")
    wrote = set()
    for f in sorted(os.listdir(pdir)):
        p = os.path.join(pdir, f)
        if os.path.islink(p) or not f.endswith(".svg"):
            continue
        text = open(p, encoding="utf-8", errors="surrogateescape").read()
        if not pat.search(text):
            continue
        os.makedirs(out, exist_ok=True)
        open(os.path.join(out, f), "w", encoding="utf-8", errors="surrogateescape").write(pat.sub(lambda m: MAP[m.group(0).lower()], text))
        wrote.add(f); files += 1
    # symlink aliases (folder.svg -> default-folder.svg, inode-directory.svg -> folder.svg) whose chain ends in a file we
    # wrote: repeat until no new link qualifies, so links to links are found too
    made = set(wrote)
    grew = True
    while grew:
        grew = False
        for f in sorted(os.listdir(pdir)):
            p = os.path.join(pdir, f)
            if f in made or not os.path.islink(p):
                continue
            target = os.readlink(p)
            if os.path.dirname(target) == "" and target in made:
                os.makedirs(out, exist_ok=True)
                os.symlink(target, os.path.join(out, f)); links += 1; made.add(f); grew = True
                aliases.setdefault(f, target)
    if wrote:
        dirs.append(f"{d}/places")

# An alias that only exists in the small fixed sizes (e.g. inode-directory -> folder) would make Qt pick that flat 16 px
# glyph even for big icons: give the scalable directories the same aliases.
for d in dirs:
    if d.startswith("scalable"):
        out = os.path.join(a.out, d)
        for name, target in aliases.items():
            if not os.path.lexists(os.path.join(out, name)) and os.path.lexists(os.path.join(out, target)):
                os.symlink(target, os.path.join(out, name)); links += 1

plain = [d for d in dirs if "@" not in d]
scaled = [d for d in dirs if "@" in d]
with open(os.path.join(a.out, "index.theme"), "w") as f:
    f.write(f"[Icon Theme]\nName={a.name}\nComment=Ghost in the Shell: {a.base} with cyan folders\nInherits={a.base},hicolor\n")
    f.write("Example=folder\n\nDirectories=" + ",".join(plain) + "\n")
    if scaled:
        f.write("ScaledDirectories=" + ",".join(scaled) + "\n")
    for d in dirs:
        section = dict(sec[d]) if d in sec else {"Size": d.split("/")[0].split("@")[0], "Type": "Fixed", "Context": "Places"}
        if "@" in d and "Scale" not in section:
            section["Scale"] = re.search(r"@(\d)x", d).group(1)
        f.write(f"\n[{d}]\n" + "".join(f"{k}={v}\n" for k, v in section.items()))
print(f"{a.name}: {files} recoloured files, {links} aliases, {len(dirs)} directories -> {a.out}")
