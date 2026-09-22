#!/usr/bin/env python3
"""Stage the Ghost in the Shell boot themes (GRUB + Plymouth) in ./staging. Nothing is installed here:
run `sudo ./install.sh` for that.  Art = the theme's own gits_eye.png, darkened, scanlines, HUD frame.

The art is rendered for one screen size, so the HUD frame is not cropped away on other aspect ratios:
  ./build.py 2560x1440        that size
  GITS_BOOT_SIZE=3840x2160    same, through the environment
  ./build.py                  the largest connected monitor (/sys/class/drm), else 1920x1080
Other screens still work: Plymouth and GRUB scale the art to cover them."""
import glob
import math
import os
import re
import shutil
import subprocess
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
STAGE = os.path.join(HERE, "staging")
EYE = os.path.expanduser("~/.local/share/gits/wallpapers/gits_eye.png")
FONTS = os.path.expanduser("~/.local/share/fonts/JetBrainsMono")
F_REG = os.path.join(FONTS, "JetBrainsMonoNerdFontMono-Regular.ttf")
F_BOLD = os.path.join(FONTS, "JetBrainsMonoNerdFontMono-Bold.ttf")
NAME = "ghost-in-the-shell"

CY, CYH, NAVY, NAVY2, RED, DIM = (0x2E, 0xD3, 0xD7), (0x5E, 0xF1, 0xF5), (0x06, 0x0A, 0x14), (0x0C, 0x1A, 0x33), (0xE5, 0x43, 0x2B), (0x8E, 0xA2, 0xAE)
SS = 2  # supersampling for the vector-ish overlays


def screen_size():
    """WxH from argv / GITS_BOOT_SIZE, else the preferred mode of the largest connected monitor."""
    want = (sys.argv[1:] or [os.environ.get("GITS_BOOT_SIZE", "")])[0]
    m = re.fullmatch(r"(\d+)x(\d+)", want.strip())
    if m:
        return int(m[1]), int(m[2])
    best = None
    for c in glob.glob("/sys/class/drm/card*-*"):
        try:
            if open(os.path.join(c, "status")).read().strip() != "connected":
                continue
            m = re.match(r"(\d+)x(\d+)", open(os.path.join(c, "modes")).readline())
        except OSError:
            continue
        if m and (best is None or int(m[1]) * int(m[2]) > best[0] * best[1]):
            best = int(m[1]), int(m[2])
    return best or (1920, 1080)


W, H = screen_size()
U = H / 1200  # the HUD was drawn for 1200 px of height


def font(path, size):
    return ImageFont.truetype(path, size)


def iris_centre(img):
    a = np.asarray(img.convert("RGB")).astype(int)
    sub = a[380:560, 900:1150]
    mask = (sub[..., 0] > 170) & (sub[..., 1] < 110) & (sub[..., 2] < 90)
    ys, xs = np.nonzero(mask)
    k, dx, dy = cover(img)[1]
    return round((xs.mean() + 900) * k - dx), round((ys.mean() + 380) * k - dy), k


def text_spaced(d, xy, s, fnt, fill, spacing=0):
    x, y = xy
    for ch in s:
        d.text((x, y), ch, font=fnt, fill=fill)
        x += d.textlength(ch, font=fnt) + spacing
    return x


def cover(img):
    """Scale + centre-crop the image to fill WxH. Returns it with (k, dx, dy): x_out = x_in * k - dx."""
    k = max(W / img.width, H / img.height)
    sw, sh = round(img.width * k), round(img.height * k)
    dx, dy = (sw - W) // 2, (sh - H) // 2
    return img.resize((sw, sh), Image.LANCZOS).crop((dx, dy, dx + W, dy + H)), (k, dx, dy)


def darkened():
    """The eye, pushed into the navy-black: vignette, bottom fade for the menu / bar, scanlines."""
    img = np.asarray(cover(Image.open(EYE).convert("RGB"))[0]).astype(np.float32)
    navy = np.array(NAVY, dtype=np.float32)
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    r = np.hypot((xx - W / 2) / (W * 0.62), (yy - H * 0.42) / (H * 0.75))
    vig = np.clip(1.15 - r * 0.9, 0.0, 1.0)[..., None]
    img = img * 0.72 * vig + navy * (1 - vig)
    fade = np.clip((yy / H - 0.58) / 0.22, 0, 1)[..., None] * 0.93
    img = img * (1 - fade) + navy * fade
    top = np.clip((0.10 - yy / H) / 0.10, 0, 1)[..., None] * 0.6
    img = img * (1 - top) + navy * top
    img[::3] *= 0.86  # scanlines
    return Image.fromarray(np.clip(img, 0, 255).astype(np.uint8)).convert("RGBA")


def overlay(draw_fn):
    layer = Image.new("RGBA", (W * SS, H * SS), (0, 0, 0, 0))
    draw_fn(ImageDraw.Draw(layer), SS)
    return layer.resize((W, H), Image.LANCZOS)


def hud(d, s, iris, title):
    """Corner brackets, header strip, scan lines through the iris, targeting ticks."""
    u = s * U  # one HUD pixel at this screen size
    m, L = 34 * u, 58 * u
    c = CY + (230,)
    for (x, y, sx, sy) in ((m, m, 1, 1), (W * s - m, m, -1, 1), (m, H * s - m, 1, -1), (W * s - m, H * s - m, -1, -1)):
        d.line([(x, y + sy * L), (x, y), (x + sx * L, y)], fill=c, width=max(1, round(2 * u)))
    f = font(F_REG, round(15 * u))
    text_spaced(d, (m + 22 * u, m + 10 * u), "SECTION 9  //  BOOT LOADER", f, DIM + (230,), 2 * u)
    right = "GHOST LINK: STANDBY"
    tw = sum(d.textlength(ch, font=f) + 2 * u for ch in right)
    text_spaced(d, (W * s - m - 22 * u - tw, m + 10 * u), right, f, DIM + (230,), 2 * u)
    d.line([(m + 22 * u, m + 36 * u), (W * s - m - 22 * u, m + 36 * u)], fill=CY + (60,), width=max(1, round(u)))
    d.rectangle([m + 2 * u, m + 12 * u, m + 12 * u, m + 22 * u], fill=RED + (255,))
    ix, iy, k = iris[0] * s, iris[1] * s, iris[2] * s  # the ticks sit on the ring, which follows the eye's scale
    d.line([(0, iy), (W * s, iy)], fill=CY + (26,), width=s)
    d.line([(ix, 0), (ix, H * s)], fill=CY + (26,), width=s)
    for a in (0, 90, 180, 270):
        ca, sa = math.cos(math.radians(a)), math.sin(math.radians(a))
        d.line([(ix + ca * 250 * k, iy + sa * 250 * k), (ix + ca * 272 * k, iy + sa * 272 * k)], fill=CYH + (220,), width=max(1, round(2 * u)))


def make_ring(size=480):
    s = 4
    layer = Image.new("RGBA", (size * s, size * s), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    c = size * s / 2
    def arc(r, a0, a1, w, col):
        d.arc([c - r * s, c - r * s, c + r * s, c + r * s], a0, a1, fill=col, width=int(w * s))
    for i in range(8):
        arc(228, i * 45 + 4, i * 45 + 34, 4, CY + (235,))
    for i in range(72):
        a = math.radians(i * 5)
        r0, r1 = (198, 214) if i % 9 == 0 else (206, 214)
        d.line([(c + math.cos(a) * r0 * s, c + math.sin(a) * r0 * s), (c + math.cos(a) * r1 * s, c + math.sin(a) * r1 * s)],
               fill=CYH + ((200,) if i % 9 == 0 else (110,)), width=int((2 if i % 9 == 0 else 1) * s))
    # red marker: the "eye" tick
    d.polygon([(c, (c - 196 * s)), (c - 9 * s, c - 219 * s), (c + 9 * s, c - 219 * s)], fill=RED + (255,))
    return layer.resize((size, size), Image.LANCZOS)


def text_png(s, path_, size, color=CY, bold=False, spacing=3, pad=4):
    f = font(F_BOLD if bold else F_REG, size)
    tmp = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
    w = int(sum(tmp.textlength(ch, font=f) + spacing for ch in s)) + pad * 2
    img = Image.new("RGBA", (w, int(size * 1.5)), (0, 0, 0, 0))
    text_spaced(ImageDraw.Draw(img), (pad, size * 0.15), s, f, color + (255,), spacing)
    img.save(path_)


def plymouth(art, iris):
    out = os.path.join(STAGE, "plymouth", NAME)
    os.makedirs(out, exist_ok=True)
    bg = Image.alpha_composite(art, overlay(lambda d, s: hud(d, s, iris, "")))
    bg.convert("RGB").save(os.path.join(out, "bg.png"), optimize=True)
    ring = round(480 * iris[2])
    make_ring().resize((ring, ring), Image.LANCZOS).save(os.path.join(out, "ring.png"))
    text_png("GHOST  IN  THE  SHELL", os.path.join(out, "title.png"), 40, CYH, True, 10)
    stages = ["INITIALIZING GHOST LINK", "MOUNTING FILESYSTEMS", "LINKING NEURAL BUS", "SYNCHRONIZING SECTION 9", "ACCESS GRANTED"]
    for i, t in enumerate(stages):
        text_png(t, os.path.join(out, f"status{i}.png"), 22, DIM, False, 5)
    Image.new("RGBA", (600, 10), CY + (255,)).save(os.path.join(out, "bar_fill.png"))
    fr = Image.new("RGBA", (600, 10), NAVY + (200,))
    ImageDraw.Draw(fr).rectangle([0, 0, 599, 9], outline=CY + (255,), width=1)
    fr.save(os.path.join(out, "bar_frame.png"))
    Image.new("RGBA", (6, 10), RED + (255,)).save(os.path.join(out, "bar_head.png"))
    # passphrase dialog (only shown if the disk ever gets encrypted)
    box = Image.new("RGBA", (620, 110), NAVY + (235,))
    ImageDraw.Draw(box).rectangle([0, 0, 619, 109], outline=CY + (255,), width=2)
    box.save(os.path.join(out, "box.png"))
    text_png("PASSPHRASE //", os.path.join(out, "lock.png"), 22, CYH, True, 3)
    ent = Image.new("RGBA", (300, 30), NAVY2 + (255,))
    ImageDraw.Draw(ent).rectangle([0, 0, 299, 29], outline=CY + (140,), width=1)
    ent.save(os.path.join(out, "entry.png"))
    Image.new("RGBA", (14, 14), CYH + (255,)).save(os.path.join(out, "bullet.png"))
    script = open(os.path.join(HERE, "plymouth.script.in")).read()
    for key, val in (("IRIS_X", iris[0]), ("IRIS_Y", iris[1]), ("ART_W", W), ("ART_H", H), ("RING", ring)):
        script = script.replace(f"@{key}@", str(val))
    open(os.path.join(out, f"{NAME}.script"), "w").write(script)
    open(os.path.join(out, f"{NAME}.plymouth"), "w").write(f"""[Plymouth Theme]
Name=Ghost in the Shell
Description=CRT eye, rotating targeting ring, cyan progress bar. Matches the desktop, lock screen and SDDM.
ModuleName=script

[script]
ImageDir=/usr/share/plymouth/themes/{NAME}
ScriptFile=/usr/share/plymouth/themes/{NAME}/{NAME}.script
ConsoleLogBackgroundColor=0x060a14
""")


def grub(art, iris):
    out = os.path.join(STAGE, "grub", NAME)
    os.makedirs(out, exist_ok=True)
    bg = Image.alpha_composite(art, overlay(lambda d, s: hud(d, s, iris, "")))
    bg.convert("RGB").save(os.path.join(out, "background.png"), optimize=True)
    g = H / 1080  # the menu was laid out for 1080 px of height
    small, big = max(12, round(16 * g)), max(14, round(18 * g))
    for size in sorted({small, big}):
        subprocess.run(["grub-mkfont", "-s", str(size), "-o", os.path.join(out, f"jbm{size}.pf2"), F_REG], check=True, stderr=subprocess.DEVNULL)
    half, item_h, pad, gap = round(260 * g), round(34 * g), round(8 * g), round(6 * g)
    Image.new("RGBA", (8, 40), CY + (255,)).save(os.path.join(out, "select_c.png"))
    w = Image.new("RGBA", (8, 40), CY + (255,))
    ImageDraw.Draw(w).rectangle([0, 0, 3, 39], fill=RED + (255,))
    w.save(os.path.join(out, "select_w.png"))
    Image.new("RGBA", (8, 40), CY + (255,)).save(os.path.join(out, "select_e.png"))
    open(os.path.join(out, "theme.txt"), "w").write(f"""# Ghost in the Shell: cyan on navy-black, red tick on the selected entry. Rendered for {W}x{H}, scales to others.
title-text: ""
desktop-image: "background.png"
desktop-image-scale-method: "crop"
desktop-color: "#060A14"
terminal-font: "JetBrainsMono NFM Regular {small}"
terminal-left: "0"
terminal-top: "0"
terminal-width: "100%"
terminal-height: "100%"
terminal-border: "0"

+ boot_menu {{
  left = 50%-{half}
  top = 64%
  width = {2 * half}
  height = 24%
  item_font = "JetBrainsMono NFM Regular {big}"
  item_color = "#9FC5D6"
  selected_item_color = "#060A14"
  icon_width = 0
  icon_height = 0
  item_icon_space = 12
  item_height = {item_h}
  item_padding = {pad}
  item_spacing = {gap}
  scrollbar = true
  scrollbar_width = 6
  scrollbar_thumb = "select_c.png"
  selected_item_pixmap_style = "select_*.png"
}}

+ label {{
  top = 89%
  left = 50%-{half}
  width = {2 * half}
  align = "center"
  id = "__timeout__"
  text = "AUTO-BOOT IN %d"
  font = "JetBrainsMono NFM Regular {small}"
  color = "#5EF1F5"
}}

+ progress_bar {{
  id = "__timeout__"
  left = 50%-{half}
  top = 93%
  width = {2 * half}
  height = 6
  show_text = false
  bg_color = "#0C1A33"
  fg_color = "#2ED3D7"
  border_color = "#2ED3D7"
  text_color = "#060A14"
}}

+ label {{
  top = 96%
  left = 50%-{half}
  width = {2 * half}
  align = "center"
  text = "ENTER  boot     E  edit     C  console"
  font = "JetBrainsMono NFM Regular {small}"
  color = "#596977"
}}
""")


if __name__ == "__main__":
    shutil.rmtree(STAGE, ignore_errors=True)
    art = darkened()
    iris = iris_centre(Image.open(EYE))
    print("iris centre", iris)
    plymouth(art, iris)
    grub(art, iris)
    open(os.path.join(STAGE, "size"), "w").write(f"{W}x{H}\n")   # install.sh sets GRUB_GFXMODE from it
    print("staged ->", STAGE, f"({W}x{H})")
