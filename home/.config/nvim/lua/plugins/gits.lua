-- Ghost in the Shell look: colourscheme, statusline, bufferline, dashboard.
-- The colourscheme itself lives in colors/gits.lua + lua/gits/, the lualine theme in lua/lualine/themes/gits.lua.
local c = require("gits.palette")

-- Dashboard art: the colour theme's art set (~/.local/share/gits/art/current/dashboard.txt), else ~/.config/nvim/lua/gits/lain.txt;
-- coloured the same way as the terminal banner
-- (hair dim, eyes bright, hairclip red, the rest cyan).
local function art_items()
  local data = os.getenv("XDG_DATA_HOME") or (os.getenv("HOME") .. "/.local/share")
  local path = data .. "/gits/art/current/dashboard.txt"
  if vim.fn.filereadable(path) == 0 then
    path = vim.fn.stdpath("config") .. "/lua/gits/lain.txt"
  end
  local ok, lines = pcall(vim.fn.readfile, path)
  if not ok then
    return {}
  end
  -- the rest of the dashboard (tagline box, 6 keys with gaps, startup line) needs ~19 rows: give the art what is left, crop it from
  -- the bottom (the face stays), and drop it only when fewer than 14 rows remain
  local avail = vim.o.lines - 19
  if avail < 14 then
    return {}
  end
  if avail < #lines then
    lines = vim.list_slice(lines, 1, avail)
  end
  local width = 0
  for _, l in ipairs(lines) do
    width = math.max(width, vim.fn.strdisplaywidth(l)) -- cells, not bytes: the art is braille (3 bytes per cell)
  end
  local items = {}
  for _, line in ipairs(lines) do
    line = line .. string.rep(" ", width - vim.fn.strdisplaywidth(line)) -- equal widths keep the shape when centred
    local segs, i = {}, 1
    while i <= #line do
      local hl, len = "GitsArt", 1
      if line:sub(i, i + 2) == "//=" then
        hl, len = "GitsArtClip", 3
      else
        local ch = line:sub(i, i)
        if ch == "#" or ch == "%" then
          hl = "GitsArtHair"
        elseif ch == "@" then
          hl = "GitsArtEye"
        end
      end
      local last = segs[#segs]
      if last and last.hl == hl then
        last[1] = last[1] .. line:sub(i, i + len - 1)
      else
        segs[#segs + 1] = { line:sub(i, i + len - 1), hl = hl }
      end
      i = i + len
    end
    items[#items + 1] = { text = segs, align = "center" }
  end
  items[#items].padding = 1
  return items
end

-- the tagline box from the terminal banner
local function frame_items()
  local rows = {
    { { "┌─[ ", hl = "GitsFrame" }, { "wired://navi-00", hl = "GitsFrameText" }, { " ]──────────────────────", hl = "GitsFrame" } },
    { { "│ ", hl = "GitsFrame" }, { "the net is vast and infinite.", hl = "GitsFrameText" } },
    { { "└─ ", hl = "GitsFrame" }, { "what if a cyber-brain could possibly generate its own ghost?", hl = "GitsFrameText" } },
  }
  local width = 0
  for _, row in ipairs(rows) do
    local w = 0
    for _, seg in ipairs(row) do
      w = w + vim.fn.strdisplaywidth(seg[1])
    end
    row.w = w
    width = math.max(width, w)
  end
  local items = {}
  for _, row in ipairs(rows) do
    local segs = vim.deepcopy(row)
    segs.w = nil
    if row.w < width then
      segs[#segs + 1] = { string.rep(" ", width - row.w), hl = "GitsFrame" }
    end
    items[#items + 1] = { text = segs, align = "center" }
  end
  items[#items].padding = 1
  return items
end

return {
  { "LazyVim/LazyVim", opts = { colorscheme = "gits" } },

  {
    "folke/snacks.nvim",
    opts = function(_, opts)
      opts.dashboard = opts.dashboard or {}
      opts.dashboard.width = 70
      opts.dashboard.sections = {
        art_items,
        frame_items,
        { section = "keys", gap = 1, padding = 1 },
        { section = "startup" },
      }
      opts.indent = vim.tbl_deep_extend("force", opts.indent or {}, {
        indent = { char = "│" },
        scope = { char = "│" },
      })
    end,
  },

  {
    "nvim-lualine/lualine.nvim",
    opts = function(_, opts)
      opts.options = vim.tbl_deep_extend("force", opts.options or {}, {
        theme = "gits",
        -- flat strip with thin dividers, like waybar
        component_separators = { left = "│", right = "│" },
        section_separators = { left = "", right = "" },
      })
      -- the prompt's "▶" in front of the mode
      opts.sections.lualine_a = {
        {
          "mode",
          fmt = function(mode)
            return "▶ " .. mode
          end,
        },
      }
      -- LazyVim's default error glyph (U+F057) is drawn broken by our terminal font, use Material ones
      for _, comp in ipairs(opts.sections.lualine_c) do
        if type(comp) == "table" and comp[1] == "diagnostics" then
          comp.symbols = { error = "󰅚 ", warn = "󰀪 ", info = "󰋽 ", hint = "󰌶 " }
        end
      end
      -- "Top/Bot/45%" is redundant next to the line:col, and without it the strip fits half-screen windows
      -- (when it doesn't fit, nvim truncates the middle and prints a bare "<")
      opts.sections.lualine_y = { { "location", padding = { left = 1, right = 1 } } }
      opts.sections.lualine_z = {
        function()
          return "󰥔 " .. os.date("%R")
        end,
      }
    end,
  },

  {
    "akinsho/bufferline.nvim",
    opts = function(_, opts)
      opts.options = vim.tbl_deep_extend("force", opts.options or {}, {
        separator_style = "thin",
        indicator = { style = "underline" },
        show_buffer_close_icons = false,
        show_close_icon = false,
        modified_icon = "●",
      })
      -- active buffer = solid cyan "tab" like kitty's tab bar, everything else recedes
      local sel = { fg = c.bg, bg = c.cyan, bold = true, italic = false }
      local idle = { fg = c.fg_dim, bg = c.bg_hl }
      local dim = { fg = c.muted, bg = c.bg_hl }
      opts.highlights = {
        fill = { bg = c.bg },
        background = idle,
        buffer_visible = dim,
        buffer_selected = sel,
        close_button = idle,
        close_button_visible = dim,
        close_button_selected = sel,
        separator = { fg = c.bg, bg = c.bg_hl },
        separator_visible = { fg = c.bg, bg = c.bg_hl },
        separator_selected = { fg = c.bg, bg = c.cyan },
        indicator_visible = { fg = c.bg_hl, bg = c.bg_hl },
        indicator_selected = { fg = c.red_hi, bg = c.cyan },
        modified = { fg = c.yellow, bg = c.bg_hl },
        modified_visible = { fg = c.yellow, bg = c.bg_hl },
        modified_selected = { fg = c.bg, bg = c.cyan },
        numbers = idle,
        numbers_visible = dim,
        numbers_selected = sel,
        diagnostic = idle,
        diagnostic_visible = dim,
        diagnostic_selected = sel,
        error = idle,
        error_visible = dim,
        error_selected = sel,
        error_diagnostic = idle,
        error_diagnostic_visible = dim,
        error_diagnostic_selected = sel,
        warning = idle,
        warning_visible = dim,
        warning_selected = sel,
        warning_diagnostic = idle,
        warning_diagnostic_visible = dim,
        warning_diagnostic_selected = sel,
        info = idle,
        info_visible = dim,
        info_selected = sel,
        info_diagnostic = idle,
        info_diagnostic_visible = dim,
        info_diagnostic_selected = sel,
        hint = idle,
        hint_visible = dim,
        hint_selected = sel,
        hint_diagnostic = idle,
        hint_diagnostic_visible = dim,
        hint_diagnostic_selected = sel,
        tab = idle,
        tab_selected = sel,
        tab_separator = { fg = c.bg, bg = c.bg_hl },
        tab_separator_selected = { fg = c.bg, bg = c.cyan },
        tab_close = { fg = c.red, bg = c.bg },
        offset_separator = { fg = c.line, bg = c.bg_dark },
        duplicate = dim,
        duplicate_visible = dim,
        duplicate_selected = sel,
        pick = { fg = c.red_hi, bg = c.bg_hl, bold = true },
        pick_visible = { fg = c.red_hi, bg = c.bg_hl, bold = true },
        pick_selected = { fg = c.bg, bg = c.cyan, bold = true },
      }
    end,
  },

  {
    "folke/noice.nvim",
    opts = {
      views = {
        cmdline_popup = { border = { style = "single" } },
        popupmenu = { border = { style = "single" } },
        confirm = { border = { style = "single" } },
        hover = { border = { style = "single" } },
      },
    },
  },
}
