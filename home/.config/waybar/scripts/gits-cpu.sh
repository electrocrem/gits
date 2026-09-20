#!/usr/bin/env bash
# CPU usage + package temperature (k10temp) with a detailed tooltip, monochrome.
hw() { local d; for d in /sys/class/hwmon/hwmon*; do [[ $(<"$d/name") == "$1" ]] && { echo "$d"; return; }; done; }
milli() { [[ -r $1 ]] && echo $(( $(<"$1") / 1000 )); }

# usage: delta of /proc/stat since the previous call
state=${XDG_RUNTIME_DIR:-/tmp}/gits-cpu.stat
read -r _ u n s i w q sq _ < /proc/stat
total=$((u + n + s + i + w + q + sq)); idle=$((i + w)); usage=0
if [[ -r $state ]]; then
    read -r pt pi <"$state"
    dt=$((total - pt)); di=$((idle - pi))
    (( dt > 0 )) && usage=$(( 100 * (dt - di) / dt ))
fi
echo "$total $idle" >"$state"

k=$(hw k10temp); temp=$(milli "$k/temp1_input"); temp=${temp:-0}
g=$(hw amdgpu);  gpu=$(milli "$g/temp1_input")
f=$(hw asus)
fan1=$(cat "$f/fan1_input" 2>/dev/null); fan2=$(cat "$f/fan2_input" 2>/dev/null)
ghz=$(cat /sys/devices/system/cpu/cpu*/cpufreq/scaling_cur_freq 2>/dev/null | awk '{s+=$1;n++} END{if(n) printf "%.2f", s/n/1e6}')
model=$(awk -F': ' '/model name/{print $2; exit}' /proc/cpuinfo)
load=$(cut -d' ' -f1-3 /proc/loadavg)

cls=normal; (( temp >= 75 )) && cls=warning; (( temp >= 88 )) && cls=critical
tip=$(printf '%s\n──────────────────────────\nUSAGE  %s%%\nTEMP   %s°C\nFREQ   %s GHz\nLOAD   %s' "$model" "$usage" "$temp" "${ghz:-?}" "$load")
[[ -n $gpu ]]  && tip+=$(printf '\nGPU    %s°C' "$gpu")
[[ -n $fan1 ]] && tip+=$(printf '\nFAN    CPU %s rpm' "$fan1")
[[ -n $fan2 ]] && tip+=$(printf ' / GPU %s rpm' "$fan2")

jq -nc --arg text "$(printf ' %02d%%  %s°C' "$usage" "$temp")" --arg tip "$tip" --arg cls "$cls" \
    '{text:$text, tooltip:$tip, class:$cls}'
