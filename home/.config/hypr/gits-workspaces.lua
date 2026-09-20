-- Workspaces show up only while they are in use (have windows or are active).
-- Workspace 1 is always kept, so the bar never goes empty. Waybar lists whatever Hyprland reports
-- (no persistent-workspaces in the layout).
hl.workspace_rule({ workspace = "1", persistent = true })
