#!/usr/bin/env python3
"""Idempotent edits that a plain file copy cannot do.  Used by install.sh.

    post.py kded                  stop kded6 from recreating the GTK settings that hang GTK4 apps
    post.py kdeglobals            recolour KDE/Qt accents (Breeze blue -> cyan) and greys -> navy
    post.py logseq  <gits.css>    make Logseq load the GitS stylesheet (theme plugin route)
    post.py vscode  <ext-dir>     register the theme extension for Code - OSS
    post.py zen     <zen-dir>     install userChrome/userContent/user.js into the default Zen profile
Every file that gets modified is copied once to <file>.bak-pre-gits first.
"""
import configparser, json, os, re, shutil, sys, time

HOME = os.path.expanduser("~")


def backup(path):
    if os.path.exists(path) and not os.path.exists(path + ".bak-pre-gits"):
        shutil.copy2(path, path + ".bak-pre-gits")


def kdeglobals():
    p = os.path.join(HOME, ".config/kdeglobals")
    if not os.path.exists(p):
        print("kdeglobals: not present, skipped")
        return
    backup(p)
    out, sec, n = [], "", 0
    for ln in open(p).read().split("\n"):
        m = re.match(r"\[(.+)\]$", ln)
        if m:
            sec = m.group(1)
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


cmd = sys.argv[1] if len(sys.argv) > 1 else ""
{"kded": kded, "kdeglobals": kdeglobals, "logseq": lambda: logseq(sys.argv[2]), "vscode": lambda: vscode(sys.argv[2]),
 "zen": lambda: zen(sys.argv[2])}.get(cmd, lambda: sys.exit(__doc__))()
