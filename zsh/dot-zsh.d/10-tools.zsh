if command -v starship &> /dev/null; then
  eval "$(starship init zsh)"
fi

if command -v atuin &> /dev/null; then
  eval "$(atuin init zsh --disable-up-arrow)"
fi

if command -v task &> /dev/null; then
  eval "$(task --completion zsh)"
fi

FZF_GIT="$DOTFILES_HOME/vendor/fzf-git.sh"
if [[ -f $FZF_GIT ]]; then
  source $FZF_GIT
fi

Z_HOOK="$(brew --prefix)/etc/profile.d/z.sh"
if [[ -f $Z_HOOK ]]; then
  source $Z_HOOK
fi
