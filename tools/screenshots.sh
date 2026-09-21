#!/usr/bin/env bash
# Maintainer tool: regenerate the README screenshots in docs/img on a live session, without personal data.
#   tools/screenshots.sh [workspace]     (default: the first empty workspace from 4 up)
#   ONLY="player mixer" tools/screenshots.sh   retake just those pictures (names are listed at the bottom of this file)
#   FULL=1 tools/screenshots.sh          save the whole screen instead of the crop (to tune the crop boxes; look at them before publishing)
# It switches to an empty workspace for a few minutes, pauses notifications, runs the widgets and the popups in their demo modes
# (made-up SSID/IP/to-do/tracks/clipboard/windows/projects), opens throw-away windows (kitty, Dolphin, ...) showing this repository, takes the
# shots with grim and puts everything back (workspace, widgets, notifications). A shot is only taken while the chosen workspace is the
# active one, so a workspace switch of yours can never leak into a picture. Needs: grim, python-pillow, hyprctl, jq, kitty, the gits-* tools.
# Don't touch the mouse or keyboard while it runs.
set -u
want() { [[ -z ${ONLY:-} || " $ONLY " == *" $1 "* ]]; }
REPO=$(cd "$(dirname "$0")/.." && pwd); OUT=$REPO/docs/img; mkdir -p "$OUT"
TMP=$(mktemp -d); trap 'rm -rf "$TMP"' EXIT
export GITS_PANEL_DEMO=1
orig_ws=$(hyprctl activeworkspace -j | jq -r .id)
orig_win=$(hyprctl activewindow -j 2>/dev/null | jq -r '.address // empty')
paused=$(dunstctl is-paused 2>/dev/null)
ws=${1:-$(for i in 4 5 6 7 8; do hyprctl workspaces -j | jq -e --argjson i "$i" 'map(select(.id == $i and .windows > 0)) | length == 0' >/dev/null && { echo "$i"; break; }; done)}
[[ -n $ws ]] || { echo "no empty workspace found" >&2; exit 1; }
scale=$(hyprctl monitors -j | jq -r '.[0].scale'); orig_cursor=$(hyprctl cursorpos)
focus() { hyprctl dispatch "hl.dsp.focus({ workspace = $1 })" >/dev/null; }
cursor() { hyprctl eval "hl.config({ cursor = { invisible = $1 } })" >/dev/null; }   # no pointer in the pictures
PIDS=()    # processes started by this script: the only ones it ever kills
killall_mine() { for p in "${PIDS[@]}"; do kill "$p" 2>/dev/null; done; PIDS=(); }
restore() {
    gits-panel close 2>/dev/null; kill $(pgrep -f "[p]anel.py menu") 2>/dev/null; pkill -x wlogout 2>/dev/null
    gits-osd stop >/dev/null 2>&1; gits-osd start >/dev/null 2>&1
    # kitty asks before closing a window with a running program: end the throw-away ones by pid
    for p in $(hyprctl clients -j | jq -r '.[] | select(.class | startswith("gits-shot")) | .pid'); do kill "$p" 2>/dev/null; done
    killall_mine; tmux -L gitsshot kill-server 2>/dev/null
    cursor false
    "$HOME/.config/gits-widgets/run.sh" restart >/dev/null 2>&1
    [[ $paused == false ]] && dunstctl set-paused false
    focus "$orig_ws"; [[ -n $orig_win ]] && hyprctl dispatch "hl.dsp.focus({ window = \"address:$orig_win\" })" >/dev/null
    hyprctl dispatch "hl.dsp.cursor.move({x=${orig_cursor%%,*},y=${orig_cursor##*, }})" >/dev/null
    rm -rf "$TMP"
}
trap restore EXIT
# shot <out.jpg> [x y w h]   (logical pixels; no box = whole screen). Refuses to shoot unless our workspace is the visible one.
shot() {
    local out=$1 now
    now=$(hyprctl activeworkspace -j | jq -r .id)
    if [[ $now != "$ws" ]]; then focus "$ws"; sleep 0.6; now=$(hyprctl activeworkspace -j | jq -r .id); fi
    [[ $now == "$ws" ]] || { echo "workspace $now is active, not $ws: skipped $(basename "$out")" >&2; return 1; }
    grim "$TMP/full.png"
    [[ -n ${FULL:-} ]] && set --  "$out"    # tuning mode: whole screen
    python3 - "$TMP/full.png" "$out" "$scale" "${@:2}" <<'PY'
import sys
from PIL import Image
src, out, scale, *box = sys.argv[1:]
im = Image.open(src).convert("RGB"); s = float(scale)
if box and box[0] == "auto":   # "auto X Y": a point inside a popup card (logical px); the box is the dark card around it, plus its frame
    import numpy as np
    a = np.asarray(im).astype(int); dark = lambda x, y: a[y, x].max() < 34
    sx, sy = int(float(box[1]) * s), int(float(box[2]) * s)
    if not dark(sx, sy):
        sys.exit(f"auto crop: ({box[1]}, {box[2]}) is not on a popup card")
    t = b = sy
    while dark(sx, t - 1): t -= 1
    while dark(sx, b + 1): b += 1
    l = r = sx
    while dark(l - 1, t + 5): l -= 1
    while dark(r + 1, t + 5): r += 1
    m = 4
    box = [(l - m) / s, (t - m) / s, (r - l + 2 * m) / s, (b - t + 2 * m) / s]
if box:
    x, y, w, h = map(float, box); im = im.crop((int(x * s), int(y * s), int((x + w) * s), int((y + h) * s)))
im.save(out, quality=88)
PY
    rm -f "$TMP/full.png"
}
dunstctl set-paused true; cursor true
GITS_WIDGETS_DEMO=1 GITS_WIDGETS_ART=$REPO/assets/gits_eye.png GITS_WEATHER_LOCATION=Tokyo "$HOME/.config/gits-widgets/run.sh" restart
focus "$ws"; hyprctl dispatch 'hl.dsp.cursor.move({x=20,y=780})' >/dev/null; sleep 4

# ---------------------------------------------------------------- desktop
# the bar shows the title of any media player, playing or paused (a browser tab is enough): pictures with the bar wait until there is none
playing() { [[ -n $(playerctl -l 2>/dev/null) ]]; }
want desktop && { echo "desktop"; if playing; then echo "a media player exists (playerctl -l): the bar would show its title, skipped desktop (close it and retake)" >&2; else shot "$OUT/desktop.jpg"; fi; }
want bar && { echo "bar"; if playing; then echo "a media player exists: skipped bar" >&2; else shot "$OUT/bar.jpg" 0 0 1280 44; fi; }

# ---------------------------------------------------------------- popups (all in demo mode: made-up data)
popup() {  # popup <mode> <out> <x y w h>
    gits-panel "$1"; sleep 1.7; shot "$2" "${@:3}"; gits-panel close; sleep 0.6
}
printf -- '- 2026-09-19 22:10  buy a USB-C dock\n- 2026-09-20 09:30  ask Batou about the tachikoma firmware\n- 2026-09-20 18:45  rice: try the new glitch preset\n- 2026-09-21 01:05  reboot to check the login guard\n' >"$TMP/notes.md"
export GITS_NOTES=$TMP/notes.md GITS_PANEL_ART=$REPO/assets/gits_eye.png
want control-panel && { echo "control panel"; popup control "$OUT/control-panel.jpg" 930 40 350 700; }
want player && { echo "player"; popup media "$OUT/player.jpg" auto 496 68; }
want radio && { echo "radio"; GITS_PANEL_ART=$REPO/assets/gits_eye.png popup radio "$OUT/radio.jpg" auto 496 68; }
want mixer && { echo "mixer"; popup mixer "$OUT/mixer.jpg" 500 40 380 300; }
want notifications && { echo "notifications"; popup notify "$OUT/notifications.jpg" 900 40 380 400; }
unset GITS_PANEL_ART
want launcher && { echo "launcher"; GITS_PANEL_AUTOTEXT=${LAUNCHER_QUERY:-te} popup launch "$OUT/launcher.jpg" auto 362 130; }
want calc && { echo "calculator"; GITS_PANEL_AUTOTEXT="sqrt(1764) * 2" popup launch "$OUT/calculator.jpg" auto 362 130; }
want clipboard && { echo "clipboard"; popup clip "$OUT/clipboard.jpg" auto 362 130; }
want windows && { echo "window switcher"; popup windows "$OUT/windows.jpg" auto 362 130; }
want emoji && { echo "emoji"; GITS_PANEL_AUTOTEXT=cat popup emoji "$OUT/emoji.jpg" auto 362 130; }
want keys && { echo "key bindings"; popup keys "$OUT/keys.jpg" auto 362 130; }
want note && { echo "quick note"; popup note "$OUT/note.jpg" auto 412 130; }
menu() {  # menu <out> <title> <tag> <x y w h>   (lines on stdin)
    local out=$1 title=$2 tag=$3; shift 3
    python3 "$HOME/.config/gits-widgets/panel.py" menu "$title" "$tag" index >/dev/null 2>&1 &
    local p=$!; PIDS+=("$p"); sleep 1.9; shot "$out" "$@"; kill "$p" 2>/dev/null; sleep 0.6
}
want wifi && { echo "wifi menu"
    {
        printf '%s\n' "󰖪  Turn Wi-Fi off" "󰑐  Rescan networks"
        printf '● ▂▄▆█  %-30.30s %3s%%  %s%s\n' "LAIN-NET" 92 "󰌾" "  [saved]"
        printf '  ▂▄▆█  %-30.30s %3s%%  %s%s\n' "Section9-Guest" 81 "󰌾" "  [saved]"
        printf '  ▂▄▆   %-30.30s %3s%%  %s%s\n' "Tachikoma_5G" 67 "󰌾" ""
        printf '  ▂▄    %-30.30s %3s%%  %s%s\n' "CoffeeShop Free WiFi" 44 " " ""
        printf '  ▂▄    %-30.30s %3s%%  %s%s\n' "Wired-Sanctuary" 31 "󰌾" ""
        printf '%s\n' "󰛳  Advanced settings (nmtui)"
    } | menu "$OUT/wifi.jpg" "󰖩  WI-FI" "// 無線" auto 424 130; }
want bluetooth && { echo "bluetooth menu"
    {
        printf '%s\n' "󰂲  Turn Bluetooth off" "󰂰  Scan for devices (8 s)"
        printf '%s%s  %-26.26s  %s\n' "● " "󰋋" "WH-1000XM5" "connected · 78%"
        printf '%s%s  %-26.26s  %s\n' "  " "󰍽" "MX Master 3" "paired"
        printf '%s%s  %-26.26s  %s\n' "  " "󰌌" "Keychron K2" "paired"
        printf '%s%s  %-26.26s  %s\n' "  " "󰏲" "Pixel 8" "paired"
        printf '%s\n' "󰒓  Advanced settings (blueman)"
    } | menu "$OUT/bluetooth.jpg" "󰂯  BLUETOOTH" "// 青歯" auto 424 130; }
want focus && { echo "focus timer menu"
    printf '%s\n' "25 min work · 5 min break (classic)" "50 min · 10 min" "15 min · 3 min (short)" "90 min · 15 min (deep work)" \
        | menu "$OUT/focus.jpg" $'\U000F13AB  FOCUS' "// 集中" auto 424 130; }
want settings-menu && { echo "settings menu"
    (gits-settings >/dev/null 2>&1 &); sleep 1.8; shot "$OUT/settings-menu.jpg" 380 90 520 700
    kill $(pgrep -f "[p]anel.py menu") 2>/dev/null; sleep 0.6; }
want osd && { echo "osd"; gits-osd volume 64; sleep 0.7; shot "$OUT/osd.jpg" 430 590 420 140; sleep 1.2; }

# ---------------------------------------------------------------- notifications on screen (real dunst popups with made-up text)
want dunst && { echo "notification popups"
    dunstctl set-paused false; dunstctl close-all
    notify-send -a "Telegram Desktop" -u normal "Section 9 // chat" "meeting moved to 15:00, bring the report"
    notify-send -a "GitS" -u critical "Battery Low" "Battery is at 19%. Connect the charger."
    notify-send -a "Phone" -u low "Alex" "are you coming tonight?"
    sleep 2; shot "$OUT/notification-popups.jpg" 830 40 450 330
    dunstctl close-all; dunstctl set-paused true; sleep 0.5; }

# ---------------------------------------------------------------- throw-away windows on the workspace
# app <name> <geometry-out-var> <command...>: run a program in its own kitty (class gits-shot-<name>), print its geometry "x y w h"
app() {
    local name=$1; shift
    printf '#!/usr/bin/env bash\ncd %q\n%s\n' "${APPDIR:-$REPO}" "$*" >"$TMP/$name.sh"; chmod +x "$TMP/$name.sh"
    hyprctl dispatch "hl.dsp.exec_cmd(\"kitty ${KITTY_OPTS:-} --class gits-shot-$name $TMP/$name.sh\")" >/dev/null; sleep "${WAIT:-7}"
    hyprctl clients -j | jq -r --arg c "gits-shot-$name" '.[] | select(.class == $c) | "\(.at[0]) \(.at[1]) \(.size[0]) \(.size[1])"'
}
closeapp() { for p in $(hyprctl clients -j | jq -r --arg c "gits-shot-$1" '.[] | select(.class == $c) | .pid'); do kill "$p" 2>/dev/null; done; sleep 1; }
snapapp() {  # snapapp <name> <out> <command...>
    local name=$1 out=$2 x y w h; shift 2
    read -r x y w h < <(app "$name" "$@")
    [[ -n ${FRAC_W:-} && -n ${w:-} ]] && w=$(awk -v w="$w" -v f="$FRAC_W" 'BEGIN { printf "%d", w * f }')
    [[ -n ${FRAC_H:-} && -n ${h:-} ]] && h=$(awk -v h="$h" -v f="$FRAC_H" 'BEGIN { printf "%d", h * f }')
    if [[ -n ${x:-} ]]; then shot "$OUT/$out" "$x" "$y" "$w" "$h"; else echo "window $name did not appear" >&2; fi
    closeapp "$name"
}
# btop without the network box (LAN address) and the process list; lazygit without its start-up popup
sed 's/^shown_boxes = .*/shown_boxes = "cpu mem"/' "$HOME/.config/btop/btop.conf" >"$TMP/btop.conf" 2>/dev/null
echo 'disableStartupPopups: true' >"$TMP/lazygit.yml"
BTOP="btop -c $TMP/btop.conf"; LAZYGIT="lazygit --use-config-file=$TMP/lazygit.yml,$HOME/.config/lazygit/config.yml"
want terminal && { echo "terminal"; FRAC_W=0.55 FRAC_H=0.72 WAIT=9 snapapp term terminal.jpg 'exec env GITS_BANNER_FAST=1 zsh -i'; }
want doctor && { echo "gits-doctor"; FRAC_W=0.62 KITTY_OPTS="-o font_size=9" snapapp doctor doctor.jpg 'GITS_NO_BANNER=1 gits-doctor 2>&1 | head -40; sleep 600'; }
want nvim-dashboard && { echo "nvim dashboard"; WAIT=8 APPDIR=$TMP snapapp nvim-dash nvim-dashboard.jpg 'exec nvim'; }
want nvim && { echo "nvim"; WAIT=9 snapapp nvim nvim.jpg 'exec nvim install.sh'; }
want btop && { echo "btop"; WAIT=12 snapapp btop btop.jpg "for i in 1 2 3 4 5 6; do timeout 25 yes >/dev/null & done; exec $BTOP"; }
want lazygit && { echo "lazygit"; snapapp lazygit lazygit.jpg "exec $LAZYGIT"; }
want yazi && { echo "yazi"; APPDIR=$REPO/home/.config snapapp yazi yazi.jpg 'exec yazi'; }
want tmux && { echo "tmux"
    tmux -L gitsshot -f "$HOME/.config/tmux/tmux.conf" new-session -d -s shot -c "$REPO" 'nvim install.sh' \; split-window -h -c "$REPO" "$BTOP" \; split-window -v -c "$REPO" 'exec env GITS_BANNER_FAST=1 zsh -i' 2>/dev/null
    WAIT=12 snapapp tmux tmux.jpg 'exec tmux -L gitsshot attach -t shot'; tmux -L gitsshot kill-server 2>/dev/null; }
want tiling && { echo "tiling"
    read -r _ < <(app t1 'exec env GITS_BANNER_FAST=1 zsh -i')
    read -r _ < <(WAIT=2 app t2 'exec nvim install.sh')
    read -r _ < <(WAIT=2 APPDIR=$REPO/home/.config app t3 'exec yazi')
    sleep 2; shot "$OUT/tiling.jpg" 0 26 1280 774   # without the bar (it may show the track that is playing)
    closeapp t3; closeapp t2; closeapp t1; }

want wlogout && { echo "wlogout"; (gits-logout >/dev/null 2>&1 &); sleep 2.2; shot "$OUT/wlogout.jpg" 160 230 960 340; pkill -x wlogout; sleep 0.8; }

# Dolphin: only when none is running (it is a single-instance app: a new window would live in YOUR process)
want dolphin && { echo "dolphin"
    if pgrep -x dolphin >/dev/null; then echo "dolphin is already running: skipped" >&2; else
        dolphin --new-window "$REPO/home/.config" >/dev/null 2>&1 & dp=$!; PIDS+=("$dp"); sleep 6
        geo=$(hyprctl clients -j | jq -r '.[] | select(.class == "org.kde.dolphin") | "\(.at[0]) \(.at[1]) \(.size[0]) \(.size[1])"' | head -1)
        [[ -n $geo ]] && { read -r x y w h <<<"$geo"; shot "$OUT/dolphin.jpg" "$x" "$y" "$w" "$h"; } || echo "dolphin window did not appear" >&2
        kill "$dp" 2>/dev/null; sleep 1
    fi; }

# newwin <addresses-before>: geometry "x y w h" of the first window on our workspace that was not there before
clients_now() { hyprctl clients -j | jq -r --argjson w "$ws" '.[] | select(.workspace.id == $w) | .address'; }
newwin() {
    hyprctl clients -j | jq -r --argjson w "$ws" --arg old "$1" '($old | split("\n")) as $o
        | [.[] | select(.workspace.id == $w and ((.address as $a | $o | index($a)) | not))] | first // empty | "\(.at[0]) \(.at[1]) \(.size[0]) \(.size[1])"'
}

# VS Code (Code - OSS) with a throw-away user dir, so none of your settings, recent files or accounts show up
want vscode && { echo "vs code"
    if command -v code >/dev/null && [[ -d $HOME/.vscode-oss/extensions/gits.ghost-in-the-shell-1.0.0 ]]; then
        mkdir -p "$TMP/vsc/User"
        echo '{"workbench.colorTheme":"Ghost in the Shell","workbench.startupEditor":"none","window.titleBarStyle":"custom","update.mode":"none","telemetry.telemetryLevel":"off","security.workspace.trust.enabled":false,"workbench.tips.enabled":false,"chat.disableAIFeatures":true,"workbench.welcomePage.walkthroughs.openOnInstall":false,"workbench.secondarySideBar.defaultVisibility":"hidden","git.openRepositoryInParentFolders":"never"}' >"$TMP/vsc/User/settings.json"
        before=$(clients_now)
        code --user-data-dir "$TMP/vsc" --extensions-dir "$HOME/.vscode-oss/extensions" "$REPO" "$REPO/install.sh" >/dev/null 2>&1 &
        sleep 16; geo=$(newwin "$before")
        [[ -n $geo ]] && { read -r x y w h <<<"$geo"; shot "$OUT/vscode.jpg" "$x" "$y" "$w" "$h"; } || echo "vs code window did not appear" >&2
        pkill -f "$TMP/vsc"; sleep 2; pkill -9 -f "$TMP/vsc"; sleep 1
    else echo "code or the GitS theme extension is missing: skipped" >&2; fi; }

# SDDM greeter in test mode (a plain window; needs the theme installed with install.sh --system)
want sddm && { echo "sddm"
    if [[ -d /usr/share/sddm/themes/ghost-in-the-shell ]] && command -v sddm-greeter-qt6 >/dev/null; then
        sddm-greeter-qt6 --test-mode --theme /usr/share/sddm/themes/ghost-in-the-shell >/dev/null 2>&1 & sp=$!; PIDS+=("$sp"); sleep 6
        geo=$(hyprctl clients -j | jq -r --argjson p "$sp" '.[] | select(.pid == $p) | "\(.at[0]) \(.at[1]) \(.size[0]) \(.size[1])"' | head -1)
        [[ -n $geo ]] && { read -r x y w h <<<"$geo"; shot "$OUT/sddm.jpg" "$x" "$y" "$w" "$h"; } || echo "greeter window did not appear" >&2
        kill "$sp" 2>/dev/null; sleep 1
    else echo "sddm greeter or theme missing: skipped" >&2; fi; }
# ---------------------------------------------------------------- the small demo animation (popups opening one after another)
want gif && { echo "demo gif"
    if command -v wf-recorder >/dev/null && command -v ffmpeg >/dev/null; then
        wf-recorder -g "330,40 620x560" -f "$TMP/rec.mp4" >/dev/null 2>&1 & rp=$!; PIDS+=("$rp"); sleep 1.5
        GITS_PANEL_AUTOTEXT=te gits-panel launch; sleep 3.4
        gits-panel clip; sleep 2.4
        gits-panel keys; sleep 2.4
        GITS_PANEL_ART=$REPO/assets/gits_eye.png gits-panel media; sleep 2.6
        gits-panel mixer; sleep 2.4
        gits-panel close; sleep 1.2
        kill -INT "$rp"; wait "$rp" 2>/dev/null; sleep 1
        ffmpeg -v error -y -i "$TMP/rec.mp4" -vf "fps=${GIF_FPS:-12},scale=${GIF_W:-560}:-1:flags=lanczos,split[a][b];[a]palettegen=max_colors=${GIF_COLORS:-96}:stats_mode=diff[p];[b][p]paletteuse=dither=bayer:bayer_scale=4:diff_mode=rectangle" -loop 0 "$OUT/demo.gif" \
            && du -h "$OUT/demo.gif" | cut -f1
    else echo "wf-recorder or ffmpeg missing: skipped" >&2; fi; }
echo "done: $OUT"
# names: desktop bar control-panel player radio mixer notifications launcher calc clipboard windows emoji keys note wifi bluetooth focus
#        settings-menu osd dunst terminal doctor nvim-dashboard nvim btop lazygit yazi tmux tiling wlogout dolphin vscode sddm gif
