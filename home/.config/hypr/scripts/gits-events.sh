#!/usr/bin/env bash
# gits-events: UI sounds for session events, one small background loop (started from gits.lua on login).
#   login   played once when the daemon starts        plug / unplug   mains power connected / removed
#   lock / unlock   hyprlock appears / disappears
#   layout   the new keyboard layout on the GitS OSD on every switch (no sound)
#   game      while a Steam game runs: the gaming workflow, gamemode for the game, notifications paused; all back when it ends
#             (the game is the "reaper SteamLaunch AppId=N" process Steam starts it under). Off: GITS_AUTO_GAMEMODE=0
#   battery   a warning at 25 % and a critical one at 12 % while discharging (the charge limit of an ASUS keeps it near 98 %, that is not a warning);
#             early because the worn battery holds ~9.5 Wh, and upowerd powers off at 8 % (~/.local/share/gits-power/setup.sh)
# Mute everything: `gits-sound off`. Single instance (flock). Polls every 2 s: two file reads and two pgreps.
exec 9>"${XDG_RUNTIME_DIR:-/tmp}/gits-events.lock"
flock -n 9 || exit 0
echo $$ >"${XDG_RUNTIME_DIR:-/tmp}/gits-events.pid"   # install.sh restarts a running copy so a new version takes effect without a re-login

ac=""
for d in /sys/class/power_supply/*; do
    [[ $(cat "$d/type" 2>/dev/null) == Mains ]] && { ac=$d/online; break; }
done
last_ac=$(cat "$ac" 2>/dev/null)
locked=0
pgrep -x hyprlock >/dev/null && locked=1
warned=0

[[ -n ${GITS_EVENTS_NO_LOGIN:-} ]] || gits-sound login

# auto game mode (see the header): remembers what it changed and puts back only that
game_pid="" game_prev="" game_paused=0
game_name() {   # the game's name from its Steam app manifest (any library folder), else "AppId N"
    local id f
    id=$(tr '\0' ' ' <"/proc/$1/cmdline" 2>/dev/null | grep -oP 'AppId=\K[0-9]+')
    for f in "$HOME"/.local/share/Steam/steamapps "$HOME"/.var/app/com.valvesoftware.Steam/.local/share/Steam/steamapps \
             $(grep -oP '"path"\s+"\K[^"]+' "$HOME/.local/share/Steam/steamapps/libraryfolders.vdf" 2>/dev/null | sed 's|$|/steamapps|'); do
        [[ -r $f/appmanifest_$id.acf ]] && { sed -nE 's/^\s*"name"\s*"(.*)"/\1/p' "$f/appmanifest_$id.acf" | head -1; return; }
    done
    echo "AppId $id"
}
gamemode() {   # RegisterGame / UnregisterGame for $game_pid over D-Bus (returns at once; `gamemoded -r PID` would block this loop)
    command -v gamemoded >/dev/null || return 0
    timeout 5 gdbus call --session --dest com.feralinteractive.GameMode --object-path /com/feralinteractive/GameMode \
        --method "com.feralinteractive.GameMode.$1" "$game_pid" >/dev/null 2>&1
}
game_on() {
    game_pid=$1
    local name; name=$(game_name "$1")
    game_prev=$(gits-workflow current 2>/dev/null)
    [[ $game_prev == gaming ]] || gits-workflow set gaming >/dev/null 2>&1
    gamemode RegisterGame
    notify-send -a "GitS Notify" -c gits.game -i applications-games -r 32 "󰊴  Game mode" "$name: gaming workflow, gamemode, notifications paused until you quit"
    if [[ $(dunstctl is-paused 2>/dev/null) == false ]]; then sleep 3; dunstctl set-paused true; game_paused=1; fi
}
game_off() {
    gamemode UnregisterGame   # gamemoded drops a dead pid by itself too; this is for when the game outlives this check
    [[ -n $game_prev && $game_prev != gaming && $(gits-workflow current 2>/dev/null) == gaming ]] && gits-workflow set "$game_prev" >/dev/null 2>&1
    local missed=0
    if ((game_paused)); then missed=$(dunstctl count waiting 2>/dev/null || echo 0); dunstctl set-paused false; fi
    notify-send -a "GitS Notify" -i applications-games -r 32 "󰊴  Game mode off" "workflow ${game_prev:-unchanged}$( ((missed)) && echo ", $missed notification(s) while you played")"
    game_pid="" game_prev="" game_paused=0
}

# layout OSD: the new keyboard layout on the GitS OSD (bottom centre, like volume) on every switch
# (caps lock, Super+K, bar click). Event-driven over socket2; Hyprland sends "activelayout" once per keyboard,
# so repeats are dropped. Turn off with GITS_EVENTS_NO_LAYOUT=1.
sock="$XDG_RUNTIME_DIR/hypr/$HYPRLAND_INSTANCE_SIGNATURE/.socket2.sock"
if [[ -z ${GITS_EVENTS_NO_LAYOUT:-} && -S $sock ]] && command -v socat >/dev/null && command -v gits-osd >/dev/null; then
    (
        kbd() { hyprctl devices -j 2>/dev/null | jq -r '[.keyboards[] | select(.main)][0] // empty
            | "\(.active_layout_index) \(.layout | split(",") | map(if . == "us" or . == "gb" then "EN" else ascii_upcase end) | join(","))"'; }
        last=$(hyprctl devices -j 2>/dev/null | jq -r '[.keyboards[] | select(.main)][0].active_keymap // empty')
        socat -U - "UNIX-CONNECT:$sock" 2>/dev/null | while IFS= read -r line; do
            [[ $line == activelayout'>>'* ]] || continue
            name=${line##*,}
            [[ $name == "$last" || $name == error ]] && continue
            last=$name
            read -r idx codes < <(kbd)
            [[ $idx =~ ^[0-9]+$ ]] && gits-osd layout "$idx" 0 "$codes"
        done
    ) &
    listener=$!
    trap 'pkill -P "$listener" 2>/dev/null; kill "$listener" 2>/dev/null; exit 0' TERM INT   # take the socket reader along
fi

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
            if (( pct <= 12 && warned < 2 )); then
                notify-send -a GitS -u critical -i battery-empty -r 31 "Battery critical" "${pct}%: plug in the charger, the laptop powers off at 8%"; warned=2
            elif (( pct <= 25 && warned < 1 )); then
                notify-send -a GitS -u normal -c gits.battery -i battery-caution -r 31 "Battery low" "${pct}% left (a few minutes on this battery)"; warned=1
            fi
        else
            warned=0
        fi
    fi
    if [[ ${GITS_AUTO_GAMEMODE:-1} != 0 ]]; then
        gp=$(pgrep -o -f 'SteamLaunch AppId=[0-9]+')
        if [[ -n $gp && -z $game_pid ]]; then game_on "$gp"
        elif [[ -z $gp && -n $game_pid ]]; then game_off; fi
    fi
    if pgrep -x hyprlock >/dev/null; then
        (( locked )) || { gits-sound lock; locked=1; }
    elif (( locked )); then
        gits-sound unlock; locked=0
    fi
done
