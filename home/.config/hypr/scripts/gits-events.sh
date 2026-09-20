#!/usr/bin/env bash
# gits-events: UI sounds for session events, one small background loop (started from gits.lua on login).
#   login   played once when the daemon starts        plug / unplug   mains power connected / removed
#   lock / unlock   hyprlock appears / disappears
#   battery   a warning at 15 % and a critical one at 7 % while discharging (the charge limit of an ASUS keeps it near 98 %, that is not a warning)
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
warned=0

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
    pct=$(gits-battery percent 2>/dev/null)
    if [[ -n $pct ]]; then
        if [[ $(gits-battery status) == Discharging ]]; then
            if (( pct <= 7 && warned < 2 )); then
                notify-send -a GitS -u critical -i battery-empty -r 31 "Battery critical" "${pct}%: plug in the charger"; warned=2
            elif (( pct <= 15 && warned < 1 )); then
                notify-send -a GitS -u normal -i battery-caution -r 31 "Battery low" "${pct}% left"; warned=1
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
