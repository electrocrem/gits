-- Ghost in the Shell for Hyprland: the whole session config, no HyDE. install.sh puts it at ~/.config/hypr/hyprland.lua.
-- Everything else lives in ~/.config/hypr/gits/*.lua. Set GITS_NESTED=1 to test it in a nested Hyprland window (no services are started).
local root = assert(debug.getinfo(1, "S").source:match("^@(.*)/"), "not loaded from a file")
package.path = root .. "/?.lua;" .. root .. "/?/init.lua;" .. package.path
gits = { root = root, home = os.getenv("HOME") }
-- load order matters: env, then options (defaults + theme), then the chosen layout / workflow / animation, then rules, binds, hooks, services.
-- A module that fails does not stop the ones after it: the error goes to the log below and to a notification once the session is up.
local log = (os.getenv("XDG_STATE_HOME") or (gits.home .. "/.local/state")) .. "/gits/config-errors.log"
os.execute("mkdir -p '" .. log:match("^(.*)/") .. "'")
local out = io.open(log, "w")
for _, m in ipairs({ "env", "options", "variant", "rules", "binds", "hooks", "start" }) do
    local ok, err = xpcall(require, debug.traceback, "gits." .. m)
    if not ok and out then out:write("gits.", m, ": ", tostring(err), "\n\n") end
end
if out then out:close() end
