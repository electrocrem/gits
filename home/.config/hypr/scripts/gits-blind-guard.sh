#!/usr/bin/env bash
# Blind-login guard. On this hybrid AMD+NVIDIA laptop the panel hangs off the AMD GPU (card2). Now and then SDDM's
# kwin_wayland greeter has not released it yet when the session starts: Hyprland then fails with "Could not take
# device: Device or resource busy", comes up on the NVIDIA GPU with no monitor and just sits there alive, so
# start-hyprland never restarts it and the screen stays black.
# Run from hyprland.lua on `hyprland.start`: if this instance still has no monitor after ~12s (two checks), end the
# session (SIGTERM to start-hyprland, which stops Hyprland cleanly) so SDDM shows the greeter again; logging in
# again works. Does nothing when a monitor exists or when hyprctl cannot be asked.
# Env: GITS_BLIND_DELAY / GITS_BLIND_RECHECK (seconds), GITS_BLIND_DRYRUN=1 (only log what would happen).
sig=${HYPRLAND_INSTANCE_SIGNATURE:-}
[[ -n $sig ]] || exit 0
log=${XDG_STATE_HOME:-$HOME/.local/state}/gits-login.log

monitors() {  # number of active monitors; fails if hyprctl / jq cannot answer
    local out
    out=$(hyprctl monitors -j 2>/dev/null) || return 1
    jq 'length' <<<"$out" 2>/dev/null
}

sleep "${GITS_BLIND_DELAY:-8}"
n=$(monitors) || exit 0
[[ $n == 0 ]] || exit 0
sleep "${GITS_BLIND_RECHECK:-4}"
n=$(monitors) || exit 0
[[ $n == 0 ]] || exit 0

pid=$(head -n1 "${XDG_RUNTIME_DIR:-/run/user/$UID}/hypr/$sig/hyprland.lock" 2>/dev/null)
[[ $pid =~ ^[1-9][0-9]*$ ]] || exit 0
comm=$(ps -o comm= -p "$pid" 2>/dev/null)
[[ ${comm,,} == hyprland ]] || exit 0
target=$pid
ppid=$(ps -o ppid= -p "$pid" | tr -d ' ')
[[ $(ps -o comm= -p "$ppid" 2>/dev/null) == start-hyprland ]] && target=$ppid

echo "$(date +%T) blind-guard: no monitor on $sig (Hyprland $pid): ending session via pid $target${GITS_BLIND_DRYRUN:+ (dry run)}" >>"$log"
[[ -n ${GITS_BLIND_DRYRUN:-} ]] && exit 0
kill -TERM "$target"
exit 0
