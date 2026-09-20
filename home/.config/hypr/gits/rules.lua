-- window and layer rules (HyDE's window_rules.lua / layer_rules.lua, without the regex helper)
local function rx(list) return "^(" .. table.concat(list, "|") .. ")$" end

local floating_class = rx({
    "Bitwarden", "org.keepassxc.KeePassXC", "hyprland-share-picker", "blueman-manager", "pavucontrol-qt", "com\\.gabm\\.satty", "vlc",
    "kvantummanager", "qt6ct", "qt[56]ct", "nwg-(look|displays)", "org\\.kde\\.ark", "org\\.pulseaudio\\.pavucontrol",
    "nm-(applet|connection-editor)", "hyprpolkitagent", "console-dropdown", "gits-sysmon", "org\\.kde\\.dolphin", ".*dialog.*",
    "[Xx]dg-desktop-portal-gtk", "org\\.freedesktop\\.impl\\.portal\\.desktop\\.(hyprland|gtk)",
    "org\\.opengamingcollective\\.rog-control-center",
})
local floating_title = rx({
    "Progress Dialog — Dolphin", "Copying — Dolphin", "Choose Files", "Save As", "Confirm to replace files", "File Operation Progress",
    "Open", "Authentication Required", "Add Folder to Workspace", "File Upload.*", "Choose wallpaper.*", "Library.*", ".*dialog.*",
    "Open File", "Volume Control", "Save As.*", "File Already Exists — Dolphin",
})
local pip_title = "^([Pp]icture[-\\s]?[Ii]n[-\\s]?[Pp]icture(.*))$"

hl.window_rule({
    name = "gits_filemanagers",
    match = { class = "^(.*dolphin.*)$|^(.*pcmanfm-qt.*)$|^(.*nemo.*)$|^(.*ark.*)$|.*Nautilus.*" },
    opaque = true,
    float = false,
})
hl.window_rule({ name = "gits_floating_class", tag = "+gits_floating", match = { class = floating_class }, float = true })
hl.window_rule({ name = "gits_floating_title", tag = "+gits_floating", match = { title = floating_title }, float = true })
hl.window_rule({
    name = "gits_pip", tag = "+gits_pin", match = { title = pip_title }, float = true,
    move = "(monitor_w*0.73) (monitor_h*0.72)", size = "(monitor_w*0.25) (monitor_h*0.25)", pin = true,
})
hl.window_rule({
    name = "gits_modals", tag = "+gits_modals",
    match = {
        class = "^(pinentry-.*)$",
        title = rx({ "Choose Files", "Open File", "Save As.*", "File Operation Progress", "Authentication Required", "File Upload.*" }),
        initial_title = rx({ "Open File", "Save As.*" }),
        modal = true,
    },
    float = true, center = true, pin = true,
})
hl.window_rule({
    name = "xwayland_video_bridge_fixes", match = { class = "xwaylandvideobridge" },
    no_initial_focus = true, no_focus = true, no_anim = true, no_blur = true, no_follow_mouse = true,
    max_size = { 1, 1 }, opacity = 0.0, float = true, workspace = "special:xwayland_video_bridge silent",
})
-- the drop-down terminal (gits-dropdown) lives on its own special workspace
hl.window_rule({ name = "gits_dropdown", match = { class = "^(console-dropdown)$" }, workspace = "special:console silent", float = true, size = "(monitor_w*0.8) (monitor_h*0.5)", center = true })

hl.layer_rule({ name = "gits_layer_blur", match = { namespace = rx({ "rofi", "notifications", "swaync-(notification-window|control-center)", "waybar", "logout_dialog" }) }, blur = true })
hl.layer_rule({ name = "gits_layer_ignore_alpha", match = { namespace = rx({ "rofi", "notifications", "swaync-(notification-window|control-center)", "waybar", "selection" }) }, ignore_alpha = 0 })
hl.layer_rule({ name = "gits_layer_no_anim", no_anim = true, match = { namespace = "selection" } })

-- workspace 1 always exists (the bar never goes empty); the others appear while in use
hl.workspace_rule({ workspace = "1", persistent = true })
