# Ghost in the Shell: OPT-IN tmux autostart. Off by default; with GITS_TMUX=1 every interactive kitty shell starts inside its own
# tmux session (status strip = ~/.config/tmux/tmux.conf). Put `export GITS_TMUX=1` in ~/.config/zsh/user.zsh above the gits block to turn it on.
# Leaving tmux (last pane exits, or prefix + d) closes the window; if tmux cannot start you simply keep the plain shell.
# tmux itself stays installed and themed (`tmux`, prefix + f for the project switcher); only the automatic start is off.
# Never inside tmux, ssh, Neovim/Vim terminals, VS Code, Emacs, or anything that is not kitty.
gits_tmux() {
    [[ -o interactive && -t 0 && -t 1 && -z $TMUX && -n $GITS_TMUX && -z $GITS_NO_TMUX ]] || return
    [[ -n $KITTY_WINDOW_ID && $TERM == xterm-kitty ]] || return
    [[ -z $SSH_CONNECTION && -z $NVIM && -z $VIM && -z $INSIDE_EMACS && $TERM_PROGRAM != vscode ]] || return
    (( $+commands[tmux] )) || return
    tmux new-session && exit
}
gits_tmux
