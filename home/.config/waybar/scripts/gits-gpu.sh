#!/usr/bin/env bash
# GPU temperature. Shows the discrete NVIDIA card only while it is already awake
# (querying a suspended dGPU with nvidia-smi would wake it and burn battery),
# otherwise the always-on AMD iGPU.
hw() { local d; for d in /sys/class/hwmon/hwmon*; do [[ $(<"$d/name") == "$1" ]] && { echo "$d"; return; }; done; }
milli() { [[ -r $1 ]] && echo $(( $(<"$1") / 1000 )); }

igpu=$(milli "$(hw amdgpu)/temp1_input")
ibusy=$(cat /sys/class/drm/card*/device/gpu_busy_percent 2>/dev/null | head -1)

dstate=""; dtemp=""; dinfo=""
for d in /sys/bus/pci/devices/*; do
    [[ $(<"$d/vendor") == 0x10de && $(<"$d/class") == 0x03* ]] || continue
    dstate=$(<"$d/power/runtime_status")
    if [[ $dstate == active ]]; then
        dinfo=$(nvidia-smi --query-gpu=name,temperature.gpu,utilization.gpu,power.draw,memory.used,memory.total \
                --format=csv,noheader,nounits 2>/dev/null)
        IFS=',' read -r dname dtemp dutil dpow dmu dmt <<<"$dinfo"
        dtemp=${dtemp// /}
    fi
    break
done

shown=${igpu:-0}; src=iGPU
if [[ -n $dtemp ]]; then shown=$dtemp; src=dGPU; fi
cls=normal; (( shown >= 80 )) && cls=warning; (( shown >= 90 )) && cls=critical

tip=$(printf 'iGPU  AMD Radeon (always on)\n──────────────────────────\nTEMP   %s°C\nBUSY   %s%%' "${igpu:-?}" "${ibusy:-?}")
if [[ -n $dtemp ]]; then
    tip+=$(printf '\n\ndGPU  %s\n──────────────────────────\nTEMP   %s°C\nUSAGE  %s%%\nPOWER  %s W\nVRAM   %s / %s MiB' \
        "${dname# }" "$dtemp" "${dutil// /}" "${dpow// /}" "${dmu// /}" "${dmt// /}")
elif [[ -n $dstate ]]; then
    tip+=$'\n\ndGPU  NVIDIA — asleep (not polled to save power)'
fi

jq -nc --arg text "$(printf '󰢮 %s°C' "$shown")" --arg tip "$tip" --arg cls "$cls" \
    '{text:$text, tooltip:$tip, class:$cls}'
