#!/usr/bin/env bash
# Keyboard layout indicator, event-driven: prints once, then again on every Hyprland
# "activelayout" event (no polling). waybar's own hyprland/language cannot do upper-case
# short names in 0.15 (format-<lang> disables the module).
short() { case "$1" in English*) echo EN;; Russian*) echo RU;; *) echo "${1:0:2}" | tr a-z A-Z;; esac; }
emit() { jq -nc --arg text "󰌌 $(short "$1")" --arg tip "layout: $1"$'\ncaps lock / click: switch' '{text:$text, tooltip:$tip}'; }

cur=$(hyprctl devices -j 2>/dev/null | jq -r '[.keyboards[] | select(.main)][0].active_keymap // empty')
emit "${cur:-?}"

sock="$XDG_RUNTIME_DIR/hypr/$HYPRLAND_INSTANCE_SIGNATURE/.socket2.sock"
socat -U - "UNIX-CONNECT:$sock" 2>/dev/null | while IFS= read -r line; do
    [[ $line == activelayout'>>'* ]] && emit "${line##*,}"
done
