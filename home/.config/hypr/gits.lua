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

-- Screen recording (gits-rec, needs wf-recorder): Super+Alt+R = area (again = stop), Super+Ctrl+R = whole monitor
hl.bind("SUPER + ALT + R", hl.dsp.exec_cmd("gits-rec toggle area"), {description = "[GitS] record area / stop"})
hl.bind("SUPER + CTRL + R", hl.dsp.exec_cmd("gits-rec toggle screen"), {description = "[GitS] record screen / stop"})

-- Health check ~90 s after login: a notification only when gits-doctor finds a FAIL (the panel footer always shows the totals)
hl.on("hyprland.start", function()
    hl.exec_cmd("sh -c 'sleep 90; command -v gits-doctor >/dev/null || exit 0; gits-doctor -q >/dev/null 2>&1; n=$?; "
        .. "[ \"$n\" -gt 0 ] && notify-send -a GitS -u critical \"Health check\" \"$n problem(s): Super+I -> Health check\"; exit 0'")
end)

-- Open a project (git repos and Godot projects, recent first): terminal in the folder, plus the Godot editor for Godot projects
hl.bind("SUPER + O", hl.dsp.exec_cmd("gits-project"), {description = "[GitS] open a project"})

-- Focus timer (pomodoro): Super+F opens the menu (start 25/5, 50/10, ...; stop / skip while it runs)
hl.bind("SUPER + F", hl.dsp.exec_cmd("gits-focus menu"), {description = "[GitS] focus timer"})

-- Quick notes into ~/notes/inbox.md: Super+N adds a line, Super+Shift+O lists the latest and copies one
hl.bind("SUPER + N", hl.dsp.exec_cmd("gits-note add"), {description = "[GitS] quick note"})
hl.bind("SUPER + SHIFT + O", hl.dsp.exec_cmd("gits-note list"), {description = "[GitS] recent notes"})

-- Our own launcher (command palette: apps with icons, settings, projects, windows, notes, calculator, web) and clipboard history, both GTK
-- popups that close on Esc / a click outside; they replace HyDE's rofi launcher and clipboard menu on the same keys
hl.bind("SUPER + A", hl.dsp.exec_cmd("gits-panel launch"), {description = "[GitS] launcher / command palette"})
hl.bind("SUPER + V", hl.dsp.exec_cmd("gits-panel clip"), {description = "[GitS] clipboard history"})

-- HyDE-free replacements (same keys and flags as HyDE's binds, so these take over): volume / brightness with the GitS OSD (gits-vol, gits-bright),
-- screenshots (gits-shot), power menu (gits-logout), system monitor (gits-sysmon), keyboard layout switch
local hw = {locked = true}
local hwr = {locked = true, repeating = true}
hl.bind("F10", hl.dsp.exec_cmd("gits-vol mute"), {description = "[Hardware Controls|Audio] un/mute output", locked = true})
hl.bind("F11", hl.dsp.exec_cmd("gits-vol down"), {description = "[Hardware Controls|Audio] decrease volume", locked = true, repeating = true})
hl.bind("F12", hl.dsp.exec_cmd("gits-vol up"), {description = "[Hardware Controls|Audio] increase volume", locked = true, repeating = true})
hl.bind("XF86AudioMute", hl.dsp.exec_cmd("gits-vol mute"), {description = "[Hardware Controls|Audio] un/mute output", locked = true})
hl.bind("XF86AudioMicMute", hl.dsp.exec_cmd("gits-vol mic-mute"), {description = "[Hardware Controls|Audio] un/mute microphone", locked = true})
hl.bind("XF86AudioLowerVolume", hl.dsp.exec_cmd("gits-vol down"), {description = "[Hardware Controls|Audio] decrease volume", locked = true, repeating = true})
hl.bind("XF86AudioRaiseVolume", hl.dsp.exec_cmd("gits-vol up"), {description = "[Hardware Controls|Audio] increase volume", locked = true, repeating = true})
hl.bind("XF86MonBrightnessUp", hl.dsp.exec_cmd("gits-bright up"), {description = "[Hardware Controls|Brightness] increase brightness", locked = true, repeating = true})
hl.bind("XF86MonBrightnessDown", hl.dsp.exec_cmd("gits-bright down"), {description = "[Hardware Controls|Brightness] decrease brightness", locked = true, repeating = true})
hl.bind("SUPER + P", hl.dsp.exec_cmd("gits-shot area"), {description = "[Utilities] screenshot a region (annotate)", locked = true})
hl.bind("SUPER + CTRL + P", hl.dsp.exec_cmd("gits-shot area --no-edit"), {description = "[Utilities] screenshot a region, no editor", locked = true})
hl.bind("SUPER + ALT + P", hl.dsp.exec_cmd("gits-shot screen"), {description = "[Utilities] print monitor", locked = true})
hl.bind("Print", hl.dsp.exec_cmd("gits-shot all"), {description = "[Utilities] print all monitors", locked = true})
hl.bind("SUPER + CTRL + S", hl.dsp.exec_cmd("gits-shot ocr"), {description = "[Utilities] OCR scanner", locked = true})
hl.bind("CTRL + ALT + DELETE", hl.dsp.exec_cmd("gits-logout"), {description = "[Window Management] logout menu"})
hl.bind("CTRL + SHIFT + ESCAPE", hl.dsp.exec_cmd("gits-sysmon"), {description = "[Launcher|Apps] system monitor"})
hl.bind("SUPER + K", hl.dsp.exec_cmd("hyprctl switchxkblayout all next"), {description = "[Utilities] toggle keyboard layout", locked = true})

-- Popups under the bar (gits-panel): control panel and player
hl.bind("SUPER + SHIFT + C", hl.dsp.exec_cmd("gits-panel control"), {description = "[GitS] control panel"})
hl.bind("SUPER + SHIFT + M", hl.dsp.exec_cmd("gits-panel media"), {description = "[GitS] player popup"})
hl.bind("SUPER + ALT + V", hl.dsp.exec_cmd("gits-panel mixer"), {description = "[GitS] sound mixer"})
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
