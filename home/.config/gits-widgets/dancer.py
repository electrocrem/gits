"""Lain dancing, as a sprite for the radio popup (animation from pryanostnik/lain-dance, MIT; the GIF is lain.gif next to this file).

    frames = load(height, style)     # list of cairo.ImageSurface, all the same size; [] if Pillow / numpy / the GIF are missing
    style: "holo" (cyan hologram with scan lines, the default) or "color" (the colours of the drawing)

The surfaces are drawn at 2x the logical size (paint them with cr.scale(0.5, 0.5)): smooth on a scaled screen.
"""
import os

HERE = os.path.dirname(os.path.abspath(__file__))
GIF = os.path.join(HERE, "lain.gif")


def hexrgb(h):
    import numpy as np
    return np.array([int(h[i:i + 2], 16) for i in (1, 3, 5)], dtype=float)


def _pil_frames(height, style):
    import numpy as np
    from PIL import Image, ImageDraw, ImageSequence
    src = Image.open(GIF)
    rgbs, masks = [], []
    for fr in ImageSequence.Iterator(src):
        base = Image.new("RGBA", fr.size, (255, 255, 255, 255))
        base.alpha_composite(fr.convert("RGBA"))
        rgb = base.convert("RGB")
        flood = rgb.copy()   # the background is the white that touches the border; white inside the figure stays
        for corner in ((0, 0), (flood.width - 1, 0), (0, flood.height - 1), (flood.width - 1, flood.height - 1)):
            if min(flood.getpixel(corner)) > 200 and flood.getpixel(corner) != (255, 0, 255):
                ImageDraw.floodfill(flood, corner, (255, 0, 255), thresh=18)
        masks.append(~(np.asarray(flood) == (255, 0, 255)).all(axis=2))
        rgbs.append(np.asarray(rgb).astype(float))
    ys, xs = np.where(np.any(masks, axis=0))
    y0, y1, x0, x1 = ys.min(), ys.max() + 1, xs.min(), xs.max() + 1
    out = []
    for rgb, fg in zip(rgbs, masks):
        rgb, fg = rgb[y0:y1, x0:x1], fg[y0:y1, x0:x1]
        lum = (rgb @ np.array([0.299, 0.587, 0.114])) / 255
        if style == "color":
            col = 70 + rgb * (185 / 255)
        else:   # hologram: light = bright cyan, ink = deep teal
            t = np.clip(lum, 0, 1)[..., None] ** 0.8
            col = hexrgb("#083C54") * (1 - t) + hexrgb("#96FAFF") * t   # hex, so a colour theme (gits-theme) recolours them
        alpha = fg * 255.0
        if style != "color":   # scan lines
            alpha = alpha * np.where(np.arange(fg.shape[0]) % 3 == 0, 0.62, 1.0)[:, None]
        rgba = np.dstack([col, alpha]).astype("uint8")
        im = Image.fromarray(rgba, "RGBA")
        k = height * 2 / im.height
        im = im.convert("RGBa").resize((max(1, round(im.width * k)), height * 2), Image.LANCZOS).convert("RGBA")
        out.append(im)
    return out


def _cached(height, style):
    """The processed frames as a strip PNG in the cache: preparing them takes over a second, reading them a few milliseconds."""
    from PIL import Image
    cache = os.path.join(os.environ.get("XDG_CACHE_HOME", os.path.expanduser("~/.cache")), "gits-widgets")
    path = os.path.join(cache, f"lain-{style}-{height}.png")
    stamp = max(os.path.getmtime(GIF), os.path.getmtime(os.path.abspath(__file__)))
    if os.path.exists(path) and os.path.getmtime(path) > stamp:
        strip = Image.open(path).convert("RGBA")
        n = 8   # the frames of lain.gif
        w = strip.width // n
        return [strip.crop((i * w, 0, (i + 1) * w, strip.height)) for i in range(n)]
    frames = _pil_frames(height, style)
    try:
        os.makedirs(cache, exist_ok=True)
        strip = Image.new("RGBA", (frames[0].width * len(frames), frames[0].height), (0, 0, 0, 0))
        for i, f in enumerate(frames):
            strip.paste(f, (i * f.width, 0))
        strip.save(path + ".tmp", format="PNG")
        os.replace(path + ".tmp", path)
    except OSError:
        pass
    return frames


def load(height, style="holo"):
    try:
        import cairo
        import numpy as np
        frames = []
        for im in _cached(height, style):
            a = np.asarray(im).astype("float")
            a[..., :3] *= a[..., 3:4] / 255.0                      # cairo wants premultiplied alpha
            bgra = np.dstack([a[..., 2], a[..., 1], a[..., 0], a[..., 3]]).astype("uint8")
            frames.append(cairo.ImageSurface.create_for_data(bytearray(bgra.tobytes()), cairo.FORMAT_ARGB32, im.width, im.height, im.width * 4))
        return frames
    except Exception:   # noqa: BLE001 - the popup works without her
        return []
