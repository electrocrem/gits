-- Automatic game mode: while a game is fullscreen on any monitor, animations, blur and shadows are off (no config reload, so no hitch);
-- they come back as they were when the game leaves fullscreen or closes. The manual preset (Super+Alt+G, workflow "gaming") stays as is.
-- A game = a fullscreen window that says so (content type "game") or whose class looks like one: Steam / Proton (steam_app_*), gamescope,
-- Wine (*.exe), Minecraft, Roblox (Sober). More classes: GITS_GAME_CLASSES="lua-pattern;lua-pattern". GITS_GAMEMODE=0 turns it off.
if os.getenv("GITS_GAMEMODE") == "0" then return end

local patterns = { "^steam_app_%d+$", "^gamescope$", "%.exe$", "^Minecraft", "^org%.vinegarhq%.Sober$", "^cs2$", "^dota2$" }
for p in (os.getenv("GITS_GAME_CLASSES") or ""):gmatch("[^;]+") do patterns[#patterns + 1] = p end

local KEYS = { "animations.enabled", "decoration.blur.enabled", "decoration.shadow.enabled" }
local saved   -- the values from before the game, while game mode is on

local function is_game(w)
    if w.content_type == "game" then return true end
    for _, p in ipairs({ w.class or "", w.initial_class or "" }) do
        for _, pat in ipairs(patterns) do
            if p:match(pat) then return true end
        end
    end
    return false
end

-- a game is on screen: fullscreen, on the workspace its monitor is showing
local function game_on_screen()
    for _, w in ipairs(hl.get_windows() or {}) do
        if (tonumber(w.fullscreen) or 0) > 0 and w.workspace and w.monitor and w.monitor.active_workspace
            and w.workspace.id == w.monitor.active_workspace.id and is_game(w) then
            return w
        end
    end
end

-- set("decoration.blur.enabled", false) -> hl.config({ decoration = { blur = { enabled = false } } })
local function set(key, value)
    local parts = {}
    for part in key:gmatch("[^.]+") do parts[#parts + 1] = part end
    local t = {}
    local node = t
    for i = 1, #parts - 1 do node[parts[i]] = {}; node = node[parts[i]] end
    node[parts[#parts]] = value
    hl.config(t)
end

local function check()
    local game = game_on_screen()
    if game and not saved then
        saved = {}
        for _, k in ipairs(KEYS) do saved[k] = hl.get_config(k); set(k, false) end
        hl.exec_cmd("notify-send -a 'GitS' -t 2000 -i input-gaming 'GAME MODE' '" .. (game.class or "game"):gsub("'", "") .. ": effects off'")
    elseif not game and saved then
        for _, k in ipairs(KEYS) do if saved[k] ~= nil then set(k, saved[k]) end end
        saved = nil
    end
end

local function safe_check() pcall(check) end
for _, ev in ipairs({ "window.fullscreen", "window.active", "window.close", "window.destroy", "workspace.active", "window.move_to_workspace" }) do
    hl.on(ev, safe_check)
end
safe_check()   -- after a config reload the effects are back on: a game still on screen turns them off again
