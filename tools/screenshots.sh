#!/usr/bin/env bash
# Maintainer tool: regenerate the README screenshots in docs/img on a live session, without personal data.
#   tools/screenshots.sh [workspace]     (default: the first empty workspace from 4 up)
#   ONLY="player mixer" tools/screenshots.sh   retake just those pictures (names: desktop control-panel player mixer notifications settings-menu osd terminal nvim-dashboard)
# It switches to an empty workspace for about a minute, pauses notifications, runs the widgets and the popups in their demo modes
# (made-up SSID/IP/to-do/tracks/apps), opens a throw-away kitty for the terminal and Neovim pictures, takes the shots with grim and
# puts everything back (workspace, widgets, notifications). Needs: grim, python-pillow, hyprctl, jq, kitty, the gits-* tools.
# Don't touch the mouse or keyboard while it runs.
set -u
want() { [[ -z ${ONLY:-} || " $ONLY " == *" $1 "* ]]; }
REPO=$(cd "$(dirname "$0")/.." && pwd); OUT=$REPO/docs/img; mkdir -p "$OUT"
export GITS_PANEL_DEMO=1
orig_ws=$(hyprctl activeworkspace -j | jq -r .id)
orig_win=$(hyprctl activewindow -j 2>/dev/null | jq -r '.address // empty')
paused=$(dunstctl is-paused 2>/dev/null)
ws=${1:-$(for i in 4 5 6 7 8; do hyprctl workspaces -j | jq -e --argjson i "$i" 'map(select(.id == $i and .windows > 0)) | length == 0' >/dev/null && { echo "$i"; break; }; done)}
[[ -n $ws ]] || { echo "no empty workspace found" >&2; exit 1; }
scale=$(hyprctl monitors -j | jq -r '.[0].scale'); orig_cursor=$(hyprctl cursorpos)
focus() { hyprctl dispatch "hl.dsp.focus({ workspace = $1 })" >/dev/null; }
restore() {
    gits-panel close 2>/dev/null; gits-osd stop >/dev/null 2>&1; gits-osd start >/dev/null 2>&1
    # kitty asks before closing a window with a running program (nvim): end the throw-away ones by pid
    for p in $(hyprctl clients -j | jq -r '.[] | select(.class | startswith("gits-shot")) | .pid'); do kill "$p" 2>/dev/null; done
    cursor false
    "$HOME/.config/gits-widgets/run.sh" restart >/dev/null 2>&1
    [[ $paused == false ]] && dunstctl set-paused false
    focus "$orig_ws"; [[ -n $orig_win ]] && hyprctl dispatch "hl.dsp.focus({ window = \"address:$orig_win\" })" >/dev/null
    hyprctl dispatch "hl.dsp.cursor.move({x=${orig_cursor%%,*},y=${orig_cursor##*, }})" >/dev/null
}
cursor() { hyprctl eval "hl.config({ cursor = { invisible = $1 } })" >/dev/null; }   # no pointer in the pictures
trap restore EXIT
# crop <out.jpg> <x> <y> <w> <h>   (logical pixels; no arguments = whole screen)
shot() {
    local out=$1; grim "$OUT/.full.png"
    python3 - "$OUT/.full.png" "$out" "$scale" "${@:2}" <<'PY'
import sys
from PIL import Image
src, out, scale, *box = sys.argv[1:]
im = Image.open(src).convert("RGB"); s = float(scale)
if box:
    x, y, w, h = map(float, box); im = im.crop((int(x * s), int(y * s), int((x + w) * s), int((y + h) * s)))
im.save(out, quality=88)
PY
    rm -f "$OUT/.full.png"
}
dunstctl set-paused true; cursor true
GITS_WIDGETS_DEMO=1 GITS_WEATHER_LOCATION=Tokyo "$HOME/.config/gits-widgets/run.sh" restart
focus "$ws"; hyprctl dispatch 'hl.dsp.cursor.move({x=20,y=780})' >/dev/null; sleep 4

want desktop && { echo "desktop"; shot "$OUT/desktop.jpg"; }
popup() {  # popup <mode> <out> <x y w h>
    gits-panel "$1"; sleep 1.7; shot "$2" "${@:3}"; gits-panel close; sleep 0.6
}
export GITS_PANEL_ART=$REPO/assets/gits_eye.png
want control-panel && { echo "control panel"; popup control "$OUT/control-panel.jpg" 930 40 350 700; }
want player && { echo "player"; popup media "$OUT/player.jpg" 470 40 340 490; }
want mixer && { echo "mixer"; popup mixer "$OUT/mixer.jpg" 500 40 380 300; }
want notifications && { echo "notifications"; popup notify "$OUT/notifications.jpg" 900 40 380 400; }
unset GITS_PANEL_ART
want settings-menu && { echo "settings menu"
    (gits-settings >/dev/null 2>&1 &); sleep 1.8; shot "$OUT/settings-menu.jpg" 380 90 520 700
    kill $(pgrep -f "[p]anel.py menu") 2>/dev/null; sleep 0.6; }
want osd && { echo "osd"; gits-osd volume 64; sleep 0.7; shot "$OUT/osd.jpg" 430 590 420 140; sleep 1.2; }

throwaway() {  # throwaway <class> <command...>: a kitty on the workspace, returns its geometry "x y w h"
    local cls=$1; shift
    hyprctl dispatch "hl.dsp.exec_cmd(\"kitty --class $cls $*\")" >/dev/null; sleep "${WAIT:-7}"
    hyprctl clients -j | jq -r --arg c "$cls" '.[] | select(.class == $c) | "\(.at[0]) \(.at[1]) \(.size[0]) \(.size[1])"'
}
want terminal && { echo "terminal"; read -r x y w h < <(WAIT=9 throwaway gits-shot-term env GITS_BANNER_FAST=1 zsh -i); shot "$OUT/terminal.jpg" $x $y $w $h; }
want nvim-dashboard && { echo "nvim dashboard"; read -r x y w h < <(WAIT=8 throwaway gits-shot-nvim nvim); shot "$OUT/nvim-dashboard.jpg" $x $y $w $h; }
echo "done: $OUT"
