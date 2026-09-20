-- ~/.local/state/gits/state: `key=value` lines (layout, workflow, animation). Written by gits-layout / gits-workflow / gits-anim, read here.
local M = {}
local dir = (os.getenv("XDG_STATE_HOME") or (os.getenv("HOME") .. "/.local/state")) .. "/gits"
M.dir, M.file = dir, dir .. "/state"
function M.get(key, default)
    local f = io.open(M.file, "r")
    if not f then return default end
    for line in f:lines() do
        local k, v = line:match("^([%w_]+)=(.*)$")
        if k == key and v ~= "" then f:close(); return v end
    end
    f:close()
    return default
end
return M
