#!/usr/bin/env bash
#

set -e

IMAGE_NAME="sbox"
HOST_CC_CONFIG="$HOME/.config/claude-container"
LOCAL_CC_CONFIG="/root/.claude"
LOCAL_CONFIG="/root/.config"

if ! docker image inspect "$IMAGE_NAME" >/dev/null 2>&1; then
  QUIET=1 "$DOTFILES_HOME/sbox/build.sh"
fi

mkdir -p "$HOST_CC_CONFIG"

XTRA_ARGS=""
if find .venv -mindepth 1 -maxdepth 1 2>/dev/null | read; then
  XTRA_ARGS='-v "/workspace/.venv"'
fi

CMD='bash -lc "start"'
if [[ -n "$NO_CLAUDE" ]]; then
  CMD="bash"
fi

podman run -it --rm \
    -v "$(pwd):/workspace" \
    -v "$HOST_CC_CONFIG:/root/.claude" \
    -v "$DOTFILES_HOME/git:$LOCAL_CONFIG/git" \
    -v "$DOTFILES_HOME/claude/commands:$LOCAL_CC_CONFIG/commands" \
    -v "$DOTFILES_HOME/claude/skills:$LOCAL_CC_CONFIG/skills" \
    $XTRA_ARGS \
    -e "CLAUDE_CONFIG_DIR=/root/.claude" \
    -w /workspace \
    "$IMAGE_NAME" \
    $CMD
