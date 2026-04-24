#!/usr/bin/env bash
#
# Run a coding agent in a macOS sandbox using sbox (sandbox-exec wrapper).
# This uses the native macOS Seatbelt sandbox instead of containers.
#
# Usage: sbox-agent [-w write_path] [-W write_prefix_path] [-d deny_path]... [--] [agent] [agent-args...]
#   -w path: allow write access to path (repeatable)
#   -W path: allow write access to path and any path sharing its prefix (repeatable)
#   -d path: deny read/write access to path (repeatable)
#   agent: claude (default), codex, etc.
#   Use -- before agent args that start with - to prevent them being parsed as sbox-agent flags.

set -e

EXTRA_ARGS=()
while getopts "w:W:d:" opt; do
  case "$opt" in
    w) EXTRA_ARGS+=(-w "$OPTARG") ;;
    W) EXTRA_ARGS+=(-W "$OPTARG") ;;
    d) EXTRA_ARGS+=(-d "$OPTARG") ;;
    *) echo "Usage: sbox-agent [-w write_path] [-W write_prefix_path] [-d deny_path]... [agent] [agent-args...]" >&2; exit 1 ;;
  esac
done
shift $((OPTIND - 1))

KNOWN_AGENTS="claude codex"
if [[ -n "$1" && " $KNOWN_AGENTS " == *" $1 "* ]]; then
  AGENT="$1"
  shift
else
  AGENT="claude"
fi

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
  "$HOME/.rustup"                                   # Rust/Cargo
  "$HOME/.cache"                                    # Generic cache
  "$HOME/Library/pnpm"                              # pnpm global store
  "$HOME/.local"                                    # XDG data
  "$HOME/.npm"                                      # npm cache
  "$HOME/.dbt"                                      # DBT Data
  "$HOME/go"                                        # Golang
)
for p in "${OPTIONAL_WRITE_PATHS[@]}"; do
  [[ -d "$p" ]] && WRITE_PATHS+=(-w "$p")
done

# Agent-specific args
AGENT_ARGS=()
case "$AGENT" in
  claude)
    # Claude can spawn codex, so both need write access.
    CLAUDE_CONFIG="${CLAUDE_CONFIG_DIR:-$HOME/.claude}"
    mkdir -p "$CLAUDE_CONFIG"
    WRITE_PATHS+=(-W "$CLAUDE_CONFIG")
    WRITE_PATHS+=(-W "$HOME/.claude.json")

    CODEX_CONFIG="$HOME/.codex"
    mkdir -p "$CODEX_CONFIG"
    WRITE_PATHS+=(-w "$CODEX_CONFIG")

    AGENT_ARGS=(--dangerously-skip-permissions)

    CC_TOOLSHED="${CODE_ROOT:-$HOME/src}/cc-toolshed"
    if [[ -d "$CC_TOOLSHED" ]]; then
      WRITE_PATHS+=(-w "$CC_TOOLSHED")
      AGENT_ARGS+=(--add-dir "$CC_TOOLSHED/memory" --plugin-dir "$CC_TOOLSHED")
      export CLAUDE_CODE_ADDITIONAL_DIRECTORIES_CLAUDE_MD=1
    fi
    ;;
  codex)
    CODEX_CONFIG="$HOME/.codex"
    mkdir -p "$CODEX_CONFIG"
    WRITE_PATHS+=(-w "$CODEX_CONFIG")
    WRITE_PATHS+=(-w "$HOME/.agents")

    # Disable codex's inner Seatbelt sandbox — nested sandbox-exec is not
    # allowed by macOS, and our outer sbox already provides isolation.
    AGENT_ARGS=(--dangerously-bypass-approvals-and-sandbox)
    ;;
esac

export IS_SBOX=1

exec \
  sbox \
  "${WRITE_PATHS[@]}" \
  "${EXTRA_ARGS[@]}" \
  --allow-keychain \
  -- \
  "$AGENT" "${AGENT_ARGS[@]}" "$@"
