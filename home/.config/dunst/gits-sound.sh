#!/usr/bin/env bash
# dunst rule script: a short blip for every popup that is really a message. A notification with the category gits.<name> (our own
# tools: screenshot, send to phone, YubiKey touch, game mode, low battery) plays that sound instead. Skipped: our other quiet
# messages ("GitS Notify"), the hidden original of a KDE Connect message (its cleaned "Phone" copy makes the sound instead) and low
# urgency chatter from tools that opt out. Critical popups get the error sound. Hooked in by dunstrc.d/55-gits-sound.conf.
case ${DUNST_CATEGORY:-} in gits.[a-z]*) exec gits-sound "${DUNST_CATEGORY#gits.}" ;; esac
case ${DUNST_APP_NAME:-} in "GitS Notify"|"KDE Connect") exit 0 ;; esac
case ${DUNST_URGENCY:-NORMAL} in CRITICAL) exec gits-sound error ;; esac
exec gits-sound notify
