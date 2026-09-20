#!/usr/bin/env bash
# CPU/platform power profile (power-profiles-daemon) + battery draw for the GitS bar.
#   gits-perf.sh              waybar JSON
#   gits-perf.sh next|prev    cycle performance -> balanced -> power-saver, refresh the bar (signal 9)
#   gits-perf.sh menu         rofi menu of the profiles
#   gits-perf.sh set <name>   set a profile
# ASUS laptops: asusd already switches the profile by itself on plug/unplug (`asusctl profile get` shows the AC and
# battery choices; ROG Control Center edits them). This module only shows the result and lets you override it.
profiles=(performance balanced power-saver)
cur=$(powerprofilesctl get 2>/dev/null); cur=${cur:-balanced}

meta() {  # profile -> "icon|SHORT|description"
    case $1 in
        performance) echo "󰓅|PERF|max clocks and fans, most heat and battery use" ;;
        balanced)    echo "󰾅|BAL|default: fast when needed, quiet when idle" ;;
        power-saver) echo "󰌪|SAVE|low clocks and fan noise, longest battery" ;;
        *)           echo "󰈸|${1^^}|$1" ;;
    esac
}
refresh() { pkill -RTMIN+9 -x waybar; }

case ${1:-} in
    next|prev)
        idx=0; for i in "${!profiles[@]}"; do [[ ${profiles[i]} == "$cur" ]] && idx=$i; done
        n=${#profiles[@]}
        [[ $1 == next ]] && idx=$(( (idx + 1) % n )) || idx=$(( (idx + n - 1) % n ))
        powerprofilesctl set "${profiles[idx]}" && refresh; exit 0 ;;
    set) powerprofilesctl set "${2:?profile}" && refresh; exit $? ;;
    menu)
        rows=()
        for p in "${profiles[@]}"; do
            IFS='|' read -r ic sh desc <<<"$(meta "$p")"
            mark="  "; [[ $p == "$cur" ]] && mark="● "
            rows+=("$(printf '%s%s  %-12s %s' "$mark" "$ic" "$p" "$desc")")
        done
        pick=$(printf '%s\n' "${rows[@]}" | gits-menu "󰓅  POWER PROFILE" "// 電力") || exit 0
        p=$(awk '{ for (i = 1; i <= NF; i++) if ($i == "performance" || $i == "balanced" || $i == "power-saver") { print $i; exit } }' <<<"$pick")
        [[ -n $p ]] && powerprofilesctl set "$p"
        refresh; exit 0 ;;
esac

IFS='|' read -r ic sh desc <<<"$(meta "$cur")"
ps=/sys/class/power_supply
bat=$(ls -d $ps/BAT* 2>/dev/null | head -1)
ac=$(cat $ps/A{C,DP}*/online 2>/dev/null | head -1)
status=$(cat "$bat/status" 2>/dev/null); cap=$(cat "$bat/capacity" 2>/dev/null)
uw=$(cat "$bat/power_now" 2>/dev/null || echo 0); watts=$(awk -v u="$uw" 'BEGIN{printf "%.1f", u/1e6}')
eta=""
if [[ -n $bat && $uw -gt 0 ]]; then
    en=$(cat "$bat/energy_now" 2>/dev/null || echo 0); ef=$(cat "$bat/energy_full" 2>/dev/null || echo 0)
    case $status in
        Discharging) eta=$(awk -v e="$en" -v p="$uw" 'BEGIN{h=e/p; printf "%dh %02dm left", h, (h-int(h))*60}') ;;
        Charging)    eta=$(awk -v e="$en" -v f="$ef" -v p="$uw" 'BEGIN{h=(f-e)/p; printf "%dh %02dm to full", h, (h-int(h))*60}') ;;
    esac
fi
src="battery"; [[ $ac == 1 ]] && src="AC power"
tip=$(printf 'POWER PROFILE  %s\n──────────────────────────\n%s\n\nSOURCE  %s\nDRAW    %s W  (%s)\n%s\nclick: control panel · right: profile menu · scroll: cycle' \
    "$cur" "$desc" "$src" "$watts" "${status:-?} ${cap:+$cap%}" "${eta:+ETA     $eta
}")
jq -nc --arg text "$(printf '\U000F0493')" --arg tip "$tip" --arg cls "$cur" '{text:$text, tooltip:$tip, class:$cls}'
