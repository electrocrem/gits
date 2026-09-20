# Leaving HyDE

Goal: `gits-hyde` becomes a self-contained Hyprland setup (no HyDE at install time or at run time), then HyDE is removed from the author's machine.
Done step by step; the HyDE session stayed installed and bootable until the last step.

## What HyDE provides today (inventory, Sep 2026)

| Block | Size | Replaced by |
|---|---|---|
| Hyprland base config (`~/.local/share/hypr/lua/*.lua`: binds, window/layer rules, variables, env, start-up, layouts, workflows, animations) | ~2300 lines + a TOML/dispatcher framework | our own `hyprland.lua` with plain Lua modules, state in `~/.local/state/gits/` (phase 3) |
| 13 systemd units `hyde-Hyprland-*` (bar, dunst, hypridle, wallpaper, clipboard x3, applets x3, blue-light, battery notify, config watcher) | | our own user units / exec hooks (phase 4) |
| `hyde-shell` scripts (~1.9 MB); the ones this setup called: system monitor, volume, brightness, screenshot, logout menu, keyboard switch, cliphist, launcher, theme/wallpaper/layout/workflow/animation/bar/lock-screen selectors, waybar service | | `gits-sysmon`, `gits-vol`, `gits-bright`, `gits-shot`, `gits-logout`, `gits-panel launch/clip`, own selectors (phases 1-3) |
| wallbash colour generation (GTK, Qt/Kvantum, qt6ct, rofi, dunst, kitty, waybar `theme.css`, hyprlock) | | frozen static files built from the fixed GitS palette (phase 5) |
| Theme store, other themes, wallpaper switching | | dropped: one theme |

## Status (Sep 20 2026)

Phases 0-6 are done: the config is `home/.config/hypr/hyprland.lua` + `gits/*.lua`, the services are systemd user units (`gits-session.target`),
the former wallbash outputs are plain files (kitty, GTK + adw-gtk3, Kvantum, qt5ct/qt6ct, dunstrc, hyprlock.conf, hypridle.conf, the waybar
and wlogout styles), the installer needs only Hyprland 0.55+, and `tools/roundtrip.sh` covers install / uninstall. The config was tested in a
nested Hyprland window (`GITS_NESTED=1`), including every layout and workflow, the window rules, the bar and the lock screen.

Phase 7 (cut-over): before the first standalone login rename HyDE's `~/.local/lib/hyde/shell/activate` (it exports `HYPRLAND_CONFIG` pointing at
HyDE's own config); the way back is written down in `~/.local/share/gits-hyde/pre-standalone/ROLLBACK.md`. After a few days of use HyDE's
directories can be deleted (they are moved to `~/.local/share/gits-hyde/hyde-removed/` first, not deleted).

## How the pieces map

* Hyprland base config -> `hypr/gits/{env,options,variant,rules,binds,hooks,start}.lua`; layouts, workflows and animations in `gits/{layouts,workflows,animations}`,
  selected by `gits-layout`, `gits-workflow`, `gits-anim` (state in `~/.local/state/gits/state`).
* `hyde-Hyprland-*` units -> `gits-bar`, `gits-notifications`, `gits-idle`, `gits-sunset`, `gits-wallpaper`, `gits-clip-*`, `gits-polkit`, `gits-applet-*`
  (`Restart=on-failure`, so the old watchdog and stale-unit guard are gone); battery warnings live in `gits-events.sh`.
* `hyde-shell` scripts -> `gits-vol`, `gits-bright`, `gits-shot`, `gits-logout`, `gits-sysmon`, `gits-panel launch|clip|windows|emoji|keys`, `gits-wall`, `gits-open`, `gits-dropdown`, `gits-battery`.
* Decisions: one theme, one wallpaper set (no theme / wallpaper switcher); 4 layouts, 5 workflows, the `gits` animation preset (+ off).
