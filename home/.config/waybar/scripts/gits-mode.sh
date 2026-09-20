#!/usr/bin/env bash
# Workflow ("operating mode") switcher for the GitS bar.
#   gits-mode.sh          print the current mode as waybar JSON
#   gits-mode.sh next|prev  cycle to the next / previous mode, then refresh the bar (signal 8)
# Modes are the workflow files of the Hyprland config: ~/.config/hypr/gits/workflows/*.lua (gits-workflow list)
modes=(01-default editing gaming powersaver snappy)


label() {  # key -> "icon|SHORT|Name|description"
    case $1 in
        01-default)  echo "󰄯|NORM|Default|balanced: theme blur, shadows, gaps and animations" ;;
        editing)     echo "󰏫|EDIT|Editing|no xray/blur, true colours for writing and colour picking" ;;
        gaming)      echo "󰊗|GAME|Gaming|no blur, shadows, gaps, animations or transparency" ;;
        powersaver)  echo "󰌪|ECO|Powersaver|no animations or effects, readable, saves power" ;;
        snappy)      echo "󰓅|SNAP|Snappy|no animations or effects, readable" ;;
        *)           echo "?|${1:-?}|${1:-unknown}|unknown workflow" ;;
    esac
}

cur=$(gits-workflow current 2>/dev/null); cur=${cur:-01-default}

if [[ $1 == next || $1 == prev ]]; then
    n=${#modes[@]}; idx=0
    for i in "${!modes[@]}"; do [[ ${modes[i]} == "$cur" ]] && idx=$i; done
    [[ $1 == next ]] && idx=$(( (idx + 1) % n )) || idx=$(( (idx + n - 1) % n ))
    gits-workflow set "${modes[idx]}" >/dev/null 2>&1   # refreshes the bar itself
    exit 0
fi

IFS='|' read -r icon short name desc <<<"$(label "$cur")"
tip="MODE  $name"$'\n'"$desc"$'\n──────────────────────'
for m in "${modes[@]}"; do
    IFS='|' read -r _i _s n _d <<<"$(label "$m")"
    [[ $m == "$cur" ]] && tip+=$'\n'"▸ $n" || tip+=$'\n'"  $n"
done
tip+=$'\n──────────────────────\nclick: next · scroll: next/prev · right: menu'
cls=${cur#*-}; [[ $cur == 01-default ]] && cls=default
jq -nc --arg text "$icon $short" --arg cls "$cls" --arg tip "$tip" '{text:$text, class:$cls, tooltip:$tip}'
