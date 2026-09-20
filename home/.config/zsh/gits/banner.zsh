# Ghost in the Shell: ASCII banner on interactive kitty shells (art: ~/.config/zsh/gits/art.png via kitty graphics, or {shodan,cyborg,lain}.txt; pick with GITS_BANNER_ART)
# System info sits to the right of the art (fastfetch); tagline is "typed".
# Skipped inside tmux/nested shells and when GITS_NO_BANNER=1; GITS_BANNER_FAST=1 turns the typing off.
gits_banner() {
    [[ -o interactive && -t 1 && -z $TMUX && -z $GITS_NO_BANNER && $SHLVL -le 2 ]] || return
    setopt localoptions extendedglob
    local dir=${${(%):-%x}:A:h}
    local art_name=${GITS_BANNER_ART:-image} tag foot net=wired://navi-00 title="SECTION 9 // NAVI-00" img_h=0
    local c=$'\e[36m' d=$'\e[2;36m' w=$'\e[1;97m' r=$'\e[0m'

    # image mode: real picture through the kitty graphics protocol, sized to fit the window
    if [[ $art_name == image ]]; then
        if [[ -n $KITTY_WINDOW_ID && -r $dir/art.png ]] && (( $+commands[fastfetch] )); then
            img_h=$(( LINES - 6 )); (( img_h > 24 )) && img_h=24
            # ~1.6 cells of width per row, plus padding and a 52 column info block
            (( img_h * 8 / 5 + 3 + 52 > COLUMNS )) && img_h=$(( (COLUMNS - 55) * 5 / 8 ))
            (( img_h < 8 )) && img_h=0
        fi
        (( img_h )) && { c=$'\e[94m' d=$'\e[34m' } || art_name=shodan   # too small / not kitty: fall back to ASCII
    fi
    [[ $art_name == shodan ]] && { c=$'\e[31m' d=$'\e[2;31m' w=$'\e[1;91m' net=shodan://citadel title="CITADEL STATION // SHODAN" }   # SHODAN is red
    local -a raw info=()
    (( img_h )) || raw=("${(@f)$(<$dir/$art_name.txt)}")
    local artw=50 line k v i

    if (( img_h )); then
        fastfetch -c $dir/fastfetch-image.jsonc --logo $dir/art.png --logo-type kitty-direct \
            --logo-height $img_h --logo-width $(( img_h * 8 / 5 )) --logo-padding-right 3 2>/dev/null
    else
        # system info: "Key: value" lines from fastfetch, key coloured
        if (( COLUMNS >= 92 )) && (( $+commands[fastfetch] )); then
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
    elif (( img_h )); then
        tag="the net is vast and infinite."
        foot="what if a cyber-brain could possibly generate its own ghost?"
    else
        tag="my ghost whispers. the net listens."
        foot="if you have a ghost, you are human. if not, you are a shell."
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
