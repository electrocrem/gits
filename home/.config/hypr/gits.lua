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

-- Popups under the bar (gits-panel): control panel and player
hl.bind("SUPER + SHIFT + C", hl.dsp.exec_cmd("gits-panel control"), {description = "[GitS] control panel"})
hl.bind("SUPER + SHIFT + M", hl.dsp.exec_cmd("gits-panel media"), {description = "[GitS] player popup"})
hl.bind("SUPER + SHIFT + N", hl.dsp.exec_cmd("gits-panel notify"), {description = "[GitS] notification centre"})

-- Click away closes any rofi menu: an invisible click catcher is put under every rofi layer (see the script header)
hl.on("hyprland.start", function()
    hl.exec_cmd(home .. "/.config/hypr/scripts/gits-layer-watch.sh")
end)

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
