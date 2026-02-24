#!/usr/bin/env bash
#
# Run Claude Code in a macOS sandbox using sbox (sandbox-exec wrapper).
# This uses the native macOS Seatbelt sandbox instead of containers.

set -e

# Allow writes to the current working directory
WRITE_PATHS=(-w "$(pwd)")

# Claude config directory and state file
CLAUDE_CONFIG="${CLAUDE_CONFIG_DIR:-$HOME/.claude}"
mkdir -p "$CLAUDE_CONFIG"
WRITE_PATHS+=(-w "$CLAUDE_CONFIG")
WRITE_PATHS+=(-w "$HOME/.claude.json")

# Allow writes to common development paths if they exist
[[ -d ".venv" ]] && WRITE_PATHS+=(-w "$(pwd)/.venv")
[[ -d "node_modules" ]] && WRITE_PATHS+=(-w "$(pwd)/node_modules")

# Go module cache (needed for go get/build/mod download)
GOMODCACHE="${GOMODCACHE:-${GOPATH:-$HOME/go}/pkg/mod}"
[[ -d "$GOMODCACHE" ]] && WRITE_PATHS+=(-w "$GOMODCACHE")

# Rust/Cargo cache
[[ -d "$HOME/.cargo" ]] && WRITE_PATHS+=(-w "$HOME/.cargo")

# Set up dedicated SSH key for Claude
CLAUDE_SSH_KEY="$HOME/.ssh/claude_ecdsa"
if [[ ! -f "$CLAUDE_SSH_KEY" ]]; then
    echo "Creating dedicated SSH key for Claude at $CLAUDE_SSH_KEY"
    ssh-keygen -t ecdsa -f "$CLAUDE_SSH_KEY" -N "" -C "claude@$(hostname)"
    echo ""
    echo "Add this public key to your Git hosting service:"
    cat "${CLAUDE_SSH_KEY}.pub"
    echo ""
fi

# Deny access to sensitive paths
DENY_PATHS=(
    --deny "$HOME/.ssh"
    --deny "$HOME/.gnupg"
    --deny "$HOME/.aws"
)

# Export SSH environment variables for Claude to use this key
export GIT_SSH_COMMAND="ssh -i $CLAUDE_SSH_KEY -o IdentitiesOnly=yes -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null"
export IS_SANDBOX=1

exec \
  sbox \
  "${WRITE_PATHS[@]}" \
  "${DENY_PATHS[@]}" \
  -- \
  claude --dangerously-skip-permissions "$@"
