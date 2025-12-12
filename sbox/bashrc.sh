export LS_OPTIONS='--color=auto'
eval "$(dircolors -b)"
alias ls='ls $LS_OPTIONS'
alias ll='ls $LS_OPTIONS -l'
alias l='ls $LS_OPTIONS -lA'

export PATH="/tools:$PATH"

if [[ -f $HOME/.local/bin/env ]]; then
    source "$HOME/.local/bin/env"
fi

export UV_LINK_MODE=copy
