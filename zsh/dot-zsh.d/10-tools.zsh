if command -v direnv &> /dev/null; then
  eval "$(direnv hook zsh)"
fi

if command -v zoxide &> /dev/null; then
  eval "$(zoxide init zsh)"
fi

if command -v starship &> /dev/null; then
  eval "$(starship init zsh)"
fi

if command -v atuin &> /dev/null; then
  eval "$(atuin init zsh --disable-up-arrow)"
fi

if command -v task &> /dev/null; then
  eval "$(task --completion zsh)"
fi
