#!/usr/bin/env python3
"""Idempotent edits that a plain file copy cannot do.  Used by install.sh.

    post.py kded                  stop kded6 from recreating the GTK settings that hang GTK4 apps
    post.py kdeglobals            recolour KDE/Qt accents (Breeze blue -> cyan) and greys -> navy, pin the GitS icon theme
    post.py logseq  <gits.css>    make Logseq load the GitS stylesheet (theme plugin route)
    post.py vscode  <ext-dir>     register the theme extension for Code - OSS
    post.py zen     <zen-dir>     install userChrome/userContent/user.js into the default Zen profile
    post.py spotify               point Spicetify at Spotify and apply the GitS theme (~/.config/spicetify/Themes/GitS)
    post.py vesktop               enable ~/.config/vesktop/themes/gits.css in Vesktop (Discord)
    post.py steam                 cyan Steam tray icon (its own steam_tray_mono.png, which the tray looks up before the theme)
    post.py kde-apps              pick the GitS colour scheme inside the installed KF6 apps (Dolphin, Ark, Okular...)
    post.py flatpak               GitS icons for Flatpak apps (user override: ICON_THEME + read access to ~/.local/share/icons)
Every file that gets modified is copied once to <file>.bak-pre-gits first.
"""
import configparser, json, os, re, shutil, subprocess, sys, time

HOME = os.path.expanduser("~")


def backup(path):
    if os.path.exists(path) and not os.path.exists(path + ".bak-pre-gits"):
        shutil.copy2(path, path + ".bak-pre-gits")


def create(path):
    """A file gits makes from nothing: the marker tells uninstall.sh to delete it instead of restoring a backup."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    open(path, "w").close()
    open(path + ".gits-created", "w").close()


def kdeglobals():
    """Apply color-schemes/GitS.colors to ~/.config/kdeglobals the way Plasma does (its Colors:* / ColorEffects:* / WM sections
    replace the old ones), and pin the icon theme and widget style: KF6 apps (Dolphin, Ark...) take all of these from kdeglobals,
    not from qt6ct, and fall back to Breeze (blue folders, light window) or to whatever scheme a previous setup left there."""
    p = os.path.join(HOME, ".config/kdeglobals")
    scheme = next((f for f in (os.path.join(HOME, ".local/share/color-schemes/GitS.colors"),
                               os.path.join(os.path.dirname(os.path.abspath(__file__)), "../home/.local/share/color-schemes/GitS.colors"))
                   if os.path.exists(f)), None)
    if not os.path.exists(p):
        create(p)
    backup(p)

    def sections(text):
        """[(name, [lines])] in order; name None for lines before the first header"""
        out, name, body = [], None, []
        for ln in text.split("\n"):
            m = re.match(r"^\[(.+)\]$", ln)
            if m:
                out.append((name, body))
                name, body = m.group(1), []
            else:
                body.append(ln)
        out.append((name, body))
        return out

    ours = lambda n: n and (n.startswith("Colors:") or n.startswith("ColorEffects:") or n == "WM")
    old = open(p).read()
    secs = [(n, b) for n, b in sections(old) if not ours(n)] if scheme else sections(old)
    if scheme:
        secs += [(n, b) for n, b in sections(open(scheme).read()) if ours(n)]
    # single keys: [General] ColorScheme, [Icons] Theme, [KDE] widgetStyle
    want = {"General": {"ColorScheme": "GitS"} if scheme else {}, "Icons": {"Theme": "GitS-Icons"}, "KDE": {"widgetStyle": "kvantum"}}
    for sec, kv in want.items():
        i = next((i for i, (n, _) in enumerate(secs) if n == sec), None)
        if i is None:
            secs.append((sec, []))
            i = len(secs) - 1
        # an accent colour (Plasma's "accent from wallpaper / custom") would override the scheme's cyan selection
        drop = set(kv) | ({"AccentColor", "LastUsedCustomAccentColor", "ColorSchemeHash"} if sec == "General" and scheme else set())
        body = [l for l in secs[i][1] if l.split("=", 1)[0] not in drop]
        while body and body[-1] == "":
            body.pop()
        secs[i] = (sec, [f"{k}={v}" for k, v in kv.items()] + body + [""])
    text = "\n".join(("" if n is None else f"[{n}]\n") + "\n".join(b).strip("\n") + ("\n" if b and any(b) else "")
                      for n, b in secs if n is not None or any(b)).strip("\n") + "\n"
    text = re.sub(r"\n(\[)", r"\n\n\1", re.sub(r"\n{2,}", "\n", text)).lstrip("\n")
    if text == old:
        print("kdeglobals: already GitS")
        return
    open(p, "w").write(text)
    print("kdeglobals: GitS colours, icons and widget style" + ("" if scheme else " (GitS.colors not found: colours left as they were)"))


STEAM_PUBLIC = [".local/share/Steam/public", ".var/app/com.valvesoftware.Steam/.local/share/Steam/public"]


def steam():
    # Steam's tray item names steam_tray_mono and points IconThemePath at its own public/ dir, so the tray finds the white PNG
    # there before any icon theme (and waybar <= 0.15 drops its per-app icon override on every icon update). Replace that PNG
    # with the cyan GitS-Icons glyph; a Steam client update puts the white one back: run this again (install.sh does).
    svg = os.path.join(HOME, ".local/share/icons/GitS-Icons/22/panel/steam_tray_mono.svg")
    dirs = [os.path.join(HOME, d) for d in STEAM_PUBLIC if os.path.isfile(os.path.join(HOME, d, "steam_tray_mono.png"))]
    if not dirs:
        print("steam: no Steam install, skipped")
        return
    if not os.path.exists(svg) or not shutil.which("rsvg-convert"):
        print("steam: needs the GitS-Icons theme and rsvg-convert (librsvg), skipped")
        return
    for d in dirs:
        png = os.path.join(d, "steam_tray_mono.png")
        backup(png)
        r = subprocess.run(["rsvg-convert", "-w", "48", "-h", "48", "-o", png, svg], capture_output=True, text=True)
        if r.returncode != 0:
            shutil.copy2(png + ".bak-pre-gits", png)
            print("steam: rsvg-convert failed: " + r.stderr.strip())
            return
    print("steam: cyan tray icon (restart Steam)")


# KF6 apps keep their colour scheme in their own rc ([UiSettings] ColorScheme). Unset, KColorSchemeManager outside Plasma picks
# Breeze Light/Dark from Qt's colour-scheme hint, which qt6ct does not give: Breeze Light text (#232629) on the Kvantum navy
# background, unreadable. Only apps that are installed get the key. uninstall.sh walks the same list.
KDE_APPS = {"dolphin": "dolphinrc", "ark": "arkrc", "okular": "okularrc", "gwenview": "gwenviewrc", "kate": "katerc",
            "kwrite": "kwriterc", "konsole": "konsolerc", "filelight": "filelightrc", "spectacle": "spectaclerc",
            "partitionmanager": "partitionmanagerrc", "kcalc": "kcalcrc", "elisa": "elisarc", "haruna": "harunarc",
            "kdeconnect-app": "kdeconnect-apprc"}


def kde_apps():
    done = []
    for binary, rc in KDE_APPS.items():
        if not shutil.which(binary):
            continue
        p = os.path.join(HOME, ".config", rc)
        text = open(p).read() if os.path.exists(p) else None
        if text is not None and re.search(r"(?m)^\[UiSettings\]\n(?:[^\[].*\n)*?ColorScheme=GitS$", text):
            continue
        if text is None:
            create(p)
            text = ""
        else:
            backup(p)
        if "[UiSettings]" in text:
            text = re.sub(r"(?m)^ColorScheme=.*\n?", "", text)   # only UiSettings uses this key in these rc files
            text = text.replace("[UiSettings]\n", "[UiSettings]\nColorScheme=GitS\n", 1)
        else:
            text = text.rstrip("\n") + ("\n\n" if text.strip() else "") + "[UiSettings]\nColorScheme=GitS\n"
        open(p, "w").write(text)
        done.append(binary)
    print("kde-apps: GitS colour scheme in " + (", ".join(done) if done else "nothing new"))


def kded():
    """GTK4 apps hang while loading the theme if gtk-4.0/settings.ini says prefer-dark-theme=true (GTK 4.22). The file lives in
    the theme dir (~/.config/gtk-4.0 is a symlink into it) and KDE's kded6 'gtkconfig' module keeps recreating it."""
    rc = os.path.join(HOME, ".config/kded6rc")
    have = open(rc).read() if os.path.exists(rc) else ""
    if "[Module-gtkconfig]" not in have and ">>> gits:kded >>>" not in have:
        state = os.path.join(HOME, ".local/share/gits-install")
        os.makedirs(state, exist_ok=True)
        with open(os.path.join(state, "installed.list"), "a") as lst:  # so uninstall.sh can undo it
            lst.write(f"new:{rc}\n" if not have else "")
            lst.write(f"block:kded:#:{rc}\n")
        if have:
            backup(rc)
        with open(rc, "a") as f:
            f.write(("\n" if have and not have.endswith("\n") else "") +
                    "# >>> gits:kded >>>\n[Module-gtkconfig]\nautoload=false\n# <<< gits:kded <<<\n")
        print("kded: gtkconfig module set to autoload=false (takes effect at the next kded6 start)")
    ini = os.path.join(HOME, ".config/gtk-4.0/settings.ini")
    if os.path.isfile(ini) and re.search(r"gtk-application-prefer-dark-theme\s*=\s*true", open(ini).read()):
        os.makedirs(os.path.join(HOME, ".local/state/gits"), exist_ok=True)
        shutil.move(ini, os.path.join(HOME, ".local/state/gits/gtk4-settings.ini.removed"))
        print("kded: removed the gtk-4.0/settings.ini that hangs GTK4 apps")


def logseq(css):
    base = os.path.join(HOME, ".logseq")
    plug = os.path.join(base, "plugins", "nord-theme")
    if not os.path.isdir(plug):
        print("logseq: the 'Nord theme' plugin is not installed; copy logseq/gits.css to <graph>/logseq/custom.css instead (see README)")
        return
    bak = os.path.join(base, "plugins-backup", "nord-theme")
    os.makedirs(bak, exist_ok=True)
    for f in ("custom.css", "package.json"):
        if os.path.exists(os.path.join(plug, f)) and not os.path.exists(os.path.join(bak, f)):
            shutil.copy2(os.path.join(plug, f), os.path.join(bak, f))
    shutil.copyfile(css, os.path.join(plug, "custom.css"))
    pj = os.path.join(plug, "package.json")
    d = json.load(open(pj))
    d["title"] = "Ghost in the Shell"
    d["description"] = "Ghost in the Shell: navy + cyan phosphor"
    d["logseq"]["themes"][0].update(name="Ghost in the Shell", description="Navy + cyan phosphor, square corners")
    json.dump(d, open(pj, "w"))
    print("logseq: GitS stylesheet installed over the Nord plugin (originals in ~/.logseq/plugins-backup)")


def vscode(extdir):
    root = os.path.join(HOME, ".vscode-oss/extensions")
    reg = os.path.join(root, "extensions.json")
    name = os.path.basename(extdir.rstrip("/"))
    if not os.path.isdir(root):
        print("vscode: ~/.vscode-oss not present, skipped")
        return
    if not os.path.exists(reg):
        print("vscode: no extensions.json yet (start Code - OSS once), skipped")
        return
    data = json.load(open(reg))
    if any(e.get("identifier", {}).get("id") == "gits.ghost-in-the-shell" for e in data):
        print("vscode: already registered")
        return
    backup(reg)
    path = os.path.join(root, name)
    data.append({
        "identifier": {"id": "gits.ghost-in-the-shell"}, "version": "1.0.0",
        "location": {"$mid": 1, "fsPath": path, "external": "file://" + path, "path": path, "scheme": "file"},
        "relativeLocation": name,
        "metadata": {"installedTimestamp": int(time.time() * 1000), "pinned": False, "source": "resource"},
    })
    json.dump(data, open(reg, "w"))
    print("vscode: theme extension registered (restart Code, pick 'Ghost in the Shell')")


def zen(src):
    root = os.path.join(HOME, ".var/app/app.zen_browser.zen/.zen")
    ini = os.path.join(root, "profiles.ini")
    if not os.path.exists(ini):
        print("zen: Zen (flatpak) profile not found, skipped")
        return
    cp = configparser.ConfigParser(interpolation=None)
    cp.read(ini)
    rel = next((cp[s]["Default"] for s in cp.sections() if s.startswith("Install") and "Default" in cp[s]), None)
    if not rel:
        rel = next((cp[s]["Path"] for s in cp.sections() if s.startswith("Profile") and cp[s].get("Default") == "1"), None)
    prof = os.path.join(root, rel) if rel else None
    if not prof or not os.path.isdir(prof):
        print("zen: default profile not found, skipped")
        return
    os.makedirs(os.path.join(prof, "chrome"), exist_ok=True)
    for f in ("userChrome.css", "userContent.css"):
        dst = os.path.join(prof, "chrome", f)
        backup(dst)
        shutil.copyfile(os.path.join(src, f), dst)
    uj = os.path.join(prof, "user.js")
    have = open(uj).read() if os.path.exists(uj) else ""
    backup(uj)
    add = [l for l in open(os.path.join(src, "user.js")).read().splitlines() if l.strip() and l not in have]
    if add:
        with open(uj, "a") as f:
            f.write(("\n" if have and not have.endswith("\n") else "") + "\n".join(add) + "\n")
    print(f"zen: styles installed into {rel} (takes effect on the next browser start)")


def spotify():
    if not shutil.which("spicetify"):
        print("spotify: spicetify not installed (AUR spicetify-cli), skipped")
        return
    # spotify-launcher keeps Spotify in the home dir, so Spicetify can patch it without sudo; the Flatpak one is read-only
    app = next((d for d in (os.path.join(HOME, ".local/share/spotify-launcher/install/usr/share/spotify"), "/opt/spotify")
                if os.path.isdir(os.path.join(d, "Apps"))), None)
    prefs = os.path.join(HOME, ".config/spotify/prefs")
    if not app:
        print("spotify: no spotify-launcher / /opt/spotify install found, skipped")
        return
    if not os.path.exists(prefs):
        print("spotify: start Spotify once (it writes ~/.config/spotify/prefs), skipped")
        return
    if not os.access(app, os.W_OK):
        print(f"spotify: {app} is not writable, skipped")
        return
    sp = lambda *a: subprocess.run(["spicetify", "-q", *a], stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)
    r = sp("config", "spotify_path", app, "prefs_path", prefs, "current_theme", "GitS", "color_scheme", "gits",
           "inject_css", "1", "replace_colors", "1")
    if r.returncode == 0:
        r = sp("backup", "apply")
        if r.returncode != 0:   # already backed up (e.g. after a Spotify update): re-apply over the fresh files
            r = sp("restore", "backup", "apply")
    if r.returncode == 0:
        print("spotify: GitS applied (after a Spotify update run: spicetify backup apply)")
    else:
        print("spotify: spicetify failed: " + (r.stderr.strip().splitlines() or ["?"])[-1])


def vesktop():
    root = os.path.join(HOME, ".config/vesktop")
    if not os.path.isdir(os.path.join(root, "themes")):
        print("vesktop: no ~/.config/vesktop/themes, skipped")
        return
    p = os.path.join(root, "settings/settings.json")
    if not os.path.exists(p):
        create(p)
    data = json.load(open(p)) if os.path.getsize(p) else {}
    themes = data.setdefault("enabledThemes", [])
    if "gits.css" in themes:
        print("vesktop: already enabled")
        return
    if not os.path.exists(p + ".gits-created"):
        backup(p)
    themes.append("gits.css")
    json.dump(data, open(p, "w"), indent=4)
    print("vesktop: gits.css enabled (restart Vesktop)")


def flatpak():
    if not shutil.which("flatpak"):
        print("flatpak: not installed, skipped")
        return
    # GTK apps inside take the theme name from the settings portal, but an old global ICON_THEME override (a previous rice) wins
    # for the apps that read it; the theme itself and its base (Tela-circle-grey, /usr/share/icons) are visible via /run/host
    cur = subprocess.run(["flatpak", "override", "--user", "--show"], capture_output=True, text=True).stdout
    if "ICON_THEME=GitS-Icons" in cur and "xdg-data/icons:ro" in cur:
        print("flatpak: already set")
        return
    g = os.path.join(os.environ.get("XDG_DATA_HOME", os.path.join(HOME, ".local/share")), "flatpak/overrides/global")
    if os.path.exists(g):
        backup(g)
    else:
        os.makedirs(os.path.dirname(g), exist_ok=True)
        open(g + ".gits-created", "w").close()
    r = subprocess.run(["flatpak", "override", "--user", "--env=ICON_THEME=GitS-Icons", "--filesystem=xdg-data/icons:ro"],
                       capture_output=True, text=True)
    print("flatpak: GitS icons for Flatpak apps (restart them)" if r.returncode == 0 else "flatpak: override failed: " + r.stderr.strip())


cmd = sys.argv[1] if len(sys.argv) > 1 else ""
{"kded": kded, "kdeglobals": kdeglobals, "logseq": lambda: logseq(sys.argv[2]), "vscode": lambda: vscode(sys.argv[2]),
 "zen": lambda: zen(sys.argv[2]), "spotify": spotify, "vesktop": vesktop, "flatpak": flatpak, "kde-apps": kde_apps, "steam": steam}.get(cmd, lambda: sys.exit(__doc__))()
