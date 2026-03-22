export PAGER=bat
export LSCOLORS="Gxfxcxdxbxegedabagacad"
export GPG_TTY=$(tty)
export RIPGREP_CONFIG_PATH="$HOME/.config/ripgrep/config"
export FZF_DEFAULT_OPTS='--bind ctrl-f:page-down,ctrl-b:page-up'

CARGO_ENV="$HOME/.cargo/env"
if [[ -f $CARGO_ENV ]]; then
  source $CARGO_ENV
fi

export NVM_DIR="$HOME/.nvm"
[ -s "$NVM_DIR/nvm.sh" ] && source "$NVM_DIR/nvm.sh"  # This loads nvm
[ -s "$NVM_DIR/bash_completion" ] && source "$NVM_DIR/bash_completion"  # This loads nvm bash_completion
