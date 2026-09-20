#!/usr/bin/env bash
# dunst rule script: HyDE announces volume / brightness / mute changes as popups ("46....", "muted", app "HyDE Notify").
# They are hidden (skip_display in 80-gits-osd.conf) and shown as the GitS on-screen display instead. The real value is
# read from the system, not parsed from the popup text.
summary=${DUNST_SUMMARY:-}; body=${DUNST_BODY:-}; icon=${DUNST_ICON_PATH:-}
if [[ $icon == *microphone* ]]; then kind=mic
elif [[ $body =~ (_bl[0-9]*$|backlight|acpi_video|nvidia_wmi) ]]; then kind=brightness
else kind=volume; fi
muted=0; pct=0
case $kind in
    volume|mic)
        src=@DEFAULT_AUDIO_SINK@; [[ $kind == mic ]] && src=@DEFAULT_AUDIO_SOURCE@
        out=$(wpctl get-volume "$src" 2>/dev/null)
        pct=$(awk '{printf "%d", $2 * 100 + 0.5}' <<<"$out")
        [[ $out == *MUTED* || $summary == muted ]] && muted=1 ;;
    brightness)
        pct=$(brightnessctl -m 2>/dev/null | cut -d, -f4 | tr -d %) ;;
esac
exec gits-osd "$kind" "${pct:-0}" "$muted"
