#!/usr/bin/env bash
#

set -e

IMAGE_NAME="sbox"

HOST_CC_CONFIG="$HOME/.config/claude-container"
LOCAL_CC_CONFIG="/root/.claude"
LOCAL_CONFIG="/root/.config"

"$DOTFILES_HOME/sbox/build.sh"

mkdir -p "$HOST_CC_CONFIG"

podman run -it --rm \
    -v "$(pwd):/workspace" \
    -v "/workspace/.venv" \
    -v "$HOST_CC_CONFIG:/root/.claude" \
    -v "$DOTFILES_HOME/git:$LOCAL_CONFIG/git" \
    -v "$DOTFILES_HOME/claude/commands:$LOCAL_CC_CONFIG/commands" \
    -v "$DOTFILES_HOME/claude/skills:$LOCAL_CC_CONFIG/skills" \
    -e "CLAUDE_CONFIG_DIR=/root/.claude" \
    -w /workspace \
    "$IMAGE_NAME" \
    bash
