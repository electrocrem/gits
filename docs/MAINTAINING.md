# Working on gits

Everything that is not needed to *use* the desktop, but is handy when you want to change it or keep the repo up to date.

## Layout of the repo

```
install.sh / uninstall.sh   installer and its inverse
packages.txt                pacman packages needed
home/                       mirror of $HOME (config files, scripts, extensions)
assets/                     pictures (wallpapers, lock/boot art, banner, the dancing Lain) — see NOTICE.md
zen/  logseq/               browser and notes-app styles (installed by tools/post.py)
tools/export.py             refresh this repo from your live $HOME
tools/screenshots.sh        retake the pictures in docs/img and the demo GIF
tools/lock-shot.sh          a picture of the lock screen without locking your session
tools/roundtrip.sh          install twice + uninstall in a throw-away $HOME and compare
tools/make-assets.py        generates original placeholder artwork when assets/ is incomplete
tools/post.py               idempotent edits: kdeglobals, Logseq, VS Code, Zen, Spotify, Vesktop, Flatpak
docs/PITFALLS.md            what broke and why
docs/PALETTE.md             the colours
```

The Hyprland config lives in `home/.config/hypr/gits/*.lua` (options, rules, binds, layouts, workflows, animation presets). The bar, notifications, idle
timers, night light, wallpaper, clipboard and tray applets run as systemd user units under `gits-session.target`.

## What the installer touches, exactly

* Copies `home/` into `$HOME` (`@HOME@` becomes your home directory). Anything that already exists and differs is moved to
  `~/.local/share/gits-install/backup/<time>/` first.
* Appends marked blocks (`>>> gits:… >>>`) to **your** `~/.config/zsh/user.zsh` and `~/.config/nvim/lua/config/options.lua`. Nothing else in those
  files is changed. If your zsh does not read `user.zsh` by itself (the installer asks zsh, it does not guess), one more marked line (`gits:zsh-wire`)
  is added to the `.zshrc` your shell reads. `uninstall.sh` removes it again.
* Puts the wallpapers in `~/.local/share/gits/wallpapers/`, the session units in `~/.config/systemd/user/`, and builds the cursor, icon and sound
  themes and the frames of the dancing Lain on the lock screen. Login sets the GTK theme (adw-gtk3-dark + our colours), icons and cursor through gsettings.
* Recolours the accents in `~/.config/kdeglobals`, registers the VS Code theme, installs the Zen styles into the default profile, swaps the
  stylesheet of the Logseq *Nord* theme plugin (originals are kept).
* `--system` copies the SDDM theme to `/usr/share/sddm/themes`, writes `/etc/sddm.conf.d/zz-gits.conf`, and builds and installs the Plymouth and GRUB
  themes (`home/.local/share/gits-boot`, it can `--revert`).

A module of the Hyprland config that fails to load does not stop the others: the error goes to `~/.local/state/gits/config-errors.log` and `gits-doctor`
reports it. To try the config without logging out: `GITS_NESTED=1 Hyprland -c ~/.config/hypr/hyprland.lua` opens it in a window (no services are started).

## GRUB "sparse file not allowed"

If GRUB prints `error: commands/loadenv.c:check_blocklists:289:sparse file not allowed. Press any key to continue` on every boot (btrfs root +
`GRUB_SAVEDEFAULT=true`), run `./install.sh --fix-grub`. GRUB will then always boot the first entry instead of the last chosen one.

## Updating this repo from a live system

```bash
tools/export.py --check     # what differs between $HOME and the repo
tools/export.py             # copy it over (explicit manifest; pictures only from assets/; no backups or caches)
tools/screenshots.sh        # retake docs/img and the demo GIF on an empty workspace (demo data, a few minutes, hands off the mouse)
ONLY="player mixer" tools/screenshots.sh     # retake just some
tools/lock-shot.sh          # the lock screen picture, from a nested Hyprland window
```

`screenshots.sh` runs the widgets and popups in demo mode (made-up clipboard, windows, projects, tracks), checks that its workspace is the visible one
before every shot, and refuses to shoot the bar while any media player exists (the bar would show its title). `lock-shot.sh` never runs hyprlock on your
session: it starts a nested Hyprland window, points hyprlock at that compositor only, checks the environment of the process before anything else
and confirms afterwards that your session was never locked.

## Notes on testing

* Tested end to end on the author's machine (CachyOS, Hyprland 0.56 Lua config, AMD + NVIDIA laptop). The installer's file handling (backups,
  idempotency, uninstall round trip) is tested against a throw-away `$HOME` by `tools/roundtrip.sh` and in CI.
* Boot-time pieces (Plymouth, GRUB) cannot be exercised without a reboot.
* Logseq: only the route through an installed theme plugin is tested. On a fresh Logseq copy `logseq/gits.css` to `<graph>/logseq/custom.css`.

## Settings you can change without editing files

| What | How |
|---|---|
| Colour theme | the appearance menu (`gits-panel appearance`, Super+I → Appearance: theme, your accent, lock-screen mascot, wallpaper) or `gits-theme set NAME` / `gits-theme option NAME KEY VALUE` (your options live in `NAME.user`); themes are `~/.config/gits/themes/NAME.theme`: the roles of `gits.theme` with other colours, plus optional `description`, `wallpaper = FILE`, `mascot = NAME`, `lock_bg = FILE` and `swap = OLD -> NEW` lines (text swapped in the themed files: another lock-screen picture, mascot, caption). The icon theme is recoloured too |
| Window animations | `gits-anim` menu (`Super+Shift+Y`): `cyber` (default), `gits`, `lively` (springs), `off`; the neon border runner is opt-in: `touch ~/.local/state/gits-neon-border` |
| Wallpaper | `gits-wall --pick`, or drop pictures (GIFs too) into `~/Pictures/wallpapers` |
| Radio station | `GITS_RADIO_STREAM` (stream URL), `GITS_RADIO_API` (an AzuraCast now-playing URL), `GITS_RADIO_NAME`, `GITS_RADIO_VOLUME` |
| Dancing Lain in the radio popup | `GITS_RADIO_LAIN=holo|color|off`, `GITS_RADIO_LAIN_SPEED=1`, `GITS_RADIO_FLASH=0` (no flash on the beat) |
| Plain lock screen | copy `~/.config/hypr/hyprlock/static.conf` over `~/.config/hypr/hyprlock.conf` |
| Weather card | `GITS_WEATHER_LOCATION="Berlin"` (default: by IP; `off` stops the request) |
| Home server card | `GITS_SERVER=pi` (ssh destination with key login and python3; Docker via `docker` or `sudo -n docker`), `GITS_SERVER_NAME` |
| Glitch bursts on the wallpaper | `GITS_WIDGETS_GLITCH=0` |
| tmux in every terminal | `export GITS_TMUX=1` (off by default) |
| Your own rows in Super+I | `~/.config/gits/settings.tsv` |
