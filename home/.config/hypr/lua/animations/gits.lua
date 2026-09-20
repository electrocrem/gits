local animation = {
    name = "Ghost in the Shell",
    icon = "",
    description = "Cyberpunk: windows lock in with a hard overshoot and get deleted in a flash, workspaces jump-cut like a data hop, the active border runs a neon light around the frame."
}

if not hl then
    return animation
end
-- prod utilizes the stored hyde.config.anim.duration_scale to dynamically change anim speed!
local prod = function(ds)
    return ds * hyde.config.anim.duration_scale
end

hl.curve("linear", {type = "bezier", points = {{0, 0}, {1, 1}}})
-- lock-in: hard start and a ~8% overshoot, so a window "snaps" into place and settles
hl.curve("gits_lock", {type = "bezier", points = {{0.2, 1.4}, {0.35, 1}}})
-- data hop: exponential in-out, almost nothing, then a violent move, then a stop
hl.curve("gits_zap", {type = "bezier", points = {{0.9, 0}, {0.1, 1}}})
-- delete: slow blink, then it collapses
hl.curve("gits_delete", {type = "bezier", points = {{0.85, 0}, {1, 0.35}}})
hl.curve("gits_scan", {type = "bezier", points = {{0.4, 0}, {0.2, 1}}})

-- windows appear from 55% with the overshoot and fade in, disappear by collapsing to 30%
hl.animation({leaf = "windows", enabled = true, speed = prod(3), bezier = "gits_lock", style = "popin 55%"})
hl.animation({leaf = "windowsIn", enabled = true, speed = prod(3), bezier = "gits_lock", style = "popin 55%"})
hl.animation({leaf = "windowsOut", enabled = true, speed = prod(2), bezier = "gits_delete", style = "popin 30%"})
hl.animation({leaf = "windowsMove", enabled = true, speed = prod(3.5), bezier = "gits_lock"})
hl.animation({leaf = "fade", enabled = true, speed = prod(2.5), bezier = "gits_scan"})
hl.animation({leaf = "fadeIn", enabled = true, speed = prod(2), bezier = "gits_scan"})
hl.animation({leaf = "fadeOut", enabled = true, speed = prod(1.6), bezier = "gits_delete"})
-- menus, rofi, notifications pop in the same way
hl.animation({leaf = "layersIn", enabled = true, speed = prod(3), bezier = "gits_lock", style = "popin 70%"})
hl.animation({leaf = "layersOut", enabled = true, speed = prod(1.8), bezier = "gits_delete", style = "fade"})
hl.animation({leaf = "fadeLayersIn", enabled = true, speed = prod(2), bezier = "gits_scan"})
hl.animation({leaf = "fadeLayersOut", enabled = true, speed = prod(1.5), bezier = "gits_delete"})
-- workspaces: fast jump-cut with a bit of fade, not a lazy slide
hl.animation({leaf = "workspaces", enabled = true, speed = prod(3.5), bezier = "gits_zap", style = "slidefade 12%"})
hl.animation({leaf = "specialWorkspace", enabled = true, speed = prod(3), bezier = "gits_zap", style = "slidefadevert 12%"})
-- border colour changes on focus like a scan line; the neon "runner" gradient below is opt-in
hl.animation({leaf = "border", enabled = true, speed = prod(6), bezier = "gits_scan"})
-- Neon runner: the active border's cyan/blue gradient circles the window. Costs battery (the compositor redraws every
-- frame while it runs), so it is only on when the flag file exists: `touch ~/.local/state/gits-neon-border`, then
-- `hyde-shell animations --set gits` (delete the file to turn it off).
local flag = (os.getenv("XDG_STATE_HOME") or (os.getenv("HOME") .. "/.local/state")) .. "/gits-neon-border"
local f = io.open(flag, "r")
if f then
    f:close()
    hl.animation({leaf = "borderangle", enabled = true, speed = prod(90), bezier = "linear", style = "loop"})
else
    hl.animation({leaf = "borderangle", enabled = false})
end

return animation
