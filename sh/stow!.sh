#!/usr/bin/env bash

set -e

if [[ -z $DOTFILES_HOME ]]; then
  echo "DOTFILES_HOME unset"
  exit 1
fi

if ! which dev-deno > /dev/null; then
  export PATH="${PATH}:${DOTFILES_HOME}/bin"
fi

$DOTFILES_HOME/ts/stow.ts "$@"
