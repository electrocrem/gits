-- Several monitors: workspaces 1-5 live on the main one, 6-10 on the next one (a third monitor gets none of its own).
-- The main monitor: GITS_MAIN_MONITOR=<connector> if set, else a laptop panel (eDP), else the largest one (ties: the leftmost).
-- The session starts focused on it, and XWayland apps (games) see it as the primary output.
-- Re-applied whenever a monitor comes or goes. One monitor: nothing changes. GITS_WS_SPLIT=0 turns the split off.
-- The same choice of main monitor is made by the desktop widgets and the panel popups (gits-widgets).
if os.getenv("GITS_WS_SPLIT") == "0" then return end

local function area(m) return m.width * m.height end

-- monitors in order: main first, the rest left to right
local function ordered()
    local want = os.getenv("GITS_MAIN_MONITOR") or ""
    local mons = {}
    for _, m in ipairs(hl.get_monitors() or {}) do
        if not m.is_mirror then mons[#mons + 1] = m end
    end
    local function rank(m)
        if want ~= "" and m.name == want then return 0 end
        if want == "" and m.name:match("^eDP") then return 1 end
        return 2
    end
    table.sort(mons, function(a, b)
        if rank(a) ~= rank(b) then return rank(a) < rank(b) end
        if area(a) ~= area(b) then return area(a) > area(b) end
        return a.position.x < b.position.x
    end)
    -- only the main one is picked by size; the others keep their left-to-right order
    local rest = { table.unpack(mons, 2) }
    table.sort(rest, function(a, b) return a.position.x < b.position.x end)
    return { mons[1], table.unpack(rest) }
end

local function apply()
    local mons = ordered()
    if #mons < 2 then return mons[1] end
    local home = { mons[1].name, mons[2].name }
    for i = 1, 10 do
        hl.workspace_rule({ workspace = tostring(i), monitor = home[i <= 5 and 1 or 2], default = (i == 1 or i == 6) })
    end
    -- workspaces that already exist move over too (rules only place new ones)
    for _, ws in ipairs(hl.get_workspaces() or {}) do
        local want = ws.id >= 1 and ws.id <= 10 and home[ws.id <= 5 and 1 or 2]
        if want and ws.monitor and ws.monitor.name ~= want then
            hl.dispatch(hl.dsp.workspace.move({ workspace = tostring(ws.id), monitor = want }))
        end
    end
    return mons[1]
end

local function safe_apply() local ok, main = pcall(apply); return ok and main or nil end

safe_apply()   -- on a config reload the monitors are already there
hl.on("hyprland.start", function()
    local main = safe_apply()
    if not main then return end
    hl.dispatch(hl.dsp.focus({ monitor = main.name }))
    hl.exec_cmd("sh -c 'command -v xrandr >/dev/null || exit 0; sleep 2; xrandr --output " .. main.name .. " --primary 2>/dev/null'")
end)
hl.on("monitor.added", safe_apply)
hl.on("monitor.removed", safe_apply)
