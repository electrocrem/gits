#!/usr/bin/env bash
# Removes the "error: commands/loadenv.c:check_blocklists:289:sparse file not allowed. / Press any key to continue"
# GRUB screen. Cause: GRUB_DEFAULT=saved + GRUB_SAVEDEFAULT=true make every menu entry run `savedefault`
# (= save_env saved_entry), but /boot/grub/grubenv lives on btrfs and GRUB cannot write blocklist files there.
# Trade-off: GRUB no longer remembers the last chosen entry; it always boots entry 0 (the default kernel).
#
#   sudo ~/.local/share/gits-boot/fix-grub-savedefault.sh          apply
#   sudo ~/.local/share/gits-boot/fix-grub-savedefault.sh --revert restore the backup and regenerate
set -euo pipefail
[[ $EUID -eq 0 ]] || { echo "run with sudo" >&2; exit 1; }

CFG=/etc/default/grub
BAK=/etc/default/grub.bak-pre-savedefault

if [[ ${1:-} == --revert ]]; then
    [[ -f $BAK ]] || { echo "no backup at $BAK" >&2; exit 1; }
    cp -a "$BAK" "$CFG"
    grub-mkconfig -o /boot/grub/grub.cfg
    echo "reverted"; exit 0
fi

[[ -f $BAK ]] || cp -a "$CFG" "$BAK"
sed -i -E \
    -e 's/^GRUB_DEFAULT=.*/GRUB_DEFAULT=0/' \
    -e 's/^GRUB_SAVEDEFAULT=.*/GRUB_SAVEDEFAULT=false/' "$CFG"
grep -E '^GRUB_(DEFAULT|SAVEDEFAULT)=' "$CFG"

grub-mkconfig -o /boot/grub/grub.cfg

# Every entry ran `savedefault` before; none should now.
left=$(grep -c '^\s*savedefault' /boot/grub/grub.cfg || true)
echo "savedefault calls left in grub.cfg: $left"
[[ $left -eq 0 ]] && echo "OK: reboot and the error screen is gone" || echo "WARN: some entries still call savedefault (grub-btrfs snapshot entries?)"
