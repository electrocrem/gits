#!/usr/bin/env bash
# Ghost in the Shell for Hyprland: installer. The whole desktop: Hyprland config, bar, popups, lock screen, notifications, terminal, themes.
#
#   ./install.sh                 user-level install (no sudo)
#   ./install.sh --system        ... plus SDDM, Plymouth and GRUB themes (asks for sudo)
#   ./install.sh --deps          ... pacman -S --needed for the packages in packages.txt first (asks for sudo)
#   ./install.sh --login-guards  ... plus the blind-login guard (hybrid AMD/NVIDIA laptops)
#   ./install.sh --telegram      ... also build the Telegram theme into ~/Downloads
#   ./install.sh --dry-run       only print what would happen
#
# Every file that already exists and differs is moved to ~/.local/share/gits-install/backup/<time>/ first;
# ./uninstall.sh puts everything back. Running the installer twice is safe. Log out and in afterwards (or pick the Hyprland session
# at the login screen): the compositor config is read at login.
set -euo pipefail

REPO=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
export PYTHONDONTWRITEBYTECODE=1   # the build scripts import the widgets: no __pycache__ that uninstall would leave behind
STATE=$HOME/.local/share/gits-install
STAMP=$(date +%Y%m%d-%H%M%S)
BK=$STATE/backup/$STAMP
LIST=$STATE/installed.list
WALLS=$HOME/.local/share/gits/wallpapers

DRY=0 SYSTEM=0 DEPS=0 GUARDS=0 TELEGRAM=0 FIXGRUB=0
for a in "$@"; do
    case $a in
        --dry-run) DRY=1 ;;
        --system) SYSTEM=1 ;;
        --deps) DEPS=1 ;;
        --login-guards) GUARDS=1 ;;
        --telegram) TELEGRAM=1 ;;
        --fix-grub) FIXGRUB=1 ;;
        -h | --help) sed -n '2,13p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
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
    command -v Hyprland >/dev/null || die "Hyprland is not installed (pacman -S hyprland)"
    hv=$(Hyprland --version 2>/dev/null | grep -oE '[0-9]+\.[0-9]+' | head -1)
    [[ -z $hv ]] || printf '0.55\n%s\n' "$hv" | sort -CV || die "Hyprland $hv is too old: the config is Lua, which needs 0.55 or newer"
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
    if [[ -f $file ]] && grep -q ">>> gits:$id >>>" "$file"; then return 0; fi
    if ((DRY)); then echo "   (dry) append gits:$id block to $file"; return 0; fi
    mkdir -p "$(dirname "$file")"
    [[ -f $file ]] && { mkdir -p "$BK/$(dirname "${file#"$HOME"/}")"; [[ -e $BK/${file#"$HOME"/} ]] || cp -a "$file" "$BK/${file#"$HOME"/}"; } || record "new:$file"
    printf '\n%s >>> gits:%s >>>\n%s\n%s <<< gits:%s <<<\n' "$c" "$id" "$text" "$c" "$id" >>"$file"
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
# another colour theme than GitS (gits-theme): the files below are GitS, so put the GitS originals back first and switch again at the end
THEME=$(sed -n 's/^theme=//p' "${XDG_STATE_HOME:-$HOME/.local/state}/gits/state" 2>/dev/null | head -1 || true)
if [[ -n $THEME && $THEME != gits && -x $HOME/.local/bin/gits-theme ]]; then
    say "colour theme $THEME: back to GitS while copying"
    run "$HOME/.local/bin/gits-theme" set gits --no-reload >/dev/null
else
    THEME=
fi
# ~/.config/gtk-4.0 used to be a link into a GTK theme directory: writing through it would edit that theme, so replace the link
if [[ -L $HOME/.config/gtk-4.0 ]]; then
    if ((DRY)); then echo "   (dry) replace the link ~/.config/gtk-4.0"; else mkdir -p "$BK/.config"; mv "$HOME/.config/gtk-4.0" "$BK/.config/gtk-4.0"; record "$HOME/.config/gtk-4.0"; fi
fi
count=0
while IFS= read -r -d '' f; do
    rel=${f#"$REPO"/home/}
    [[ $rel == */gits-blind-guard.sh ]] && ((!GUARDS)) && continue   # hypr/gits/start.lua runs it when it exists: opt-in only
    place "$f" "$HOME/$rel"
    count=$((count + 1))
done < <(find "$REPO/home" -type f -print0)
say "$count files"

# pictures used by the desktop and friends
run mkdir -p "$WALLS"
for f in gits_smoke.png gits_eye.png gits_cyborg.jpg gits_teal_wires.jpg; do
    s=$(asset "$f") && place "$s" "$WALLS/$f"
done
s=$(asset gits_eye.png) && place "$s" "$HOME/.config/hypr/hyprlock/gits_lock_bg.png"
s=$(asset gits_eye.png) && place "$s" "$HOME/.local/share/gits-sddm/ghost-in-the-shell/background.png"
for f in art.png cyborg.txt lain.txt shodan.txt; do
    s=$(asset "$f") && place "$s" "$HOME/.config/zsh/gits/$f"
done
s=$(asset lain.txt) && place "$s" "$HOME/.config/nvim/lua/gits/lain.txt"
# the GitS art set (terminal banner, fastfetch, Neovim dashboard, radio dancer): ~/.local/share/gits/art/gits, "current" = the theme's set
ART=$HOME/.local/share/gits/art
s=$(asset art.png) && place "$s" "$ART/gits/banner.png"
s=$(asset cyborg.txt) && place "$s" "$ART/gits/banner.txt" && place "$s" "$ART/gits/dashboard.txt"
s=$(asset lain-dance.gif) && place "$s" "$HOME/.config/gits-widgets/lain.gif"   # the radio popup and the lock screen dance from it

# ------------------------------------------------------------------ hooks into your own config files
say "hooking into zsh and neovim"
add_block "$HOME/.config/zsh/user.zsh" zsh "#" <<'EOF'
# Ghost in the Shell: tmux autostart (opt-in: GITS_TMUX=1), banner (GITS_NO_BANNER=1 disables) and fzf colours
[[ -r ${0:A:h}/gits/tmux.zsh ]] && source ${0:A:h}/gits/tmux.zsh
[[ -r ${0:A:h}/gits/banner.zsh ]] && source ${0:A:h}/gits/banner.zsh
[[ -r ${0:A:h}/gits/colors.zsh ]] && source ${0:A:h}/gits/colors.zsh
EOF

# user.zsh only runs when the shell's own startup files source it, and a plain zsh setup does not. Ask zsh itself
# (started the way your terminal starts it): if the block above never runs, hook one line into the .zshrc it reads.
if ! command -v zsh >/dev/null; then
    warn "zsh is not installed: the banner and fzf colours need it (pacman -S zsh)"
elif ((DRY)); then
    echo "   (dry) check that zsh reads ~/.config/zsh/user.zsh; if it does not, source it from .zshrc"
else
    zsh_reads_gits() {   # the xtrace of an interactive start mentions gits/colors.zsh only if the block ran
        local trace rc; trace=$(mktemp)
        env -u GITS_TMUX GITS_NO_BANNER=1 GITS_NO_TMUX=1 timeout 30 zsh -ixc exit </dev/null >/dev/null 2>"$trace" || true
        grep -q 'gits/colors.zsh' "$trace"; rc=$?
        rm -f "$trace"; return $rc
    }
    rcdir=$(zsh -c 'print -r -- ${ZDOTDIR:-$HOME}' </dev/null 2>/dev/null | tail -1) || true   # reads ~/.zshenv only
    [[ $rcdir == /* ]] || rcdir=$HOME
    have_rc=0   # with no startup file at all some zsh builds run their first-use wizard: then there is nothing to probe
    for f in .zshenv .zprofile .zshrc .zlogin; do [[ -e $rcdir/$f ]] && have_rc=1; done
    if ((have_rc)) && zsh_reads_gits; then
        say "zsh already reads ~/.config/zsh/user.zsh"
    else
        add_block "$rcdir/.zshrc" zsh-wire "#" <<'EOF'
# Ghost in the Shell: this zsh setup does not read ~/.config/zsh/user.zsh (banner, tmux helper, fzf colours) by itself
[[ -r ${XDG_CONFIG_HOME:-$HOME/.config}/zsh/user.zsh ]] && source ${XDG_CONFIG_HOME:-$HOME/.config}/zsh/user.zsh
EOF
        if zsh_reads_gits; then say "hooked ~/.config/zsh/user.zsh into $rcdir/.zshrc"
        else warn "zsh still does not run ~/.config/zsh/user.zsh: add 'source ~/.config/zsh/user.zsh' to the startup file your shell reads"; fi
    fi
fi

# no Neovim config of your own: the GitS look is a set of LazyVim plugin specs, so start from the LazyVim starter
if [[ ! -e $HOME/.config/nvim/init.lua && ! -e $HOME/.config/nvim/init.vim ]]; then
    place "$REPO/tools/nvim-starter/init.lua" "$HOME/.config/nvim/init.lua"
    place "$REPO/tools/nvim-starter/lazy.lua" "$HOME/.config/nvim/lua/config/lazy.lua"
    say "Neovim: no config found, installed the LazyVim starter (the first nvim start downloads the plugins)"
fi
if [[ -d $HOME/.config/nvim ]]; then
    place "$REPO/tools/nvim-gits-options.lua" "$HOME/.config/nvim/lua/config/gits-options.lua"
    add_block "$HOME/.config/nvim/lua/config/options.lua" nvim "--" <<'EOF'
require("config.gits-options") -- Ghost in the Shell: square frames, red block cursor
EOF
fi

# ------------------------------------------------------------------ apps
say "apps"
if ((DRY)); then
    echo "   (dry) post.py kded / kdeglobals / logseq / vscode / zen / spotify / vesktop / flatpak / kde-apps / steam"
else
    python3 "$REPO/tools/post.py" kded
    python3 "$REPO/tools/post.py" kdeglobals
    python3 "$REPO/tools/post.py" kde-apps
    python3 "$REPO/tools/post.py" logseq "$REPO/logseq/gits.css"
    python3 "$REPO/tools/post.py" vscode "$HOME/.vscode-oss/extensions/gits.ghost-in-the-shell-1.0.0"
    python3 "$REPO/tools/post.py" zen "$REPO/zen"
    python3 "$REPO/tools/post.py" spotify
    python3 "$REPO/tools/post.py" vesktop
    python3 "$REPO/tools/post.py" flatpak
fi

command -v dunstctl >/dev/null && run dunstctl reload 2>/dev/null || true

# things generated from scripts
say "building the cursor theme"
if [[ -d $HOME/.local/share/icons/Bibata-Modern-Ice || -d /usr/share/icons/Bibata-Modern-Ice ]]; then
    [[ -d $HOME/.local/share/icons/Bibata-Modern-Ice ]] || warn "Bibata is only in /usr/share/icons: linking it for the builder"
    [[ -d $HOME/.local/share/icons/Bibata-Modern-Ice ]] || { run mkdir -p "$HOME/.local/share/icons"; run ln -s /usr/share/icons/Bibata-Modern-Ice "$HOME/.local/share/icons/Bibata-Modern-Ice"; }
    run python3 "$HOME/.local/share/gits-cursor/build.py" || warn "cursor build failed"
else
    warn "skipped: Bibata-Modern-Ice not found"
fi
say "building the icon theme (cyan folders on top of Tela-circle-grey)"
run python3 "$HOME/.local/share/gits-icons/build.py" || warn "icon theme build failed (needs Tela-circle-grey: AUR tela-circle-icon-theme-grey): the theme falls back to it"
((DRY)) || python3 "$REPO/tools/post.py" steam
run python3 "$HOME/.local/share/gits-sounds/build.py" || warn "UI sounds not built (needs python-numpy)"
run python3 "$HOME/.local/share/gits-lock/tachikoma.py" >/dev/null || warn "lock screen Tachikoma not built (needs python-numpy): the lock screen has no mascot"
[[ -e $HOME/.local/share/gits/art/current ]] || run ln -sfn gits "$HOME/.local/share/gits/art/current"   # gits-theme moves it with the theme
run python3 "$HOME/.local/share/gits-lock/build.py" >/dev/null || warn "dancing Lain frames not built (needs python-pillow and python-numpy): GITS_LOCK_MASCOT=lain stays blank"
((TELEGRAM)) && run python3 "$HOME/.local/share/gits-telegram/build.py"

[[ -n $THEME ]] && { run "$HOME/.local/bin/gits-theme" set "$THEME" --no-reload >/dev/null || warn "colour theme $THEME not applied again: run  gits-theme set $THEME"; }

# ------------------------------------------------------------------ activation
say "session units"
if ((DRY)); then
    echo "   (dry) systemctl --user daemon-reload; gits-idle apply"
else
    [[ -n ${GITS_SKIP_PREFLIGHT:-} ]] || systemctl --user daemon-reload 2>/dev/null || true   # (tests run with a throw-away $HOME: leave the real session alone)
    GITS_IDLE_NO_RESTART=1 "$HOME/.local/bin/gits-idle" apply >/dev/null 2>&1 || true   # write the sleep timers into hypridle.conf
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
say "${B}done${C0}${C1}: log out and in (pick the Hyprland session), then run  ${B}gits-doctor${C0}${C1}  for a health report${C0}"
echo "  to try the config first, inside your current session:  GITS_NESTED=1 Hyprland -c ~/.config/hypr/hyprland.lua"
((SYSTEM)) || echo "  boot/login screens:  ./install.sh --system   (SDDM + Plymouth + GRUB, needs sudo)"
