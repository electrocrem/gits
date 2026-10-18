#!/usr/bin/env bash
# YubiKey (FIDO2 / U2F, pam_u2f) for this desktop: run with `sudo ./setup.sh` after registering your key once:
#   mkdir -p ~/.config/Yubico && pamu2fcfg > ~/.config/Yubico/u2f_keys      (touch the key when it blinks)
# What you get:
#   login screen (SDDM) and lock screen (hyprlock): password AND a key touch, in that order: type the password, Enter, then
#   touch the blinking key (switch off for a while: yubikey-mode off 8h)
#   sudo and the polkit password dialogs:            a touch INSTEAD of the password; without the key, the password as before
#   hints everywhere the key is waited for: "touch / insert the key" on the lock screen (gits-lock-u2f label), under the
#   login field (SDDM), a notification for sudo / polkit; pam_u2f's own cue in a terminal
# The text console (Ctrl+Alt+F3) never asks for the key: that is the way back in if the key is lost while locked.
#   ./setup.sh --revert   removes every line this added (the key is then not used anywhere) and the helpers
# Lines it writes end in "# gits-yubikey"; re-running replaces them (and any older pam_u2f line in these four files).
set -euo pipefail
[[ $EUID -eq 0 ]] || { echo "run with sudo" >&2; exit 1; }
SRC=$(dirname "$(readlink -f "$0")")
USR=${SUDO_USER:-}
LOCK=(/etc/pam.d/sddm /etc/pam.d/hyprlock)
ELEVATE=(/etc/pam.d/sudo /etc/pam.d/polkit-1)
CUE='[cue_prompt=◈ Коснитесь YubiKey]'

strip() {   # drop our lines and any other pam_u2f line (an older hand-made setup)
    sed -i -E '/# gits-yubikey$/d; /yubikey-mode-check|gits-u2f-hint/d; /^[[:space:]]*auth[[:space:]].*pam_u2f\.so/d' "$1"
}
insert_after_last() {   # FILE TYPE TEXT: put TEXT below the last "TYPE" line
    local f=$1 type=$2 tmp
    tmp=$(mktemp)
    BLOCK="$3" awk -v t="$type" '{ line[NR] = $0; if ($1 == t) last = NR } END { for (i = 1; i <= NR; i++) { print line[i]; if (i == last) print ENVIRON["BLOCK"] } if (!last) print ENVIRON["BLOCK"] }' "$f" >"$tmp"
    cat "$tmp" >"$f"; rm -f "$tmp"
}
insert_before_first() {   # FILE TYPE TEXT: put TEXT above the first "TYPE" line
    local f=$1 type=$2 text=$3 tmp
    tmp=$(mktemp)
    BLOCK="$text" awk -v t="$type" '!done && $1 == t { print ENVIRON["BLOCK"]; done = 1 } { print } END { if (!done) print ENVIRON["BLOCK"] }' "$f" >"$tmp"
    cat "$tmp" >"$f"; rm -f "$tmp"
}

if [[ ${1:-} == --revert ]]; then
    for f in "${LOCK[@]}" "${ELEVATE[@]}"; do [[ -f $f ]] && strip "$f"; done
    [[ -f /etc/pam.d/polkit-1 ]] && cmp -s <(grep -v '^#' /etc/pam.d/polkit-1) <(grep -v '^#' /usr/lib/pam.d/polkit-1) && rm -f /etc/pam.d/polkit-1
    rm -f /usr/local/bin/yubikey-mode /usr/local/bin/yubikey-mode-check /usr/local/bin/gits-u2f-hint /etc/yubikey-mode/off
    rmdir /etc/yubikey-mode 2>/dev/null || true
    echo "YubiKey: removed from sddm, hyprlock, sudo, polkit"; exit 0
fi

command -v pamu2fcfg >/dev/null || { echo "pam-u2f is not installed (pacman -S pam-u2f)" >&2; exit 1; }
keys=$(getent passwd "${USR:-root}" | cut -d: -f6)/.config/Yubico/u2f_keys
[[ -n $USR && -s $keys ]] || { echo "no registered key in $keys: run  pamu2fcfg > ~/.config/Yubico/u2f_keys  as yourself first" >&2; exit 1; }

for f in yubikey-mode yubikey-mode-check gits-u2f-hint; do install -m 755 -o root -g root "$SRC/$f" "/usr/local/bin/$f"; done
[[ -f /etc/pam.d/polkit-1 ]] || install -m 644 /usr/lib/pam.d/polkit-1 /etc/pam.d/polkit-1   # our copy wins over the vendor file

for f in "${LOCK[@]}"; do
    [[ -f $f ]] || continue
    cp -n "$f" "$f.bak-pre-gits-yubikey"
    strip "$f"
    # after the password lines: hyprlock starts PAM as soon as it locks, and a pam_u2f placed first gives up after a few
    # seconds without a touch, so the next password attempt would fail anyway. Password first, then the touch, is natural.
    insert_after_last "$f" auth "auth       [success=ignore default=2]  pam_exec.so quiet /usr/local/bin/yubikey-mode-check   # gits-yubikey
auth       optional     pam_exec.so quiet stdout /usr/local/bin/gits-u2f-hint begin   # gits-yubikey
auth       required     pam_u2f.so cue $CUE   # gits-yubikey
auth       optional     pam_exec.so quiet /usr/local/bin/gits-u2f-hint end   # gits-yubikey"
done
for f in "${ELEVATE[@]}"; do
    [[ -f $f ]] || continue
    cp -n "$f" "$f.bak-pre-gits-yubikey"
    strip "$f"
    insert_before_first "$f" auth "auth       optional     pam_exec.so quiet /usr/local/bin/gits-u2f-hint begin   # gits-yubikey
auth       sufficient   pam_u2f.so cue nouserok $CUE   # gits-yubikey
auth       optional     pam_exec.so quiet /usr/local/bin/gits-u2f-hint end   # gits-yubikey"
    # a touch ends "auth" at pam_u2f (sufficient), so the notification is closed from "account", which always follows
    insert_before_first "$f" account "account    optional     pam_exec.so quiet /usr/local/bin/gits-u2f-hint end   # gits-yubikey"
done
for f in "${LOCK[@]}" "${ELEVATE[@]}"; do [[ -f $f ]] && { echo "== $f"; grep -nE '^(auth|account)' "$f" | head -8; }; done
/usr/local/bin/yubikey-mode
