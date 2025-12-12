#!/usr/bin/env bash
#

set -e

HOST_CC_CONFIG="$HOME/.config/claude-container"
LOCAL_CC_CONFIG="/root/.claude"
LOCAL_CONFIG="/root/.config"

mkdir -p "$HOST_CC_CONFIG"

podman run -it --rm \
    -v "$(pwd):/workspace" \
    -v "$HOST_CC_CONFIG:/root/.claude" \
    -v "$DOTFILES_HOME/sbox/start.sh:/usr/local/bin/start" \
    -v "$DOTFILES_HOME/sbox/bashrc.sh:/root/.bashrc" \
    -v "$DOTFILES_HOME/git:$LOCAL_CONFIG/git" \
    -v "$DOTFILES_HOME/claude/commands:$LOCAL_CC_CONFIG/commands" \
    -v "$DOTFILES_HOME/claude/skills:$LOCAL_CC_CONFIG/skills" \
    -e "CLAUDE_CONFIG_DIR=/root/.claude" \
    -w /workspace \
    node:20 \
    bash
