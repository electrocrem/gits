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

-- @BLIND_GUARD@
