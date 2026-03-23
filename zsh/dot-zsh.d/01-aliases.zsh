reload!() {
  # Unset any env vars added after the pre-zsh.d snapshot
  local -a _env_after=( ${(k)parameters[(R)*export*]} )
  for key in "${_env_after[@]}"; do
    (( ${_reload_env_before[(Ie)$key]} )) || unset "$key"
  done
  # Restore PATH to its pre-zsh.d state
  PATH="$_reload_path_before"
  exec $SHELL -l
}

# misc
alias speedtest="networkQuality -v -s"

# git
alias gs='git status'
alias lg='lazygit'

# proxyman
alias pm='proxyman-cli proxy'

# term
alias term-reset='reset; tput cnorm'
