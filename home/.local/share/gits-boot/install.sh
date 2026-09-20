#!/usr/bin/env bash
# Install (or revert) the Ghost in the Shell boot themes: Plymouth splash + GRUB menu.
#   sudo ./install.sh            install
#   sudo ./install.sh --revert   back to the CachyOS plymouth theme and the Retroboot GRUB theme
set -euo pipefail
[[ $EUID -eq 0 ]] || { echo "run with sudo:  sudo $0 ${*:-}"; exit 1; }

NAME=ghost-in-the-shell
HERE=$(cd "$(dirname "$0")" && pwd)
PLY=/usr/share/plymouth/themes
GRUBT=/usr/share/grub/themes
CFG=/etc/default/grub

if [[ ${1:-} == --revert ]]; then
    if [[ -f $CFG.bak-pre-gits ]]; then cp -a "$CFG.bak-pre-gits" "$CFG"; echo "restored $CFG from backup"; fi
    plymouth-set-default-theme -R cachyos
    grub-mkconfig -o /boot/grub/grub.cfg
    echo "reverted (theme folders are left in place)"; exit 0
fi

[[ -d $HERE/staging/plymouth/$NAME && -d $HERE/staging/grub/$NAME ]] || { echo "run build.py first"; exit 1; }

echo "==> copying themes"
rm -rf "${PLY:?}/$NAME" "${GRUBT:?}/$NAME"
cp -r "$HERE/staging/plymouth/$NAME" "$PLY/$NAME"
cp -r "$HERE/staging/grub/$NAME" "$GRUBT/$NAME"
chown -R root:root "$PLY/$NAME" "$GRUBT/$NAME"
find "$PLY/$NAME" "$GRUBT/$NAME" -type d -exec chmod 755 {} + -o -type f -exec chmod 644 {} +

echo "==> $CFG"
[[ -f $CFG.bak-pre-gits ]] || cp -a "$CFG" "$CFG.bak-pre-gits"
# 1) the cmdline line is quoted wrongly: the kernel gets ONE argument "GRUB_CMDLINE_LINUX_DEFAULT=nowatchdog ... splash ...",
#    so `splash` (needed for plymouth), `loglevel=3` and `nowatchdog` were never applied. Same options, sane quoting.
if grep -q "^GRUB_CMDLINE_LINUX_DEFAULT=\"GRUB_CMDLINE_LINUX_DEFAULT=" "$CFG"; then
    sed -i 's|^GRUB_CMDLINE_LINUX_DEFAULT=.*|GRUB_CMDLINE_LINUX_DEFAULT="nowatchdog nvme_load=YES splash loglevel=3 nvidia_drm.modeset=1"|' "$CFG"
fi
# 2) native panel resolution, so the theme is not stretched from 1280x1024
sed -i 's|^GRUB_GFXMODE=.*|GRUB_GFXMODE=1920x1200x32,auto|' "$CFG"
# 3) the theme
sed -i "s|^GRUB_THEME=.*|GRUB_THEME=\"$GRUBT/$NAME/theme.txt\"|" "$CFG"
diff -u "$CFG.bak-pre-gits" "$CFG" || true

echo "==> plymouth theme + initramfs (mkinitcpio -P, takes a minute)"
plymouth-set-default-theme -R "$NAME"

echo "==> grub.cfg"
grub-mkconfig -o /boot/grub/grub.cfg

echo
echo "done. plymouth theme: $(plymouth-set-default-theme). Reboot to see it."
echo "if anything looks wrong:  sudo $0 --revert"
