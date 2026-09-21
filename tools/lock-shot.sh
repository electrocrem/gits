#!/usr/bin/env bash
# Maintainer tool: a picture of the lock screen WITHOUT locking your session.
#   tools/lock-shot.sh [out.jpg]        (default: docs/img/lock.jpg)
# hyprlock must never run on the live compositor while you test it. This starts a NESTED Hyprland window (GITS_NESTED=1: no services) on
# an empty workspace and runs hyprlock against that compositor only: WAYLAND_DISPLAY and HYPRLAND_INSTANCE_SIGNATURE are set to the nested
# ones, the environment of the hyprlock process is checked before anything else happens (it is killed at once if it points at your session),
# and afterwards the script confirms that your session was never locked. The picture is taken from the nested compositor's own socket, after its
# "started without start-hyprland" banner is dismissed, at a moment when the clock is NOT glitching (the same slot formula as gits-lock-clock).
# The other animations (Lain, cursor, scanner) are a moment of their loops.
set -u
REPO=$(cd "$(dirname "$0")/.." && pwd); OUT=${1:-$REPO/docs/img/lock.jpg}
TMP=$(mktemp -d); orig=$(hyprctl activeworkspace -j | jq -r .id); outer_sig=$HYPRLAND_INSTANCE_SIGNATURE; outer_wl=$WAYLAND_DISPLAY
NP="" LP=""
cleanup() {
    [[ -n $LP ]] && kill "$LP" 2>/dev/null; sleep 0.4; [[ -n $NP ]] && kill "$NP" 2>/dev/null; sleep 1.2
    hyprctl dispatch "hl.dsp.focus({ workspace = $orig })" >/dev/null 2>&1
    echo "your session locked? $(loginctl show-session "$XDG_SESSION_ID" -p LockedHint --value)"; rm -rf "$TMP"
}
trap cleanup EXIT
ws=""; for i in 5 6 7 8 9; do n=$(hyprctl clients -j | jq --argjson i $i '[.[]|select(.workspace.id==$i)]|length'); [[ $n -eq 0 ]] && { ws=$i; break; }; done
[[ -n $ws ]] || { echo "no empty workspace" >&2; exit 1; }
before=$(ls "$XDG_RUNTIME_DIR" | grep -E '^wayland-[0-9]+$' | sort)
hyprctl dispatch "hl.dsp.focus({ workspace = $ws })" >/dev/null; sleep 0.6
GITS_NESTED=1 Hyprland -c "$HOME/.config/hypr/hyprland.lua" >"$TMP/nested.log" 2>&1 & NP=$!; sleep 5
nested_wl=$(comm -13 <(echo "$before") <(ls "$XDG_RUNTIME_DIR" | grep -E '^wayland-[0-9]+$' | sort) | head -1)
nested_sig=""; for d in "$XDG_RUNTIME_DIR"/hypr/*/; do [[ $(head -1 "$d/hyprland.lock" 2>/dev/null) == "$NP" ]] && nested_sig=$(basename "$d"); done
if [[ -z $nested_wl || -z $nested_sig || $nested_wl == "$outer_wl" || $nested_sig == "$outer_sig" ]]; then echo "cannot identify the nested compositor safely: nothing was locked" >&2; exit 1; fi
WAYLAND_DISPLAY=$nested_wl HYPRLAND_INSTANCE_SIGNATURE=$nested_sig hyprlock --config "$HOME/.config/hypr/hyprlock.conf" >"$TMP/lock.log" 2>&1 & LP=$!; sleep 1.5
env=$(tr '\0' '\n' <"/proc/$LP/environ" | grep -E '^(WAYLAND_DISPLAY|HYPRLAND_INSTANCE_SIGNATURE)=' | tr '\n' ' ')
if [[ $env != *"WAYLAND_DISPLAY=$nested_wl"* || $env == *"$outer_sig"* ]]; then echo "hyprlock points at the wrong compositor: killed" >&2; kill -9 "$LP"; LP=""; exit 1; fi
sleep 3
HYPRLAND_INSTANCE_SIGNATURE=$nested_sig hyprctl dismissnotify -1 >/dev/null 2>&1; sleep 0.6
glitching() { local slot=$(( ${EPOCHREALTIME/./} / 150000 )) k; for k in 0 1 2 3; do (( ((slot + k) * 2654435761 >> 7) % 27 == 0 )) && return 0; done; return 1; }
for _ in $(seq 60); do glitching || break; sleep 0.05; done
for try in 1 2 3; do   # the nested window only renders while it is visible: bring it back if you switched away
    [[ $(hyprctl activeworkspace -j | jq -r .id) == "$ws" ]] || { hyprctl dispatch "hl.dsp.focus({ workspace = $ws })" >/dev/null; sleep 1.5; }
    WAYLAND_DISPLAY=$nested_wl timeout 8 grim "$TMP/l.png" 2>/dev/null && [[ -s $TMP/l.png ]] && break
done
[[ -s $TMP/l.png ]] || { echo "no picture from the nested compositor" >&2; exit 1; }
python3 - "$TMP/l.png" "$OUT" <<'PY'
import sys
from PIL import Image
im = Image.open(sys.argv[1]).convert("RGB")
im.save(sys.argv[2], quality=88)
print("saved", sys.argv[2], im.width, "x", im.height)
PY
