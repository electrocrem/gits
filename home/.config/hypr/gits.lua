-- Ghost in the Shell: everything the setup hooks into Hyprland, in one file.
-- install.sh adds a single `dofile(".../gits.lua")` line to hyprland.lua; delete that line to switch it all off.
local home = os.getenv("HOME")

-- Workspaces appear as they are used (1..N), see gits-workspaces.lua
dofile(home .. "/.config/hypr/gits-workspaces.lua")

-- Crash watchdog: revives waybar after a segfault (see the script header). Single instance (flock).
hl.on("hyprland.start", function()
    hl.exec_cmd(home .. "/.config/waybar/scripts/gits-watchdog.sh")
end)

-- Waybar sometimes starts before the session environment is imported ("cannot open display"), systemd gives up
-- after a few tries and the bar is simply missing. A few seconds after login: if there is no waybar, clear the
-- failed unit and start it again. Does nothing when the bar is already up.
hl.on("hyprland.start", function()
    hl.exec_cmd(
        "sh -c 'sleep 10; pgrep -x waybar >/dev/null || { systemctl --user reset-failed hyde-Hyprland-bar.service; hyde-shell waybar.py --watch; }'"
    )
end)

-- If Hyprland died during login and start-hyprland restarted it, the first instance's session services are still
-- running against the dead compositor (waybar "not working", no notifications, no idle...). Restart those.
hl.on("hyprland.start", function()
    hl.exec_cmd(home .. "/.config/hypr/scripts/gits-stale-guard.sh")
end)

-- Desktop widgets (clock, calendar, player, weather, network, battery, load, to-do): ~/.config/gits-widgets
-- run.sh start | stop | restart | toggle ; it replaces an instance left over from a dead compositor.
hl.on("hyprland.start", function()
    hl.exec_cmd(home .. "/.config/gits-widgets/run.sh start")
end)

-- UI sounds (login chime, charger plug/unplug, lock/unlock; notifications are a dunst rule): gits-sound, muted by `gits-sound off`
hl.on("hyprland.start", function()
    hl.exec_cmd(home .. "/.config/hypr/scripts/gits-events.sh")
end)

-- Super+J: HyDE binds it to dwindle's togglesplit, which the master layout (the one in use) ignores. Same combination and flags
-- (only a description), so this replaces it: dwindle -> toggle split, master -> rotate the master area (gits-layout-toggle).
hl.bind("SUPER + J", hl.dsp.exec_cmd("gits-layout-toggle"), {description = "[Layout Management] toggle split / rotate master (by layout)"})

-- M4 / ROG key (KEY_PROG1 = XF86Launch1): ROG Control Center, as Armoury Crate on Windows (gits-rog toggles the window)
hl.bind("XF86Launch1", hl.dsp.exec_cmd("gits-rog"), {description = "[GitS] ROG Control Center (M4 / ROG key)"})

-- Touchpad off/on: the touchpad key and Super+Ctrl+T (gits-touchpad; runtime only, a new session starts with it on)
hl.bind("XF86TouchpadToggle", hl.dsp.exec_cmd("gits-touchpad toggle"), {description = "[GitS] toggle touchpad"})
hl.bind("SUPER + CTRL + T", hl.dsp.exec_cmd("gits-touchpad toggle"), {description = "[GitS] toggle touchpad"})
hl.on("hyprland.start", function()
    hl.exec_cmd("rm -f " .. (os.getenv("XDG_STATE_HOME") or (home .. "/.local/state")) .. "/gits-touchpad/off")
end)

-- All settings in one menu (gits-settings) and HyDE's tiling-layout selector (dwindle / master / monocle / scrolling)
hl.bind("SUPER + I", hl.dsp.exec_cmd("gits-settings"), {description = "[GitS] all settings"})
hl.bind("SUPER + SHIFT + L", hl.dsp.exec_cmd("hyde-shell layouts --select"), {description = "[GitS] select tiling layout"})

-- Sleep / lock / screen-off timers per power source (gits-idle writes hypridle.conf; also re-applied on plug/unplug)
hl.on("hyprland.start", function()
    hl.exec_cmd("sh -c 'sleep 6; command -v gits-idle >/dev/null && gits-idle apply'")
end)

-- Popups under the bar (gits-panel): control panel and player
hl.bind("SUPER + SHIFT + C", hl.dsp.exec_cmd("gits-panel control"), {description = "[GitS] control panel"})
hl.bind("SUPER + SHIFT + M", hl.dsp.exec_cmd("gits-panel media"), {description = "[GitS] player popup"})
hl.bind("SUPER + SHIFT + N", hl.dsp.exec_cmd("gits-panel notify"), {description = "[GitS] notification centre"})

-- On-screen display for volume / brightness / keyboard backlight (gits-osd; HyDE's popups are turned into it by a dunst rule)
hl.on("hyprland.start", function()
    hl.exec_cmd("gits-osd start")
end)

-- ROG Control Center (asusctl's tray app, ASUS laptops): its ~/.config/autostart entry never runs here because nothing
-- starts xdg-autostart.target in a HyDE session (that would launch every autostart file at once). Start just this one,
-- after the bar's tray is up, and only if it is installed and not already running.
hl.on("hyprland.start", function()
    hl.exec_cmd(
        "sh -c 'command -v rog-control-center >/dev/null || exit 0; sleep 8; "
        .. "pgrep -f \"^/usr/bin/rog-control-center\" >/dev/null || exec setsid -f rog-control-center --autostart --background'"
    )
end)

-- @BLIND_GUARD@
