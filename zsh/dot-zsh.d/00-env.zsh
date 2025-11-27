ssh-add --apple-use-keychain "$HOME/.ssh/id_ed25519"

# Deduplicate $PATH entries
typeset -U PATH path

SCRIPT_PATH="${(%):-%x}"
SCRIPT_DIR="${SCRIPT_PATH:A:h}"

export DOTFILES_HOME="${SCRIPT_DIR:h:h}"
export GPG_TTY=$(tty)
export RIPGREP_CONFIG_PATH="$HOME/.config/ripgrep/config"
export FZF_DEFAULT_OPTS='--bind ctrl-f:page-down,ctrl-b:page-up'

path+=("$DOTFILES_HOME/bin" "$HOME/.local/bin")

CARGO_ENV="$HOME/.cargo/env"
if [[ -f $CARGO_ENV ]]; then
  source $CARGO_ENV
fi
