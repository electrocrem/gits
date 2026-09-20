#!/usr/bin/env bash
# Undo ./install.sh: restore every file it replaced (from ~/.local/share/gits-hyde/backup/*, oldest copy wins),
# delete the files it created, remove the blocks it appended to user.zsh / options.lua.
# System-level pieces (SDDM, GRUB, Plymouth) are left alone; the commands to revert them are printed at the end.
#   ./uninstall.sh [--dry-run]
set -euo pipefail
STATE=$HOME/.local/share/gits-hyde
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

sort -u "$LIST" | sed 's/^new://' | sort -u | while IFS= read -r entry; do
    if [[ $entry == block:* ]]; then
        IFS=: read -r _ id c file <<<"$entry"
        [[ -f $file ]] || continue
        echo "removing block gits-hyde:$id from $file"
        if ((!DRY)); then
            # drop the marker block and the blank line install.sh put in front of it
            awk -v s=">>> gits-hyde:$id >>>" -v e="<<< gits-hyde:$id <<<" '
                skip { if (index($0, e)) skip = 0; next }
                index($0, s) { if (have && buf != "") print buf; have = 0; skip = 1; next }
                { if (have) print buf; buf = $0; have = 1 }
                END { if (have) print buf }' "$file" >"$file.gits-tmp" && mv "$file.gits-tmp" "$file"
        fi
        continue
    fi
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

# edits made by tools/post.py (kdeglobals, Logseq, VS Code, Zen): each left a .bak-pre-gits / plugins-backup copy
restore_bak() { [[ -f $1.bak-pre-gits ]] && { echo "restore  $1"; run mv "$1.bak-pre-gits" "$1"; } || true; }
restore_bak "$HOME/.config/kdeglobals"
restore_bak "$HOME/.vscode-oss/extensions/extensions.json"
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
systemctl --user stop gits-session.target 2>/dev/null || true

# things the installer generated from scripts (not tracked as placed files)
for d in "$HOME/.local/share/icons/GitS-Icons" "$HOME/.local/share/icons/GitS-Cursors"; do
    [[ -d $d ]] && { echo "delete   $d"; run rm -rf "$d"; }
done
if compgen -G "$HOME/.local/share/gits-sounds/*.wav" >/dev/null; then
    echo "delete   generated UI sounds"
    run rm -f "$HOME"/.local/share/gits-sounds/*.wav
    run rmdir "$HOME/.local/share/gits-sounds" 2>/dev/null || true
fi

# files that were created by the blocks' host (nothing to restore) and are now empty
for f in "$HOME/.config/zsh/user.zsh" "$HOME/.config/nvim/lua/config/options.lua" "$HOME/.config/kded6rc"; do
    [[ -f $f && ! -s $f ]] && run rm -f "$f"
done
((DRY)) || systemctl --user daemon-reload 2>/dev/null || true
((DRY)) || mv "$LIST" "$LIST.uninstalled-$(date +%s)"
cat <<TXT

Not touched (edited outside your \$HOME, needs sudo):
  SDDM:     sudo rm -rf /usr/share/sddm/themes/ghost-in-the-shell /etc/sddm.conf.d/zz-gits.conf
  Boot:     sudo ~/.local/share/gits-boot/install.sh --revert     (run BEFORE removing that folder)
  GRUB:     sudo cp /etc/default/grub.bak-pre-savedefault /etc/default/grub && sudo grub-mkconfig -o /boot/grub/grub.cfg
Logseq, Zen, VS Code and kdeglobals were restored from their .bak-pre-gits / plugins-backup copies (log out and in for Qt colours).
Log out and in. (The session units gits-*.service are removed; whatever was in place before is back.)
TXT
