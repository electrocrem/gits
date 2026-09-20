#!/usr/bin/env bash
# Ghost in the Shell for HyDE / Hyprland: installer.
#
#   ./install.sh                 user-level install (no sudo): theme, waybar, widgets, hyprlock, terminal, editors...
#   ./install.sh --apply         ... and switch HyDE to the theme right away (see the warning in README.md)
#   ./install.sh --system        ... plus SDDM, Plymouth and GRUB themes (asks for sudo)
#   ./install.sh --deps          ... pacman -S --needed for the packages in packages.txt first (asks for sudo)
#   ./install.sh --login-guards  ... plus the blind-login guard (hybrid AMD/NVIDIA laptops)
#   ./install.sh --telegram      ... also build the Telegram theme into ~/Downloads
#   ./install.sh --dry-run       only print what would happen
#
# Every file that already exists and differs is moved to ~/.local/share/gits-hyde/backup/<time>/ first;
# ./uninstall.sh puts everything back. Running the installer twice is safe.
set -euo pipefail

REPO=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
STATE=$HOME/.local/share/gits-hyde
STAMP=$(date +%Y%m%d-%H%M%S)
BK=$STATE/backup/$STAMP
LIST=$STATE/installed.list
THEME="Ghost in the Shell"
THEME_DIR=$HOME/.config/hyde/themes/$THEME

DRY=0 APPLY=0 SYSTEM=0 DEPS=0 GUARDS=0 TELEGRAM=0 FIXGRUB=0
for a in "$@"; do
    case $a in
        --dry-run) DRY=1 ;;
        --apply) APPLY=1 ;;
        --system) SYSTEM=1 ;;
        --deps) DEPS=1 ;;
        --login-guards) GUARDS=1 ;;
        --telegram) TELEGRAM=1 ;;
        --fix-grub) FIXGRUB=1 ;;
        -h | --help) sed -n '2,15p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
        *) echo "unknown option: $a (see --help)" >&2; exit 2 ;;
    esac
done

if [[ -t 1 ]]; then C1=$'\e[38;2;46;211;215m' C2=$'\e[38;2;240;200;80m' C3=$'\e[38;2;240;80;80m' C0=$'\e[0m' B=$'\e[1m'; else C1= C2= C3= C0= B=; fi
say()  { printf '%s//%s %s\n' "$C1" "$C0" "$*"; }
warn() { printf '%s[warn]%s %s\n' "$C2" "$C0" "$*"; }
die()  { printf '%s[fail]%s %s\n' "$C3" "$C0" "$*" >&2; exit 1; }
run()  { if ((DRY)); then printf '   (dry) %s\n' "$*"; else "$@"; fi; }

[[ $EUID -ne 0 ]] || die "run as your normal user, not root (sudo is asked for only where needed)"

# ------------------------------------------------------------------ preflight
say "checking the system"
if [[ -z ${GITS_SKIP_PREFLIGHT:-} ]]; then
    command -v hyde-shell >/dev/null || die "HyDE is not installed (hyde-shell not found): https://github.com/HyDE-Project/HyDE"
    [[ -f $HOME/.config/hypr/hyprland.lua ]] || die "~/.config/hypr/hyprland.lua not found: this setup targets Hyprland's Lua config (0.55+ with HyDE)"
    command -v pacman >/dev/null || warn "not an Arch-based system: package checks are skipped, everything else should still work"
fi

pkgs=$(grep -vE '^\s*(#|$)' "$REPO/packages.txt" | awk '{print $1}')
if command -v pacman >/dev/null; then
    have() {  # fonts may come from ~/.local/share/fonts instead of a package: ask fontconfig
        pacman -Qq "$1" >/dev/null 2>&1 && return 0
        case $1 in
            ttf-jetbrains-mono-nerd) fc-list | grep -qi "JetBrainsMono Nerd" ;;
            noto-fonts-cjk) fc-list :lang=ja | grep -q . ;;
            *) return 1 ;;
        esac
    }
    missing=$(for p in $pkgs; do have "$p" || echo "$p"; done | paste -sd' ' -)
    if [[ -n $missing ]]; then
        if ((DEPS)); then
            say "installing missing packages: $missing"
            run sudo pacman -S --needed --noconfirm $missing
        else
            warn "missing packages: $missing"
            warn "  install them with:  sudo pacman -S --needed $missing   (or rerun with --deps)"
        fi
    else
        say "all packages from packages.txt are installed"
    fi
    [[ -d $HOME/.local/share/icons/Bibata-Modern-Ice || -d /usr/share/icons/Bibata-Modern-Ice ]] ||
        warn "Bibata-Modern-Ice cursor theme missing (AUR: bibata-cursor-theme): the GitS-Cursors builder takes its alias links from it"
fi

# ------------------------------------------------------------------ helpers
mkdir -p "$STATE" 2>/dev/null || true
record() { ((DRY)) || echo "$1" >>"$LIST"; }

is_text() { grep -Iq . "$1" 2>/dev/null || [[ ! -s $1 ]]; }

# place SRC DST : copy (with @HOME@ -> $HOME), back up whatever is there, remember DST for uninstall
place() {
    local src=$1 dst=$2 tmp
    tmp=$(mktemp)
    if is_text "$src"; then sed "s|@HOME@|$HOME|g" "$src" >"$tmp"; else cp "$src" "$tmp"; fi
    if [[ -e $dst || -L $dst ]]; then
        if cmp -s "$tmp" "$dst"; then rm -f "$tmp"; return 0; fi
        if ((DRY)); then echo "   (dry) backup + overwrite $dst"; rm -f "$tmp"; return 0; fi
        mkdir -p "$BK/$(dirname "${dst#"$HOME"/}")"
        mv "$dst" "$BK/${dst#"$HOME"/}"
    else
        ((DRY)) && { echo "   (dry) create $dst"; rm -f "$tmp"; return 0; }
        record "new:$dst"
    fi
    mkdir -p "$(dirname "$dst")"
    install -m "$(stat -c %a "$src")" "$tmp" "$dst"
    rm -f "$tmp"
    [[ -e $BK/${dst#"$HOME"/} ]] && record "$dst"
    return 0
}

# link TARGET LINKNAME
link() {
    local target=$1 name=$2
    [[ -L $name && $(readlink "$name") == "$target" ]] && return 0
    if ((DRY)); then echo "   (dry) link $name -> $target"; return 0; fi
    if [[ -e $name || -L $name ]]; then mkdir -p "$BK/$(dirname "${name#"$HOME"/}")"; mv "$name" "$BK/${name#"$HOME"/}"; else record "new:$name"; fi
    mkdir -p "$(dirname "$name")"
    ln -s "$target" "$name"
    [[ -e $BK/${name#"$HOME"/} || -L $BK/${name#"$HOME"/} ]] && record "$name"
    return 0
}

# add_block FILE ID COMMENT_PREFIX  (block text on stdin): append once, wrapped in markers
add_block() {
    local file=$1 id=$2 c=$3 text
    text=$(cat)
    if [[ -f $file ]] && grep -q ">>> gits-hyde:$id >>>" "$file"; then return 0; fi
    if ((DRY)); then echo "   (dry) append gits-hyde:$id block to $file"; return 0; fi
    mkdir -p "$(dirname "$file")"
    [[ -f $file ]] && { mkdir -p "$BK/$(dirname "${file#"$HOME"/}")"; [[ -e $BK/${file#"$HOME"/} ]] || cp -a "$file" "$BK/${file#"$HOME"/}"; } || record "new:$file"
    printf '\n%s >>> gits-hyde:%s >>>\n%s\n%s <<< gits-hyde:%s <<<\n' "$c" "$id" "$text" "$c" "$id" >>"$file"
    record "block:$id:$c:$file"
}

# ------------------------------------------------------------------ artwork
say "artwork"
ASSETS=$REPO/assets
need=(gits_smoke.png gits_eye.png)
for f in "${need[@]}"; do
    if [[ ! -f $ASSETS/$f ]]; then
        warn "assets/$f missing: generating an original placeholder set (tools/make-assets.py)"
        run python3 "$REPO/tools/make-assets.py"
        break
    fi
done
asset() { [[ -f $ASSETS/$1 ]] && echo "$ASSETS/$1"; }

# ------------------------------------------------------------------ files
say "copying configuration"
count=0
while IFS= read -r -d '' f; do
    rel=${f#"$REPO"/home/}
    place "$f" "$HOME/$rel"
    count=$((count + 1))
done < <(find "$REPO/home" -type f -print0)
say "$count files"

# pictures used by the theme and friends
WP=$THEME_DIR/wallpapers
run mkdir -p "$WP"
for f in gits_smoke.png gits_eye.png gits_cyborg.jpg gits_teal_wires.jpg; do
    s=$(asset "$f") && place "$s" "$WP/$f"
done
[[ -f $WP/gits_cyborg.jpg || ${DRY} == 1 ]] && side=gits_cyborg.jpg || side=gits_smoke.png
link "$WP/gits_smoke.png" "$THEME_DIR/wall.set"
link "$WP/$side" "$THEME_DIR/wall.awww.png"
link "$WP/$side" "$THEME_DIR/wall.hyprlock.png"
s=$(asset gits_eye.png) && place "$s" "$HOME/.config/hypr/hyprlock/gits_lock_bg.png"
s=$(asset gits_eye.png) && place "$s" "$HOME/.local/share/gits-sddm/ghost-in-the-shell/background.png"
for f in art.png cyborg.txt lain.txt shodan.txt; do
    s=$(asset "$f") && place "$s" "$HOME/.config/zsh/gits/$f"
done
s=$(asset lain.txt) && place "$s" "$HOME/.config/nvim/lua/gits/lain.txt"

# ------------------------------------------------------------------ hooks into your own config files
say "hooking into hyprland.lua, zsh and neovim"
HL=$HOME/.config/hypr/hyprland.lua
if ((GUARDS)) && [[ -f $HOME/.config/hypr/gits.lua ]] && ! grep -q 'gits-blind-guard' "$HOME/.config/hypr/gits.lua"; then
    ((DRY)) || { sed -i "/-- @BLIND_GUARD@/{
r $REPO/tools/blind-guard.lua.in
d
}" "$HOME/.config/hypr/gits.lua"; }
fi
printf 'dofile(os.getenv("HOME") .. "/.config/hypr/gits.lua")  -- Ghost in the Shell hooks (remove this line to disable)\n' | add_block "$HL" hyprland "--"

add_block "$HOME/.config/zsh/user.zsh" zsh "#" <<'EOF'
# Ghost in the Shell banner (disable with GITS_NO_BANNER=1) and fzf colours
[[ -r ${0:A:h}/gits/banner.zsh ]] && source ${0:A:h}/gits/banner.zsh
[[ -r ${0:A:h}/gits/colors.zsh ]] && source ${0:A:h}/gits/colors.zsh
EOF

if [[ -d $HOME/.config/nvim ]]; then
    place "$REPO/tools/nvim-gits-options.lua" "$HOME/.config/nvim/lua/config/gits-options.lua"
    add_block "$HOME/.config/nvim/lua/config/options.lua" nvim "--" <<'EOF'
require("config.gits-options") -- Ghost in the Shell: square frames, red block cursor
EOF
fi

# ------------------------------------------------------------------ apps
say "apps"
if ((DRY)); then
    echo "   (dry) post.py kded / kdeglobals / logseq / vscode / zen"
else
    python3 "$REPO/tools/post.py" kded
    python3 "$REPO/tools/post.py" kdeglobals
    python3 "$REPO/tools/post.py" logseq "$REPO/logseq/gits.css"
    python3 "$REPO/tools/post.py" vscode "$HOME/.vscode-oss/extensions/gits.ghost-in-the-shell-1.0.0"
    python3 "$REPO/tools/post.py" zen "$REPO/zen"
fi

command -v dunstctl >/dev/null && run dunstctl reload 2>/dev/null || true

# things generated from scripts
say "building the cursor theme"
if [[ -d $HOME/.local/share/icons/Bibata-Modern-Ice || -d /usr/share/icons/Bibata-Modern-Ice ]]; then
    [[ -d $HOME/.local/share/icons/Bibata-Modern-Ice ]] || warn "Bibata is only in /usr/share/icons: linking it for the builder"
    [[ -d $HOME/.local/share/icons/Bibata-Modern-Ice ]] || run ln -s /usr/share/icons/Bibata-Modern-Ice "$HOME/.local/share/icons/Bibata-Modern-Ice"
    run python3 "$HOME/.local/share/gits-cursor/build.py" || warn "cursor build failed"
else
    warn "skipped: Bibata-Modern-Ice not found"
fi
say "building the icon theme (cyan folders on top of Tela-circle-grey)"
run python3 "$HOME/.local/share/gits-icons/build.py" || warn "icon theme build failed (needs Tela-circle-grey, shipped with HyDE): the theme falls back to it"
run python3 "$HOME/.local/share/gits-sounds/build.py" || warn "UI sounds not built (needs python-numpy)"
((TELEGRAM)) && run python3 "$HOME/.local/share/gits-telegram/build.py"

# ------------------------------------------------------------------ HyDE selection
setstate() {  # setstate KEY VALUE  in HyDE's staterc
    local rc=$HOME/.local/state/hyde/staterc
    ((DRY)) && { echo "   (dry) staterc $1=$2"; return; }
    mkdir -p "$(dirname "$rc")"; touch "$rc"
    if grep -q "^$1=" "$rc"; then sed -i "s|^$1=.*|$1=\"$2\"|" "$rc"; else echo "$1=\"$2\"" >>"$rc"; fi
}
if ((APPLY)); then
    say "switching HyDE to $THEME"
    warn "the theme sets the cursor theme live; GTK apps (waybar, Zen) can crash on that. The bar watchdog revives waybar."
    setstate HYPRLOCK_LAYOUT "$THEME"
    run hyde-shell theme.switch.sh -s "$THEME" || warn "theme.switch failed"
    run hyde-shell waybar.py --set ghost-in-the-shell || true
    run hyde-shell animations --set gits || true
    run hyde-shell hyprlock.sh --reload || true
    run hyde-shell workflows --set 01-default || true
fi

# ------------------------------------------------------------------ system part (sudo)
if ((SYSTEM)); then
    say "system themes (sudo)"
    SDDM_SRC=$HOME/.local/share/gits-sddm/ghost-in-the-shell
    if [[ -d /usr/share/sddm/themes ]]; then
        run sudo rm -rf /usr/share/sddm/themes/ghost-in-the-shell
        run sudo cp -r "$SDDM_SRC" /usr/share/sddm/themes/ghost-in-the-shell
        run sudo mkdir -p /etc/sddm.conf.d
        # zz- sorts last, so it wins over other files' Current=
        printf '[Theme]\nCurrent=ghost-in-the-shell\n' | run sudo tee /etc/sddm.conf.d/zz-gits.conf >/dev/null
        say "SDDM theme installed (the greeter needs Qt6: sddm 0.21+)"
    else
        warn "SDDM not installed: skipped"
    fi
    if command -v plymouth-set-default-theme >/dev/null || [[ -d /usr/share/plymouth ]]; then
        run python3 "$HOME/.local/share/gits-boot/build.py"
        run sudo "$HOME/.local/share/gits-boot/install.sh"
    else
        warn "plymouth not installed (pacman -S plymouth): boot themes skipped"
    fi
fi
if ((FIXGRUB)); then
    run sudo "$HOME/.local/share/gits-boot/fix-grub-savedefault.sh"
fi

# ------------------------------------------------------------------ done
echo
say "${B}done${C0}${C1}: run  ${B}gits-doctor${C0}${C1}  for a health report${C0}"
if ((!APPLY)); then
    cat <<EOF

next steps (not done automatically, they change your live session):
  hyde-shell theme.switch.sh -s "$THEME"      # or rerun with --apply
  hyde-shell waybar.py --set ghost-in-the-shell
  hyde-shell animations --set gits
then log out and in once so every app picks up the cursor and colours.
EOF
fi
((SYSTEM)) || echo "  boot/login screens:  ./install.sh --system   (SDDM + Plymouth + GRUB, needs sudo)"
