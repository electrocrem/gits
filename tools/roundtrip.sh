#!/usr/bin/env bash
# Install twice into a throw-away $HOME, uninstall, and require the original files back. Used by CI; runnable locally:
#   tools/roundtrip.sh
set -euo pipefail
REPO=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
FH=$(mktemp -d)
trap 'rm -rf "$FH"' EXIT
mkdir -p "$FH/.config/hypr" "$FH/.config/zsh" "$FH/.config/nvim/lua/config" "$FH/.config/rofi/themes" "$FH/.logseq/plugins/nord-theme" "$FH/.vscode-oss/extensions"
printf -- '-- user config\nhl.config({})\n' >"$FH/.config/hypr/hyprland.lua"
printf '# my zsh\n' >"$FH/.config/zsh/user.zsh"
printf -- '-- my options\n' >"$FH/.config/nvim/lua/config/options.lua"
echo "USER STYLE" >"$FH/.config/rofi/themes/style_1.rasi"
printf '[Colors:Button]\nDecorationFocus=61,174,233\n' >"$FH/.config/kdeglobals"
echo '{"name":"nord-theme","logseq":{"themes":[{"name":"Nord"}]}}' >"$FH/.logseq/plugins/nord-theme/package.json"
echo "/* nord */" >"$FH/.logseq/plugins/nord-theme/custom.css"
echo '[]' >"$FH/.vscode-oss/extensions/extensions.json"

snap() { (cd "$FH" && find . -type f -not -path './.local/share/gits-hyde/*' -print0 | sort -z | xargs -0 md5sum); }
snap >"$FH.before"

export HOME=$FH GITS_SKIP_PREFLIGHT=1
"$REPO/install.sh" >/dev/null
echo "-- edited" >>"$FH/.config/hypr/gits-workspaces.lua"; sleep 1      # a second run must back up our own older copy
"$REPO/install.sh" >/dev/null
[[ -f $FH/.config/hypr/gits.lua && -x $FH/.local/bin/gits-doctor ]] || { echo "installer did not place its files"; exit 1; }
[[ $(grep -c '>>> gits-hyde' "$FH/.config/hypr/hyprland.lua") == 1 ]] || { echo "hyprland.lua block duplicated or missing"; exit 1; }
! grep -rIl '@HOME@' "$FH" >/dev/null || { echo "unsubstituted @HOME@ token left"; exit 1; }
"$REPO/uninstall.sh" >/dev/null

snap >"$FH.after"
if diff "$FH.before" "$FH.after"; then echo "round trip OK: original state restored"; rm -f "$FH.before" "$FH.after"
else rm -f "$FH.before" "$FH.after"; exit 1; fi
