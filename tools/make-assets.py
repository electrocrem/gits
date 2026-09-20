#!/usr/bin/env python3
"""Generate original placeholder artwork for the Ghost in the Shell setup (no third-party images).

Writes into ./assets only the files that are missing, so your own pictures always win:
    gits_smoke.png     desktop wallpaper (also the source of the SDDM/lock backgrounds if the others are absent)
    gits_eye.png       darker HUD picture: boot (GRUB/Plymouth), SDDM, lock screen
    gits_lock_bg.png   lock screen (copy of gits_eye.png)
    cyborg.txt lain.txt shodan.txt   terminal banner art (plain ASCII; only used when there is no art.png)

    tools/make-assets.py [--force] [--size 2880x1800]
"""
import math, os, random, subprocess, sys
from PIL import Image, ImageDraw, ImageFilter, ImageFont

OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets")
FORCE = "--force" in sys.argv
W, H = 2880, 1800
if "--size" in sys.argv:
    W, H = map(int, sys.argv[sys.argv.index("--size") + 1].lower().split("x"))
BG, BG2, CY, CYB, FG, DIM, RED = "#060A14", "#0C1A33", "#2ED3D7", "#5EF1F5", "#C8F4FF", "#596977", "#E5432B"


def rgba(hexc, a):
    h = hexc.lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16), int(a)


def font(size, bold=True):
    for pat in ("JetBrainsMono Nerd Font:bold" if bold else "JetBrainsMono Nerd Font", "monospace:bold"):
        try:
            p = subprocess.run(["fc-match", "-f", "%{file}", pat], capture_output=True, text=True).stdout
            if p:
                return ImageFont.truetype(p, size)
        except (OSError, subprocess.SubprocessError):
            pass
    return ImageFont.load_default()


def gradient():
    im = Image.new("RGB", (W, H), BG)
    px = ImageDraw.Draw(im)
    top, bot = tuple(int(BG[i:i + 2], 16) for i in (1, 3, 5)), tuple(int(BG2[i:i + 2], 16) for i in (1, 3, 5))
    for y in range(H):
        t = (y / H) ** 1.4
        px.line([(0, y), (W, y)], fill=tuple(int(a + (b - a) * t) for a, b in zip(top, bot)))
    return im.convert("RGBA")


def grid(im, step, alpha, cx=None):
    ov = Image.new("RGBA", im.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(ov)
    for x in range(0, W, step):
        d.line([(x, 0), (x, H)], fill=rgba(CY, alpha))
    for y in range(0, H, step):
        d.line([(0, y), (W, y)], fill=rgba(CY, alpha))
    return Image.alpha_composite(im, ov)


def rings(im, cx, cy, radii, alpha):
    ov = Image.new("RGBA", im.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(ov)
    for i, r in enumerate(radii):
        d.ellipse([cx - r, cy - r, cx + r, cy + r], outline=rgba(CY, alpha), width=2 if i % 3 else 3)
        for k in range(0, 360, 15 if i % 2 else 30):
            a = math.radians(k)
            r2 = r + (18 if k % 90 == 0 else 8)
            d.line([(cx + r * math.cos(a), cy + r * math.sin(a)), (cx + r2 * math.cos(a), cy + r2 * math.sin(a))], fill=rgba(CY, alpha + 25), width=2)
    return Image.alpha_composite(im, ov)


def eye(im, cx, cy, r, bright):
    ov = Image.new("RGBA", im.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(ov)
    d.ellipse([cx - r, cy - r * 0.55, cx + r, cy + r * 0.55], outline=rgba(CYB, 150 * bright), width=4)
    for k in range(7):
        rr = r * (0.42 - k * 0.05)
        d.ellipse([cx - rr, cy - rr, cx + rr, cy + rr], outline=rgba(CY, (60 + 20 * k) * bright), width=3)
    d.ellipse([cx - 16, cy - 16, cx + 16, cy + 16], fill=rgba(RED, 230 * bright))
    glow = ov.filter(ImageFilter.GaussianBlur(14))
    return Image.alpha_composite(Image.alpha_composite(im, glow), ov)


def scanlines(im, alpha):
    ov = Image.new("RGBA", im.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(ov)
    for y in range(0, H, 4):
        d.line([(0, y), (W, y)], fill=(0, 0, 0, alpha))
    return Image.alpha_composite(im, ov)


def vignette(im, strength):
    mask = Image.new("L", (W, H), 0)
    d = ImageDraw.Draw(mask)
    d.ellipse([-W * 0.25, -H * 0.35, W * 1.25, H * 1.35], fill=255)
    mask = mask.filter(ImageFilter.GaussianBlur(min(W, H) // 5))
    dark = Image.new("RGBA", (W, H), rgba("#000000", strength))
    inv = Image.eval(mask, lambda v: 255 - v)
    dark.putalpha(inv.point(lambda v: int(v * strength / 255)))
    return Image.alpha_composite(im, dark)


def brackets(im, m=90, l=160):
    ov = Image.new("RGBA", im.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(ov)
    for sx, sy in ((m, m), (W - m, m), (m, H - m), (W - m, H - m)):
        dx, dy = (l if sx < W / 2 else -l), (l if sy < H / 2 else -l)
        d.line([(sx, sy + dy), (sx, sy), (sx + dx, sy)], fill=rgba(CY, 200), width=4)
    d.text((m + 30, H - m - 60), "GHOST IN THE SHELL  //  SECTION 9  //  NAVI-00", font=font(28), fill=rgba(CYB, 190))
    return Image.alpha_composite(im, ov)


def noise(im, amount):
    random.seed(7)
    ov = Image.effect_noise((W // 2, H // 2), 40).resize((W, H)).convert("RGBA")
    ov.putalpha(amount)
    return Image.alpha_composite(im, ov)


def wallpaper():
    im = gradient()
    im = grid(im, 90, 14)
    im = rings(im, int(W * 0.68), int(H * 0.5), [180, 260, 380, 520, 700, 900], 55)
    im = eye(im, int(W * 0.68), int(H * 0.5), 240, 1.0)
    im = scanlines(im, 30)
    im = vignette(im, 170)
    im = brackets(im)
    return noise(im, 10).convert("RGB")


def lockbg():
    im = gradient()
    im = grid(im, 120, 9)
    im = rings(im, W // 2, H // 2, [220, 330, 470, 640], 40)
    im = eye(im, W // 2, H // 2, 200, 0.8)
    im = scanlines(im, 40)
    im = vignette(im, 210)
    return noise(im, 8).convert("RGB")


ASCII = r"""
              .-~~~~~~~~~~~~~~-.
          .-'                    '-.
       .-'      .-~~~~~~~~~~-.      '-.
      /       .'   .-~~~~~~-.  '.       \
     |       /    /  .----.  \    \       |
     |      |    |  ( (@@) )  |    |      |
     |       \    \  '----'  /    /       |
      \       '.   '-.____.-'   .'       /
       '-.      '-.          .-'      .-'
          '-.       '~~~~~~'       .-'
             '~-.______________.-~'
                  |  |    |  |
                  |__|    |__|
""".strip("\n")


def main():
    os.makedirs(OUT, exist_ok=True)
    made = []

    def need(name):
        return FORCE or not os.path.exists(os.path.join(OUT, name))

    if need("gits_smoke.png"):
        wallpaper().save(os.path.join(OUT, "gits_smoke.png"), optimize=True)
        made.append("gits_smoke.png")
    if need("gits_eye.png"):
        lockbg().save(os.path.join(OUT, "gits_eye.png"), optimize=True)
        made.append("gits_eye.png")
    if need("gits_lock_bg.png"):
        Image.open(os.path.join(OUT, "gits_eye.png")).save(os.path.join(OUT, "gits_lock_bg.png"), optimize=True)
        made.append("gits_lock_bg.png")
    for n in ("cyborg", "lain", "shodan"):
        if need(n + ".txt"):
            with open(os.path.join(OUT, n + ".txt"), "w") as f:
                f.write(ASCII + "\n")
            made.append(n + ".txt")
    print("generated:", ", ".join(made) if made else "nothing (assets/ already complete)")


main()
