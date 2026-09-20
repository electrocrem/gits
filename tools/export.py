#!/usr/bin/env python3
"""Maintainer tool: refresh ./home (and zen/, logseq/) from the live $HOME.

* copies an explicit manifest only (nothing is picked up by accident)
* copies *.bak* / caches never; images only from the ASSETS list below (into ./assets, installed by install.sh)
* rewrites the absolute home directory to the token @HOME@ (install.sh turns it back into the installer's $HOME)

    tools/export.py            refresh the repo from $HOME
    tools/export.py --check    only report files that would change
"""
import fnmatch, os, shutil, sys, glob

HOME = os.path.expanduser("~")
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CHECK = "--check" in sys.argv

# (source relative to $HOME, [glob filters]).  A directory is copied recursively; filters, if given, are matched
# against the file name (relative to the directory) and select which files to take.
MANIFEST = [
    (".config/hyde/themes/Ghost in the Shell", ["hypr.theme", "kitty.theme", "rofi.theme", "theme.dcol", "waybar.theme", "kvantum/*"]),
    (".config/waybar/layouts/ghost-in-the-shell.jsonc", None),
    (".config/waybar/styles/ghost-in-the-shell.css", None),
    (".config/waybar/scripts", ["gits-*.sh"]),
    (".config/hypr/hyprlock/Ghost in the Shell.conf", None),
    (".config/hypr/scripts", ["gits-*.sh"]),
    (".config/hypr/gits.lua", None),
    (".config/hypr/gits-workspaces.lua", None),
    (".config/hypr/lua/animations/gits.lua", None),
    (".config/gits-widgets", ["widgets.py", "style.css", "run.sh", "panel.py", "panel.css", "osd.py"]),
    (".config/rofi/themes/style_1.rasi", None),
    (".config/wlogout/layout_1", None),
    (".config/wlogout/style_1.css", None),
    (".config/dunst/dunst.conf", None),
    (".config/dunst/gits-notify-menu.sh", None),
    (".config/dunst/dunstrc.d/50-gits-menu.conf", None),
    (".config/dunst/dunstrc.d/60-gits-kdeconnect.conf", None),
    (".config/dunst/gits-phone-notify.sh", None),
    (".config/rofi/themes/notification.rasi", None),
    (".config/rofi/themes/gits-menu.rasi", None),
    (".config/dunst/gits-sound.sh", None),
    (".config/dunst/dunstrc.d/55-gits-sound.conf", None),
    (".config/dunst/dunstrc.d/70-gits-battery.conf", None),
    (".config/dunst/gits-osd.sh", None),
    (".config/dunst/dunstrc.d/80-gits-osd.conf", None),
    (".config/rofi/themes/clipboard.rasi", None),
    (".config/satty/config.toml", None),
    (".config/zsh/gits", ["banner.zsh", "colors.zsh", "tmux.zsh", "fastfetch.jsonc", "fastfetch-image.jsonc"]),
    (".config/starship/starship.toml", None),
    (".config/nvim/colors/gits.lua", None),
    (".config/nvim/lua/gits", ["init.lua", "palette.lua"]),
    (".config/nvim/lua/lualine/themes/gits.lua", None),
    (".config/nvim/lua/plugins/gits.lua", None),
    (".config/btop/themes/gits.theme", None),
    (".config/bat/config", None),
    (".config/bat/themes/GitS.tmTheme", None),
    (".config/lazygit/config.yml", None),
    (".config/tmux/tmux.conf", None),
    (".config/fastfetch/config.jsonc", None),
    (".config/yazi/theme.toml", None),
    (".local/share/gits-cursor/build.py", None),
    (".local/share/gits-icons/build.py", None),
    (".local/share/gits-telegram/build.py", None),
    (".local/share/gits-sddm/ghost-in-the-shell", ["Main.qml", "metadata.desktop", "theme.conf"]),
    (".local/share/gits-boot", ["build.py", "install.sh", "fix-grub-savedefault.sh", "plymouth.script.in"]),
    (".local/bin/gits-doctor", None),
    (".local/bin/gits-sound", None),
    (".local/bin/gits-menu", None),
    (".local/bin/gits-wifi", None),
    (".local/bin/gits-bt", None),
    (".local/bin/gits-panel", None),
    (".local/bin/gits-media", None),
    (".local/bin/gits-osd", None),
    (".local/bin/gits-layout-toggle", None),
    (".local/bin/gits-sessions", None),
    (".local/bin/gits-rog", None),
    (".local/bin/gits-settings", None),
    (".local/bin/gits-idle", None),
    (".local/bin/gits-touchpad", None),
    (".local/share/gits-sounds/build.py", None),
    (".local/share/gits-snap/setup.sh", None),
    (".vscode-oss/extensions/gits.ghost-in-the-shell-1.0.0", None),
]
# artwork that install.sh puts in place: (source relative to $HOME, file name inside ./assets)
ASSETS = [
    (".config/hyde/themes/Ghost in the Shell/wallpapers/gits_smoke.png", "gits_smoke.png"),      # desktop wallpaper
    (".config/hyde/themes/Ghost in the Shell/wallpapers/gits_eye.png", "gits_eye.png"),          # lock screen, SDDM, GRUB, Plymouth
    (".config/hyde/themes/Ghost in the Shell/wallpapers/gits_cyborg.jpg", "gits_cyborg.jpg"),
    (".config/hyde/themes/Ghost in the Shell/wallpapers/gits_teal_wires.jpg", "gits_teal_wires.jpg"),
    (".config/zsh/gits/art.png", "art.png"),                                                     # terminal banner (kitty graphics)
    (".config/zsh/gits/cyborg.txt", "cyborg.txt"), (".config/zsh/gits/lain.txt", "lain.txt"),
    (".config/zsh/gits/shodan.txt", "shodan.txt"),
]
ZEN_FILES = ["chrome/userChrome.css", "chrome/userContent.css", "user.js"]

SKIP_NAMES = ("*.bak*", "*.pyc", "__pycache__", "*.png", "*.jpg", "*.jpeg", "*.webp", "*.gif", ".DS_Store")
# personal strings that must not leave the machine: rewritten on export
SCRUB = [("Author=electrocrem", "Author=gits-hyde")]

changed = []


def skip(name):
    return any(fnmatch.fnmatch(name, p) for p in SKIP_NAMES)


def transform(data, path):
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        return data
    text = text.replace(HOME, "@HOME@")
    for a, b in SCRUB:
        text = text.replace(a, b)
    if path.endswith("/.config/hypr/gits.lua"):  # install.sh --login-guards fills this in: keep the repo copy a template
        tpl = open(os.path.join(REPO, "tools", "blind-guard.lua.in")).read().rstrip("\n")
        text = text.replace(tpl, "-- @BLIND_GUARD@")
    return text.encode("utf-8")


def put(src, dst):
    if skip(os.path.basename(src)) or os.path.islink(src):
        return
    with open(src, "rb") as f:
        data = transform(f.read(), src)
    old = open(dst, "rb").read() if os.path.exists(dst) else None
    if old != data:
        changed.append(os.path.relpath(dst, REPO))
        if not CHECK:
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            with open(dst, "wb") as f:
                f.write(data)
            shutil.copymode(src, dst)


def walk(root, filters):
    for dp, dns, fns in os.walk(root):
        dns[:] = [d for d in dns if not skip(d)]
        for fn in fns:
            full = os.path.join(dp, fn)
            rel = os.path.relpath(full, root)
            if filters and not any(fnmatch.fnmatch(rel, g) for g in filters):
                continue
            yield full, rel


for rel, filters in MANIFEST:
    src = os.path.join(HOME, rel)
    if not os.path.exists(src):
        print("missing:", rel, file=sys.stderr)
        continue
    if os.path.isdir(src):
        for full, r in walk(src, filters):
            put(full, os.path.join(REPO, "home", rel, r))
    else:
        put(src, os.path.join(REPO, "home", rel))

# artwork (binary: copied as is)
for rel, name in ASSETS:
    src, dst = os.path.join(HOME, rel), os.path.join(REPO, "assets", name)
    if os.path.exists(src) and (not os.path.exists(dst) or open(src, "rb").read() != open(dst, "rb").read()):
        changed.append("assets/" + name)
        if not CHECK:
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            shutil.copyfile(src, dst)

# Zen: the profile with our chrome/ dir
for prof in glob.glob(os.path.join(HOME, ".var/app/app.zen_browser.zen/.zen/*/")):
    if os.path.isfile(os.path.join(prof, "chrome/userChrome.css")):
        for f in ZEN_FILES:
            if os.path.exists(os.path.join(prof, f)):
                put(os.path.join(prof, f), os.path.join(REPO, "zen", os.path.basename(f)))
        break

# Logseq: the theme stylesheet (installed into the theme plugin, see install.sh)
lg = os.path.join(HOME, ".logseq/plugins/nord-theme/custom.css")
if os.path.exists(lg):
    put(lg, os.path.join(REPO, "logseq/gits.css"))

print(("would change" if CHECK else "updated"), len(changed), "files")
for c in changed:
    print("  ", c)
