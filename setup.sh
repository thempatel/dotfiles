#!/usr/bin/env bash

set -e
export PATH="$HOME/.local/bin:$PATH"

THIS_DIR="$(realpath $(dirname "$0"))"
export DOTFILES_HOME="$THIS_DIR"
export MISE_GLOBAL_CONFIG_ROOT="$DOTFILES_HOME"
export MISE_GLOBAL_CONFIG_FILE="$MISE_GLOBAL_CONFIG_ROOT/mise.toml"
export MISE_TRUSTED_CONFIG_PATHS="$MISE_GLOBAL_CONFIG_FILE"

cd "$DOTFILES_HOME"

if ! which brew > /dev/null; then
  /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

  if [[ -d /opt/homebrew/bin/ ]]; then
    prefix=/opt/homebrew
  elif [[ -d /usr/local/Homebrew ]]; then
    prefix=/usr/local
  fi

  profile_str="$prefix/bin/brew shellenv"
  echo "eval \"\$($profile_str)\"" >> $HOME/.zprofile

  output=$($profile_str)
  eval "$output"
fi

if ! command -v mise &> /dev/null; then
  curl https://mise.run | MISE_VERSION=v2026.3.12 sh
fi
eval "$(mise activate bash)"


brew bundle --file brew/Brewfile
mise i
deno install
pre-commit install

for setup in setup/*; do
  echo "> $setup"
  $setup
done


$DOTFILES_HOME/bin/stow! -yc ./stow.yaml
