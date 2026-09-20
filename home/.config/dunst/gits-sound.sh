#!/usr/bin/env bash
# dunst rule script: a short blip for every popup that is really a message. Skipped: volume/brightness OSD ("HyDE
# Notify"), the hidden original of a KDE Connect message (its cleaned "Phone" copy makes the sound instead) and low urgency
# chatter from tools that opt out. Critical popups get the error sound. Hooked in by dunstrc.d/55-gits-sound.conf.
case ${DUNST_APP_NAME:-} in "HyDE Notify"|"KDE Connect") exit 0 ;; esac
case ${DUNST_URGENCY:-NORMAL} in CRITICAL) exec gits-sound error ;; esac
exec gits-sound notify
