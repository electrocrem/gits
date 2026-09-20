#!/usr/bin/env bash
# Safety net for a Hyprland instance that died during login (see ~/.config/zsh/.zprofile) and was restarted by
# start-hyprland: the session services (waybar, dunst, hypridle, tray applets, clipboard, portals) of the FIRST
# instance stay alive in systemd, are still connected to the dead compositor, and block the new ones from starting.
# Run from hyprland.lua a few seconds after `hyprland.start`: every hyde-Hyprland-* unit / portal whose process
# belongs to another HYPRLAND_INSTANCE_SIGNATURE is restarted (the user manager env already points at this one).
# Does nothing on a clean login.
sleep 8
cur=${HYPRLAND_INSTANCE_SIGNATURE:-}
[[ -n $cur ]] || exit 0

stale() {  # $1 = unit; true if its main process runs under another Hyprland instance
    local pid sig
    pid=$(systemctl --user show -p MainPID --value "$1" 2>/dev/null)
    [[ $pid =~ ^[1-9][0-9]*$ ]] || return 1
    sig=$(tr '\0' '\n' <"/proc/$pid/environ" 2>/dev/null | sed -n 's/^HYPRLAND_INSTANCE_SIGNATURE=//p')
    [[ -n $sig && $sig != "$cur" ]]
}

restarted=0
while read -r unit _; do
    case $unit in
        hyde-Hyprland-bar.service|hyde-Hyprland-wallpaper.service) continue ;;  # handled below
    esac
    stale "$unit" && { systemctl --user restart "$unit"; restarted=1; }
done < <(systemctl --user list-units 'hyde-Hyprland-*' 'app-Hyprland-*' --no-legend --no-pager --plain)

if stale hyde-Hyprland-wallpaper.service; then
    # a stale awww-daemon; the live instance starts its own one, so just drop the old unit
    systemctl --user stop hyde-Hyprland-wallpaper.service
fi
if stale hyde-Hyprland-bar.service; then
    systemctl --user stop hyde-Hyprland-bar.service     # kills the whole cgroup, incl. socat / gits-lang.sh helpers
    systemctl --user reset-failed hyde-Hyprland-bar.service 2>/dev/null
    hyde-shell waybar.py --watch >/dev/null 2>&1 &
    restarted=1
fi
if (( restarted )); then
    for u in xdg-desktop-portal-hyprland xdg-desktop-portal-gtk plasma-xdg-desktop-portal-kde xdg-desktop-portal; do
        systemctl --user restart "$u.service" 2>/dev/null
    done
fi
exit 0
