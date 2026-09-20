# Palette

One palette for the whole desktop: CRT cyan on navy-black, a red accent for "the eye" and for alerts.
Every config that draws colours (kitty, waybar, popups, hyprland, hyprlock, dunst, GTK, Qt, nvim, tmux, yazi, btop, satty, Zen, Logseq)
uses these values; the master copy is `home/.config/kitty/theme.conf`.

| role | hex |
|---|---|
| background | `#060A14` |
| surface (panels, hover) | `#0C1A33` |
| surface, deeper (views) | `#0A1226` |
| foreground | `#C8F4FF` (text on GTK: `#D0FDFF`) |
| accent (borders, active) | `#2ED3D7` |
| accent, bright (hover, urgent-normal frame) | `#5EF1F5` |
| accent, second (gradient end) | `#398FF0` |
| red (cursor, alerts) | `#E5432B` |
| red, light | `#FF7A5C` |
| green / yellow / blue / violet | `#34D399` / `#E8C547` / `#3B74D0` / `#7C6CE0` |
| muted text | `#9FC5D6`, dim `#254F5D` |

The 16 terminal colours are in `home/.config/kitty/theme.conf`.
