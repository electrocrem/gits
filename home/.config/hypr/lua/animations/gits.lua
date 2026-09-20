local animation = {
    name = "Ghost in the Shell",
    icon = "",
    description = "Fast, sharp, no bounce: windows snap in like a CRT switching on, workspaces cut across."
}

if not hl then
    return animation
end
-- prod utilizes the stored hyde.config.anim.duration_scale to dynamically change anim speed!
local prod = function(ds)
    return ds * hyde.config.anim.duration_scale
end

hl.curve("linear", {type = "bezier", points = {{0, 0}, {1, 1}}})
-- hard start, long flat tail: reads as "instant" but still tracks
hl.curve("gits_snap", {type = "bezier", points = {{0.16, 1}, {0.3, 1}}})
hl.curve("gits_cut", {type = "bezier", points = {{0.7, 0}, {0.84, 0}}})
hl.curve("gits_scan", {type = "bezier", points = {{0.4, 0}, {0.2, 1}}})

hl.animation({leaf = "windows", enabled = true, speed = prod(2.5), bezier = "gits_snap", style = "popin 94%"})
hl.animation({leaf = "windowsIn", enabled = true, speed = prod(2.5), bezier = "gits_snap", style = "popin 94%"})
hl.animation({leaf = "windowsOut", enabled = true, speed = prod(1.8), bezier = "gits_cut", style = "popin 94%"})
hl.animation({leaf = "windowsMove", enabled = true, speed = prod(2.5), bezier = "gits_snap"})
hl.animation({leaf = "border", enabled = true, speed = prod(5), bezier = "gits_scan"})
hl.animation({leaf = "fade", enabled = true, speed = prod(2.5), bezier = "gits_snap"})
hl.animation({leaf = "fadeIn", enabled = true, speed = prod(2.5), bezier = "gits_snap"})
hl.animation({leaf = "fadeOut", enabled = true, speed = prod(1.8), bezier = "gits_cut"})
hl.animation({leaf = "layersIn", enabled = true, speed = prod(2.5), bezier = "gits_snap", style = "fade"})
hl.animation({leaf = "layersOut", enabled = true, speed = prod(1.5), bezier = "gits_cut", style = "fade"})
hl.animation({leaf = "fadeLayersIn", enabled = true, speed = prod(2), bezier = "gits_snap"})
hl.animation({leaf = "fadeLayersOut", enabled = true, speed = prod(1.5), bezier = "gits_cut"})
hl.animation({leaf = "workspaces", enabled = true, speed = prod(3.5), bezier = "gits_snap", style = "slide"})
hl.animation({leaf = "specialWorkspace", enabled = true, speed = prod(3), bezier = "gits_snap", style = "slidevert"})

return animation
