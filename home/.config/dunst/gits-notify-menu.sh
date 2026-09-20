#!/usr/bin/env bash
# dunst's action menu (click a popup -> context menu) in the Ghost in the Shell style (a GTK popup: gits-menu).
# dunst feeds lines like "#Reply (Telegram) [226,inline-reply]" and wants the WHOLE chosen line back. The menu shows only the
# readable part ("Reply (Telegram)") and this script maps the choice back to the original line.
# Hooked in by ~/.config/dunst/dunstrc.d/50-gits-menu.conf.
mapfile -t lines
disp=()
for l in "${lines[@]}"; do
    d=${l#\#}
    disp+=("$(sed -E 's/[[:space:]]*\[[^]]*\]$//' <<<"$d")")
done
idx=$(printf '%s\n' "${disp[@]}" | gits-menu "󰂚  NOTIFICATION" "// 通知" -format i) || exit 1
printf '%s\n' "${lines[idx]}"
