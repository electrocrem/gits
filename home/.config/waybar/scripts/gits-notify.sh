#!/usr/bin/env bash
# Monochrome notification indicator (dunst) with the latest entries in the tooltip.
if ! paused=$(dunstctl is-paused 2>/dev/null); then
    jq -nc --arg text "$(printf '')" '{text:$text, class:"off", tooltip:"dunst is not running"}'; exit 0
fi
waiting=$(dunstctl count waiting 2>/dev/null || echo 0)
history=$(dunstctl count history 2>/dev/null || echo 0)
recent=$(dunstctl history 2>/dev/null | jq -r '.data[0][:4][] | "· \(.appname.data): \(.summary.data)"' 2>/dev/null | cut -c1-60)
hint=$'click: do not disturb · right: show last · middle: clear'
if [[ $paused == true ]]; then
    text=$(printf ' %s' "$waiting"); cls=dnd; head="DO NOT DISTURB — $waiting waiting"
elif (( history > 0 )); then
    text=$(printf ' %s' "$history"); cls=unread; head="$history in history"
else
    text=$(printf ''); cls=none; head="no notifications"
fi
jq -nc --arg text "$text" --arg cls "$cls" --arg tip "$head${recent:+$'\n'$recent}"$'\n'"$hint" '{text:$text, class:$cls, tooltip:$tip}'
