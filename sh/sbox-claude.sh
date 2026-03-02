#!/usr/bin/env bash
#
# Run Claude Code in a macOS sandbox using sbox (sandbox-exec wrapper).
# This uses the native macOS Seatbelt sandbox instead of containers.

set -e

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

# Claude config directory and state file.
# -W (prefix match) on the config dir so proper-lockfile's sibling
# lock file (~/.claude.lock) is also writable.
CLAUDE_CONFIG="${CLAUDE_CONFIG_DIR:-$HOME/.claude}"
mkdir -p "$CLAUDE_CONFIG"
WRITE_PATHS+=(-W "$CLAUDE_CONFIG")
WRITE_PATHS+=(-W "$HOME/.claude.json")

# Prototools cache dir
[[ -d "$HOME/.proto" ]] && WRITE_PATHS+=(-w "$HOME/.proto")

# Go module cache (needed for go get/build/mod download)
GOMODCACHE="${GOMODCACHE:-${GOPATH:-$HOME/go}/pkg/mod}"
[[ -d "$GOMODCACHE" ]] && WRITE_PATHS+=(-w "$GOMODCACHE")

# Rust/Cargo cache
[[ -d "$HOME/.cargo" ]] && WRITE_PATHS+=(-w "$HOME/.cargo")

# Generic cache
[[ -d $HOME/.cache ]] && WRITE_PATHS+=(-w "$HOME/.cache")

exec \
  sbox \
  "${WRITE_PATHS[@]}" \
  "${DENY_PATHS[@]}" \
  --allow-keychain \
  -- \
  claude --dangerously-skip-permissions "$@"
