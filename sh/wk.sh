#!/usr/bin/env bash
set -e

CODE_ROOT="${CODE_ROOT:-$HOME/src}"
WORKTREE_ROOT="$CODE_ROOT/worktrees"

usage() {
  echo "Usage: wk [--tmux] [<repo-path>]"
  echo "  No args:    fzf picker of projects in \$CODE_ROOT"
  echo "  <repo-path>: skip picker, use this repo directly"
  echo "  --tmux:     run inside tmux display-popup"
  exit 1
}

# Pick a project via fzf (basenames from CODE_ROOT, non-recursive)
pick_project() {
  local selected
  selected=$(ls -1 "$CODE_ROOT" | fzf --prompt="project> " --height=40% --reverse) || exit 0
  [[ -n "$selected" ]] || exit 0
  echo "$CODE_ROOT/$selected"
}

# Get the default branch (main/master) for a repo
default_branch() {
  local repo_path="$1"
  git -C "$repo_path" symbolic-ref refs/remotes/origin/HEAD 2>/dev/null | sed 's@^refs/remotes/origin/@@' \
    || git -C "$repo_path" rev-parse --abbrev-ref HEAD
}

# Check if a worktree directory is free for reuse.
# Free if: detached HEAD, branch merged into default, branch gone from remote,
# or no active tmux session for the directory.
is_worktree_free() {
  local wt_dir="$1"
  local repo_path="$2"

  # No active tmux session using this directory
  if ! tmux list-sessions -F '#{session_path}' 2>/dev/null | grep -qx "$wt_dir"; then
    return 0
  fi

  # Detached HEAD
  if [[ "$(git -C "$wt_dir" rev-parse --abbrev-ref HEAD 2>/dev/null)" == "HEAD" ]]; then
    return 0
  fi

  local branch
  branch=$(git -C "$wt_dir" rev-parse --abbrev-ref HEAD 2>/dev/null) || return 0

  # Branch doesn't exist on remote
  if ! git -C "$repo_path" show-ref --verify --quiet "refs/remotes/origin/$branch" 2>/dev/null; then
    return 0
  fi

  # Branch has been merged into default branch
  local default
  default=$(default_branch "$repo_path")
  if git -C "$repo_path" merge-base --is-ancestor "refs/heads/$branch" "refs/heads/$default" 2>/dev/null; then
    return 0
  fi

  return 1
}

# Find a reusable worktree or the next wk-N suffix for a repo
find_worktree_dir() {
  local repo_name="$1"
  local repo_path="$2"
  local max=0

  if [[ -d "$WORKTREE_ROOT" ]]; then
    for dir in "$WORKTREE_ROOT"/"${repo_name}"-wk-*; do
      [[ -d "$dir" ]] || continue
      local n="${dir##*-wk-}"
      [[ "$n" =~ ^[0-9]+$ ]] || continue
      (( n > max )) && max=$n

      if is_worktree_free "$dir" "$repo_path"; then
        echo "$dir"
        return 0
      fi
    done
  fi

  echo "$WORKTREE_ROOT/${repo_name}-wk-$(( max + 1 ))"
  return 1
}

# Parse args
TMUX_MODE=false
REPO_PATH=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --tmux) TMUX_MODE=true; shift ;;
    -h|--help) usage ;;
    *) REPO_PATH="$1"; shift ;;
  esac
done

# Select project
if [[ -z "$REPO_PATH" ]]; then
  REPO_PATH=$(pick_project)
fi

# Validate it's a git repo
if ! git -C "$REPO_PATH" rev-parse --git-dir &>/dev/null; then
  echo "Error: $REPO_PATH is not a git repository" >&2
  exit 1
fi

# Clean up stale worktree entries (directories deleted outside of git)
git -C "$REPO_PATH" worktree prune

REPO_NAME=$(basename "$REPO_PATH")

# Prompt for branch name
printf "branch name> "
read -r BRANCH_NAME
if [[ -z "$BRANCH_NAME" ]]; then
  echo "Error: branch name required" >&2
  exit 1
fi

# Find a reusable worktree or allocate a new one
mkdir -p "$WORKTREE_ROOT"
REUSE=false
WORKTREE_DIR=$(find_worktree_dir "$REPO_NAME" "$REPO_PATH") && REUSE=true

# If reusing, remove the old worktree first
if $REUSE; then
  git -C "$REPO_PATH" worktree remove --force "$WORKTREE_DIR" 2>/dev/null || rm -rf "$WORKTREE_DIR"
fi

# Create worktree: auto-detect if branch exists
if git -C "$REPO_PATH" show-ref --verify --quiet "refs/heads/$BRANCH_NAME" 2>/dev/null; then
  git -C "$REPO_PATH" worktree add "$WORKTREE_DIR" "$BRANCH_NAME"
elif git -C "$REPO_PATH" show-ref --verify --quiet "refs/remotes/origin/$BRANCH_NAME" 2>/dev/null; then
  git -C "$REPO_PATH" worktree add "$WORKTREE_DIR" "$BRANCH_NAME"
else
  BASE=$(default_branch "$REPO_PATH")
  git -C "$REPO_PATH" worktree add -b "$BRANCH_NAME" "$WORKTREE_DIR" "$BASE"
fi

# Allow direnv if the worktree has an .envrc
if [[ -f "$WORKTREE_DIR/.envrc" ]]; then
  direnv allow "$WORKTREE_DIR/.envrc"
fi

# Connect via sesh (wildcard config handles window layout)
sesh connect "$WORKTREE_DIR"
