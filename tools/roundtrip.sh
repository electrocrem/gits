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
unset ZDOTDIR   # the caller's own zsh dir must not leak into the test
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
[[ ! -e $FH/.config/hypr/scripts/gits-blind-guard.sh ]] || { echo "the blind-login guard must be opt-in"; exit 1; }
! grep -rIl '@HOME@' "$FH" >/dev/null || { echo "unsubstituted @HOME@ token left"; exit 1; }
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
