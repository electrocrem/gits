#!/usr/bin/env bash
# gits-events: UI sounds for session events, one small background loop (started from gits.lua on login).
#   login   played once when the daemon starts        plug / unplug   mains power connected / removed
#   lock / unlock   hyprlock appears / disappears
# Mute everything: `gits-sound off`. Single instance (flock). Polls every 2 s: two file reads and one pgrep.
exec 9>"${XDG_RUNTIME_DIR:-/tmp}/gits-events.lock"
flock -n 9 || exit 0

ac=""
for d in /sys/class/power_supply/*; do
    [[ $(cat "$d/type" 2>/dev/null) == Mains ]] && { ac=$d/online; break; }
done
last_ac=$(cat "$ac" 2>/dev/null)
locked=0
pgrep -x hyprlock >/dev/null && locked=1

[[ -n ${GITS_EVENTS_NO_LOGIN:-} ]] || gits-sound login
while sleep "${GITS_EVENTS_POLL:-2}"; do
    if [[ -n $ac ]]; then
        now=$(cat "$ac" 2>/dev/null)
        if [[ -n $now && $now != "$last_ac" ]]; then
            [[ $now == 1 ]] && gits-sound plug || gits-sound unplug
            command -v gits-idle >/dev/null && gits-idle apply >/dev/null 2>&1   # AC and battery have their own sleep timers
            last_ac=$now
        fi
    fi
    if pgrep -x hyprlock >/dev/null; then
        (( locked )) || { gits-sound lock; locked=1; }
    elif (( locked )); then
        gits-sound unlock; locked=0
    fi
done
