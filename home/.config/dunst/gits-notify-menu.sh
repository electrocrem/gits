#!/usr/bin/env bash
# dunst's action menu (click a popup -> context menu) through rofi, Ghost in the Shell style.
# dunst feeds lines like "#Reply (Telegram) [226,inline-reply]"; only the readable middle is shown, rofi still
# returns the whole line. Options given on the command line only: rofi ignores display-columns in the theme file.
# Style: ~/.config/rofi/themes/notification.rasi. Hooked in by ~/.config/dunst/dunstrc.d/50-gits-menu.conf.
gits-catcher start
/usr/bin/rofi -config notification -dmenu -p dunst: \
    -display-columns 2 -display-column-separator '^#|\s\[[^]]*\]$' "$@"
rc=$?
gits-catcher stop
exit $rc
