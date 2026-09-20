#!/usr/bin/env bash
# Monochrome media-player status with a detailed tooltip.
status=$(gits-media status 2>/dev/null)
if [[ -z $status || $status == Stopped ]]; then
    jq -nc --arg text "$(printf '  NO SIGNAL')" '{text:$text, class:"idle", tooltip:"no active media player\nclick: player popup"}'
    exit 0
fi
artist=$(gits-media metadata artist 2>/dev/null)
title=$(gits-media metadata title 2>/dev/null)
album=$(gits-media metadata album 2>/dev/null)
pos=$(gits-media metadata --format '{{duration(position)}}' 2>/dev/null)
len=$(gits-media metadata --format '{{duration(mpris:length)}}' 2>/dev/null)
name=$(gits-media metadata --format '{{playerName}}' 2>/dev/null)
line="${artist:+$artist – }$title"
(( ${#line} > 38 )) && short="${line:0:37}…" || short=$line
if [[ $status == Playing ]]; then icon=$''; cls=playing; else icon=$''; cls=paused; fi
tip=$(printf '%s\n%s\n%s\n──────────────────────\n%s / %s   [%s]\nclick: player · middle: pause · right: next · scroll: prev/next' \
    "${title:-?}" "${artist:-unknown artist}" "${album:-—}" "${pos:-0:00}" "${len:-?}" "${name:-player}")
jq -nc --arg text "$icon  $short" --arg cls "$cls" --arg tip "$tip" '{text:$text, class:$cls, tooltip:$tip}'
