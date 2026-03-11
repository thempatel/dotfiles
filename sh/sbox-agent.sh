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

# Prototools cache dir
[[ -d "$HOME/.proto" ]] && WRITE_PATHS+=(-w "$HOME/.proto")

# Go module cache (needed for go get/build/mod download)
GOMODCACHE="${GOMODCACHE:-${GOPATH:-$HOME/go}/pkg/mod}"
[[ -d "$GOMODCACHE" ]] && WRITE_PATHS+=(-w "$GOMODCACHE")

# Rust/Cargo cache
[[ -d "$HOME/.cargo" ]] && WRITE_PATHS+=(-w "$HOME/.cargo")

# Generic cache
[[ -d $HOME/.cache ]] && WRITE_PATHS+=(-w "$HOME/.cache")

# pnpm global store
[[ -d "$HOME/Library/pnpm" ]] && WRITE_PATHS+=(-w "$HOME/Library/pnpm")

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
