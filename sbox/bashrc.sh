export LS_OPTIONS='--color=auto'
eval "$(dircolors -b)"
alias ls='ls $LS_OPTIONS'
alias ll='ls $LS_OPTIONS -l'
alias l='ls $LS_OPTIONS -lA'
alias ..='cd ..'


if [[ -f $HOME/.bash_env ]]; then
  source $HOME/.bash_env
fi

export PATH="$HOME/.local/bin:${PATH}"
export PATH="$HOME/.deno/bin:${PATH}"
