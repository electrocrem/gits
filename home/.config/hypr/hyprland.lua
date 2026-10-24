-- Ghost in the Shell for Hyprland: the whole session config. install.sh puts it at ~/.config/hypr/hyprland.lua.
-- Everything else lives in ~/.config/hypr/gits/*.lua. Set GITS_NESTED=1 to test it in a nested Hyprland window (no services are started).
local root = assert(debug.getinfo(1, "S").source:match("^@(.*)/"), "not loaded from a file")
package.path = root .. "/?.lua;" .. root .. "/?/init.lua;" .. package.path
gits = { root = root, home = os.getenv("HOME") }
-- every bind with a description stays callable by it: the key list (Super+/) runs the picked one with
-- `hyprctl eval 'gits.run_bind("[Group] what")'`. hl.gits_raw_bind keeps the original across `hyprctl reload`.
gits.binds = {}
hl.gits_raw_bind = hl.gits_raw_bind or hl.bind
hl.bind = function(keys, dispatch, flags)
    local d = type(flags) == "table" and flags.description
    if d and gits.binds[d] == nil then gits.binds[d] = dispatch end
    return hl.gits_raw_bind(keys, dispatch, flags)
end
function gits.run_bind(desc)
    local d = gits.binds[desc]
    if type(d) == "function" then return d() end
    if d ~= nil then return hl.dispatch(d) end
end
-- load order matters: env, then options (defaults + theme), then the chosen layout / workflow / animation, then rules, binds, hooks, services.
-- A module that fails does not stop the ones after it: the error goes to the log below and to a notification once the session is up.
local log = (os.getenv("XDG_STATE_HOME") or (gits.home .. "/.local/state")) .. "/gits/config-errors.log"
os.execute("mkdir -p '" .. log:match("^(.*)/") .. "'")
local out = io.open(log, "w")
-- gits/local.lua is this machine's own part (monitors, overrides): the installer never ships or touches it, and it loads last so it wins.
local modules = { "env", "options", "variant", "rules", "monitors", "gamemode", "scratch", "binds", "hooks", "start" }
local f = io.open(root .. "/gits/local.lua", "r")
if f then f:close(); table.insert(modules, "local") end
for _, m in ipairs(modules) do
    local ok, err = xpcall(require, debug.traceback, "gits." .. m)
    if not ok and out then out:write("gits.", m, ": ", tostring(err), "\n\n") end
end
if out then out:close() end
