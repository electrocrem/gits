#!/usr/bin/env bash
# dunst rule script (dunstrc.d/70-gits-island.conf): hand the notification to the dynamic island (gits-island notify reads DUNST_*).
exec gits-island notify
