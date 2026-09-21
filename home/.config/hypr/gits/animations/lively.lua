local animation = {
    name = "Lively",
    icon = "",
    description = "Springs: windows pop in with a bounce, tiles wobble into place when the layout changes, workspaces slide with a spring, menus and popups spring up",
}

if not hl then
    return animation
end

-- A spring pulls the value to its target: `stiffness` = how hard, `dampening` = how quickly the wobble dies. dampening / (2 * sqrt(stiffness * mass))
-- below ~0.5 is clearly bouncy, near 1 settles without overshoot.
hl.curve("gits_bounce", {type = "spring", mass = 1, stiffness = 320, dampening = 8})   -- ratio 0.22: opens with a +23% overshoot in ~0.07 s, settles in ~0.6 s (measured on a recording)
hl.curve("gits_spring", {type = "spring", mass = 1, stiffness = 210, dampening = 14})   -- ratio 0.48: one clear overshoot
hl.curve("gits_soft", {type = "spring", mass = 1, stiffness = 170, dampening = 21})     -- ratio 0.81: settles with a hint of overshoot
hl.curve("gits_quint", {type = "bezier", points = {{0.23, 1}, {0.32, 1}}})
hl.curve("gits_out", {type = "bezier", points = {{0.5, 0}, {1, 0.4}}})

-- windows: open with a bounce from 50%, wobble into place when tiles move or resize, shrink away fast when closed
hl.animation({leaf = "windows", enabled = true, speed = 4.8, spring = "gits_spring"})
hl.animation({leaf = "windowsIn", enabled = true, speed = 6, spring = "gits_bounce", style = "popin 50%"})
hl.animation({leaf = "windowsOut", enabled = true, speed = 2.2, bezier = "gits_out", style = "popin 60%"})
hl.animation({leaf = "windowsMove", enabled = true, speed = 4.8, spring = "gits_spring"})
hl.animation({leaf = "fade", enabled = true, speed = 3, bezier = "gits_quint"})
hl.animation({leaf = "fadeIn", enabled = true, speed = 2.5, bezier = "gits_quint"})
hl.animation({leaf = "fadeOut", enabled = true, speed = 2, bezier = "gits_out"})
-- popups, menus, notifications spring up
hl.animation({leaf = "layersIn", enabled = true, speed = 4, spring = "gits_spring", style = "popin 60%"})
hl.animation({leaf = "layersOut", enabled = true, speed = 2.2, bezier = "gits_out", style = "fade"})
hl.animation({leaf = "fadeLayersIn", enabled = true, speed = 2.5, bezier = "gits_quint"})
hl.animation({leaf = "fadeLayersOut", enabled = true, speed = 2, bezier = "gits_out"})
-- workspaces slide and fade with a spring: they overshoot a little and settle
hl.animation({leaf = "workspaces", enabled = true, speed = 5, spring = "gits_soft", style = "slidefade 30%"})
hl.animation({leaf = "specialWorkspace", enabled = true, speed = 4.5, spring = "gits_spring", style = "slidefadevert 20%"})
hl.animation({leaf = "border", enabled = true, speed = 6, bezier = "gits_quint"})
-- the neon border runner is opt-in exactly as in the gits preset (it redraws every frame: battery)
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
