#!/usr/bin/env bash
# gits-events: UI sounds for session events, one small background loop (started from gits.lua on login).
#   login   played once when the daemon starts        plug / unplug   mains power connected / removed
#   lock / unlock   hyprlock appears / disappears
#   layout   the new keyboard layout on the GitS OSD on every switch (no sound)
#   battery   a warning at 25 % and a critical one at 12 % while discharging (the charge limit of an ASUS keeps it near 98 %, that is not a warning);
#             early because the worn battery holds ~9.5 Wh, and upowerd powers off at 8 % (~/.local/share/gits-power/setup.sh)
# Mute everything: `gits-sound off`. Single instance (flock). Polls every 2 s: two file reads and one pgrep.
exec 9>"${XDG_RUNTIME_DIR:-/tmp}/gits-events.lock"
flock -n 9 || exit 0
echo $$ >"${XDG_RUNTIME_DIR:-/tmp}/gits-events.pid"   # install.sh restarts a running copy so a new version takes effect without a re-login

ac=""
for d in /sys/class/power_supply/*; do
    [[ $(cat "$d/type" 2>/dev/null) == Mains ]] && { ac=$d/online; break; }
done
last_ac=$(cat "$ac" 2>/dev/null)
locked=0
pgrep -x hyprlock >/dev/null && locked=1
warned=0

[[ -n ${GITS_EVENTS_NO_LOGIN:-} ]] || gits-sound login

# layout OSD: the new keyboard layout on the GitS OSD (bottom centre, like volume) on every switch
# (caps lock, Super+K, bar click). Event-driven over socket2; Hyprland sends "activelayout" once per keyboard,
# so repeats are dropped. Turn off with GITS_EVENTS_NO_LAYOUT=1.
sock="$XDG_RUNTIME_DIR/hypr/$HYPRLAND_INSTANCE_SIGNATURE/.socket2.sock"
if [[ -z ${GITS_EVENTS_NO_LAYOUT:-} && -S $sock ]] && command -v socat >/dev/null && command -v gits-osd >/dev/null; then
    (
        kbd() { hyprctl devices -j 2>/dev/null | jq -r '[.keyboards[] | select(.main)][0] // empty
            | "\(.active_layout_index) \(.layout | split(",") | map(if . == "us" or . == "gb" then "EN" else ascii_upcase end) | join(","))"'; }
        last=$(hyprctl devices -j 2>/dev/null | jq -r '[.keyboards[] | select(.main)][0].active_keymap // empty')
        socat -U - "UNIX-CONNECT:$sock" 2>/dev/null | while IFS= read -r line; do
            [[ $line == activelayout'>>'* ]] || continue
            name=${line##*,}
            [[ $name == "$last" || $name == error ]] && continue
            last=$name
            read -r idx codes < <(kbd)
            [[ $idx =~ ^[0-9]+$ ]] && gits-osd layout "$idx" 0 "$codes"
        done
    ) &
    listener=$!
    trap 'pkill -P "$listener" 2>/dev/null; kill "$listener" 2>/dev/null; exit 0' TERM INT   # take the socket reader along
fi

while sleep "${GITS_EVENTS_POLL:-2}"; do
    if [[ -n $ac ]]; then
        now=$(cat "$ac" 2>/dev/null)
        if [[ -n $now && $now != "$last_ac" ]]; then
            [[ $now == 1 ]] && gits-sound plug || gits-sound unplug
            command -v gits-idle >/dev/null && gits-idle apply >/dev/null 2>&1   # AC and battery have their own sleep timers
            last_ac=$now
        fi
    fi
    pct=$(gits-battery percent 2>/dev/null)
    if [[ -n $pct ]]; then
        if [[ $(gits-battery status) == Discharging ]]; then
            if (( pct <= 12 && warned < 2 )); then
                notify-send -a GitS -u critical -i battery-empty -r 31 "Battery critical" "${pct}%: plug in the charger, the laptop powers off at 8%"; warned=2
            elif (( pct <= 25 && warned < 1 )); then
                notify-send -a GitS -u normal -i battery-caution -r 31 "Battery low" "${pct}% left (a few minutes on this battery)"; warned=1
            fi
        else
            warned=0
        fi
    fi
    if pgrep -x hyprlock >/dev/null; then
        (( locked )) || { gits-sound lock; locked=1; }
    elif (( locked )); then
        gits-sound unlock; locked=0
    fi
done
