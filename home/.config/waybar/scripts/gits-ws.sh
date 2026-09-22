#!/usr/bin/env bash
# One workspace button of the bar: custom/gits-ws<N> runs `gits-ws.sh N` (waybar's own hyprland/workspaces is not used:
# waybar 0.15 switches workspaces with the old `dispatch workspace N`, which a Lua Hyprland config rejects, so its clicks did nothing).
# Prints a waybar JSON line whenever the workspace changes: empty (= hidden) while it does not exist, or, with several monitors,
# when it lives on another one than this bar's ($WAYBAR_OUTPUT_NAME). class: active = focused, visible = shown on its monitor.
n=${1:?usage: gits-ws.sh <workspace number>}
out=${WAYBAR_OUTPUT_NAME:-}
sock=${XDG_RUNTIME_DIR:-/run/user/$UID}/hypr/${HYPRLAND_INSTANCE_SIGNATURE:-}/.socket2.sock
last=

emit() {
    local j
    j=$({ hyprctl -j workspaces; hyprctl -j monitors; } 2>/dev/null | jq -sc --argjson n "$n" --arg out "$out" '
        (.[0] | map(select(.id == $n)) | first) as $ws | .[1] as $mons
        | if $ws == null or ($out != "" and ($mons | length) > 1 and $ws.monitor != $out) then {text: ""}
          else
            ($mons | map(select(.focused)) | first | .activeWorkspace.id) as $foc
            | ($mons | map(select(.name == $ws.monitor)) | first | .activeWorkspace.id) as $vis
            | {text: ($n | tostring),
               class: (if $foc == $n then "active" elif $vis == $n then "visible" else "idle" end),
               tooltip: "workspace \($n) · \($ws.windows) window\(if $ws.windows == 1 then "" else "s" end)"}
          end') || return
    [[ $j != "$last" ]] && { printf '%s\n' "$j"; last=$j; }
}

while :; do
    emit
    # re-check on the events that can change a workspace button; reconnect if Hyprland restarts
    socat -u "UNIX-CONNECT:$sock" - 2>/dev/null | while IFS= read -r ev; do
        case ${ev%%>>*} in
            workspace | workspacev2 | focusedmon | focusedmonv2 | createworkspace | createworkspacev2 | destroyworkspace | destroyworkspacev2 | \
                moveworkspace | moveworkspacev2 | openwindow | closewindow | movewindow | movewindowv2 | monitoradded | monitoraddedv2 | monitorremoved | monitorremovedv2) emit ;;
        esac
    done
    sleep 1
done
