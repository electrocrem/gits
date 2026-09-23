#!/usr/bin/env bash
# Pending updates (repo + AUR) from `gits-update --check`; hidden when there are none. Click opens gits-update.
out=$(gits-update --check 2>/dev/null | tail -1)
repo=$(sed -n 's/.*repo: \([0-9]*\).*/\1/p' <<<"$out"); aur=$(sed -n 's/.*aur: \([0-9]*\).*/\1/p' <<<"$out")
n=$(( ${repo:-0} + ${aur:-0} ))
(( n == 0 )) && { echo '{"text":""}'; exit 0; }
cls=normal; (( n >= 50 )) && cls=warning
jq -nc --arg text "󰚰 $n" --arg tip "$(printf 'UPDATES\n──────────\nREPO  %s\nAUR   %s\n\nclick: update the system' "${repo:-0}" "${aur:-0}")" --arg cls "$cls" \
    '{text:$text, tooltip:$tip, class:$cls}'
