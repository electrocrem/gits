# Leaving HyDE: the plan

Goal: `gits-hyde` becomes a self-contained Hyprland setup (no HyDE at install time or at run time), then HyDE is removed from the author's machine.
Done step by step, the HyDE session stays installed and bootable until the last step.

## What HyDE provides today (inventory, Sep 2026)

| Block | Size | Replaced by |
|---|---|---|
| Hyprland base config (`~/.local/share/hypr/lua/*.lua`: binds, window/layer rules, variables, env, start-up, layouts, workflows, animations) | ~2300 lines + a TOML/dispatcher framework | our own `hyprland.lua` with plain Lua modules, state in `~/.local/state/gits/` (phase 3) |
| 13 systemd units `hyde-Hyprland-*` (bar, dunst, hypridle, wallpaper, clipboard x3, applets x3, blue-light, battery notify, config watcher) | | our own user units / exec hooks (phase 4) |
| `hyde-shell` scripts (~1.9 MB); the ones this setup called: system monitor, volume, brightness, screenshot, logout menu, keyboard switch, cliphist, launcher, theme/wallpaper/layout/workflow/animation/bar/lock-screen selectors, waybar service | | `gits-sysmon`, `gits-vol`, `gits-bright`, `gits-shot`, `gits-logout`, `gits-panel launch/clip`, own selectors (phases 1-3) |
| wallbash colour generation (GTK, Qt/Kvantum, qt6ct, rofi, dunst, kitty, waybar `theme.css`, hyprlock) | | frozen static files built from the fixed GitS palette (phase 5) |
| Theme store, other themes, wallpaper switching | | dropped: one theme |

## Phases

0. **Own UI pieces (done):** control panel, player, mixer, notification centre, settings hub, OSD, launcher / command palette, clipboard history, menus, focus timer, notes, project launcher, idle timers.
1. **Decouple our scripts (done for the easy part):** no `hyde-shell` in the bar, the panel, the volume / brightness / screenshot / logout / system-monitor / keyboard keys, the clipboard and the launcher.
   Left (they need HyDE's state/config system, so they wait for phase 3): selectors for theme, wallpaper, layout, workflow, animations, bar, lock screen; `gits-mode.sh` (workflow switch), the GAME tile, the waybar watchdog and stale guard (they start waybar through `hyde-shell waybar.py --watch`), doctor checks of `staterc`.
2. **Own tools for the rest of HyDE's actions:** `gits-wall` (awww), `gits-battery` (low / critical notifier, on top of `gits-events.sh`), keybinding cheat sheet (from `hyprctl binds`), emoji / glyph pickers in the launcher.
3. **Standalone Hyprland config** (the big one): port variables, binds, window/layer rules, env, start-up, 4 layouts (dwindle, master, monocle, scrolling), 5 workflows (default, editing, gaming, powersaver, snappy), the `gits` animation preset. Test it in a nested Hyprland window first, then as a second SDDM session, never on the running one.
4. **Session services:** units / hooks for waybar, dunst, hypridle, hyprsunset, awww, clipboard (wl-paste + cliphist), applets, battery.
5. **Freeze wallbash output:** `GitS-Gtk` (from `Wallbash-Gtk`), Kvantum, qt6ct, dunstrc, rofi theme, wlogout style, hyprlock.conf, waybar colours as plain files in the repo.
6. **Installer and repo:** `install.sh` without the HyDE check, package list, `tools/roundtrip.sh` and a nested-session boot test, README rewritten ("standalone").
7. **Cut-over:** snapshot, switch the session over, live with both for a while, then remove `~/.local/share/hypr`, `~/.local/lib/hyde`, `~/.config/hyde`, `~/.local/share/hyde`, `~/HyDE`, the `hyde-shell` binary and the units. The HyDE packages stay (they are ordinary packages).

## Decisions taken (change them before phase 3 starts)

* One theme (GitS), one wallpaper set: no theme or wallpaper switcher.
* Keep: 4 layouts, 5 workflows, the `gits` animation preset (+ off), the waybar layout as it is.
* HyDE's GPL-derived template (`kvantum.theme`) is replaced by our own file in phase 5, so the repository stops carrying GPL-3 material.
