#!/usr/bin/env bash
# Btrfs snapshots for the root subvolume, the safety net under all the theming: run with `sudo ./setup.sh`.
# What is already there (CachyOS): snapper config "root", snap-pac (a before/after snapshot around every pacman
# transaction), grub-btrfs with grub-btrfs-snapper.path (snapshots show up in the GRUB menu), /boot inside the root
# subvolume (so a snapshot carries its own kernel). What this adds:
#   - hourly/daily snapshots (timeline: 5 hourly + 7 daily kept) and the boot-time cleanup timer
#   - one labelled baseline snapshot of the working GitS setup
#   - a GRUB menu refresh so the new snapshots are bootable
# Rolling back: pick "Arch Linux snapshots" in GRUB, boot the snapshot, then `sudo snapper -c root rollback` (or
# btrfs-assistant). /home is a separate subvolume and is NOT rolled back (the dotfiles live in ~/gits-hyde on GitHub).
#   ./setup.sh --revert   turns the timeline off again (snapshots stay until snapper's cleanup removes them)
set -euo pipefail
[[ $EUID -eq 0 ]] || { echo "run with sudo" >&2; exit 1; }
command -v snapper >/dev/null || { echo "snapper is not installed" >&2; exit 1; }

if [[ ${1:-} == --revert ]]; then
    snapper -c root set-config TIMELINE_CREATE=no
    systemctl disable --now snapper-timeline.timer
    echo "timeline snapshots off"; exit 0
fi

snapper -c root get-config >/dev/null 2>&1 || snapper -c root create-config /
snapper -c root set-config TIMELINE_CREATE=yes TIMELINE_CLEANUP=yes \
    TIMELINE_LIMIT_HOURLY=5 TIMELINE_LIMIT_DAILY=7 TIMELINE_LIMIT_WEEKLY=0 TIMELINE_LIMIT_MONTHLY=0 TIMELINE_LIMIT_YEARLY=0
systemctl enable --now snapper-timeline.timer snapper-cleanup.timer
systemctl enable --now grub-btrfs-snapper.path 2>/dev/null || true

snapper -c root create -t single -c number -d "GitS baseline: setup working ($(date +%F))"
if [[ -x /etc/grub.d/41_snapshots-btrfs ]] && command -v grub-mkconfig >/dev/null; then
    grub-mkconfig -o /boot/grub/grub.cfg 2>&1 | tail -3
fi
echo; snapper -c root list | tail -6
echo; systemctl list-timers 'snapper-*' --no-pager | head -5
