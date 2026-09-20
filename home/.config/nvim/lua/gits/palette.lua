-- Ghost in the Shell palette. Same values as ~/.config/hyde/themes/Ghost in the Shell/kitty.theme,
-- so the editor matches the terminal, waybar, rofi and the prompt.
return {
  -- surfaces (navy-black -> lifted navy)
  bg = "#060A14",
  bg_dark = "#04070E", -- floats' shadow / sidebars
  bg_alt = "#0A1226", -- cursorline, statusline
  bg_hl = "#0C1A33", -- selections' base, popups, inactive tab
  line = "#242F41", -- borders, indent guides
  line_hl = "#3F4C5C", -- active borders, scope guide

  -- text
  fg = "#C8F4FF",
  fg_dim = "#9FC5D6",
  muted = "#596977", -- comments
  faint = "#3F4C5C",
  white = "#DDF9FF",

  -- accents
  cyan = "#2ED3D7", -- the main colour
  cyan_hi = "#5EF1F5",
  cyan_lo = "#254F5D",
  red = "#E5432B", -- the "eye"
  red_hi = "#FF7A5C",
  green = "#34D399",
  green_hi = "#6EE7B7",
  yellow = "#E8C547",
  yellow_hi = "#F5DC7E",
  blue = "#3B74D0",
  blue_hi = "#459BF1",
  purple = "#7C6CE0",
  purple_hi = "#A99CF5",

  -- tinted backgrounds for diffs / diagnostics (dark, low chroma)
  diff_add = "#0B2A26",
  diff_del = "#2E1216",
  diff_chg = "#0E2340",
  diff_txt = "#1B3D66",
}
