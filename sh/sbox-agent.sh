#!/usr/bin/env bash
#
# Run a coding agent in a macOS sandbox using sbox (sandbox-exec wrapper).
# This uses the native macOS Seatbelt sandbox instead of containers.
#
# Usage: sbox-agent [-d deny_path]... [agent] [agent-args...]
#   -d path: deny read/write access to path (repeatable)
#   agent: claude (default), codex, etc.

set -e

DENY_PATHS=()
while getopts "d:" opt; do
  case "$opt" in
    d) DENY_PATHS+=(-d "$OPTARG") ;;
    *) echo "Usage: sbox-agent [-d deny_path]... [agent] [agent-args...]" >&2; exit 1 ;;
  esac
done
shift $((OPTIND - 1))

AGENT="${1:-claude}"
shift 2>/dev/null || true

# Allow writes to the current working directory
WRITE_PATHS=(-w "$(pwd)")

# If inside a git worktree, the real .git metadata (index, refs, objects)
# lives in the main repo's .git/worktrees/<name>/ directory, which is
# outside $(pwd). Allow writes there too so git stash/commit/etc. work.
GIT_COMMON_DIR="$(git rev-parse --git-common-dir 2>/dev/null)" || true
GIT_DIR="$(git rev-parse --git-dir 2>/dev/null)" || true
if [[ -n "$GIT_DIR" && -n "$GIT_COMMON_DIR" && "$GIT_DIR" != "$GIT_COMMON_DIR" ]]; then
    WRITE_PATHS+=(-w "$GIT_DIR")
    WRITE_PATHS+=(-w "$GIT_COMMON_DIR")
fi

# Optional writable paths (tool caches, package stores, etc.)
OPTIONAL_WRITE_PATHS=(
  "$HOME/.proto"                                    # Prototools
  "${GOMODCACHE:-${GOPATH:-$HOME/go}/pkg/mod}"      # Go module cache
  "$HOME/.cargo"                                    # Rust/Cargo
  "$HOME/.cache"                                    # Generic cache
  "$HOME/Library/pnpm"                              # pnpm global store
  "$HOME/.local/share"                              # XDG data
)
for p in "${OPTIONAL_WRITE_PATHS[@]}"; do
  [[ -d "$p" ]] && WRITE_PATHS+=(-w "$p")
done

# Config directories for agents that may be invoked (directly or as subprocesses).
# Claude can spawn codex, so both need write access regardless of which agent is primary.
CLAUDE_CONFIG="${CLAUDE_CONFIG_DIR:-$HOME/.claude}"
mkdir -p "$CLAUDE_CONFIG"
WRITE_PATHS+=(-W "$CLAUDE_CONFIG")
WRITE_PATHS+=(-W "$HOME/.claude.json")

CODEX_CONFIG="$HOME/.codex"
mkdir -p "$CODEX_CONFIG"
WRITE_PATHS+=(-w "$CODEX_CONFIG")

# Agent-specific args
AGENT_ARGS=()
case "$AGENT" in
  claude)
    AGENT_ARGS=(--dangerously-skip-permissions)
    ;;
  codex)
    # Disable codex's inner Seatbelt sandbox — nested sandbox-exec is not
    # allowed by macOS, and our outer sbox already provides isolation.
    AGENT_ARGS=(--dangerously-bypass-approvals-and-sandbox)
    ;;
esac

export IS_SBOX=1

exec \
  sbox \
  "${WRITE_PATHS[@]}" \
  "${DENY_PATHS[@]}" \
  --allow-keychain \
  -- \
  "$AGENT" "${AGENT_ARGS[@]}" "$@"
