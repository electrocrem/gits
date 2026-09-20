-- lualine theme for the Ghost in the Shell colourscheme: flat strip like waybar,
-- the mode block is the "active tab" (dark text on a solid accent) like the kitty tab bar.
local c = require("gits.palette")

local function mode(accent)
  return {
    a = { fg = c.bg, bg = accent, gui = "bold" },
    b = { fg = accent, bg = c.bg_hl },
    c = { fg = c.fg_dim, bg = c.bg_alt },
  }
end

local theme = {
  normal = mode(c.cyan),
  insert = mode(c.green),
  visual = mode(c.purple_hi),
  replace = mode(c.red_hi),
  command = mode(c.yellow),
  terminal = mode(c.blue_hi),
  inactive = {
    a = { fg = c.muted, bg = c.bg_alt },
    b = { fg = c.muted, bg = c.bg_alt },
    c = { fg = c.muted, bg = c.bg_alt },
  },
}

return theme
