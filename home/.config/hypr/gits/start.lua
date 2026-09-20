-- what runs at login: the session units (bar, notifications, idle, night light, wallpaper, clipboard, applets) through systemd, then our own helpers.
-- GITS_NESTED=1 (a Hyprland window inside a running session, for testing the config) starts nothing.
if os.getenv("GITS_NESTED") then return end
local home = gits.home
local function exists(p) local f = io.open(p, "r"); if f then f:close(); return true end; return false end

hl.on("hyprland.start", function()
    -- toolkit settings, before the bar and the popups start (GTK apps read them from gsettings; Qt gets them from qt6ct / Kvantum files)
    hl.exec_cmd("sh -c 'g=org.gnome.desktop.interface; gsettings set $g gtk-theme adw-gtk3-dark; gsettings set $g icon-theme GitS-Icons; "
        .. "gsettings set $g color-scheme prefer-dark; gsettings set $g cursor-theme GitS-Cursors'")
    hl.exec_cmd("gits-session start")                       -- import the session environment, (re)start gits-session.target
    hl.exec_cmd("hyprctl setcursor GitS-Cursors 22")
    hl.exec_cmd(home .. "/.config/gits-widgets/run.sh start")   -- desktop widgets
    hl.exec_cmd("gits-osd start")                           -- volume / brightness / keyboard backlight display
    hl.exec_cmd(home .. "/.config/hypr/scripts/gits-events.sh")   -- login chime, plug / lock sounds, battery warnings
    hl.exec_cmd("sh -c 'sleep 6; command -v gits-idle >/dev/null && gits-idle apply'")   -- sleep / lock timers of the current power source
    -- ROG Control Center (ASUS laptops): its autostart entry never runs in a session like this one
    hl.exec_cmd("sh -c 'command -v rog-control-center >/dev/null || exit 0; sleep 8; pgrep -f \"^/usr/bin/rog-control-center\" >/dev/null || exec setsid -f rog-control-center --autostart --background'")
    hl.exec_cmd("rm -f " .. (os.getenv("XDG_STATE_HOME") or (home .. "/.local/state")) .. "/gits-touchpad/off")
    -- health check ~90 s after login: a notification only when gits-doctor finds a FAIL
    hl.exec_cmd("sh -c 'sleep 90; command -v gits-doctor >/dev/null || exit 0; gits-doctor -q >/dev/null 2>&1; n=$?; [ \"$n\" -gt 0 ] && notify-send -a GitS -u critical \"Health check\" \"$n problem(s): Super+I -> Health check\"; exit 0'")
    -- opt-in: black-screen guard for hybrid AMD/NVIDIA laptops (install.sh --login-guards puts the script there)
    local guard = home .. "/.config/hypr/scripts/gits-blind-guard.sh"
    if exists(guard) then hl.exec_cmd(guard) end
end)
