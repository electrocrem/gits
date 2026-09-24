# Terminal banner on interactive kitty shells. The art is the colour theme's set, ~/.local/share/gits/art/current/ (gits-theme points it
# at the theme's): banner.png via kitty graphics, else its banner.txt; its banner.conf gives the title and the lines. GITS_BANNER_ART=shodan|
# cyborg|lain picks one of the ASCII pieces next to this file instead.
# System info sits to the right of the art (fastfetch); tagline is "typed".
# Inside tmux (started by tmux.zsh) it is shown once, in the first pane of a new session. The picture goes through tmux as
# kitty "unicode placeholders" (kitten icat --unicode-placeholder --passthrough=tmux: the image lives in kitty, the pane only
# holds text cells); if that fails it falls back to ASCII art (GITS_BANNER_ART_TMUX, default cyborg). Skipped in nested
# shells and when GITS_NO_BANNER=1; GITS_BANNER_FAST=1 turns the typing off.
gits_banner() {
    [[ -o interactive && -t 1 && -z $GITS_NO_BANNER && $SHLVL -le 2 ]] || return
    setopt localoptions extendedglob
    local art_name=${GITS_BANNER_ART:-image}
    if [[ -n $TMUX ]]; then
        # first pane of a session created a moment ago; later panes/windows stay quiet
        [[ $(tmux display -p '#{window_index}:#{pane_index}') == ${$(tmux show -gv base-index):-0}:${$(tmux show -gwv pane-base-index):-0} ]] || return
        zmodload zsh/datetime 2>/dev/null
        (( EPOCHSECONDS - $(tmux display -p "#{session_created}") < 10 )) || return
    fi
    local dir=${${(%):-%x}:A:h} art=${XDG_DATA_HOME:-$HOME/.local/share}/gits/art/current
    local tag foot net=section9://tachikoma-00 title="SECTION 9 // PUBLIC SECURITY" img_h=0 tag_ascii foot_ascii
    [[ -r $art/banner.conf ]] && source $art/banner.conf
    local png=$art/banner.png; [[ -r $png ]] || png=$dir/art.png
    local c=$'\e[36m' d=$'\e[2;36m' w=$'\e[1;97m' r=$'\e[0m'

    # image mode: real picture through the kitty graphics protocol, sized to fit the window
    if [[ $art_name == image ]]; then
        if [[ -n $KITTY_WINDOW_ID && -r $png ]] && (( $+commands[fastfetch] )) && [[ -z $TMUX || -n $commands[kitten] ]]; then
            img_h=$(( LINES - 6 )); (( img_h > 24 )) && img_h=24
            # ~1.6 cells of width per row, plus padding and a 52 column info block
            (( img_h * 8 / 5 + 3 + 52 > COLUMNS )) && img_h=$(( (COLUMNS - 55) * 5 / 8 ))
            (( img_h < 8 )) && img_h=0
        fi
        # tmux: the picture as placeholder text rows. icat prints the image data (DCS-wrapped for tmux), then the rows with
        # absolute positioning (--place); keep the data and the bare rows, drop the positioning (\e7 \e[1;0H \e8 \r \e[0C).
        local -a ph=(); local gfx phcol
        if (( img_h )) && [[ -n $TMUX ]]; then
            local out=$(kitten icat --passthrough=tmux --unicode-placeholder --transfer-mode=stream --align=left \
                --place=$(( img_h * 8 / 5 ))x${img_h}@0x0 $png 2>/dev/null)
            gfx=${out%%$'\e[38:2:'*}
            local rest=${out#"$gfx"} body
            phcol=${rest%%m*}                                   # "\e[38:2:R:G:B" (image id lives in the foreground colour)
            body=${rest#"$phcol"m}
            phcol=$'\e[38;2;'${phcol#$'\e[38:2:'}m; phcol=${phcol//:/;}
            body=${body//$'\e7'/}; body=${body//$'\e8'/}; body=${body//$'\e[1;0H'/}; body=${body//$'\e[0C'/}
            body=${body//$'\r'/}; body=${body//$'\e[39m'/}
            ph=("${(@f)body}")
            (( ${#gfx} > 100 && ${#ph} >= img_h )) || { img_h=0; ph=(); }
        fi
        (( img_h )) && { c=$'\e[94m' d=$'\e[34m' } || art_name=${${TMUX:+${GITS_BANNER_ART_TMUX:-theme}}:-theme}   # too small / not kitty: fall back to ASCII
    fi
    [[ $art_name == shodan ]] && { c=$'\e[31m' d=$'\e[2;31m' w=$'\e[1;91m' net=shodan://citadel title="CITADEL STATION // SHODAN" }   # SHODAN is red
    local -a raw info=()
    if (( ! img_h )); then
        if [[ $art_name == theme && -r $art/banner.txt ]]; then raw=("${(@f)$(<$art/banner.txt)}"); else raw=("${(@f)$(<$dir/${art_name/theme/cyborg}.txt)}"); fi
    fi
    local artw=50 line k v i
    # the info column starts right after the widest art line (the old art was 47 columns wide, the braille one 38)
    if (( ${#raw} )); then artw=0; for line in "${raw[@]}"; do (( ${#line} + 3 > artw )) && artw=$(( ${#line} + 3 )); done; fi

    if (( img_h )) && [[ -n $TMUX ]]; then
        # picture cells on the left, fastfetch's info column (no logo) on the right, vertically centred
        # (without a logo fastfetch aligns values with an absolute "cursor to column 7" code, which would jump into the picture:
        # rebuild those lines as "KEY   │ value" ourselves; piped fastfetch prints no colours, so colour the key here)
        local -a fi=(); local ln
        for ln in "${(@f)$(fastfetch -c $dir/fastfetch-image.jsonc --logo none 2>/dev/null)}"; do
            if [[ $ln == *$'\e[7G'* ]]; then
                k=${${ln%%$'\e[7G'*}%% │*}; v=${ln#*$'\e[7G'}
                fi+=("${c}${(r:7:)k}${d}│ ${r}${v[1,COLUMNS-img_h*8/5-14]}")
            else
                fi+=("$ln")
            fi
        done
        local foff=$(( (${#ph} - ${#fi}) / 2 )); (( foff < 0 )) && foff=0
        print -rn -- "$gfx"
        for (( i = 1; i <= ${#ph}; i++ )); do
            if (( i > foff && i - foff <= ${#fi} )); then print -r -- "${phcol}${ph[i]}${r}   ${fi[i-foff]}"; else print -r -- "${phcol}${ph[i]}${r}"; fi
        done
    elif (( img_h )); then
        fastfetch -c $dir/fastfetch-image.jsonc --logo $png --logo-type kitty-direct \
            --logo-height $img_h --logo-width $(( img_h * 8 / 5 )) --logo-padding-right 3 2>/dev/null
    else
        # system info: "Key: value" lines from fastfetch, key coloured
        if (( COLUMNS >= artw + 42 )) && (( $+commands[fastfetch] )); then
            for line in "${(@f)$(fastfetch -c $dir/fastfetch.jsonc --logo none 2>/dev/null)}"; do
                [[ $line == *": "* ]] || continue
                k=${line%%: *}; v=${line#*: }
                case $k in Packages) k=PKGS;; Terminal) k=TERM;; GPU*) k=GPU;; Disk*) k=DISK;; esac
                info+=("${c}${(r:7:)${(U)k}}${d}│ ${r}${v[1,COLUMNS-artw-12]}")
            done
            info=("${d}┌─[ ${c}${title}${d} ]${r}" "${d}│${r}" $info "${d}└──────────────────────${r}")
        fi

        local off=$(( (${#raw} - ${#info}) / 2 )) art
        (( off < 0 )) && off=0
        for (( i = 1; i <= ${#raw}; i++ )); do
            art=${raw[i]}
            art=${art//(#m)[#%]/${d}${MATCH}${r}}      # hair: dim
            art=${art//@/${w}@${r}}                    # eyes: bright
            art=${art//\/\/=/${c}//=${r}}              # hairclip
            if (( ${#info} )) && (( i > off && i - off <= ${#info} )); then
                print -r -- "${art}${(l:$(( artw - ${#raw[i]} )):: :)}${info[i-off]}"
            else
                print -r -- "$art"
            fi
        done
    fi

    if [[ $art_name == lain ]]; then
        tag="present day. present time."
        foot="no matter where you are, everyone is always connected."
    elif [[ $art_name == shodan ]]; then
        tag="look at you, hacker."
        foot="a pathetic creature of meat and bone."
    elif (( ! img_h )) && [[ -n $tag_ascii ]]; then
        tag=$tag_ascii foot=$foot_ascii
    fi
    print -r -- "${d}  ┌─[ ${c}${net}${d} ]────────────────────────────${r}"
    printf '%s' "${d}  │ ${c}"
    if [[ -z $GITS_BANNER_FAST ]] && zmodload zsh/zselect 2>/dev/null; then
        for (( i = 1; i <= ${#tag}; i++ )); do printf '%s' "${tag[i]}"; zselect -t 1; done
    else
        printf '%s' "$tag"
    fi
    print -r -- "${r}"
    print -r -- "${d}  └─ ${c}${foot}${r}"
    print
}
gits_banner
