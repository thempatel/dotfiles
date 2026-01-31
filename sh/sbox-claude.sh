#!/usr/bin/env bash
#
# Run Claude Code in a macOS sandbox using sbox (sandbox-exec wrapper).
#
# Usage:
#   sbox-claude.sh [options] [-- claude args...]
#
# Options:
#   --test    Test mode: show policy and run a dummy command instead of claude

set -e

# Parse arguments
TEST_MODE=false
while [[ $# -gt 0 ]]; do
    case "$1" in
        --test)
            TEST_MODE=true
            shift
            ;;
        --)
            shift
            break
            ;;
        *)
            break
            ;;
    esac
done

# Pre-compute paths to avoid issues with command substitution in heredocs
CWD="$(pwd)"
CLAUDE_CONFIG="${CLAUDE_CONFIG_DIR:-$HOME/.claude}"
mkdir -p "$CLAUDE_CONFIG"

# Go module cache (needed for go get/build/mod download)
GOMODCACHE="${GOMODCACHE:-${GOPATH:-$HOME/go}/pkg/mod}"

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

# Export SSH environment variables for Claude to use this key
export GIT_SSH_COMMAND="ssh -i $CLAUDE_SSH_KEY -o IdentitiesOnly=yes -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null"
export IS_SANDBOX=1

# Build policy file
# Note: trailing / forces subpath (directory) even if path doesn't exist
POLICY=$(cat <<EOF
# Allow writes to the current working directory
++$CWD/

# Claude config directory and state files
++$CLAUDE_CONFIG/
++$HOME/.claude.json
++$HOME/.claude.lock
++~^$HOME/.claude.json.*
++$HOME/.local/share/claude/
++$HOME/.local/state/claude/

# Common development paths (may not exist yet, so force subpath with /)
++$CWD/.venv/
++$CWD/node_modules/

# Go module cache
++$GOMODCACHE/

# Rust/Cargo cache
++$HOME/.cargo/

# Deny access to sensitive paths (but allow Claude's SSH key)
-$HOME/.ssh/
+$CLAUDE_SSH_KEY
+${CLAUDE_SSH_KEY}.pub
-$HOME/.gnupg/
-$HOME/.aws/
EOF
)

if [[ "$TEST_MODE" == true ]]; then
    echo "=== Test Mode ==="
    echo ""
    echo "Policy file contents:"
    echo "---------------------"
    echo "$POLICY"
    echo "---------------------"
    echo ""
    echo "Verifying policy with sbox --debug..."
    echo ""
    sbox --debug -f <(echo "$POLICY") -- echo "Sandbox OK: can execute commands"
else
    exec sbox -f <(echo "$POLICY") -- claude --dangerously-skip-permissions "$@"
fi
