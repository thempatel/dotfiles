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

if [[ -z "${CODE_ROOT:-}" ]]; then
  echo "sbox-agent: CODE_ROOT must be set in the environment" >&2
  exit 1
fi

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

# All of $HOME is writable; the sandbox exists to protect the OS, not home.
WRITE_PATHS=(-w "$HOME")

# Read-only paths under $HOME that run code outside the sandbox later (at
# login, in every new shell) or hold credentials.
READ_ONLY_PATHS=(
  "$HOME/Library/LaunchAgents"
  "$HOME/.zshrc"
  "$HOME/.zshenv"
  "$HOME/.zprofile"
  "$HOME/.bashrc"
  "$HOME/.profile"
  "$HOME/.ssh"
  "$HOME/.ssh/config"
)

# Seatbelt checks writes through a symlink against its target, so deny the
# target too, unless it lives in the repo the agent was opened in: an agent
# working in dotfiles can edit zsh/dot-zshrc, one working elsewhere can't.
REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null)" || true
DENY_WRITE_PATHS=()
for p in "${READ_ONLY_PATHS[@]}"; do
  DENY_WRITE_PATHS+=(-D "$p")
  [[ -L "$p" ]] || continue
  target="$(realpath "$p")"
  [[ -n "$REPO_ROOT" && "$target" == "$REPO_ROOT"/* ]] && continue
  DENY_WRITE_PATHS+=(-D "$target")
done

# Agent-specific args
AGENT_ARGS=()
case "$AGENT" in
  claude)
    AGENT_ARGS=(--dangerously-skip-permissions)

    CC_TOOLSHED="$CODE_ROOT/cc-toolshed"
    [[ -d "$CC_TOOLSHED" ]] && AGENT_ARGS+=(--plugin-dir "$CC_TOOLSHED")
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
  "${DENY_WRITE_PATHS[@]}" \
  "${EXTRA_ARGS[@]}" \
  --allow-keychain \
  -- \
  "$AGENT" "${AGENT_ARGS[@]}" "$@"
