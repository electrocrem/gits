-- session environment + our tools in PATH
local home = os.getenv("HOME")
local function env(k, v) hl.env(k, v) end
-- the XDG base directories, spelled out: waybar's config and some scripts expand $XDG_CONFIG_HOME
env("XDG_CONFIG_HOME", os.getenv("XDG_CONFIG_HOME") or (home .. "/.config"))
env("XDG_DATA_HOME", os.getenv("XDG_DATA_HOME") or (home .. "/.local/share"))
env("XDG_CACHE_HOME", os.getenv("XDG_CACHE_HOME") or (home .. "/.cache"))
env("XDG_STATE_HOME", os.getenv("XDG_STATE_HOME") or (home .. "/.local/state"))
env("XDG_CURRENT_DESKTOP", "Hyprland")
env("XDG_SESSION_TYPE", "wayland")
env("XDG_SESSION_DESKTOP", "Hyprland")
env("QT_AUTO_SCREEN_SCALE_FACTOR", "1")
env("QT_QPA_PLATFORM", "wayland;xcb")
env("QT_WAYLAND_DISABLE_WINDOWDECORATION", "1")
env("QT_QPA_PLATFORMTHEME", "qt6ct")
env("MOZ_ENABLE_WAYLAND", "1")
env("GDK_SCALE", "1")
env("ELECTRON_OZONE_PLATFORM_HINT", "auto")
env("XCURSOR_THEME", "GitS-Cursors")
env("XCURSOR_SIZE", "22")
-- plus the Flatpak launchers (com.spotify.Client, ...): the system ones are usually there already, the per-user ones (flatpak --user) are not
local path = home .. "/.local/bin:" .. (os.getenv("PATH") or "/usr/local/bin:/usr/bin")
for _, d in ipairs({ "/var/lib/flatpak/exports/bin", (os.getenv("XDG_DATA_HOME") or (home .. "/.local/share")) .. "/flatpak/exports/bin" }) do
    if not (":" .. path .. ":"):find(":" .. d .. ":", 1, true) then path = path .. ":" .. d end
end
env("PATH", path)

-- NVIDIA session-wide only when it drives the screen (desktop / MUX "Ultimate" mode). On hybrid laptops the
-- iGPU stays primary and the dGPU is used per app (prime-run), so it can sleep when nothing needs it.
local function nvidia_primary()
    for i = 0, 7 do
        local d = "/sys/class/drm/card" .. i .. "/device/"
        local b, v = io.open(d .. "boot_vga", "r"), io.open(d .. "vendor", "r")
        local boot = b and b:read("*l"); local vendor = v and v:read("*l")
        if b then b:close() end
        if v then v:close() end
        if boot == "1" then return vendor == "0x10de" end
    end
    return false
end
if nvidia_primary() then
    env("LIBVA_DRIVER_NAME", "nvidia")
    env("__GLX_VENDOR_LIBRARY_NAME", "nvidia")
    env("GBM_BACKEND", "nvidia-drm")
end
