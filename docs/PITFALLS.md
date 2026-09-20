# Pitfalls found while building this (and how the setup deals with them)

Notes from real breakage on a CachyOS + Hyprland 0.56 (Lua config) laptop with an AMD iGPU and an NVIDIA dGPU.

## Login and session

* **Login race on hybrid AMD + NVIDIA.** SDDM's kwin_wayland greeter sometimes still holds the AMD card when the
  session starts. Hyprland then fails with "Could not take device: Device or resource busy" and comes up on the
  NVIDIA card with no monitor, alive but black. `gits-blind-guard.sh` (opt-in: `--login-guards`) ends the session
  after ~12 s without a monitor so SDDM shows the greeter again. Known false positive: logging in with the lid
  closed and no external monitor.
* **Leftover session services.** If Hyprland restarts during login, units of the dead first instance can keep running against
  the old compositor (no bar, no notifications). `gits-doctor` compares the `HYPRLAND_INSTANCE_SIGNATURE` of every `gits-*` unit
  with the current one; `gits-session restart` fixes it. Units that were started on demand by the old compositor (KDE's
  `plasma-kactivitymanagerd`, `plasma-xdg-desktop-portal-kde`) end up as "failed" with "The Wayland connection broke": harmless,
  clear with `systemctl --user reset-failed`.
* **The `Health check` alert right after login can be stale.** It is sent ~90 s after login from the state at that moment; a
  failed unit that was reset later still leaves the notification on screen. Re-run `gits-doctor`.
* **Do not put blocking waits in `~/.zprofile`.** A "wait until the sddm greeter is gone" guard broke four logins in
  a row. Anything in the login path is untestable without a real logout.
* **Waybar at login** can fail with "cannot open display" (it starts before the environment is imported); systemd
  gives up after a few tries. `gits-bar.service` has `Restart=on-failure`, so systemd starts it again.

## Crashes triggered by changing the cursor theme at runtime

Waybar (GTK3) and Zen (GTK3/Wayland) segfault in libgdk-3 when the cursor theme changes while they run
(`hyprctl setcursor`, `gsettings set ... cursor-theme`, `theme.switch`). systemd restarts the bar (`gits-bar.service`) within
a second or two. Three or more Zen crashes make its next start show "Open Zen in Troubleshoot Mode?": close Zen
(`flatpak kill app.zen_browser.zen`) and set `toolkit.startup.recent_crashes` to 0 in the profile's `prefs.js`.

**KDE apps silently undo the cursor theme.** `~/.config/kcminputrc` holds its own `cursorTheme`; whenever a KDE app
(KDE Connect, Dolphin) starts `kded6`, its GTK sync module writes that value into gsettings/xsettingsd. Keep it in
sync with `GitS-Cursors`. `kquitapp6 kded6` makes it segfault (harmless, it restarts).

`~/.local/share/gits-cursor/build.py` draws the cursors with cairo. Its `index.theme` must NOT contain
`Inherits=Bibata-Modern-Ice`, otherwise Hyprland draws Bibata's shapes.

## Portals, doctor and small shell traps

* **A user-level `~/.local/share/xdg-desktop-portal/hyprland-portals.conf` with `FileChooser=kde;gtk`** (some dotfile sets ship one) makes every file dialog start
  `plasma-xdg-desktop-portal-kde`, a KDE service inside a non-KDE session; it dies with every compositor restart and shows up in
  `systemctl --user --failed`. Without the file the system default `hyprland;gtk` applies (GTK dialogs): delete it.
* **`gits-doctor` cannot read `/proc/PID/environ` of every unit.** The polkit agent is non-dumpable, its `environ` is owned by root:
  the shell prints "Permission denied" for the `<` redirection itself, not for the command, so `2>/dev/null` inside the pipe does not
  help. Test `[[ -r ... ]]` first.
* **Match a process by its real `argv[0]`.** `setsid -f rog-control-center` runs as `rog-control-center`, not `/usr/bin/rog-control-center`;
  `pgrep -f "^/usr/bin/..."` never matched, so the doctor warned and the autostart could start a second copy. Use `^(/usr/bin/)?name`.
* **Removing the last file a shell glob expects** (`~/.config/zsh/completions/*.zsh`) turns the loop into an error in zsh: add `(N)`.

## Look, lock screen and menus

* The **workflow** `gaming` silently overrides the whole look (gaps 0, no blur/shadow/animations, opacity 1). Keep
  `01-default` unless you are gaming (`gits-workflow set 01-default`).
* **Hyprlock**: never
  stop a live hyprlock (`pkill`/`systemctl stop`): ext-session-lock treats that as a crash and locks you out;
  recover with `hyprctl --instance 0 eval 'hl.clear_crashed_lockscreen()'`.
* dunst: put extra rules in `dunstrc.d/` (drop-ins) instead of editing `dunstrc`.
  rofi ignores `display-columns` in a theme file, hence the wrapper script for the action menu.

## Icons

`GitS-Icons` (`home/.local/share/gits-icons/build.py`) inherits Tela-circle-grey and recolours only the `places` icons.
Qt resolves `inode-directory` (what Dolphin asks for) through an alias that the base theme has in every size; if the
alias is copied only to the small fixed sizes Qt picks the flat 16 px glyph even for big icons, so the builder copies
aliases (including links to links) to the `scalable` directories too. `kiconfinder6 <name>` shows which file wins.

## Boot

* **GRUB theme parser rejects decimals** (`top = 95.5%` → "grub_strtoull: unrecognized number"): integers only.
* `/etc/default/grub` may ship broken quoting on `GRUB_CMDLINE_LINUX_DEFAULT`; the boot installer repairs it.
* **"error: commands/loadenv.c:check_blocklists:289:sparse file not allowed. Press any key to continue"** on every
  boot: `GRUB_DEFAULT=saved` + `GRUB_SAVEDEFAULT=true` make each entry run `save_env`, but `grubenv` on btrfs cannot
  be written. `./install.sh --fix-grub` sets `GRUB_DEFAULT=0`, `GRUB_SAVEDEFAULT=false` and regenerates grub.cfg
  (GRUB then always boots the first entry).

## Apps

* **Zen** paints its background through `.zen-browser-generic-background` variables: override them there, not only on
  `:root`. Styles load at browser start only. A real HUD new-tab page would need a signed extension.
* **Logseq** does not read `~/.logseq/config/custom.css`; only per-graph `logseq/custom.css` and theme plugins.
  The selected theme lives in the app's state (Logseq rewrites `preferences.json` on start), so the installer swaps
  the stylesheet of an installed theme plugin. A third-party theme must define `--lx-gray-01..12` and
  `--lx-accent-*` itself, and use `html:root:root[data-theme="dark"]` to beat Logseq's own `:root[data-theme=dark]`;
  otherwise sidebar text falls back to `--ls-header-button-background` and disappears.
* **GTK4 apps hang forever at start** (GTK 4.22, generated `Wallbash-Gtk` theme). Cause: `gtk-4.0/settings.ini` inside
  the theme dir (`~/.config/gtk-4.0` is a symlink into it) contains `gtk-application-prefer-dark-theme=true`; GTK reads
  it while loading the theme, switches variant, reloads, and recurses (a deep `libgtk-4` stack in `load_from_file`).
  KDE's `kded6` "gtkconfig" module recreates that file whenever any KDE app
  starts. Fix: `rm ~/.config/gtk-4.0/settings.ini` and `[Module-gtkconfig] autoload=false` in `~/.config/kded6rc`
  (`install.sh` does both; `gits-doctor` checks). Found by bisecting a copy of the theme dir, then each key.
  `gtk4-layer-shell` must still be LD_PRELOADed before GTK loads (widgets.py re-execs itself).
* **KDE Connect** mirrors phone notifications to dunst with HTML-**escaped** markup (`&lt;b&gt;`, `&lt;br/&gt;`), so
  `markup = strip` cannot help; they can also cover the widgets and contain private text. `gits-phone-notify.sh`
  (a dunst rule script) hides the original and shows a cleaned, short copy under the app name "Phone"; the copy has no
  action buttons. Testing tip: `dunstctl set-paused true` while taking screenshots, and check results through
  `dunstctl history` with synthetic messages instead of looking at the screen.
* Never `pkill -f <script name>` from a tool shell: it matches (and kills) the calling shell. Use the `[g]its`
  bracket trick or `pgrep -x`.

## Menus, sounds, power (round 6)

* **XDG autostart never runs in this session.** `xdg-autostart.target` is not started, so `~/.config/autostart/*.desktop`
  (e.g. ROG Control Center) do nothing. Starting the target would launch every autostart file at once; `gits/start.lua`
  starts the one wanted app by hand instead.
* **dunst rule patterns are regular expressions.** `summary = "*"` is invalid ("Invalid preceding regular expression"
  in the journal, one warning per popup); use `".*"`. Scripts of *all* matching rules run, not only the last one.
* **rofi `-theme-str`:** several statements in one argument swallow the strings (`content: "A"; } tag { content: "B"`
  ends up as the text). Pass one `-theme-str` per statement. `-auto-select` with `-filter` returns nothing here, so
  menus are tested by their generated lines, not by scripted picking. Menus map rows to data with `-format i`
  instead of parsing the visible text (long rows get ellipsised).
* **ASUS: asusd already switches the power profile on plug/unplug** (AC and battery profiles, shown by
  `asusctl profile get`). A second switcher would fight it, so the bar module only shows the profile and lets you
  override it until the next plug event.
* **The bar must fit the panel width.** On a 1920x1200 panel at scale 1.5 that is 1280 logical px; waybar reports
  "Bar configured (width: 1312)" when the modules need more and the last ones are cut off. Every added module needs
  a matching diet elsewhere (the power-profile module is icon-only for that reason).
* **Audio spectrum without cava:** `parec -d <default sink>.monitor` (mono s16le) + numpy FFT in a thread. The
  card re-checks the default sink every 4 s (headphones on/off) and only animates while sound plays.

## Terminal, tmux, notifications (round 6b)

* **Installer blocks next to hand-made hooks run twice.** The same line lived in `user.zsh` (added by hand earlier) and in
  the `gits:zsh` block: `banner.zsh` was sourced twice, fastfetch printed twice. Same story for `hyprland.lua`
  (inline hooks + the block of a module). `gits-doctor` now counts the hooks.
* **kitty pictures inside tmux:** `fastfetch --logo-type kitty-direct` does not pass through tmux. The banner uses
  `kitten icat --unicode-placeholder --passthrough=tmux`: the image data goes through tmux's DCS passthrough
  (`allow-passthrough on`), the pane only holds text cells. icat prints those rows with absolute positioning
  (`\e7 \e[1;0H ... \e8`) which has to be stripped, and the image id rides in the foreground colour (tmux needs the
  `RGB` terminal feature). fastfetch without a logo aligns values with `\e[7G` (jumps into the picture): rebuild the lines.
* **tmux autostart is opt-in (`GITS_TMUX=1`):** one tmux session per kitty window turned out to be more machinery than it is worth for most people.
* **`tmux new-session && exit`, not `exec tmux`** (when the autostart is on): a broken tmux config with `exec` leaves a window that closes at once.
  One session per kitty window needs `detach-on-destroy on`, otherwise closing one session throws its client into another.
* **The battery status flaps near full and battery notifiers spam.** Around 98% (the ASUS charge limit itself was 100%) the status flips between Full / Not charging / Discharging and it posts a critical
  "Battery Full" plus phantom "Charger Plug Out". A dunst rule with `skip_display` + `history_ignore` hides them
  (`dunstrc.d/70-gits-battery.conf`); the real low-battery warnings stay.
* **Animation presets:** `borderangle` with style `loop` redraws every frame while it runs, hence the neon border is opt-in.

## Popups, OSD, layouts (round 6c)

* **Hyprland sends ALL input to an exclusive-keyboard layer surface.** A popup with `KeyboardMode.EXCLUSIVE` gets no clicks
  outside its own rectangle, and a separate click catcher below it never sees one either (tested with a virtual uinput mouse);
  `notify::is-active` never fires for layer surfaces, so "close on focus loss" was dead code too. The popups are therefore one
  fullscreen transparent exclusive surface that draws the card in the corner: click outside the card = close (a click on the
  bar button too, i.e. a toggle), Escape = close.
* **rofi cannot be made to close on a click outside**: it is exclusive too (an invisible catcher below it gets no clicks), and a
  fullscreen transparent rofi window with `click-to-exit` ignores clicks on its empty area. So this setup's own list menus
  (`gits-menu`: Wi-Fi, Bluetooth, notification actions, settings) are GTK popups (`panel.py menu`); a rofi menu, if you add one, still needs Esc.
* **The keybinding hint went blank with a rewritten rofi theme.** `home/.config/rofi/themes/clipboard.rasi` keeps the original widget tree
  and only restyles it. Widgets that carry `content:` must be named `textbox-...`.
* **Testing input without a compositor tool:** `/dev/uinput` is writable for the session user. A virtual mouse (EV_REL + BTN_LEFT)
  moves the pointer and clicks; `hyprctl dispatch 'hl.dsp.cursor.move({x=..,y=..})'` warps it first. A virtual keyboard
  injects keys such as KEY_PROG1. Nudge the pointer a little before clicking, or the click lands on the previous surface.
* **Gtk.Picture stretches its container:** its natural size is the picture's size, so an oddly shaped cover made the media popup
  huge. The cover is now a fixed-size drawing area with centre-crop.
* **`hl.device({ name = ..., enabled = false })` (via `hyprctl eval`) disables one input device at runtime** (checked on a virtual
  mouse); `hyprctl reload` restores it. `hyprctl eval` runs arbitrary Hyprland Lua.
* **`python3` re-execs itself with LD_PRELOAD (gtk4-layer-shell):** the process command line becomes `/usr/bin/python3 ...`,
  so `pgrep -f '^python3 ...'` never matches. A launcher that trusted it started a new OSD daemon on every volume key press
  (50 of them). Match the script path instead, and prefer `$!` of the first launch.
* **`pkill -f pattern` from a tool shell matches the shell's own command line** whenever the pattern text appears in it
  (also in an unrelated sed expression). Use `[x]pattern` and keep the plain text out of the same command.
* **Super+J = dwindle `togglesplit`, but the master layout answers "Unknown master layoutmsg:
  togglesplit".** `gits-layout-toggle` picks the right message for the active layout.
* **dunst patterns are POSIX regular expressions:** no `(?i)`, no `\\.` escapes in the config (use `[.]`).
* **Hyprland does not reload a `dofile`d file on its own:** after editing a `gits/*.lua` module run `hyprctl reload`.
* **A stock hypridle.conf turns the screen off with `hyprctl dispatch dpms off`, which does not exist in the Lua config** ("')' expected near 'off'"): the
  screen-off stage never worked. The working form is `hyprctl dispatch 'hl.dsp.dpms({ action = "off" })'`; `gits-idle` generates it. Never start a
  second hypridle to test a config: its lock and suspend actions really run.
* **`pactl` prints "Invalid ASCII character" for non-ASCII stream names but the JSON that follows is fine:** read stdout only and decode
  with `errors="replace"` (a Cyrillic track title otherwise breaks the mixer). Group streams by application: Spotify opens two.
* **Never signal waybar with a real-time number that no module registered:** the default action of `SIGRTMIN+n` is to terminate it.
  Modules that must update fast poll (`interval: 1`) instead of using a signal that other layouts may not define.
* **A shell-script stand-in for a binary has the interpreter's name in `/proc/PID/comm`:** detect processes through the command line
  when testing with stubs.
* **A dashboard picture that needs more rows than the window has simply vanishes.** The Neovim dashboard now crops the art from the bottom to the
  rows that are left (tagline box + keys need ~19), and hides it only below 14.
* **GTK4 CSS `transform` animations do not run with the cairo renderer** (only `opacity` did): a `scaleY` "open from a line" keyframe left the card at full
  height. `Gtk.Revealer` with `SLIDE_UP` uncovers a card top-down (`SLIDE_DOWN` slides it in from above, bottom first), and a drawing area laid over it
  paints the scan line at the revealed edge; nothing redraws once the effect is over. `GITS_PANEL_SLOW=1` slows it 10x for frame-by-frame screenshots.
* **A theme-switch tool writes `~/.config/gtk-3.0/settings.ini`**, so an icon theme built after the last switch is missing there
  (`Tela-circle-grey` instead of `GitS-Icons`). `gits-doctor --fix` edits the key; do not re-run the theme switch for this (it changes the cursor theme at
  runtime, which crashes waybar and Zen).
* **hyprsunset reads its profiles from `~/.config/hypr/hyprsunset.conf` and switches by the clock itself**; only its unit needs a restart after a change.
  Profile blocks that contain only comments (the stock sample) are dropped by `gits-daynight`.
* **A preloaded library is inherited by every child process.** The GTK4 apps here re-exec themselves with `LD_PRELOAD=libgtk4-layer-shell.so` (it must be loaded
  before libwayland). Every `bash`/`git`/`hyprctl` they spawned inherited it and loaded GTK's libraries too: `gits-project --tsv` took 2.9 s from Python but
  0.07 s from a shell, and the launcher needed 3.6 s to appear. `os.environ.pop("LD_PRELOAD")` right after the imports fixed it (launcher 0.55 s).
* **`subprocess.run(capture_output=True)` waits for EOF on the pipes:** a `git status` that leaves a background maintenance process behind keeps them
  open. Give background jobs `</dev/null 2>/dev/null` and do the cheap work before the slow work.
* **`gits-panel close` followed at once by `gits-panel <same mode>`** was swallowed (the dying popup still looked alive, so the second call toggled it off);
  `close` now waits until the old process is gone.
