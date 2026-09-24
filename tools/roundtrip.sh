#!/usr/bin/env bash
# Install twice into a throw-away $HOME, uninstall, and require the original files back. Used by CI; runnable locally:
#   tools/roundtrip.sh
set -euo pipefail
REPO=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
FH=$(mktemp -d)
FH2=
trap 'rm -rf "$FH" "$FH2"' EXIT
mkdir -p "$FH/.config/hypr" "$FH/.config/zsh" "$FH/.config/nvim/lua/config" "$FH/.logseq/plugins/nord-theme" "$FH/.vscode-oss/extensions"
printf -- '-- user config\nhl.config({})\n' >"$FH/.config/hypr/hyprland.lua"
printf '# my zsh\n' >"$FH/.config/zsh/user.zsh"
printf -- '-- my options\n' >"$FH/.config/nvim/lua/config/options.lua"
mkdir -p "$FH/.config/gtk-4.0"; echo "USER GTK" >"$FH/.config/gtk-4.0/gtk.css"
printf '[Colors:Button]\nDecorationFocus=61,174,233\n' >"$FH/.config/kdeglobals"
echo '{"name":"nord-theme","logseq":{"themes":[{"name":"Nord"}]}}' >"$FH/.logseq/plugins/nord-theme/package.json"
echo "/* nord */" >"$FH/.logseq/plugins/nord-theme/custom.css"
echo '[]' >"$FH/.vscode-oss/extensions/extensions.json"

snap() { (cd "${1:-$FH}" && find . -type f -not -path './.local/share/gits-install/*' -print0 | sort -z | xargs -0 md5sum); }
snap >"$FH.before"

export HOME=$FH GITS_SKIP_PREFLIGHT=1
unset ZDOTDIR XDG_CONFIG_HOME XDG_DATA_HOME XDG_STATE_HOME XDG_CACHE_HOME   # the caller's own dirs must not leak into the test
"$REPO/install.sh" >/dev/null
echo "-- edited" >>"$FH/.config/hypr/gits/options.lua"; sleep 1      # a second run must back up our own older copy
"$REPO/install.sh" >/dev/null
[[ -f $FH/.config/hypr/gits/binds.lua && -x $FH/.local/bin/gits-doctor && -f $FH/.config/systemd/user/gits-bar.service ]] || { echo "installer did not place its files"; exit 1; }
grep -q 'gits' "$FH/.config/hypr/hyprland.lua" && ! grep -q 'user config' "$FH/.config/hypr/hyprland.lua" || { echo "hyprland.lua was not replaced"; exit 1; }
if command -v zsh >/dev/null; then   # a plain zsh setup does not read user.zsh: the installer must hook it from .zshrc, once
    [[ $(grep -c '>>> gits:zsh-wire >>>' "$FH/.zshrc" 2>/dev/null) == 1 ]] || { echo "zsh hook missing or duplicated in .zshrc"; exit 1; }
    ztrace=$(mktemp); GITS_NO_BANNER=1 GITS_NO_TMUX=1 zsh -ixc exit </dev/null >/dev/null 2>"$ztrace" || true
    grep -q 'gits/colors.zsh' "$ztrace" || { echo "zsh does not run the gits block after install"; rm -f "$ztrace"; exit 1; }
    rm -f "$ztrace"
fi
[[ -f $FH/.config/gits-widgets/lain.gif ]] || { echo "the dancing Lain (lain.gif) was not installed: assets/lain-dance.gif is missing from the repo"; exit 1; }
if python3 -c 'import PIL, numpy' 2>/dev/null; then [[ -s $FH/.local/share/gits-lock/lain-0.txt && -s $FH/.local/share/gits-lock/tachikoma-0.txt ]] || { echo "the lock screen frames were not built"; exit 1; }; fi
[[ -L $FH/.local/share/gits/art/current && -r $FH/.local/share/gits/art/current/banner.conf ]] || { echo "no art set linked at ~/.local/share/gits/art/current"; exit 1; }
if python3 -c 'import PIL, numpy' 2>/dev/null; then [[ -s $FH/.local/share/gits/art/gits/dancer-0.png ]] || { echo "the radio dancer (Tachikoma) was not built"; exit 1; }; fi
[[ ! -e $FH/.config/hypr/scripts/gits-blind-guard.sh ]] || { echo "the blind-login guard must be opt-in"; exit 1; }
! grep -rIl '@HOME@' "$FH" >/dev/null || { echo "unsubstituted @HOME@ token left"; exit 1; }

# colour themes: every file holding GitS colours is listed; a theme recolours them, survives a reinstall, and GitS comes back byte for byte
python3 "$REPO/home/.local/bin/gits-theme" check "$REPO/home" || { echo "home/.config/gits/themes/files is incomplete"; exit 1; }
tsnap() { snap | grep -vE ' \./\.local/share/gits/theme-base/| \./\.local/state/gits/state$| \./\.config/gits/themes/probe\.theme$'; }
tsnap >"$FH.gits"
python3 - "$FH/.config/gits/themes" <<'PY'   # a made-up theme: every GitS colour with its hue turned half way round
import colorsys, re, sys
out = ["name = Probe", "swap = SECTION 9 -> PROBE 9"]
for ln in open(sys.argv[1] + "/gits.theme"):
    m = re.match(r"\s*([a-z_]+)\s*=\s*#([0-9A-Fa-f]{6})", ln)
    if m:
        h, l, s = colorsys.rgb_to_hls(*(int(m.group(2)[i:i + 2], 16) / 255 for i in (0, 2, 4)))
        out.append(m.group(1) + " = #%02X%02X%02X" % tuple(round(v * 255) for v in colorsys.hls_to_rgb((h + 0.5) % 1, l, s)))
open(sys.argv[1] + "/probe.theme", "w").write("\n".join(out) + "\n")
PY
T=$FH/.local/bin/gits-theme
"$T" set probe --no-reload >/dev/null
recoloured() { [[ $("$T" current) == probe ]] && ! grep -qi '2ed3d7' "$FH/.config/kitty/theme.conf" "$FH/.config/hypr/gits/options.lua" "$FH/.local/share/color-schemes/GitS.colors" && ! grep -q '46, 211, 215' "$FH/.config/hypr/hyprlock.conf" && grep -q 'PROBE 9' "$FH/.config/hypr/hyprlock.conf" && ! grep -q '=46,211,215' "$FH/.config/kdeglobals"; }
recoloured || { echo "the probe theme did not recolour the configs"; exit 1; }
"$REPO/install.sh" >/dev/null
recoloured || { echo "a reinstall lost the colour theme"; exit 1; }
echo "# my own line" >>"$FH/.config/kitty/theme.conf"   # a hand edit under another theme: GitS comes back anyway, the edit is kept beside it
"$T" set gits --no-reload >/dev/null 2>&1
grep -q "my own line" "$FH/.config/kitty/theme.conf.gits-theme-edited" || { echo "the hand-edited file was not kept as .gits-theme-edited"; exit 1; }
rm -f "$FH/.config/kitty/theme.conf.gits-theme-edited"
tsnap >"$FH.gits2"
diff "$FH.gits" "$FH.gits2" >/dev/null || { diff "$FH.gits" "$FH.gits2" | head; echo "switching back to GitS did not restore the files byte for byte"; exit 1; }
# your own options on top of a theme: GitS with a magenta accent and no mascot, then forgotten again: byte for byte once more
"$T" option gits accent '#FF2E97' && "$T" option gits mascot off && "$T" set gits --no-reload >/dev/null
grep -qi 'ff2e97' "$FH/.config/kitty/theme.conf" && grep -q 'GITS_LOCK_MASCOT=off' "$FH/.config/hypr/hyprlock.conf" || { echo "the accent / mascot options did not reach the files"; exit 1; }
"$T" info | python3 -c 'import json,sys; d=json.load(sys.stdin); g=[t for t in d["themes"] if t["id"]=="gits"][0]; assert g["user"]["accent"]=="#FF2E97" and g["mascot"]=="off"' || { echo "gits-theme info does not show the options"; exit 1; }
"$T" option gits --reset && "$T" set gits --no-reload >/dev/null
tsnap >"$FH.gits2"
diff "$FH.gits" "$FH.gits2" >/dev/null || { diff "$FH.gits" "$FH.gits2" | head; echo "forgetting the options did not restore the files byte for byte"; exit 1; }
rm -f "$FH.gits" "$FH.gits2" "$FH/.config/gits/themes/probe.theme"
echo "colour themes OK: recoloured and text swapped, kept over a reinstall, GitS restored byte for byte"
"$REPO/uninstall.sh" >/dev/null

snap >"$FH.after"
if diff "$FH.before" "$FH.after"; then echo "round trip OK: original state restored"; rm -f "$FH.before" "$FH.after"
else rm -f "$FH.before" "$FH.after"; exit 1; fi

# a zsh setup that already reads user.zsh must not get a second hook, and must come back untouched
if command -v zsh >/dev/null; then
    FH2=$(mktemp -d)
    mkdir -p "$FH2/.config/zsh"
    printf '# my zsh\n' >"$FH2/.config/zsh/user.zsh"
    printf 'source ~/.config/zsh/user.zsh\n' >"$FH2/.zshrc"
    snap "$FH2" >"$FH2.before"
    HOME=$FH2 "$REPO/install.sh" >/dev/null
    ! grep -q 'gits:zsh-wire' "$FH2/.zshrc" || { echo "installer hooked zsh although .zshrc already reads user.zsh"; exit 1; }
    HOME=$FH2 "$REPO/uninstall.sh" >/dev/null
    snap "$FH2" >"$FH2.after"
    if diff "$FH2.before" "$FH2.after"; then echo "zsh already wired: no second hook, original state restored"; rm -f "$FH2.before" "$FH2.after"
    else rm -f "$FH2.before" "$FH2.after"; exit 1; fi
fi
