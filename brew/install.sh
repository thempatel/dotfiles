#!/usr/bin/env bash

if [[ -z $DOTFILES_HOME ]]; then
  echo "DOTFILES_HOME unset"
  exit 1
fi

cd $DOTFILES_HOME/brew

brew bundle --file ./Brewfile
arch=$(uname -m)

if [[ -f ./Brewfile.${arch} ]]; then
  brew bundle --file ./Brewfile.${arch}
fi
