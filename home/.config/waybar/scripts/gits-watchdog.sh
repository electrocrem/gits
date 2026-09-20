#!/usr/bin/env bash
# Brings waybar back after a CRASH (GTK3 segfaults now and then, e.g. when the cursor theme changes).
# A crashed bar leaves its socat/gits-lang.sh helpers behind, so systemd still calls the unit "active" and nothing
# restarts it. A bar hidden on purpose (Super+Ctrl+B) stops cleanly (Result=success) and is left alone.
# Started once from hyprland.lua. At most 3 restarts per 2 minutes, so a broken config cannot loop.
unit=hyde-Hyprland-bar.service
exec 9>"${XDG_RUNTIME_DIR:-/tmp}/gits-waybar-watchdog.lock"
flock -n 9 || exit 0

restarts=()
while sleep 5; do
    case $(systemctl --user show -p Result --value "$unit" 2>/dev/null) in
        core-dump|signal|exit-code|timeout|watchdog|resources) ;;
        *) continue ;;
    esac
    pgrep -x waybar >/dev/null && continue  # something (HyDE reload) already started a new one
    now=$(date +%s); recent=()
    for t in "${restarts[@]}"; do (( now - t < 120 )) && recent+=("$t"); done
    restarts=("${recent[@]}")
    (( ${#restarts[@]} >= 3 )) && continue
    restarts+=("$now")
    systemctl --user stop "$unit" 2>/dev/null
    systemctl --user reset-failed "$unit" 2>/dev/null
    hyde-shell waybar.py --watch >/dev/null 2>&1 9>&- &
    disown
done
