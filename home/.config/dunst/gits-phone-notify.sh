#!/usr/bin/env bash
# dunst rule script for KDE Connect: shows a clean copy of a phone notification instead of the original.
# KDE Connect sends the body HTML-escaped ("&lt;b&gt;hi&lt;/b&gt;&lt;br/&gt;"), which dunst prints literally and cannot
# strip. Here: unescape, <br> -> newline, drop tags, cut to 6 lines / 240 chars, then re-send under the app name "Phone"
# (a new one, so the rule cannot loop). The newest message replaces the previous one (stack tag).
# Trade-off: the copy has no Reply / Mark-as-read buttons; the original stays in the history (dunstctl history-pop).
# Hooked in by ~/.config/dunst/dunstrc.d/60-gits-kdeconnect.conf.
summary=${DUNST_SUMMARY:-}
body=${DUNST_BODY:-}
clean=$(GITS_BODY=$body python3 - <<'PY'
import html, os, re
t = html.unescape(os.environ.get("GITS_BODY", ""))
t = re.sub(r"(?i)<br\s*/?>", "\n", t)
t = re.sub(r"<[^>]+>", "", t)                       # remaining tags
t = html.unescape(t)
lines = [l.strip() for l in t.splitlines() if l.strip()][:6]
t = "\n".join(lines)
if len(t) > 240:
    t = t[:239].rstrip() + "…"
print(html.escape(t, quote=False))                  # dunst renders markup: keep a stray "<" literal
PY
)
(notify-send -a "Phone" -u low -t 8000 -i smartphone \
    -h string:x-dunst-stack-tag:gits-phone "$(python3 -c 'import html,sys;print(html.escape(html.unescape(sys.argv[1]),quote=False))' "$summary")" "$clean" &) >/dev/null 2>&1
