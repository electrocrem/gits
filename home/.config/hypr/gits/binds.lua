-- key bindings. Press SUPER + / for the list.
local MOD = "SUPER"
local function bind(keys, dispatch, desc, flags)
    flags = flags or {}
    flags.description = desc
    hl.bind(keys, dispatch, flags)
end
local function run(cmd) return hl.dsp.exec_cmd(cmd) end

-- ---------------------------------------------------------------- functions used below
local function cycle_fullscreen()
    local w = assert(hl.get_active_window(), "No active window to toggle fullscreen")
    local nxt = ((tonumber(w.fullscreen) or 0) + 1) % 3
    hl.dispatch(hl.dsp.window.fullscreen_state({ internal = nxt, client = nxt, window = w }))
end
local function move_window(dir, pix)
    local lut = { l = { -1, 0 }, r = { 1, 0 }, u = { 0, -1 }, d = { 0, 1 } }
    lut.left, lut.right, lut.up, lut.down = lut.l, lut.r, lut.u, lut.d
    local m = lut[dir]
    return function()
        local w = hl.get_active_window()
        local args = (w and w.floating) and { x = m[1] * pix, y = m[2] * pix, relative = true } or { direction = dir }
        hl.dispatch(hl.dsp.window.move(args))
    end
end

-- ---------------------------------------------------------------- apps
bind(MOD .. " + T", run("kitty"), "[Launcher|Apps] terminal emulator")
bind(MOD .. " + ALT + T", run("gits-dropdown"), "[Launcher|Apps] dropdown terminal")
bind(MOD .. " + E", run("gits-open explorer"), "[Launcher|Apps] file explorer")
bind(MOD .. " + B", run("gits-open browser"), "[Launcher|Apps] browser")
bind(MOD .. " + C", run("gits-open editor"), "[Launcher|Apps] text editor")
bind("CTRL + SHIFT + ESCAPE", run("gits-sysmon"), "[Launcher|Apps] system monitor")

-- ---------------------------------------------------------------- windows
bind(MOD .. " + Q", hl.dsp.window.close(), "[Window Management] close focused window")
bind("ALT + F4", hl.dsp.window.close(), "[Window Management] close focused window")
bind(MOD .. " + ALT + F4", hl.dsp.window.kill(), "[Window Management] kill focused window")
bind(MOD .. " + Delete", hl.dsp.exit(), "[Window Management] exit hyprland session")
bind(MOD .. " + W", hl.dsp.window.float({ action = "toggle" }), "[Window Management] toggle float")
bind(MOD .. " + G", hl.dsp.group.toggle(), "[Window Management] toggle group")
bind("ALT + P", hl.dsp.window.pseudo(), "[Window Management] pseudotiling")
bind("SHIFT + F11", cycle_fullscreen, "[Window Management] cycle fullscreen")
bind(MOD .. " + SHIFT + F", hl.dsp.window.pin(), "[Window Management] toggle pin")
bind("CTRL + ALT + DELETE", run("gits-logout"), "[Window Management] logout menu")
bind(MOD .. " + CTRL + B", run("pkill -SIGUSR1 -x waybar"), "[Window Management] hide / show the bar")
bind(MOD .. " + L", run("loginctl lock-session"), "[Window Management] lock session")
bind(MOD .. " + CTRL + H", hl.dsp.group.prev(), "[Window Management|Group Navigation] change active group backwards")
bind(MOD .. " + CTRL + L", hl.dsp.group.next(), "[Window Management|Group Navigation] change active group forwards")
for key, dir in pairs({ Left = "left", Right = "right", Up = "up", Down = "down" }) do
    bind(MOD .. " + " .. key, hl.dsp.focus({ direction = dir }), "[Window Management|Change focus] focus " .. dir)
end
bind("ALT + TAB", function() hl.dispatch(hl.dsp.window.cycle_next({})); hl.dispatch(hl.dsp.window.bring_to_top({})) end, "[Window Management] cycle windows")
bind("ALT + SHIFT + TAB", function() hl.dispatch(hl.dsp.window.cycle_next({ next = false })); hl.dispatch(hl.dsp.window.bring_to_top({})) end, "[Window Management] cycle windows backwards")
local rs = { RIGHT = { 30, 0 }, LEFT = { -30, 0 }, UP = { 0, -30 }, DOWN = { 0, 30 } }
for key, d in pairs(rs) do
    bind(MOD .. " + SHIFT + " .. key, hl.dsp.window.resize({ x = d[1], y = d[2], relative = true }), "[Window Management|Resize Active Window] resize window " .. key:lower(), { repeating = true })
    bind(MOD .. " + SHIFT + CONTROL + " .. key, move_window(key:sub(1, 1):lower(), 30), "[Window Management|Move active window] " .. key:lower(), { repeating = true })
end
bind(MOD .. " + mouse:272", hl.dsp.window.drag(), "[Window Management|Drag & Resize with mouse] drag window", { mouse = true })
bind(MOD .. " + mouse:273", hl.dsp.window.resize(), "[Window Management|Drag & Resize with mouse] resize window", { mouse = true })
bind(MOD .. " + Z", hl.dsp.window.drag(), "[Window Management|Drag & Resize with mouse] hold to move window", { mouse = true })
bind(MOD .. " + X", hl.dsp.window.resize(), "[Window Management|Drag & Resize with mouse] hold to resize window", { mouse = true })
bind(MOD .. " + J", run("gits-layout-toggle"), "[Layout Management] toggle split / rotate master (by layout)")
bind(MOD .. " + SHIFT + L", run("gits-layout select"), "[Layout Management] select tiling layout")
bind(MOD .. " + SHIFT + Y", run("gits-anim select"), "[Theming] select window animations")
bind(MOD .. " + SHIFT + X", run("gits-workflow select"), "[Theming] select workflow (default / gaming / editing / powersaver / snappy)")
bind(MOD .. " + ALT + G", run("gits-workflow toggle gaming"), "[Utilities] game mode", { locked = true })

-- ---------------------------------------------------------------- launchers and menus (all GTK popups, see gits-panel)
bind(MOD .. " + A", run("gits-panel launch"), "[Launcher] launcher / command palette")
bind(MOD .. " + TAB", run("gits-panel windows"), "[Launcher] window switcher")
bind(MOD .. " + V", run("gits-panel clip"), "[Launcher] clipboard history")
bind(MOD .. " + comma", run("gits-panel emoji"), "[Launcher] emoji picker")
bind(MOD .. " + slash", run("gits-panel keys"), "[Launcher] key bindings")
bind(MOD .. " + I", run("gits-settings"), "[GitS] all settings")
bind(MOD .. " + SHIFT + C", run("gits-panel control"), "[GitS] control panel")
bind(MOD .. " + SHIFT + M", run("gits-panel media"), "[GitS] player popup")
bind(MOD .. " + ALT + V", run("gits-panel mixer"), "[GitS] sound mixer")
bind(MOD .. " + SHIFT + N", run("gits-panel notify"), "[GitS] notification centre")
bind(MOD .. " + O", run("gits-project"), "[GitS] open a project")
bind(MOD .. " + F", run("gits-focus menu"), "[GitS] focus timer")
bind(MOD .. " + N", run("gits-note add"), "[GitS] quick note")
bind(MOD .. " + SHIFT + O", run("gits-note list"), "[GitS] recent notes")

-- ---------------------------------------------------------------- hardware keys
bind("F10", run("gits-vol mute"), "[Hardware Controls|Audio] un/mute output", { locked = true })
bind("F11", run("gits-vol down"), "[Hardware Controls|Audio] decrease volume", { locked = true, repeating = true })
bind("F12", run("gits-vol up"), "[Hardware Controls|Audio] increase volume", { locked = true, repeating = true })
bind("XF86AudioMute", run("gits-vol mute"), "[Hardware Controls|Audio] un/mute output", { locked = true })
bind("XF86AudioMicMute", run("gits-vol mic-mute"), "[Hardware Controls|Audio] un/mute microphone", { locked = true })
bind("XF86AudioLowerVolume", run("gits-vol down"), "[Hardware Controls|Audio] decrease volume", { locked = true, repeating = true })
bind("XF86AudioRaiseVolume", run("gits-vol up"), "[Hardware Controls|Audio] increase volume", { locked = true, repeating = true })
bind("XF86AudioPlay", run("gits-media play-pause"), "[Hardware Controls|Media] play / pause", { locked = true })
bind("XF86AudioPause", run("gits-media play-pause"), "[Hardware Controls|Media] play / pause", { locked = true })
bind("XF86AudioNext", run("gits-media next"), "[Hardware Controls|Media] next media", { locked = true })
bind("XF86AudioPrev", run("gits-media previous"), "[Hardware Controls|Media] previous media", { locked = true })
bind("XF86MonBrightnessUp", run("gits-bright up"), "[Hardware Controls|Brightness] increase brightness", { locked = true, repeating = true })
bind("XF86MonBrightnessDown", run("gits-bright down"), "[Hardware Controls|Brightness] decrease brightness", { locked = true, repeating = true })
bind("XF86Launch1", run("gits-rog"), "[GitS] ROG Control Center (M4 / ROG key)")
bind("XF86TouchpadToggle", run("gits-touchpad toggle"), "[GitS] toggle touchpad")
bind(MOD .. " + CTRL + T", run("gits-touchpad toggle"), "[GitS] toggle touchpad")
bind(MOD .. " + K", run("hyprctl switchxkblayout all next"), "[Utilities] toggle keyboard layout", { locked = true })

-- ---------------------------------------------------------------- screenshots, recording, picker
bind(MOD .. " + SHIFT + P", run("hyprpicker -an"), "[Utilities] colour picker", { locked = true })
bind(MOD .. " + P", run("gits-shot area"), "[Utilities] screenshot a region (annotate)", { locked = true })
bind(MOD .. " + CTRL + P", run("gits-shot area --no-edit"), "[Utilities] screenshot a region, no editor", { locked = true })
bind(MOD .. " + ALT + P", run("gits-shot screen"), "[Utilities] print monitor", { locked = true })
bind("Print", run("gits-shot all"), "[Utilities] print all monitors", { locked = true })
bind(MOD .. " + CTRL + S", run("gits-shot ocr"), "[Utilities] OCR scanner", { locked = true })
bind(MOD .. " + ALT + R", run("gits-rec toggle area"), "[GitS] record area / stop")
bind(MOD .. " + CTRL + R", run("gits-rec toggle screen"), "[GitS] record screen / stop")

-- ---------------------------------------------------------------- workspaces
local kp = {
    [1] = { "KP_1", "KP_End" }, [2] = { "KP_2", "KP_Down" }, [3] = { "KP_3", "KP_Next" }, [4] = { "KP_4", "KP_Left" },
    [5] = { "KP_5", "KP_Begin" }, [6] = { "KP_6", "KP_Right" }, [7] = { "KP_7", "KP_Home" }, [8] = { "KP_8", "KP_Up" },
    [9] = { "KP_9", "KP_Prior" }, [10] = { "KP_0", "KP_Insert" },
}
for i = 1, 10 do
    local key = (i == 10) and 0 or i
    bind(MOD .. " + " .. key, hl.dsp.focus({ workspace = i }), "[Workspaces|Navigation] navigate to workspace " .. i)
    bind(MOD .. " + SHIFT + " .. key, hl.dsp.window.move({ workspace = i }), "[Workspaces|Move window to workspace] move focused window to workspace " .. i)
    bind(MOD .. " + ALT + " .. key, hl.dsp.window.move({ workspace = i, follow = false }), "[Workspaces|Move window (Don't follow)] move focused window to workspace " .. i)
    for _, k in ipairs(kp[i]) do
        bind(MOD .. " + " .. k, hl.dsp.focus({ workspace = tostring(i + 10) }), "[Workspaces|Navigation] navigate to workspace " .. (i + 10))
        bind(MOD .. " + SHIFT + " .. k, hl.dsp.window.move({ workspace = tostring(i + 10) }), "[Workspaces|Move window to workspace] move focused window to workspace " .. (i + 10))
        bind(MOD .. " + ALT + " .. k, hl.dsp.window.move({ workspace = tostring(i + 10), follow = false }), "[Workspaces|Move window (Don't follow)] move focused window to workspace " .. (i + 10))
    end
end
bind(MOD .. " + CONTROL + RIGHT", hl.dsp.focus({ workspace = "r+1" }), "[Workspaces|Navigation|Relative workspace] change active workspace forwards")
bind(MOD .. " + CONTROL + LEFT", hl.dsp.focus({ workspace = "r-1" }), "[Workspaces|Navigation|Relative workspace] change active workspace backwards")
bind(MOD .. " + CONTROL + DOWN", hl.dsp.focus({ workspace = "empty" }), "[Workspaces|Navigation] navigate to the nearest empty workspace")
bind(MOD .. " + CONTROL + ALT + RIGHT", hl.dsp.window.move({ workspace = "r+1" }), "[Workspaces|Move window to workspace|Relative workspace] move focused window to next workspace")
bind(MOD .. " + CONTROL + ALT + LEFT", hl.dsp.window.move({ workspace = "r-1" }), "[Workspaces|Move window to workspace|Relative workspace] move focused window to previous workspace")
bind(MOD .. " + mouse_down", hl.dsp.focus({ workspace = "e+1" }), "[Workspaces|Navigation|Mouse] next workspace")
bind(MOD .. " + mouse_up", hl.dsp.focus({ workspace = "e-1" }), "[Workspaces|Navigation|Mouse] previous workspace")
bind(MOD .. " + S", hl.dsp.workspace.toggle_special(), "[Workspaces|Navigation|Special workspace] toggle scratchpad")
bind(MOD .. " + SHIFT + S", hl.dsp.window.move({ workspace = "special" }), "[Workspaces|Navigation|Special workspace] move focused window to scratchpad")
bind(MOD .. " + ALT + S", hl.dsp.window.move({ workspace = "special", follow = false }), "[Workspaces|Navigation|Special workspace] move focused window silently to scratchpad")
