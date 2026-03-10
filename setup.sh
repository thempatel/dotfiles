#!/usr/bin/env bash

set -e

THIS_DIR="$(realpath $(dirname "$0"))"
PROJECT_HOME="${PROJECT_HOME:-"$THIS_DIR"}"

cd "$PROJECT_HOME"

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

if ! command -v aqua &> /dev/null; then
  curl -sSfL https://raw.githubusercontent.com/aquaproj/aqua-installer/v4.0.2/aqua-installer | bash
fi

brew bundle --file brew/Brewfile
aqua i
deno install
pre-commit install

for setup in setup/*; do
  echo "> $setup"
  $setup
done

export DOTFILES_HOME=$PROJECT_HOME
$DOTFILES_HOME/bin/stow!
