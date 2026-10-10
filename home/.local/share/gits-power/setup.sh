#!/usr/bin/env bash
# Battery safety net: run with `sudo ./setup.sh`. UPower ships disabled on CachyOS and is only D-Bus activated now and
# then, so nothing acts when the battery runs dry and the laptop just loses power (Oct 10 2026: twice in one evening,
# the battery holds ~9.5 of its 62 Wh). This makes upowerd run all the time and power the machine off cleanly at 8 %.
# The desktop warnings at 25 % and 12 % come from gits-events. There is no disk swap (zram only), so no hibernate:
# CriticalPowerAction=PowerOff is what "Auto" would pick anyway, it is spelled out so a later swap file changes nothing.
#   ./setup.sh --revert   removes the drop-in and disables upower again
set -euo pipefail
[[ $EUID -eq 0 ]] || { echo "run with sudo" >&2; exit 1; }
command -v upower >/dev/null || { echo "upower is not installed (pacman -S upower)" >&2; exit 1; }
conf=/etc/UPower/UPower.conf.d/70-gits-battery.conf

if [[ ${1:-} == --revert ]]; then
    rm -f "$conf"
    systemctl disable --now upower.service
    echo "upower policy removed"; exit 0
fi

mkdir -p "${conf%/*}"
install -m 644 "$(dirname "$(readlink -f "$0")")/70-gits-battery.conf" "$conf"
systemctl enable upower.service
systemctl restart upower.service
echo "upower: $(systemctl is-active upower.service), poweroff at $(sed -n 's/^PercentageAction=//p' "$conf")%"
