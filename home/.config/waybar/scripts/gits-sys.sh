#!/usr/bin/env bash
# One compact "system" module for the bar: CPU usage + temperature as the text, everything else in the tooltip
# (CPU details and fans from gits-cpu.sh, iGPU/dGPU from gits-gpu.sh, RAM and swap). Replaces three modules.
d=$(dirname "$0")
cpu=$("$d/gits-cpu.sh"); gpu=$("$d/gits-gpu.sh")
text=$(jq -r '.text' <<<"$cpu" | sed 's/°C/°/; s/  */ /g')
ctip=$(jq -r '.tooltip' <<<"$cpu"); gtip=$(jq -r '.tooltip' <<<"$gpu")
rank() { case $1 in critical) echo 2 ;; warning) echo 1 ;; *) echo 0 ;; esac; }
cc=$(jq -r '.class' <<<"$cpu"); gc=$(jq -r '.class' <<<"$gpu")
cls=$cc; (( $(rank "$gc") > $(rank "$cc") )) && cls=$gc
read -r rt ra st sf < <(awk '/^MemTotal/{t=$2} /^MemAvailable/{a=$2} /^SwapTotal/{st=$2} /^SwapFree/{sf=$2} END{print t, a, st, sf}' /proc/meminfo)
ram=$(awk -v t="$rt" -v a="$ra" -v st="$st" -v sf="$sf" 'BEGIN{u=(t-a)/1048576; printf "RAM   %.1f / %.1f GiB  (%d%%)\nSWAP  %.1f / %.1f GiB", u, t/1048576, (t-a)*100/t, (st-sf)/1048576, st/1048576}')
jq -nc --arg text "$text" --arg tip "$ctip"$'\n\n'"$gtip"$'\n\n'"$ram"$'\n\nclick: system monitor' --arg cls "$cls" '{text:$text, tooltip:$tip, class:$cls}'
