-- Dropdown apps (gits-scratch): Super+Alt+C chat, Super+Alt+M music. Each lives on its own special workspace, floating and centred,
-- over whatever workspace is open; the key shows / hides it, and starts it the first time. Only apps that are installed get a key.
--   chat:  Telegram                                         (GITS_CHAT_CMD + GITS_CHAT_CLASS to use something else)
--   music: Spotify, YouTube Music, Feishin, else a terminal player (rmpc, ncmpcpp, cmus, termusic) in kitty
--                                                           (GITS_MUSIC_CMD + GITS_MUSIC_CLASS to use something else)
-- The class is a regex for the window rule and for gits-scratch; set GITS_SCRATCH=0 to drop the whole thing.
if os.getenv("GITS_SCRATCH") == "0" then return end

-- io.popen, not os.execute: Hyprland reaps its children itself, so os.execute never sees an exit status (always nil)
local function have(cmd)
    local f = io.popen("command -v " .. cmd .. " 2>/dev/null")
    if not f then return false end
    local out = f:read("a") or ""
    f:close()
    return out ~= ""
end

-- first installed candidate: { command, class regex }
local function pick(env, candidates)
    local cmd, class = os.getenv("GITS_" .. env .. "_CMD"), os.getenv("GITS_" .. env .. "_CLASS")
    if cmd and class then return cmd, class end
    for _, c in ipairs(candidates) do
        if have(c[1]:match("^%S+")) and (not c[3] or have(c[3])) then return c[1], c[2] end
    end
end

local pads = {
    { name = "chat", key = "C", title = "chat", size = "(monitor_w*0.62) (monitor_h*0.78)",
      pick("CHAT", {
          { "Telegram", "^(org\\.telegram\\.desktop|TelegramDesktop)$" },
          { "telegram-desktop", "^(org\\.telegram\\.desktop|TelegramDesktop)$" },
          { "org.telegram.desktop", "^(org\\.telegram\\.desktop|TelegramDesktop)$" },   -- Flatpak
      }) },
    { name = "music", key = "M", title = "music player", size = "(monitor_w*0.6) (monitor_h*0.7)",
      pick("MUSIC", {
          { "spotify", "^([Ss]potify)$" },
          { "spotify-launcher", "^([Ss]potify)$" },     -- Arch: keeps Spotify in ~, so Spicetify can theme it
          { "com.spotify.Client", "^([Ss]potify)$" },   -- Flatpak
          { "youtube-music", "^(com\\.github\\.th_ch\\.youtube_music|YouTube Music)$" },
          { "com.github.th_ch.youtube_music", "^(com\\.github\\.th_ch\\.youtube_music|YouTube Music)$" },   -- Flatpak
          { "feishin", "^(feishin|Feishin)$" },
          { "kitty --class music-dropdown -e rmpc", "^music-dropdown$", "rmpc" },
          { "kitty --class music-dropdown -e ncmpcpp", "^music-dropdown$", "ncmpcpp" },
          { "kitty --class music-dropdown -e cmus", "^music-dropdown$", "cmus" },
          { "kitty --class music-dropdown -e termusic", "^music-dropdown$", "termusic" },
      }) },
}

-- the class regexes are simple ("^(a|b\\.c)$", "[Ss]"): turn them into Lua patterns; nil = something fancier, leave it alone
local function lua_patterns(re)
    local body = re:match("^%^%((.*)%)%$$") or re:match("^%^(.*)%$$")
    if not body or body:find("[%(%)%*%+%?{}]") then return nil end
    local out = {}
    for alt in (body .. "|"):gmatch("([^|]*)|") do
        out[#out + 1] = "^" .. alt:gsub("%-", "%%-"):gsub("\\%.", "%%."):gsub(" ", "%%s") .. "$"
    end
    return out
end

local own = {}   -- pad name -> Lua patterns of its app

for _, p in ipairs(pads) do
    local cmd, class = p[1], p[2]
    if cmd then
        own[p.name] = lua_patterns(class)
        hl.window_rule({ name = "gits_scratch_" .. p.name, match = { class = class }, workspace = "special:" .. p.name .. " silent",
                         float = true, size = p.size, center = true })
        hl.bind("SUPER + ALT + " .. p.key, hl.dsp.exec_cmd(string.format("gits-scratch %s '%s' %s", p.name, class, cmd)),
                { description = "[GitS] " .. p.title .. " dropdown" })
    end
end

-- While a dropdown is shown it has the focus, so a window opened then (Super+T...) would land on the special workspace, behind the
-- app. Send anything that is not the dropdown's own app (or one of its dialogs) to the monitor's normal workspace and hide the pad.
local function is_own(pats, w)
    for _, c in ipairs({ w.class or "", w.initial_class or "" }) do
        for _, pat in ipairs(pats) do
            if c:match(pat) then return true end
        end
    end
    return false
end

hl.on("window.open", function(w)
    pcall(function()
        local pad = w.workspace and (w.workspace.name or ""):match("^special:(.+)$")
        local pats = pad and own[pad]
        if not pats or is_own(pats, w) or not (w.monitor and w.monitor.active_workspace) then return end
        local home = tostring(w.monitor.active_workspace.id)
        hl.dispatch(hl.dsp.workspace.toggle_special(pad))
        hl.dispatch(hl.dsp.window.move({ workspace = home, window = w }))
        hl.dispatch(hl.dsp.focus({ window = w }))
    end)
end)
