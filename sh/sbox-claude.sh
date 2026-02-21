#!/usr/bin/env bash

set -e

# OS-specific dependency directories to mask with empty volumes
BARE_DIR_NAMES=(node_modules .venv __pycache__ .pnpm-store)

# Build -name args for find
FIND_ARGS=()
for i in "${!BARE_DIR_NAMES[@]}"; do
  [[ $i -gt 0 ]] && FIND_ARGS+=(-o)
  FIND_ARGS+=(-name "${BARE_DIR_NAMES[$i]}")
done

# Find matching directories at top level only
BARE_MOUNTS=()
while IFS= read -r dir; do
  BARE_MOUNTS+=("$dir")
done < <(find "$(pwd -P)" -maxdepth 1 -type d \( "${FIND_ARGS[@]}" \) | sed "s|^$(pwd -P)/||")

IMAGE_NAME="sbox"
CONTAINER_NAME="sbox-$$"

# Host paths
HOST_CLAUDE_CONFIG="$HOME/.config/claude-container"

# Container paths
CTR_HOME="/home/claude"
CTR_CLAUDE_CONFIG="$CTR_HOME/.claude"
CTR_CONFIG="$CTR_HOME/.config"

# Ensure container system is running
if ! container system status >/dev/null 2>&1; then
  container system start
fi

# Check if image exists, build if not
if ! container image inspect "$IMAGE_NAME" >/dev/null 2>&1; then
  QUIET=1 "$DOTFILES_HOME/sbox/build.sh"
fi

mkdir -p "$HOST_CLAUDE_CONFIG"

# Ensure a named volume exists, creating it if needed. Echoes the volume name.
ensure_volume() {
  local cwd_slug dir_slug vol_name
  cwd_slug="$(pwd -P | tr '/' '-' | sed 's/^-//')"
  dir_slug="${1//\//-}"
  vol_name="sbox-bare-${cwd_slug}-${dir_slug}"
  if ! container volume inspect "$vol_name" >/dev/null 2>&1; then
    container volume create "$vol_name" >/dev/null
  fi
  echo "$vol_name"
}

# Build mount args for bare directories
BARE_VOLUME_ARGS=()
for dir in "${BARE_MOUNTS[@]}"; do
  dir="${dir#/}"  # strip leading slash if present
  vol_name="$(ensure_volume "$dir")"
  BARE_VOLUME_ARGS+=(--mount "type=volume,source=$vol_name,target=/workspace/$dir")
done

# Start container in detached mode
container run -d --rm \
    --name "$CONTAINER_NAME" \
    --memory 6G \
    -v "$(pwd -P):/workspace" \
    -v "$HOST_CLAUDE_CONFIG:$CTR_CLAUDE_CONFIG" \
    -v "$DOTFILES_HOME/sbox/scripts:/opt/sbox-scripts" \
    "${BARE_VOLUME_ARGS[@]}" \
    -w /workspace \
    "$IMAGE_NAME" \
    sleep infinity >/dev/null

# Cleanup on exit
trap "container stop $CONTAINER_NAME >/dev/null 2>&1 &" EXIT

# Rsync into container, resolving symlinks
sync_to_container() {
  echo "  $1 -> $2"
  rsync -aL --blocking-io -e "container exec -i" "$1" "$CONTAINER_NAME:$2"
}

sync_to_container "$DOTFILES_HOME/sbox/bashrc.sh" "$CTR_HOME/.bashrc"
sync_to_container "$HOME/.config/git/" "$CTR_HOME/.config/git/"
sync_to_container "$HOME/.claude/commands/" "$CTR_CLAUDE_CONFIG/commands/"
sync_to_container "$HOME/.claude/skills/" "$CTR_CLAUDE_CONFIG/skills/"

# Attach to container
container exec -it -w /workspace "$CONTAINER_NAME" /bin/bash
