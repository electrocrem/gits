#!/usr/bin/env bash
# Install (or revert) the Ghost in the Shell boot themes: Plymouth splash + GRUB menu.
#   sudo ./install.sh            install
#   sudo ./install.sh --revert   back to what was there before (GRUB config, Plymouth theme, initramfs setup)
# Works with dracut (EndeavourOS, Fedora-style) and mkinitcpio (Arch, CachyOS). The art is rendered by build.py
# for the main screen; GRUB_GFXMODE asks for that size and falls back to `auto` where the firmware lacks it.
set -euo pipefail
[[ $EUID -eq 0 ]] || { echo "run with sudo:  sudo $0 ${*:-}"; exit 1; }

NAME=ghost-in-the-shell
HERE=$(cd "$(dirname "$0")" && pwd)
PLY=/usr/share/plymouth/themes
GRUBT=/usr/share/grub/themes
CFG=/etc/default/grub
STATE=/var/lib/gits-boot                      # what was there before: plymouth theme name, mkinitcpio.conf
DRACUT_CONF=/etc/dracut.conf.d/zz-gits-plymouth.conf
MKI=/etc/mkinitcpio.conf

grub_cfg() { for f in /boot/grub/grub.cfg /boot/grub2/grub.cfg; do [[ -d ${f%/*} ]] && { echo "$f"; return; }; done; echo /boot/grub/grub.cfg; }
grub_mkconfig() {
    local mk; mk=$(command -v grub-mkconfig || command -v grub2-mkconfig) || { echo "no grub-mkconfig: skipped"; return; }
    "$mk" -o "$(grub_cfg)"
}
initramfs_tool() {
    if command -v dracut >/dev/null && ! command -v mkinitcpio >/dev/null; then echo dracut
    elif command -v mkinitcpio >/dev/null; then echo mkinitcpio
    else echo none; fi
}
rebuild_initramfs() {
    case $(initramfs_tool) in
        dracut) if command -v dracut-rebuild >/dev/null; then dracut-rebuild; else dracut --regenerate-all --force; fi ;;
        mkinitcpio) mkinitcpio -P ;;
        *) echo "WARN: neither dracut nor mkinitcpio found: rebuild the initramfs yourself" ;;
    esac
}
# set_kv KEY VALUE: replace the active KEY= line in $CFG, or append one
set_kv() {
    if grep -qE "^$1=" "$CFG"; then sed -i -E "s|^$1=.*|$1=$2|" "$CFG"; else echo "$1=$2" >>"$CFG"; fi
}

if [[ ${1:-} == --revert ]]; then
    if [[ -f $CFG.bak-pre-gits ]]; then cp -a "$CFG.bak-pre-gits" "$CFG"; echo "restored $CFG from backup"; fi
    prev=$(cat "$STATE/plymouth-theme" 2>/dev/null || true)
    if [[ -n $prev && -d $PLY/$prev ]]; then plymouth-set-default-theme "$prev"; else plymouth-set-default-theme --reset; fi
    rm -f "$DRACUT_CONF"
    [[ -f $STATE/plymouthd.conf ]] && cp -a "$STATE/plymouthd.conf" /etc/plymouth/plymouthd.conf
    [[ -f $STATE/mkinitcpio.conf ]] && cp -a "$STATE/mkinitcpio.conf" "$MKI"
    rebuild_initramfs
    grub_mkconfig
    echo "reverted (theme folders are left in place)"; exit 0
fi

[[ -d $HERE/staging/plymouth/$NAME && -d $HERE/staging/grub/$NAME ]] || { echo "run build.py first"; exit 1; }
SIZE=$(cat "$HERE/staging/size" 2>/dev/null || true)

echo "==> copying themes"
rm -rf "${PLY:?}/$NAME" "${GRUBT:?}/$NAME"
mkdir -p "$PLY" "$GRUBT"
cp -r "$HERE/staging/plymouth/$NAME" "$PLY/$NAME"
cp -r "$HERE/staging/grub/$NAME" "$GRUBT/$NAME"
chown -R root:root "$PLY/$NAME" "$GRUBT/$NAME"
find "$PLY/$NAME" "$GRUBT/$NAME" -type d -exec chmod 755 {} + -o -type f -exec chmod 644 {} +

echo "==> $CFG"
mkdir -p "$STATE"
[[ -f $CFG.bak-pre-gits ]] || cp -a "$CFG" "$CFG.bak-pre-gits"
# 1) a cmdline line quoted wrongly (the kernel gets ONE argument "GRUB_CMDLINE_LINUX_DEFAULT=nowatchdog ..."): unwrap it
sed -i -E 's/^GRUB_CMDLINE_LINUX_DEFAULT=(["'\''])GRUB_CMDLINE_LINUX_DEFAULT=(.*)$/GRUB_CMDLINE_LINUX_DEFAULT=\1\2/' "$CFG"
# 2) `splash`, or plymouth stays hidden behind the boot log; whatever else is on the line is kept, and so is its quoting
if ! grep -qE '^GRUB_CMDLINE_LINUX_DEFAULT=' "$CFG"; then
    echo 'GRUB_CMDLINE_LINUX_DEFAULT="splash"' >>"$CFG"
elif ! grep -E '^GRUB_CMDLINE_LINUX_DEFAULT=' "$CFG" | grep -qwE 'splash'; then
    sed -i -E "s/^(GRUB_CMDLINE_LINUX_DEFAULT=)([\"']?)(.*)\2[[:space:]]*\$/\1\2\3 splash\2/" "$CFG"
fi
# 3) the menu at the size the art was rendered for (auto if the firmware has no such mode), kept for the kernel handoff
set_kv GRUB_GFXMODE "${SIZE:+${SIZE}x32,}auto"
set_kv GRUB_GFXPAYLOAD_LINUX keep
# 4) the theme (it replaces GRUB_BACKGROUND, which is left as it was)
set_kv GRUB_THEME "\"$GRUBT/$NAME/theme.txt\""
diff -u "$CFG.bak-pre-gits" "$CFG" || true

echo "==> plymouth theme"
cur=$(plymouth-set-default-theme 2>/dev/null || true)
[[ -f $STATE/plymouth-theme || -z $cur || $cur == "$NAME" ]] || echo "$cur" >"$STATE/plymouth-theme"
plymouth-set-default-theme "$NAME"
# the script scales the art by the screen height itself; plymouth's own HiDPI guess (2x on a 1440p screen whose size it
# does not know) would hand it half the pixels and blow everything up, so pin the device scale to 1
PDC=/etc/plymouth/plymouthd.conf
mkdir -p "${PDC%/*}"; touch "$PDC"
[[ -f $STATE/plymouthd.conf ]] || cp -a "$PDC" "$STATE/plymouthd.conf"
grep -q '^\[Daemon\]' "$PDC" || printf '[Daemon]\n' >>"$PDC"
if grep -q '^DeviceScale=' "$PDC"; then sed -i 's/^DeviceScale=.*/DeviceScale=1/' "$PDC"
else sed -i '/^\[Daemon\]/a DeviceScale=1' "$PDC"; fi

echo "==> initramfs ($(initramfs_tool), takes a minute)"
case $(initramfs_tool) in
    dracut)
        # dracut only adds plymouth on its own when it was installed before the initramfs was first built
        printf '# gits: the boot splash (sudo %s --revert removes this file)\nadd_dracutmodules+=" plymouth "\n' "$0" >"$DRACUT_CONF"
        ;;
    mkinitcpio)
        if ! grep -E '^HOOKS=' "$MKI" | grep -qw plymouth; then
            [[ -f $STATE/mkinitcpio.conf ]] || cp -a "$MKI" "$STATE/mkinitcpio.conf"
            # after udev / systemd (it needs the GPU driver), before any disk unlock (it draws the passphrase prompt)
            if grep -E '^HOOKS=' "$MKI" | grep -qwE 'systemd'; then sed -i -E '/^HOOKS=/ s/\bsystemd\b/systemd plymouth/' "$MKI"
            else sed -i -E '/^HOOKS=/ s/\budev\b/udev plymouth/' "$MKI"; fi
            grep -E '^HOOKS=' "$MKI" | grep -qw plymouth || echo "WARN: could not place the plymouth hook: add it to HOOKS in $MKI by hand"
            grep -E '^HOOKS=' "$MKI"
        fi
        ;;
esac
rebuild_initramfs

echo "==> $(grub_cfg)"
grub_mkconfig

echo
echo "done. plymouth theme: $(plymouth-set-default-theme), art ${SIZE:-1920x1080}. Reboot to see it."
echo "if anything looks wrong:  sudo $0 --revert"
