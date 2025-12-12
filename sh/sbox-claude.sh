#!/usr/bin/env bash

HOST_CONFIG="$HOME/.config/claude-container"
mkdir -p "$HOST_CONFIG"

podman run -it --rm \
    -v "$(pwd):/workspace" \
    -v "$HOST_CONFIG:/root/.claude" \
    -v "$DOTFILES_HOME:/src/dotfiles" \
    -v "$DOTFILES_HOME/sbox/start.sh:/usr/local/bin/start" \
    -v "$DOTFILES_HOME/sbox/bashrc.sh:/root/.bashrc" \
    -v "$DOTFILES_HOME/git:/root/.config/git" \
    -e "CLAUDE_CONFIG_DIR=/root/.claude" \
    -w /workspace \
    node:20 \
    bash
