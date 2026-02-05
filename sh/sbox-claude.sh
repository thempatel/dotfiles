#!/usr/bin/env bash
#

set -e

IMAGE_NAME="sbox"
CONTAINER_NAME="sbox-$$"

# Host paths
HOST_CLAUDE_CONFIG="$HOME/.config/claude-container"

# Container paths
CTR_HOME="/home/claude"
CTR_CLAUDE_CONFIG="$CTR_HOME/.claude"
CTR_CONFIG="$CTR_HOME/.config"

# Check if image exists, build if not
if ! container image inspect "$IMAGE_NAME" >/dev/null 2>&1; then
  QUIET=1 "$DOTFILES_HOME/sbox/build.sh"
fi

mkdir -p "$HOST_CLAUDE_CONFIG"

# Start container in detached mode
container run -d --rm \
    --name "$CONTAINER_NAME" \
    --memory 6G \
    -v "$(pwd -P):/workspace" \
    -v "$HOST_CLAUDE_CONFIG:$CTR_CLAUDE_CONFIG" \
    -w /workspace \
    "$IMAGE_NAME" \
    sleep infinity >/dev/null

# Cleanup on exit
trap "echo 'stopping $CONTAINER_NAME'; container stop $CONTAINER_NAME 2>/dev/null" EXIT

# Rsync into container, resolving symlinks
sync_to_container() {
  rsync -aL --blocking-io -e "container exec -i" "$1" "$CONTAINER_NAME:$2"
}

sync_to_container "$HOME/.config/git/" "$CTR_HOME/.config/git/"
sync_to_container "$HOME/.claude/commands/" "$CTR_CLAUDE_CONFIG/commands/"
sync_to_container "$HOME/.claude/skills/" "$CTR_CLAUDE_CONFIG/skills/"

# Attach to container
CMD='bash -ic "start"'
if [[ -n "$NO_CLAUDE" ]]; then
  CMD="bash"
fi

container exec -it -w /workspace "$CONTAINER_NAME" bash -c "$CMD"
