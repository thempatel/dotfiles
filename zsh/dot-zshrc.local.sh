# Deduplicate $PATH entries
typeset -U PATH path

SCRIPT_PATH="${(%):-%x}"
SCRIPT_DIR="${SCRIPT_PATH:A:h}"
export DOTFILES_HOME="$(dirname $SCRIPT_DIR)"
export GPG_TTY=$(tty)
export RIPGREP_CONFIG_PATH="$HOME/.config/ripgrep/config"
export FZF_DEFAULT_OPTS='--bind ctrl-f:page-down,ctrl-b:page-up'

export ZSH="$HOME/.oh-my-zsh"
ZSH_THEME="robbyrussell"
plugins=(git)
source $ZSH/oh-my-zsh.sh

if which atuin > /dev/null; then
  eval "$(atuin init zsh --disable-up-arrow)"
fi

ssh-add --apple-use-keychain ~/.ssh/id_ed25519

ALIASES="$HOME/.zsh_aliases.local.sh"
if [[ -L $ALIASES ]]; then
  source $ALIASES
fi

FUNCS="$HOME/.zsh_funcs.local.sh"
if [[ -L $FUNCS ]]; then
  source $FUNCS
fi

path+=("$DOTFILES_HOME/bin" "$HOME/.local/bin")

CARGO_ENV="$HOME/.cargo/env"
if [[ -f $CARGO_ENV ]]; then
  source $CARGO_ENV
fi

FZF_GIT="$DOTFILES_HOME/vendor/fzf-git.sh"
if [[ -f $FZF_GIT ]]; then
  source $FZF_GIT
fi

source "$(brew --prefix)/etc/profile.d/z.sh"
