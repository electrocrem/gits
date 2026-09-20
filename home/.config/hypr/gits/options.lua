-- compositor options: HyDE's defaults, then the GitS look (was the theme's hypr.theme)
hl.config({
    input = {
        kb_layout = "us,ru",
        kb_options = "grp:caps_toggle,grp_led:caps",
        accel_profile = "flat",
        numlock_by_default = true,
    },
    dwindle = { preserve_split = true },
    master = { new_status = "master" },
    misc = {
        vrr = 0,
        disable_hyprland_logo = true,
        disable_splash_rendering = true,
        force_default_wallpaper = 0,
        anr_missed_pings = 5,
        allow_session_lock_restore = true,
        font_family = "JetBrainsMono Nerd Font",
    },
    xwayland = { force_zero_scaling = true },
    general = {
        snap = { border_overlap = true, enabled = true, monitor_gap = 1, respect_gaps = true, window_gap = 1 },
        border_size = 1,
        gaps_in = "3",
        gaps_out = "6",
        resize_on_border = true,
        col = {
            active_border = { colors = { "rgba(2ed3d7ff)", "rgba(398ff0ff)" }, angle = 90 },
            inactive_border = "rgba(2ed3d733)",
        },
    },
    decoration = {
        dim_special = 0.3,
        active_opacity = 0.96,
        inactive_opacity = 0.90,
        fullscreen_opacity = 1,
        rounding = 0,
        dim_inactive = true,
        dim_strength = 0.12,
        blur = {
            enabled = true, ignore_opacity = true, new_optimizations = true, noise = 0.04, passes = 3, popups = true,
            size = 4, xray = false, special = true,
        },
        shadow = {
            color = "rgba(2ed3d755)", color_inactive = "rgba(00000088)", enabled = true, range = 14, render_power = 4, scale = 1.0,
        },
    },
    group = {
        col = {
            border_active = { colors = { "rgba(2ed3d7ff)", "rgba(398ff0ff)" }, angle = 90 },
            border_inactive = "rgba(2ed3d733)",
        },
        groupbar = {
            col = { active = "rgba(2ed3d7ff)", inactive = "rgba(0c1a33ff)" },
            font_family = "JetBrainsMono NFM",
            font_size = 10,
            text_color = "rgba(ddf9ffff)",
        },
    },
})
