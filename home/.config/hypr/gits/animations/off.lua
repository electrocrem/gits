local animation = { name = "Off", icon = "", description = "No animations at all" }
if not hl then return animation end
hl.config({ animations = { enabled = false } })
return animation
