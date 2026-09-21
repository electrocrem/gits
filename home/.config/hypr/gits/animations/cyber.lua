local animation = {
    name = "Cyber",
    icon = "",
    description = "Simple and sharp: windows snap in fast and settle without a bounce, close in a quick fade, workspaces slide like a data hop",
}

if not hl then
    return animation
end

-- exponential curves: a violent start, a soft landing, no overshoot at all
hl.curve("cyber_out", {type = "bezier", points = {{0.16, 1}, {0.3, 1}}})    -- easeOutExpo: the move is done in the first third, the rest is a fine settle
hl.curve("cyber_in", {type = "bezier", points = {{0.7, 0}, {0.84, 0}}})     -- easeInExpo: nothing, nothing, gone

-- windows: snap in from 78% while fading in, glide when the layout changes, disappear fast
hl.animation({leaf = "windows", enabled = true, speed = 3, bezier = "cyber_out"})
hl.animation({leaf = "windowsIn", enabled = true, speed = 3, bezier = "cyber_out", style = "popin 78%"})
hl.animation({leaf = "windowsOut", enabled = true, speed = 1.8, bezier = "cyber_in", style = "popin 92%"})
hl.animation({leaf = "windowsMove", enabled = true, speed = 3, bezier = "cyber_out"})
hl.animation({leaf = "fade", enabled = true, speed = 2.5, bezier = "cyber_out"})
hl.animation({leaf = "fadeIn", enabled = true, speed = 2.2, bezier = "cyber_out"})
hl.animation({leaf = "fadeOut", enabled = true, speed = 1.6, bezier = "cyber_in"})
-- popups, menus, notifications: the same snap
hl.animation({leaf = "layersIn", enabled = true, speed = 2.6, bezier = "cyber_out", style = "popin 92%"})
hl.animation({leaf = "layersOut", enabled = true, speed = 1.6, bezier = "cyber_in", style = "fade"})
hl.animation({leaf = "fadeLayersIn", enabled = true, speed = 2.2, bezier = "cyber_out"})
hl.animation({leaf = "fadeLayersOut", enabled = true, speed = 1.5, bezier = "cyber_in"})
-- workspaces: a fast horizontal data hop with a little fade
hl.animation({leaf = "workspaces", enabled = true, speed = 3.2, bezier = "cyber_out", style = "slidefade 18%"})
hl.animation({leaf = "specialWorkspace", enabled = true, speed = 3, bezier = "cyber_out", style = "slidefadevert 15%"})
hl.animation({leaf = "border", enabled = true, speed = 5, bezier = "cyber_out"})
-- the neon border runner stays opt-in (it redraws every frame: battery), exactly as in the gits preset
local flag = (os.getenv("XDG_STATE_HOME") or (os.getenv("HOME") .. "/.local/state")) .. "/gits-neon-border"
local f = io.open(flag, "r")
if f then
    f:close()
    hl.curve("linear", {type = "bezier", points = {{0, 0}, {1, 1}}})
    hl.animation({leaf = "borderangle", enabled = true, speed = 90, bezier = "linear", style = "loop"})
else
    hl.animation({leaf = "borderangle", enabled = false})
end

return animation
