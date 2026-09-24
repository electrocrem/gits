#!/usr/bin/env bash
# Undo ./install.sh: restore every file it replaced (from ~/.local/share/gits-install/backup/*, oldest copy wins),
# delete the files it created, remove the blocks it appended to user.zsh / .zshrc / options.lua.
# System-level pieces (SDDM, GRUB, Plymouth) are left alone; the commands to revert them are printed at the end.
#   ./uninstall.sh [--dry-run]
set -euo pipefail
STATE=$HOME/.local/share/gits-install
LIST=$STATE/installed.list
DRY=0; [[ ${1:-} == --dry-run ]] && DRY=1
[[ -f $LIST ]] || { echo "nothing to do: $LIST does not exist"; exit 0; }
run() { if ((DRY)); then echo "   (dry) $*"; else "$@"; fi; }

# the oldest backup of a path is the user's original
oldest_backup() {
    local rel=${1#"$HOME"/} d
    for d in $(ls -1 "$STATE/backup" 2>/dev/null | sort); do
        [[ -e $STATE/backup/$d/$rel || -L $STATE/backup/$d/$rel ]] && { echo "$STATE/backup/$d/$rel"; return 0; }
    done
    return 0
}

# paths this installer created itself: deleted on uninstall even if a later run backed up a newer copy of them
mapfile -t CREATED < <(grep '^new:' "$LIST" | sed 's/^new://' | sort -u)
is_created() { local x; for x in "${CREATED[@]}"; do [[ $x == "$1" ]] && return 0; done; return 1; }
# files that carry one of our marker blocks: never deleted outright (you may have added your own lines since), only if the block was all they held
mapfile -t BLOCKHOSTS < <(grep '^block:' "$LIST" | cut -d: -f4- | sort -u)
is_blockhost() { local x; for x in "${BLOCKHOSTS[@]}"; do [[ $x == "$1" ]] && return 0; done; return 1; }

sort -u "$LIST" | sed 's/^new://' | sort -u | while IFS= read -r entry; do
    if [[ $entry == block:* ]]; then
        IFS=: read -r _ id c file <<<"$entry"
        [[ -f $file ]] || continue
        echo "removing block gits:$id from $file"
        if ((!DRY)); then
            # drop the marker block and the blank line install.sh put in front of it
            awk -v s=">>> gits:$id >>>" -v e="<<< gits:$id <<<" '
                skip { if (index($0, e)) skip = 0; next }
                index($0, s) { if (have && buf != "") print buf; have = 0; skip = 1; next }
                { if (have) print buf; buf = $0; have = 1 }
                END { if (have) print buf }' "$file" >"$file.gits-tmp" && mv "$file.gits-tmp" "$file"
        fi
        continue
    fi
    is_blockhost "$entry" && is_created "$entry" && continue   # emptied (and removed) by the loop below
    bk=$(oldest_backup "$entry")
    if [[ -n $bk ]] && ! is_created "$entry"; then
        echo "restore  $entry"
        run rm -rf "$entry"
        run mkdir -p "$(dirname "$entry")"
        run cp -a "$bk" "$entry"
    elif [[ -e $entry || -L $entry ]]; then
        echo "delete   $entry"
        run rm -f "$entry"
    fi
done

# edits made by tools/post.py (kdeglobals, Logseq, VS Code, Zen, Vesktop, Flatpak): each left a .bak-pre-gits / plugins-backup copy
restore_bak() { [[ -f $1.bak-pre-gits ]] && { echo "restore  $1"; run mv "$1.bak-pre-gits" "$1"; } || true; }
restore_bak "$HOME/.config/kdeglobals"
restore_bak "$HOME/.vscode-oss/extensions/extensions.json"
restore_bak "$HOME/.config/vesktop/settings/settings.json"
restore_bak "${XDG_DATA_HOME:-$HOME/.local/share}/flatpak/overrides/global"
# Steam's tray PNG (post.py steam)
for d in "$HOME/.local/share/Steam/public" "$HOME/.var/app/com.valvesoftware.Steam/.local/share/Steam/public"; do restore_bak "$d/steam_tray_mono.png"; done
# KF6 app rc files that got [UiSettings] ColorScheme=GitS (post.py kde-apps)
for rc in dolphinrc arkrc okularrc gwenviewrc katerc kwriterc konsolerc filelightrc spectaclerc partitionmanagerrc kcalcrc elisarc harunarc kdeconnect-apprc; do
    restore_bak "$HOME/.config/$rc"
    [[ -f $HOME/.config/$rc.gits-created ]] && { echo "delete   $HOME/.config/$rc"; run rm -f "$HOME/.config/$rc" "$HOME/.config/$rc.gits-created"; }
done
# files post.py created from nothing (no backup to restore): delete them
restore_bak "$HOME/.config/kcminputrc"
for m in "$HOME/.config/kdeglobals" "$HOME/.config/kcminputrc" "$HOME/.config/vesktop/settings/settings.json" "${XDG_DATA_HOME:-$HOME/.local/share}/flatpak/overrides/global"; do
    [[ -f $m.gits-created ]] && { echo "delete   $m"; run rm -f "$m" "$m.gits-created"; }
done
# a per-user Flatpak installation that only exists because post.py flatpak made the override
fp=${XDG_DATA_HOME:-$HOME/.local/share}/flatpak
[[ -f $fp.gits-created ]] && { echo "delete   $fp"; run rm -rf "$fp" "$fp.gits-created"; }
# Spotify patched by Spicetify with the GitS theme: put the original files back
if command -v spicetify >/dev/null && grep -qs '^current_theme *= *GitS' "$HOME/.config/spicetify/config-xpui.ini"; then
    echo "restore  Spotify (spicetify restore)"
    run spicetify -q restore || true
    run spicetify -q config current_theme "" color_scheme "" || true
fi
for d in "$HOME"/.var/app/app.zen_browser.zen/.zen/*/; do
    for f in chrome/userChrome.css chrome/userContent.css user.js; do restore_bak "$d$f"; done
done
if [[ -d $HOME/.logseq/plugins-backup/nord-theme ]]; then
    echo "restore  Logseq Nord plugin"
    for f in custom.css package.json; do
        [[ -f $HOME/.logseq/plugins-backup/nord-theme/$f ]] && run cp -a "$HOME/.logseq/plugins-backup/nord-theme/$f" "$HOME/.logseq/plugins/nord-theme/$f"
    done
    run rm -rf "$HOME/.logseq/plugins-backup/nord-theme"
    run rmdir "$HOME/.logseq/plugins-backup" 2>/dev/null || true
fi

# the session units
[[ -n ${GITS_SKIP_PREFLIGHT:-} ]] || systemctl --user stop gits-session.target 2>/dev/null || true   # tests (roundtrip.sh) run against a throw-away $HOME: never touch the live session

# things the installer generated from scripts (not tracked as placed files)
for d in "$HOME/.local/share/icons/GitS-Icons" "$HOME/.local/share/icons/GitS-Cursors"; do
    [[ -d $d ]] && { echo "delete   $d"; run rm -rf "$d"; }
done
if compgen -G "$HOME/.local/share/gits-lock/*-[0-9]*.txt" >/dev/null; then
    echo "delete   generated lock screen frames"
    run rm -f "$HOME"/.local/share/gits-lock/lain-*.txt "$HOME"/.local/share/gits-lock/tachikoma-*.txt
    run rmdir "$HOME/.local/share/gits-lock" 2>/dev/null || true
fi
if compgen -G "$HOME/.local/share/gits-sounds/*.wav" >/dev/null; then
    echo "delete   generated UI sounds"
    run rm -f "$HOME"/.local/share/gits-sounds/*.wav
    run rmdir "$HOME/.local/share/gits-sounds" 2>/dev/null || true
fi

# colour themes (gits-theme): the GitS originals it kept and its line in the state file (the themed files were restored or deleted above)
if [[ -d $HOME/.local/share/gits/theme-base ]]; then
    echo "delete   colour theme originals"
    run rm -rf "$HOME/.local/share/gits/theme-base"
fi
st=${XDG_STATE_HOME:-$HOME/.local/state}/gits/state
compgen -G "$HOME/.config/gits/themes/*.user" >/dev/null && { echo "delete   your theme options (*.user)"; run rm -f "$HOME"/.config/gits/themes/*.user; }
if ((!DRY)) && [[ -f $st ]] && grep -q '^theme=' "$st"; then sed -i '/^theme=/d' "$st"; [[ -s $st ]] || rm -f "$st"; fi

# files that were created by the blocks' host (nothing to restore) and are now empty
for f in "${BLOCKHOSTS[@]}" "$HOME/.config/kded6rc"; do
    [[ -f $f && ! -s $f ]] && run rm -f "$f"
done
((DRY)) || [[ -n ${GITS_SKIP_PREFLIGHT:-} ]] || systemctl --user daemon-reload 2>/dev/null || true
((DRY)) || mv "$LIST" "$LIST.uninstalled-$(date +%s)"
cat <<TXT

Not touched (edited outside your \$HOME, needs sudo):
  SDDM:     sudo rm -rf /usr/share/sddm/themes/ghost-in-the-shell /etc/sddm.conf.d/zz-gits.conf
  Boot:     sudo ~/.local/share/gits-boot/install.sh --revert     (run BEFORE removing that folder)
  GRUB:     sudo cp /etc/default/grub.bak-pre-savedefault /etc/default/grub && sudo grub-mkconfig -o /boot/grub/grub.cfg
Logseq, Zen, VS Code and kdeglobals were restored from their .bak-pre-gits / plugins-backup copies (log out and in for Qt colours).
Log out and in. (The session units gits-*.service are removed; whatever was in place before is back.)
TXT
