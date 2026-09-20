# gits-hyde — Ghost in the Shell for Hyprland

A complete, self-contained *Ghost in the Shell* desktop for Hyprland (Lua config, 0.55+): navy + cyan phosphor palette, square corners,
thin frames, kanji tags. Nothing else is needed: no dotfiles framework, no theme switcher. It started as a [HyDE](https://github.com/HyDE-Project/HyDE)
theme and has since replaced every part of it. One installer, one uninstaller, every replaced file backed up.
[Русская версия](README.ru.md)

| Area | What you get |
|---|---|
| Hyprland | the whole session config in `~/.config/hypr/gits/*.lua`: options, rules, ~200 key bindings (Super+/ lists them), 4 tiling layouts (dwindle, master, monocle, scrolling; Super+Shift+L), 5 workflows (default, editing, gaming, powersaver, snappy), animation preset `gits`; the bar, notifications, idle, night light, wallpaper and clipboard run as systemd user units (`gits-session.target`) |
| Waybar | its own layout + style, one compact CPU/GPU/RAM module (details in the tooltip), power-profile module, language, notification counter, **workflow switcher** (click: next mode); systemd restarts it if it crashes |
| Desktop widgets | GTK4 layer-shell cards: clock, calendar, media player, weather, network, battery, CPU/RAM/SSD, history graph, to-do, **audio spectrum** (LED bars from the default sink, no cava), rare wallpaper glitch bursts (on AC only, `GITS_WIDGETS_GLITCH=0` disables) |
| Lock / login / boot | hyprlock layout, SDDM (Qt6) theme, Plymouth + GRUB themes |
| Animations | preset `gits`: windows lock in with a hard overshoot and collapse when closed, workspaces jump-cut; optional neon border runner (`touch ~/.local/state/gits-neon-border`, costs battery) |
| Launchers | **GTK launcher / command palette** (Super+A: apps with icons and a most-used-first order, settings, projects, open windows, notes, a calculator, web search) and **clipboard history** (Super+V), plus a **window switcher** (Super+Tab), **emoji picker** (Super+comma) and **key binding list** (Super+/), all closing on Esc or a click outside; wlogout, dunst, notification action menu, **Wi-Fi menu** (`gits-wifi`, bar click), **Bluetooth menu** (`gits-bt`), **power-profile menu** (bar module) |
| Popups | **control panel** (`gits-panel`, Super+Shift+C, the cog next to the power button: toggles, volume/brightness/keyboard sliders, power profile, charge limit, screenshot/OCR/picker/clipboard, lock/sleep/logout/reboot/off with confirmation), **player popup** (Super+Shift+M, click on the bar player: cover, seek, transport; follows the player that is actually playing), **notification centre** (Super+Shift+N, click on the bell); all open with a GitS "scan" effect (the card is uncovered from the top by a bright scan line with glitch slivers and a double flicker, and folds back up on close) and close on Esc or an outside click; the list menus (Wi-Fi, Bluetooth, notification actions, **all settings** on Super+I) are GTK popups too, not rofi |
| System | `gits-update` (snapshot via snap-pac, `paru -Syu`, then `gits-doctor --fix` and a reboot hint), **screen recording** `gits-rec` (Super+Alt+R area / Super+Ctrl+R monitor, red REC indicator in the bar; needs `wf-recorder`), **sound mixer** popup (Super+Alt+V, click the volume icon: master, output devices, one slider per application), health chip in the panel footer plus a login alert when `gits-doctor` finds a FAIL |
| Work | `gits-project` (Super+O): git repos and Godot projects, most recent first, with the repo state at a glance (`●2 ↑1 ↓0 ✓`); Enter opens a terminal in the folder (and the Godot editor for Godot projects). `gits-focus` (Super+F): pomodoro timer, notifications paused while you work, counter in the bar. `gits-note` (Super+N adds a line to `~/notes/inbox.md`, Super+Shift+O lists and copies) |
| Night light | `gits-daynight`: evening / night warmth schedule for hyprsunset (off by default; gentle / warm / strong presets) |
| Power timers | `gits-idle` (Super+I -> Sleep and power timers, the SLEEP TIMERS button of the panel): dim / lock / screen off / sleep, separately for AC and battery, written into hypridle.conf and switched on plug/unplug |
| Settings | `gits-settings` (Super+I, the ALL SETTINGS button of the panel): network, sound, displays, KDE settings, and the selectors for tiling layout (also Super+Shift+L), workflow and animations; own rows via `~/.config/gits/settings.tsv` |
| Keys | Super+Ctrl+T / the touchpad key: touchpad off/on (`gits-touchpad`, OSD, per-device so mice keep working); M4 / ROG key (KEY_PROG1 = `XF86Launch1`): ROG Control Center, again = close (`gits-rog`) |
| OSD | volume / brightness / keyboard backlight / mic on-screen display (`gits-osd`, bottom centre) |
| Sounds | short synthesised terminal blips: notification, login, lock/unlock, charger plug/unplug (`gits-sound`, mute with `gits-sound off`) |
| Icons | `GitS-Icons`: Tela-circle-grey with cyan folders (built at install time) |
| Terminal | kitty (JetBrainsMono Nerd Font Mono, like the rest of the desktop) banner + fastfetch (the picture also works inside tmux, via kitty unicode placeholders), tmux themed, autostart per kitty window is **opt-in** (`export GITS_TMUX=1`), starship prompt, fzf, bat, btop, lazygit, tmux, yazi themes, `GitS-Cursors` (drawn with cairo) |
| Editors and apps | Neovim (LazyVim) colourscheme, VS Code / Code-OSS theme, Zen browser chrome, Logseq theme, Qt/KDE (Dolphin) via Kvantum, Telegram theme builder |
| Ops | `gits-doctor` health report, login-race guards, `gits-doctor --fix` (repairs what updates undo), `gits-sessions` (tmux project switcher, prefix + f), `Super+J` that works in the master layout too, optional btrfs snapshot setup (`home/.local/share/gits-snap/setup.sh`: snapper timeline + GRUB entries), [pitfalls](docs/PITFALLS.md) written down |

## Gallery

![Desktop](docs/img/desktop.jpg)
**Desktop:** waybar, widgets (clock, calendar, player, weather, network, battery, load, audio spectrum, to-do). Demo data, no personal info.

| | |
|---|---|
| ![Control panel](docs/img/control-panel.jpg) **Control panel** (the power button, Super+Shift+C): toggles, sliders, power profile, charge limit, tools, session, health chip | ![Player](docs/img/player.jpg) **Player popup** (Super+Shift+M) |
| ![Mixer](docs/img/mixer.jpg) **Sound mixer** (Super+Alt+V): master, outputs, one slider per app | ![Notifications](docs/img/notifications.jpg) **Notification centre** (Super+Shift+N) |
| ![Settings](docs/img/settings-menu.jpg) **All settings** (Super+I) | ![OSD](docs/img/osd.jpg) **On-screen display** for volume, brightness, keyboard backlight, touchpad |
| ![Terminal](docs/img/terminal.jpg) **Terminal:** kitty banner + fastfetch | ![Neovim dashboard](docs/img/nvim-dashboard.jpg) **Neovim dashboard** |
| ![Neovim](docs/img/nvim.jpg) **Neovim** (LazyVim) colourscheme, lualine, bufferline | ![Launcher](docs/img/launcher.jpg) **launcher** |
| ![wlogout](docs/img/wlogout.jpg) **wlogout** power menu | ![SDDM](docs/img/sddm.jpg) **SDDM** login (Qt6) |
| ![Dolphin](docs/img/dolphin.jpg) **Dolphin** (Kvantum) with `GitS-Icons` cyan folders | ![Logseq](docs/img/logseq.jpg) **Logseq** |

The popups open with a scan-line "power-on" effect (a bright line uncovers the card from the top). The lock screen (hyprlock), Plymouth and GRUB themes are not
pictured: they cannot be screenshotted safely on a live session. `tools/screenshots.sh` regenerates the pictures above on an empty workspace with the
widgets and popups in their demo modes.

## Requirements

* Arch-based distro with **Hyprland 0.55+** (the config is Lua). Developed on CachyOS + Hyprland 0.56. Works from a bare Hyprland install; a
  previous HyDE setup is fine too, its files are backed up and replaced (see below).
* Packages: see [`packages.txt`](packages.txt). `./install.sh --deps` installs them. AUR: `bibata-cursor-theme`
  (the cursor builder reuses its alias links) and `tela-circle-icon-theme-grey` (base of the icon theme).

## Install

```bash
git clone https://github.com/electrocrem/gits-hyde.git
cd gits-hyde
./install.sh --dry-run          # look at what would happen
./install.sh                    # user-level install, no sudo
./install.sh --system           # SDDM + Plymouth + GRUB themes (sudo)
```

Options: `--deps` (pacman), `--login-guards` (blind-login guard for hybrid AMD/NVIDIA laptops), `--telegram` (build the
Telegram theme into `~/Downloads`), `--fix-grub` (see below), `--dry-run`.

Then **log out and in** (Hyprland session): the compositor reads its config at login. To look at it first, inside your current session:
`GITS_NESTED=1 Hyprland -c ~/.config/hypr/hyprland.lua` opens it in a window (no services are started). A module of the config that fails to
load does not stop the others; the error goes to `~/.local/state/gits/config-errors.log` and `gits-doctor` reports it.

Afterwards run `gits-doctor` (read-only): it checks the session, units, config, theme files, the boot chain and Zen.

**Coming from HyDE?** The installer replaces `~/.config/hypr/hyprland.lua`, hyprlock/hypridle/dunst/kitty/GTK/Qt configs (all backed up).
HyDE's own login hook (`~/.local/lib/hyde/shell/activate`, sourced by its zsh config) exports `HYPRLAND_CONFIG=~/.local/share/hypr/hyde.lua`,
which would make Hyprland load HyDE's config first: rename that file (`mv activate activate.off`) before logging in. After that HyDE
(`~/.local/share/hypr`, `~/.local/lib/hyde`, `~/.config/hyde`, `~/.local/share/hyde`, `hyde-shell`) is not used by anything here and can be deleted.

### What the installer touches

* Copies `home/` into `$HOME` (`@HOME@` becomes your home directory). Anything that already exists and differs is
  moved to `~/.local/share/gits-hyde/backup/<time>/`.
* Appends marked blocks (`>>> gits-hyde:… >>>`) to **your** `~/.config/zsh/user.zsh` and `~/.config/nvim/lua/config/options.lua`.
  Nothing else in those files is changed.
* Puts the wallpapers in `~/.local/share/gits/wallpapers/`, the session units in `~/.config/systemd/user/`, builds the cursor, icon and
  sound themes. Login sets the GTK theme (adw-gtk3-dark + our colours), icons and cursor through gsettings.
* Recolours `~/.config/kdeglobals` accents, registers the VS Code theme, installs Zen styles into the default
  profile, swaps the stylesheet of the Logseq *Nord* theme plugin (originals are kept).
* `--system` copies the SDDM theme to `/usr/share/sddm/themes`, writes `/etc/sddm.conf.d/zz-gits.conf`, builds and
  installs the Plymouth/GRUB themes (`home/.local/share/gits-boot`, it can `--revert`).

### GRUB "sparse file not allowed" screen

If GRUB prints `error: commands/loadenv.c:check_blocklists:289:sparse file not allowed. Press any key to continue`
on every boot (btrfs root + `GRUB_SAVEDEFAULT=true`), run `./install.sh --fix-grub`. GRUB will then always boot the
first entry instead of the last chosen one. Details in [docs/PITFALLS.md](docs/PITFALLS.md).

## Uninstall

```bash
./uninstall.sh            # restores backups, deletes what was created, removes the appended blocks
```

System-level pieces are left alone; the commands to revert them are printed at the end.

## Layout

```
install.sh / uninstall.sh   installer and its inverse
packages.txt                pacman packages needed
home/                       mirror of $HOME (config files, scripts, extensions)
assets/                     pictures (wallpapers, lock/boot art, banner) — see NOTICE.md
zen/  logseq/               browser and notes-app styles (installed by tools/post.py)
tools/export.py             refresh this repo from your live $HOME (maintainers)
tools/make-assets.py        generates original placeholder artwork when assets/ is incomplete
tools/post.py               idempotent edits: kdeglobals, Logseq, VS Code, Zen
docs/PITFALLS.md            what broke and why
docs/PALETTE.md             the colours
docs/STANDALONE.md          how the HyDE dependency was removed
```

## Updating this repo from a live system

```bash
tools/export.py --check     # what differs between $HOME and the repo
tools/screenshots.sh        # retake docs/img on an empty workspace (demo data, ~1 minute, do not touch the mouse)
tools/export.py             # copy it over (explicit manifest, no images except assets/, no backups/caches)
```

## Notes

* Tested end to end on the author's machine (CachyOS, Hyprland 0.56 Lua config, AMD + NVIDIA laptop). The
  installer's file handling (backups, idempotency, uninstall round trip) is tested against a throw-away `$HOME`.
  Boot-time pieces (Plymouth/GRUB) cannot be exercised without a reboot.
* Logseq: only the route through an installed theme plugin is tested. On a fresh Logseq copy
  `logseq/gits.css` to `<graph>/logseq/custom.css`.
* Widget location/weather: `GITS_WEATHER_LOCATION="Berlin"` (default: by IP, `off` disables the request).

## License

Code and configs: MIT, see [LICENSE](LICENSE). The pictures in `assets/` and third-party files are **not** covered by it,
see [NOTICE.md](NOTICE.md).
