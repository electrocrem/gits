#!/usr/bin/env bash
# gits-widgets launcher.   run.sh [start|stop|restart|toggle]      (default: start)
# One instance per Wayland session: an instance left over from a dead compositor (other WAYLAND_DISPLAY) is replaced.
dir=$(cd "$(dirname "$0")" && pwd)
pidfile=${XDG_RUNTIME_DIR:-/tmp}/gits-widgets.pid

running() {  # running [display]: pid of our instance, optionally only if it is bound to that display
    local pid disp
    pid=$(cat "$pidfile" 2>/dev/null) || return 1
    [[ $pid =~ ^[0-9]+$ ]] && grep -qa 'widgets.py' "/proc/$pid/cmdline" 2>/dev/null || return 1
    if [[ -n ${1:-} ]]; then
        disp=$(tr '\0' '\n' <"/proc/$pid/environ" 2>/dev/null | sed -n 's/^WAYLAND_DISPLAY=//p')
        [[ $disp == "$1" ]] || return 1
    fi
    echo "$pid"
}
stop() { local pid; pid=$(running) && { kill "$pid"; for _ in {1..20}; do kill -0 "$pid" 2>/dev/null || break; sleep 0.1; done; }; rm -f "$pidfile"; }

case ${1:-start} in
    stop) stop ;;
    restart) stop; exec "$0" start ;;
    toggle) if running >/dev/null; then stop; else exec "$0" start; fi ;;
    start)
        running "${WAYLAND_DISPLAY:-}" >/dev/null && exit 0
        stop
        python3 "$dir/widgets.py" >"${XDG_RUNTIME_DIR:-/tmp}/gits-widgets.log" 2>&1 &
        echo $! >"$pidfile"
        ;;
    *) echo "usage: $0 [start|stop|restart|toggle]" >&2; exit 2 ;;
esac
