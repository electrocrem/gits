# Notices

## Artwork (`assets/`)

`gits_smoke.png`, `gits_eye.png`, `gits_cyborg.jpg`, `gits_teal_wires.jpg`, `art.png` and the ASCII pieces
`cyborg.txt`, `lain.txt`, `shodan.txt` are fan artwork and character art from third-party franchises (Ghost in the
Shell, Serial Experiments Lain, System Shock). They are **not** covered by this repository's MIT license, remain the
property of their respective authors and rights holders, and are included here for personal use of this setup only.

If you fork or redistribute this repository publicly, delete `assets/*.png`, `assets/*.jpg`, `assets/*.txt`. The
installer then generates original placeholder wallpapers and a generic ASCII banner with `tools/make-assets.py`.

## Third-party files

* `home/.config/Kvantum/GitS/GitS.svg` and `GitS.kvconfig` are a recoloured copy of the *GraphiteDark* Kvantum theme as shipped with
  [HyDE](https://github.com/HyDE-Project/HyDE) (`author=Vince Liuice, based on KvAdapta by Tsu Jan`); they stay under their original license
  (GPL-3.0).
* The Hyprland key bindings, window rules and layout / workflow presets in `home/.config/hypr/gits/` started as a port of HyDE's Lua
  config (GPL-3.0) and were adapted.
* GTK widgets come from the `adw-gtk-theme` package (only the colour overrides in `home/.config/gtk-*/gtk.css` are ours).
* Fonts (JetBrains Mono Nerd Font, Noto CJK) are not bundled.

## Dancing Lain (radio popup)

`assets/lain-dance.gif` (installed as `~/.config/gits-widgets/lain.gif`) is the dance animation from [pryanostnik/lain-dance](https://github.com/pryanostnik/lain-dance) (MIT). The character is
Lain Iwakura from *Serial Experiments Lain* (Triangle Staff / Pioneer LDC); like the other artwork here it stays under the rights of its owners.
