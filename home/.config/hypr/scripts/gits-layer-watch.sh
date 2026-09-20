#!/usr/bin/env bash
# gits-layer-watch: click-away-to-close for EVERY rofi menu, including HyDE's own (launcher, clipboard, keybinding hint).
# Listens to Hyprland's event socket (no polling): a "rofi" layer opens -> start the invisible click catcher under it, the
# layer closes -> stop it. See ~/.local/bin/gits-catcher. Single instance (flock), started from gits.lua at login.
exec 9>"${XDG_RUNTIME_DIR:-/tmp}/gits-layer-watch.lock"
flock -n 9 || exit 0
sock=${XDG_RUNTIME_DIR:-/run/user/$(id -u)}/hypr/${HYPRLAND_INSTANCE_SIGNATURE:-}/.socket2.sock
[[ -S $sock ]] || exit 1
while read -r ev; do
    case $ev in
        openlayer'>>'rofi) gits-catcher start ;;
        closelayer'>>'rofi) gits-catcher stop ;;
    esac
done < <(socat -u "UNIX-CONNECT:$sock" -)
