#!/usr/bin/env python3
"""Warm popups: one panel.py process kept loaded and connected to the display, waiting for the next popup.

    popupd.py serve              gits-panel.service: keeps one spare `panel.py spare` ready on $XDG_RUNTIME_DIR/gits-panel.sock
    popupd.py open [--log FILE] MODE [ARGS...]
                                 hand the popup to the spare (gits-menu; gits-panel speaks the same one-line JSON request through
                                 socat). Prints the popup's pid at once with --log (the popup writes there); without it the popup
                                 gets this process's stdin / stdout / stderr and the exit status of the popup is returned. The
                                 spare takes the caller's environment and working directory from /proc. Exit 75 = no spare (not
                                 running, stale code, other display): the caller starts panel.py the old way.

A cold popup spends ~0.2 s starting Python, importing GTK and connecting to the compositor before it builds anything. The spare has
done all that already; it takes ONE request and then is that popup (its own process, as before: closing it, killing it, its threads
and timers all go with it), while this supervisor starts the next spare. Forking a loaded process instead is not safe: importing GTK
starts threads (gdbus, gmain, fontconfig).
This file never imports GTK, so the client part stays a short Python start.
"""
import json
import os
import signal
import socket
import sys

RUN = os.environ.get("XDG_RUNTIME_DIR", "/tmp")
SOCK = os.path.join(RUN, "gits-panel.sock")
HERE = os.path.dirname(os.path.abspath(__file__))
TEMPFAIL = 75


def serve():
    import subprocess
    import time
    try:
        os.unlink(SOCK)
    except FileNotFoundError:
        pass
    lst = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    lst.bind(SOCK)
    lst.listen(16)
    env = dict(os.environ)
    ls_lib = "/usr/lib/libgtk4-layer-shell.so"
    if os.path.exists(ls_lib):   # panel.py would otherwise re-execute itself to get it
        env["LD_PRELOAD"] = (ls_lib + " " + env.get("LD_PRELOAD", "")).strip()
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))
    fails = 0
    while True:
        # the spare tells us on its stdout: "ready" once it waits on the socket, "taken" once it has a popup to show
        spare = subprocess.Popen([sys.executable, os.path.join(HERE, "panel.py"), "spare", str(lst.fileno())], env=env,
                                 pass_fds=(lst.fileno(),), stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True,
                                 start_new_session=True)
        ready = False
        for line in spare.stdout:
            if line.strip() == "ready":
                ready, fails = True, 0
            elif line.strip() == "taken":
                break
        spare.stdout.close()
        spare.stdin.close()   # its "popupd is gone" pipe: it is a popup now
        if not ready:   # died before it could serve (no display yet, broken code): back off instead of spinning
            fails += 1
            time.sleep(min(30, 2 * fails))


def open_popup(args):
    log = None
    if args[:1] == ["--log"]:
        log, args = os.path.abspath(args[1]), args[2:]
    try:
        c = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        c.settimeout(1.5)   # the next spare may still be starting: queued requests wait for it, a dead socket does not
        c.connect(SOCK)
        socket.send_fds(c, [json.dumps({"argv": args, "log": log}).encode() + b"\n"], [] if log else [0, 1, 2])
        f = c.makefile("r")
        first = f.readline().split()
    except OSError:
        return TEMPFAIL
    if first[:1] != ["pid"]:
        return TEMPFAIL   # "stale": the spare runs older code or another display
    pid = int(first[1])
    if log:
        print(pid)
        return 0
    c.settimeout(None)
    for sig in (signal.SIGTERM, signal.SIGINT, signal.SIGHUP):   # killing the client (gits-menu) closes the popup too
        signal.signal(sig, lambda s, _f: (os.kill(pid, signal.SIGTERM), os._exit(128 + s)))
    try:
        last = f.readline().split()
    except OSError:
        last = []
    return int(last[1]) if last[:1] == ["rc"] else 1


if __name__ == "__main__":
    cmd = sys.argv[1:2]
    if cmd == ["serve"]:
        serve()
    elif cmd == ["open"]:
        raise SystemExit(open_popup(sys.argv[2:]))
    else:
        print(__doc__.strip(), file=sys.stderr)
        raise SystemExit(2)
