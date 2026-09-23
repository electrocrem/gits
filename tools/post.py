#!/usr/bin/env python3
"""Idempotent edits that a plain file copy cannot do.  Used by install.sh.

    post.py kded                  stop kded6 from recreating the GTK settings that hang GTK4 apps
    post.py kdeglobals            recolour KDE/Qt accents (Breeze blue -> cyan) and greys -> navy, pin the GitS icon theme
    post.py logseq  <gits.css>    make Logseq load the GitS stylesheet (theme plugin route)
    post.py vscode  <ext-dir>     register the theme extension for Code - OSS
    post.py zen     <zen-dir>     install userChrome/userContent/user.js into the default Zen profile
    post.py spotify               point Spicetify at Spotify and apply the GitS theme (~/.config/spicetify/Themes/GitS)
    post.py vesktop               enable ~/.config/vesktop/themes/gits.css in Vesktop (Discord)
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
    p = os.path.join(HOME, ".config/kdeglobals")
    if not os.path.exists(p):
        create(p)
    backup(p)
    out, sec, n = [], "", 0
    lines = open(p).read().split("\n")
    # KF6 apps (Dolphin, Ark...) take the icon theme and the widget style from kdeglobals ([Icons] Theme, [KDE] widgetStyle), not from
    # qt6ct, and fall back to Breeze: blue folders and a light Breeze window instead of GitS-Icons + Kvantum
    want = {"Icons": ("Theme", "GitS-Icons"), "KDE": ("widgetStyle", "kvantum")}
    for s_, (k, v) in want.items():
        if "[" + s_ + "]" not in lines:
            lines += ["", "[" + s_ + "]", k + "=" + v]
            n += 1
        else:
            i = lines.index("[" + s_ + "]")
            j = next((x for x in range(i + 1, len(lines)) if lines[x].startswith("[")), len(lines))
            if not any(l.startswith(k + "=") for l in lines[i + 1:j]):
                lines.insert(i + 1, k + "=" + v)
                n += 1
    for ln in lines:
        m = re.match(r"\[(.+)\]$", ln)
        if m:
            sec = m.group(1)
        if sec in want and ln.startswith(want[sec][0] + "=") and ln != "=".join(want[sec]):
            ln, n = "=".join(want[sec]), n + 1
        if sec.startswith("Colors:"):
            k, _, v = ln.partition("=")
            new = ln
            if v == "61,174,233":
                new = k + "=" + ("94,241,245" if k == "ForegroundActive" else "46,211,215")
            elif k == "ForegroundLink" and v == "29,153,243":
                new = k + "=94,241,245"
            elif k in ("BackgroundAlternate", "BackgroundNormal") and v in ("32,35,38", "41,44,48"):
                new = k + "=" + ("6,10,20" if v == "32,35,38" else "10,18,38")
            elif k == "ForegroundNormal" and v in ("252,252,252", "255,255,255") and sec != "Colors:Selection":
                new = k + "=200,244,255"
            if sec == "Colors:Selection":
                if k == "BackgroundNormal":
                    new = k + "=46,211,215"
                elif k == "BackgroundAlternate":
                    new = k + "=94,241,245"
                elif k.startswith("Foreground"):
                    new = k + "=6,10,20"
            n += new != ln
            ln = new
        out.append(ln)
    open(p, "w").write("\n".join(out))
    print(f"kdeglobals: {n} colour lines changed")


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
 "zen": lambda: zen(sys.argv[2]), "spotify": spotify, "vesktop": vesktop, "flatpak": flatpak}.get(cmd, lambda: sys.exit(__doc__))()
