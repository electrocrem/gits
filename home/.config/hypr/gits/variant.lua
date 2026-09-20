-- the switchable parts: tiling layout, workflow (effects preset) and animation preset. `gits-layout`, `gits-workflow`, `gits-anim` write the
-- choice into ~/.local/state/gits/state and reload; a missing or broken choice falls back to the default.
local state = require("gits.state")
local function load(kind, key, fallback)
    local ok, mod = pcall(require, "gits." .. kind .. "." .. key)
    if ok then return mod end
    if key ~= fallback then
        local f = io.open((os.getenv("XDG_STATE_HOME") or (gits.home .. "/.local/state")) .. "/gits/config-errors.log", "a")
        if f then f:write("gits." .. kind .. "." .. key .. " failed, using " .. fallback .. ": " .. tostring(mod) .. "\n\n"); f:close() end
        local ok2, mod2 = pcall(require, "gits." .. kind .. "." .. fallback)
        if ok2 then return mod2 end
    end
    return nil
end
load("layouts", state.get("layout", "master"), "master")
load("workflows", state.get("workflow", "01-default"), "01-default")
load("animations", state.get("animation", "gits"), "gits")
