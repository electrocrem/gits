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
Zen, Logseq, Obsidian, Telegram, Spotify (Spicetify) and Discord (Vesktop). Plus matching icons (Flatpak apps too) and cursors, and login, boot and lock screens in the same style.

**It looks after itself.** `gits-doctor` checks that everything is in order and can repair what an update breaks. `gits-update` takes a
snapshot, updates the system, and then runs the repair.

## The keys you will use most

| Keys | What happens |
|---|---|
| `Super+A` | launcher and command palette |
| `Super+V` · `Super+Tab` · `Super+,` | clipboard history · window switcher · emoji picker |
| ``Super+` `` | workspace overview: thumbnails, drag a window's icon to another workspace |
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

* **Look:** `Super+I` → *Appearance*: the colour theme, your own accent colour on top of it, the lock-screen mascot, the radio's dancer
  and each theme's wallpaper in one window. Or `gits-theme set NAME` / `gits-theme option NAME accent '#FF2E97'`. A theme is a small file in `~/.config/gits/themes/` that gives
  the roles of `gits.theme` (background, accent, red...) other colours; the whole desktop is recoloured from it and `gits-theme set gits`
  brings the originals back exactly.
* **Window motion:** `Super+Shift+Y` — `cyber` (simple and sharp, the default), `gits` (hard snap), `lively` (springs and bounces), or `off`.
* **Wallpaper:** `gits-wall --pick`, or drop pictures into `~/Pictures/wallpapers` — GIFs work too.
* **Another radio station:** set `GITS_RADIO_STREAM` and `GITS_RADIO_API` (any AzuraCast station). Prefer a calmer Lain? `GITS_RADIO_LAIN_SPEED=0.5`;
  no flash on the beat: `GITS_RADIO_FLASH=0`; her own colours: `GITS_RADIO_LAIN=color`.
* **A plainer lock screen:** copy `~/.config/hypr/hyprlock/static.conf` over `~/.config/hypr/hyprlock.conf`.
  On battery the animations already run slower (`gits-lock`, about a third of the CPU); `GITS_LOCK_LITE=always` or `never` overrides that.
* **Weather card:** `GITS_WEATHER_LOCATION="Berlin"` (it guesses by IP otherwise).
* **Home server card:** `hl.env("GITS_SERVER", "pi")` in `local.lua` (a Host from `~/.ssh/config`, or `user@host`) shows a Raspberry Pi or any
  Linux box on the desktop: CPU, RAM, temperature, disks, Docker containers and undervoltage. It needs key login and `python3` on the server,
  nothing is installed there. `GITS_SERVER_NAME` changes the name on the card.
* **Desktop cards and the bar:** `Super+I` → *Widgets and bar*: click a tile to show / hide it, drag it (or Alt+arrows) to change
  the order; cards stay on their side of the screen, bar modules in their part of the bar. *DEFAULTS* puts both back.
* **Games:** while a Steam game runs the desktop switches itself to the *gaming* workflow, puts the game in gamemode and pauses
  notifications; all of it goes back when you quit (and you are told how many notifications came in). Off: `GITS_AUTO_GAMEMODE=0`.
* **Clipboard history** (`Super+V`): pictures show a preview; `Del` removes an entry, `Ctrl+S` pins a text so it stays on top for good.
* **Battery:** the battery card shows its health (what it holds now against new), the charge limit and the time left;
  `Super+I` → *Battery charge limit* sets 80 / 85 / 90 / 100 % or one full charge (ASUS laptops through asusctl).
* **Backups card:** `hl.env("GITS_KUMA", "http://host:3001/status/SLUG")` in `local.lua` shows the Uptime Kuma push monitors of that
  status page whose group is called *backup*, green or red, with the time of the last good run; click backs up this laptop now.
* **Greeting and daily brief:** at login a short "link established" greeting (a key skips it), then once a day the brief:
  weather, backups and server (Uptime Kuma), updates, battery and disk, yesterday's screen time (`Super+I` → *Daily brief*).
  Off: `GITS_HELLO=0`, `GITS_BRIEF=0`.
* **Screensaver:** digital rain in the theme's colours with a big clock; `Super+I` → *Sleep and power timers* → *Screensaver*
  (off by default; never over a full-screen game or video). Try it: `gits-saver preview`.
* **Time report:** `Super+I` → *Time report*: which applications had the focus today / over 7 days (local, names only; not while
  locked or away). The data is in `~/.local/share/gits/activity`.
* **Downloads:** `Super+I` → *Sort Downloads*: new files go to Images, Documents, Archives, Apps, Video, Audio, Torrents, Keys,
  Code; after 30 days to `Old/YYYY-MM`. Nothing is deleted, `gits-downloads undo` puts the last batch back. Off by default.
* **Lyrics:** the player card and the media popup show the line being sung (lrclib.net; `GITS_LYRICS=0` turns it off).
* **Phone:** `Super+Ctrl+M` sends the clipboard (a link opens on the phone), the newest screenshot or a file to your phone over KDE Connect, or rings it to find it. **Text from the screen:** `Super+Ctrl+S`, pick a region, the text (English and Russian) is in the clipboard.
* **Reminders:** type "через 20м чай", "in 1h30 stretch" or "в 18:30 созвон" in `Super+A` (Russian or English); at that time a notification with Snooze / Done, a chime and a copy on your phone. Super+I → Reminders lists and cancels them.
* **Git projects:** `Super+O` shows each project's state (● uncommitted files, ↑ commits to push, ↓ to pull); a timer fetches every 30 min so ↓ is real, and at 21:00 one notification lists your repos with work not yet on GitHub (only yours: origin on your GitHub account).
* **Desktop sound bars:** while music plays and the desktop is empty, a quiet spectrum along the bottom of the wallpaper (on AC power, not in gaming mode; GPU-drawn on the integrated graphics). Super+I → Desktop sound bars, `gits-ambient off`.
* **Reboot reminder:** after an update that only takes effect after a reboot (new kernel: its modules are gone, so USB drives and VPNs may stop working; a newer NVIDIA driver than the one loaded), one notification per boot with Reboot now / Later. Super+I → Reboot to finish updates shows why.
* **Drives:** a USB stick or SD card is mounted when plugged in, with Open / Eject in the notification; Eject flushes the writes first and names the program that keeps a busy drive; pulling one out without Eject gets a warning. Super+I → Drives.
* **Workspace presets:** `Super+Ctrl+W` opens a set of apps on their workspaces in one go (examples: Dev = browser, terminal, Godot; Chill = Steam, Spotify, Telegram). Apps that already run are moved, not started twice. "Save the windows open now" turns your current layout into a preset; they are JSON files in `~/.config/gits/presets`.
* **Free disk space:** Super+I → Free disk space lists what can go (old package versions, AUR and uv caches, the trash, shader caches of removed games, the Spotify cache, caches unused for 60 days, old logs, crash dumps, orphaned packages) with its size; tick, clean, one polkit prompt for the system parts. `gits-clean scan` in a terminal.
* **UI sounds:** short synthesised sounds for messages, lock / unlock, charger, screenshots, sending to the phone, the YubiKey waiting for a touch, game mode and low battery, in three packs (`terminal` blips, `soft` tones, `glass` bells) and three volumes: Super+I → UI sounds, `Super+Shift+U` mutes them.
* **YubiKey (or any FIDO2 key):** register it once (`pamu2fcfg > ~/.config/Yubico/u2f_keys`), then `sudo ~/.local/share/gits-yubikey/setup.sh`.
  Login and lock screen then want the password and a touch (in that order: password, Enter, touch the blinking key); `sudo` and the
  polkit dialogs take a touch instead of the password. A hint shows wherever the key is waited for. Without the key for a while:
  `Super+I` → *YubiKey* or `yubikey-mode off 8h`. Lost it while locked: `Ctrl+Alt+F3`, log in there, `sudo yubikey-mode off`.
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
