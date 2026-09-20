#!/usr/bin/env bash
# Monochrome media-player status with a detailed tooltip.
status=$(playerctl status 2>/dev/null)
if [[ -z $status || $status == Stopped ]]; then
    jq -nc --arg text "$(printf '  NO SIGNAL')" '{text:$text, class:"idle", tooltip:"no active media player\nclick: play/pause"}'
    exit 0
fi
artist=$(playerctl metadata artist 2>/dev/null)
title=$(playerctl metadata title 2>/dev/null)
album=$(playerctl metadata album 2>/dev/null)
pos=$(playerctl metadata --format '{{duration(position)}}' 2>/dev/null)
len=$(playerctl metadata --format '{{duration(mpris:length)}}' 2>/dev/null)
name=$(playerctl metadata --format '{{playerName}}' 2>/dev/null)
line="${artist:+$artist – }$title"
(( ${#line} > 38 )) && short="${line:0:37}…" || short=$line
if [[ $status == Playing ]]; then icon=$''; cls=playing; else icon=$''; cls=paused; fi
tip=$(printf '%s\n%s\n%s\n──────────────────────\n%s / %s   [%s]\nclick: pause · right: next · middle: prev' \
    "${title:-?}" "${artist:-unknown artist}" "${album:-—}" "${pos:-0:00}" "${len:-?}" "${name:-player}")
jq -nc --arg text "$icon  $short" --arg cls "$cls" --arg tip "$tip" '{text:$text, class:$cls, tooltip:$tip}'
