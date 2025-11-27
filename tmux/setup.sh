#!/usr/bin/env bash
set -e

TARGET="$HOME/.tmux/plugins/tpm"

if [[ ! -d $TARGET ]]; then
  git clone https://github.com/tmux-plugins/tpm $TARGET
elif ! git -C $TARGET rev-parse --is-inside-work-tree &> /dev/null; then
  echo "$TARGET exists but is not git repo"
  exit 1
fi
