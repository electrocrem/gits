#!/usr/bin/env sh
# gits-xprimary <output>: make <output> the XWayland primary output and keep it so for a minute (called from monitors.lua).
# X11 games (Proton) size themselves for the primary output. At login XWayland comes up after Hyprland and the monitors settle in
# several steps, so a single `xrandr --primary` can land too early or be overtaken by an older call; one instance (flock) enforces
# the newest wish from the state file until it is 60 s old.
command -v xrandr >/dev/null || exit 0
[ -n "$1" ] || exit 2
f=${XDG_RUNTIME_DIR:-/tmp}/gits-xprimary
echo "$1" >"$f"
exec 8>"$f.lock"
flock -n 8 || exit 0
while [ $(($(date +%s) - $(stat -c %Y "$f"))) -lt 60 ]; do
    m=$(cat "$f")
    xrandr --listmonitors 2>/dev/null | grep -q "[*]$m " || xrandr --output "$m" --primary 2>/dev/null
    sleep 1
done
