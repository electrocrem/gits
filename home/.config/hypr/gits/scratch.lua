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
      }) },
    { name = "music", key = "M", title = "music player", size = "(monitor_w*0.6) (monitor_h*0.7)",
      pick("MUSIC", {
          { "spotify", "^([Ss]potify)$" },
          { "youtube-music", "^(com\\.github\\.th_ch\\.youtube_music|YouTube Music)$" },
          { "feishin", "^(feishin|Feishin)$" },
          { "kitty --class music-dropdown -e rmpc", "^music-dropdown$", "rmpc" },
          { "kitty --class music-dropdown -e ncmpcpp", "^music-dropdown$", "ncmpcpp" },
          { "kitty --class music-dropdown -e cmus", "^music-dropdown$", "cmus" },
          { "kitty --class music-dropdown -e termusic", "^music-dropdown$", "termusic" },
      }) },
}

for _, p in ipairs(pads) do
    local cmd, class = p[1], p[2]
    if cmd then
        hl.window_rule({ name = "gits_scratch_" .. p.name, match = { class = class }, workspace = "special:" .. p.name .. " silent",
                         float = true, size = p.size, center = true })
        hl.bind("SUPER + ALT + " .. p.key, hl.dsp.exec_cmd(string.format("gits-scratch %s '%s' %s", p.name, class, cmd)),
                { description = "[GitS] " .. p.title .. " dropdown" })
    end
end
