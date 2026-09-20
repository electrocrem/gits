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
env("PATH", home .. "/.local/bin:" .. (os.getenv("PATH") or "/usr/local/bin:/usr/bin"))

-- NVIDIA only when the proprietary module is really loaded (hybrid laptops keep the iGPU as the primary)
local function nvidia_working()
    local v = io.open("/proc/driver/nvidia/version", "r")
    if not v then return false end
    v:close()
    local s = io.open("/sys/module/nvidia/initstate", "r")
    if not s then return true end
    local state = s:read("*l")
    s:close()
    return state == "live"
end
if nvidia_working() then
    env("LIBVA_DRIVER_NAME", "nvidia")
    env("__GLX_VENDOR_LIBRARY_NAME", "nvidia")
    env("GBM_BACKEND", "nvidia-drm")
end
