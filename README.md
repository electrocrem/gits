# gits — Ghost in the Shell for Hyprland

A whole *Ghost in the Shell* desktop for Hyprland: deep navy and cyan phosphor, square corners, thin frames, kanji tags — and a little Lain dancing
where you least expect her. One installer gives your session a new look and feel, one uninstaller takes it away again, and nothing of yours is
overwritten without a backup.

[Русская версия](README.ru.md)

![Popups opening one after another: launcher, clipboard, key bindings, player, mixer](docs/img/demo.gif)

![Desktop](docs/img/desktop.jpg)

## What you get

**A desktop that feels alive.** Clock, calendar, weather, network, battery, load and a to-do list glow on your wallpaper, next to an audio
spectrum that moves with whatever is playing. The bar at the top shows what you need and nothing more. Windows snap in crisply, and you can
change the motion (or turn it off) any time with `Super+Shift+Y`.

**Everything is one keystroke away.** `Super+A` opens a launcher that finds apps, settings, projects, open windows and notes, and does maths.
`Super+V` is your clipboard history, `Super+Tab` jumps between windows, `Super+,` picks an emoji, and `Super+/` lists every shortcut there is.

**Music, and a radio with a dancer.** `Super+Shift+M` pages through everything that is playing — Spotify, a browser tab, a video — and the last
page is a web radio (DATAMOSH; any AzuraCast station works). It shows what is on air, the cover, how many are listening, and a hologram Lain
who dances on the live spectrum, faster with the music, jumping when the beat hits. `Super+R` opens it straight away.

**A lock screen with a pulse.** The clock glitches now and then, the cursor blinks, a scanner runs along the line, and Lain dances at the
edge of the picture.

**Comfortable basics.** A control panel (`Super+Shift+C`) with the usual toggles and sliders, a sound mixer with one slider per app, a
notification centre, Wi-Fi and Bluetooth menus, on-screen display for volume and brightness, a power menu, quick notes, a focus timer,
screenshots with OCR, screen recording, a night-light schedule, and separate sleep timers for the wall socket and the battery.

**A terminal and apps that match.** A banner in kitty, a themed prompt, tmux, btop, lazygit, yazi, Neovim, VS Code, Dolphin, and styles for
Zen, Logseq, Telegram, Spotify (Spicetify) and Discord (Vesktop). Plus matching icons (Flatpak apps too) and cursors, and login, boot and lock screens in the same style.

**It looks after itself.** `gits-doctor` checks that everything is in order and can repair what an update breaks. `gits-update` takes a
snapshot, updates the system, and then runs the repair.

## The keys you will use most

| Keys | What happens |
|---|---|
| `Super+A` | launcher and command palette |
| `Super+V` · `Super+Tab` · `Super+,` | clipboard history · window switcher · emoji picker |
| `Super+/` | every shortcut, searchable |
| `Super+Shift+M` · `Super+R` | media popup with all players · the radio |
| `Super+Shift+C` · `Super+Alt+V` · `Super+Shift+N` | control panel · sound mixer · notification centre |
| `Super+I` | all settings in one menu |
| `Super+N` · `Super+F` · `Super+O` | quick note · focus timer · open a project |
| `Super+P` · `Super+Ctrl+S` · `Super+Alt+R` | screenshot a region · read text from the screen · record an area |
| `Super+L` | lock the screen |
| `Super+Shift+Y` · `Super+Shift+L` · `Super+Shift+X` | window animations · tiling layout · workflow (default, editing, gaming, battery saver) |
| `Super+Alt+W` · `Super+Alt+B` · `Super+Shift+W` | Wi-Fi · Bluetooth · wallpaper |
| `Super+Alt+N` · `Super+Ctrl+N` · `Super+Alt+I` | night light schedule · night light now · sleep timers |
| `Super+Shift+R` · `Super+Shift+U` · `Super+F7` / `F8` / `F9` | radio on / off · UI sounds on / off · previous / play-pause / next |
| `Super+Shift+T` · `Super+Alt+U` · `Super+Alt+D` · `Super+Shift+B` | tmux sessions · update the system · health report · restart the bar and services |

## Gallery

![Tiling](docs/img/tiling.jpg)
**Tiling** with gaps and neon borders: the terminal banner, yazi and Neovim side by side.

![Bar](docs/img/bar.jpg)
**The bar:** workspaces, clock, player, load and temperature, Wi-Fi, Bluetooth, volume, layout, mode, notifications, battery, tray, power.

### Launcher and quick tools
| | |
|---|---|
| ![Launcher](docs/img/launcher.jpg) **Launcher** (`Super+A`): apps, settings, projects, windows, notes and web search in one field | ![Calculator](docs/img/calculator.jpg) **Calculator** in the same field: `sqrt(1764) * 2`, `2^10`; Enter copies the result |
| ![Clipboard](docs/img/clipboard.jpg) **Clipboard history** (`Super+V`): text and images | ![Window switcher](docs/img/windows.jpg) **Window switcher** (`Super+Tab`) |
| ![Emoji](docs/img/emoji.jpg) **Emoji and symbols** (`Super+,`): search by name | ![Key bindings](docs/img/keys.jpg) **Every shortcut** (`Super+/`), searchable |
| ![Quick note](docs/img/note.jpg) **Quick note** (`Super+N`) into `~/notes/inbox.md` | ![Focus timer](docs/img/focus.jpg) **Focus timer** (`Super+F`): a pomodoro with a counter on the bar |

### Panels and menus
| | |
|---|---|
| ![Control panel](docs/img/control-panel.jpg) **Control panel** (`Super+Shift+C`): toggles, sliders, power profile, tools, session | ![Media](docs/img/player.jpg) **Media popup** (`Super+Shift+M`): one page per sound source; switch with the arrows, the dots, ← → or a two-finger swipe |
| ![Radio](docs/img/radio.jpg) **Radio** (`Super+R`): Lain dances on the live spectrum, flashing on the beat | ![Mixer](docs/img/mixer.jpg) **Sound mixer** (`Super+Alt+V`): master, outputs and one slider per app |
| ![Notification centre](docs/img/notifications.jpg) **Notification centre** (`Super+Shift+N`) | ![Wi-Fi](docs/img/wifi.jpg) **Wi-Fi** (click the bar icon) |
| ![Bluetooth](docs/img/bluetooth.jpg) **Bluetooth** (click the bar icon) | ![Settings](docs/img/settings-menu.jpg) **All settings** (`Super+I`) |
| ![OSD](docs/img/osd.jpg) **On-screen display** for volume, brightness, keyboard backlight | ![Notification popups](docs/img/notification-popups.jpg) **Notification popups**: normal, critical, from your phone |
| ![Power menu](docs/img/wlogout.jpg) **Power menu** |  |

### Terminal and tools
| | |
|---|---|
| ![Terminal](docs/img/terminal.jpg) **Terminal**: the banner and the prompt | ![gits-doctor](docs/img/doctor.jpg) **`gits-doctor`**: the health report |
| ![Neovim dashboard](docs/img/nvim-dashboard.jpg) **Neovim** start screen | ![Neovim](docs/img/nvim.jpg) **Neovim** with the GitS colours |
| ![tmux](docs/img/tmux.jpg) **tmux** | ![lazygit](docs/img/lazygit.jpg) **lazygit** |
| ![yazi](docs/img/yazi.jpg) **yazi** | ![btop](docs/img/btop.jpg) **btop** |

### Apps, login and lock
| | |
|---|---|
| ![Dolphin](docs/img/dolphin.jpg) **Dolphin** with cyan folders | ![VS Code](docs/img/vscode.jpg) **VS Code / Code-OSS** |
| ![SDDM](docs/img/sddm.jpg) **Login screen** (SDDM) | ![Lock screen](docs/img/lock.jpg) **Lock screen**: a dancing Lain, a glitching clock, a blinking cursor |

## Install

You need an Arch-based system with **Hyprland 0.55 or newer** (developed on CachyOS with Hyprland 0.56). The list of packages is in
[`packages.txt`](packages.txt), and `./install.sh --deps` installs them for you.

```bash
git clone https://github.com/electrocrem/gits.git
cd gits
./install.sh --dry-run          # look at what would happen first
./install.sh                    # install for your user, no sudo
./install.sh --system           # plus the login, boot and GRUB screens (asks for sudo)
```

Then **log out and back in** and pick the Hyprland session. Afterwards run `gits-doctor`: it looks over the session, the services, the theme and
the boot screens and tells you if something is off.

**Your files are safe.** Anything the installer would replace is first moved to `~/.local/share/gits-install/backup/<time>/`. It adds a few
clearly marked lines to your zsh and Neovim config and changes nothing else in them. Running the installer twice is harmless.

Want a peek without logging out? `GITS_NESTED=1 Hyprland -c ~/.config/hypr/hyprland.lua` opens the desktop in a window.

Other options: `--telegram` builds a Telegram theme into `~/Downloads`, `--login-guards` helps laptops with hybrid AMD/NVIDIA graphics that sometimes
log in to a black screen, and `--dry-run` only shows what would be done.

## Uninstall

```bash
./uninstall.sh
```

It restores your backups, removes what it created and takes its lines out of your zsh and Neovim config. The login, boot and GRUB screens
need sudo, so the commands to undo them are printed at the end.

## Make it yours

* **Colour theme:** `Super+I` → *Colour theme*, or `gits-theme set NAME`. A theme is a small file in `~/.config/gits/themes/` that gives
  the roles of `gits.theme` (background, accent, red...) other colours; the whole desktop is recoloured from it and `gits-theme set gits`
  brings the originals back exactly. Shipped: `gits` (Ghost in the Shell) and `lain` (Serial Experiments Lain: lavender, cream, wire red).
* **Window motion:** `Super+Shift+Y` — `cyber` (simple and sharp, the default), `gits` (hard snap), `lively` (springs and bounces), or `off`.
* **Wallpaper:** `gits-wall --pick`, or drop pictures into `~/Pictures/wallpapers` — GIFs work too.
* **Another radio station:** set `GITS_RADIO_STREAM` and `GITS_RADIO_API` (any AzuraCast station). Prefer a calmer Lain? `GITS_RADIO_LAIN_SPEED=0.5`;
  no flash on the beat: `GITS_RADIO_FLASH=0`; her own colours: `GITS_RADIO_LAIN=color`.
* **A plainer lock screen:** copy `~/.config/hypr/hyprlock/static.conf` over `~/.config/hypr/hyprlock.conf`.
* **Weather card:** `GITS_WEATHER_LOCATION="Berlin"` (it guesses by IP otherwise).
* **Home server card:** `hl.env("GITS_SERVER", "pi")` in `local.lua` (a Host from `~/.ssh/config`, or `user@host`) shows a Raspberry Pi or any
  Linux box on the desktop: CPU, RAM, temperature, disks, Docker containers and undervoltage. It needs key login and `python3` on the server,
  nothing is installed there. `GITS_SERVER_NAME` changes the name on the card.
* **Add your own rows** to the settings menu in `~/.config/gits/settings.tsv`.
* **Monitors and other per-machine settings:** put them in `~/.config/hypr/gits/local.lua` (for example
  `hl.monitor({ output = "DP-3", mode = "2560x1440@180", position = "0x0", scale = 1 })`). It loads last and the installer never touches it.

## If something looks wrong

Run `gits-doctor` first; `gits-doctor --fix` repairs what an update usually breaks. If GRUB shows
`error: ... sparse file not allowed. Press any key` on every boot, run `./install.sh --fix-grub`. More in [docs/PITFALLS.md](docs/PITFALLS.md).

## For tinkerers

How the repo is laid out, what exactly the installer touches, and how the pictures are made: [docs/MAINTAINING.md](docs/MAINTAINING.md).
The colours are in [docs/PALETTE.md](docs/PALETTE.md).

## License

Code and configs: MIT, see [LICENSE](LICENSE). The pictures in `assets/` and third-party files are **not** covered by it, see [NOTICE.md](NOTICE.md).
