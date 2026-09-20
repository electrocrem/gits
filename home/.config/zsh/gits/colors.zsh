# Ghost in the Shell: fzf colours (same palette as kitty / nvim / btop). Sourced from user.zsh.
# The theme part is appended so anything already in FZF_DEFAULT_OPTS is kept.
export FZF_DEFAULT_OPTS="${FZF_DEFAULT_OPTS} \
--border=sharp --prompt='▶ ' --pointer='▶' --marker='●' \
--color=bg:#060A14,bg+:#0C1A33,fg:#9FC5D6,fg+:#DDF9FF,hl:#2ED3D7,hl+:#5EF1F5 \
--color=info:#596977,prompt:#2ED3D7,pointer:#E5432B,marker:#E5432B,spinner:#E5432B \
--color=header:#596977,border:#254F5D,gutter:#060A14,separator:#242F41,scrollbar:#254F5D"
