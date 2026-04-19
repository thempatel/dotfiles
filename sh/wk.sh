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
  selected=$(ls -1 "$CODE_ROOT" | fzf --prompt="project> " --height=40% --reverse) || return 130
  [[ -n "$selected" ]] || return 130
  echo "$CODE_ROOT/$selected"
}

# Get the default branch (main/master) for a repo
default_branch() {
  local repo_path="$1"
  git -C "$repo_path" symbolic-ref refs/remotes/origin/HEAD 2>/dev/null | sed 's@^refs/remotes/origin/@@' \
    || git -C "$repo_path" rev-parse --abbrev-ref HEAD
}

# Resolve the best start point for a new branch.
default_start_point() {
  local repo_path="$1"
  local default
  default=$(default_branch "$repo_path")

  if git -C "$repo_path" show-ref --verify --quiet "refs/remotes/origin/$default" 2>/dev/null; then
    echo "origin/$default"
  else
    echo "$default"
  fi
}

# Keep the default branch fresh when we need to branch from it.
refresh_default_branch() {
  local repo_path="$1"
  local default
  default=$(default_branch "$repo_path")

  if git -C "$repo_path" show-ref --verify --quiet "refs/remotes/origin/$default" 2>/dev/null; then
    git -C "$repo_path" fetch origin "$default"
  fi
}

# Print branch candidates for fzf.
# Local branches are listed first; remote branches are only included when
# there is no local branch with the same short name.
list_branch_candidates() {
  local repo_path="$1"
  local remote_branch_refs
  remote_branch_refs=$(
    git -C "$repo_path" branch -r --sort=-committerdate --format='%(refname:short)' |
      sed '/HEAD ->/d' |
      head -n 100
  )
  local remote_only_branch_names
  remote_only_branch_names=$'\n'"$(
    comm -13 \
      <(git -C "$repo_path" branch --format='%(refname:short)' | sort) \
      <(printf '%s\n' "$remote_branch_refs" | sed 's#^[^/]*/##' | sort -u)
  )"$'\n'

  while IFS= read -r branch_name; do
    [[ -n "$branch_name" ]] || continue
    printf '%s\t%s\n' "$branch_name" "$branch_name"
  done < <(
    git -C "$repo_path" branch --sort=-committerdate --sort=-HEAD --format='%(refname:short)'
  )

  while IFS= read -r remote_ref; do
    [[ -n "$remote_ref" ]] || continue

    local branch_name="${remote_ref#*/}"
    [[ "$remote_only_branch_names" == *$'\n'"$branch_name"$'\n'* ]] || continue

    printf '%s\t%s\n' "$branch_name" "$remote_ref"
  done <<< "$remote_branch_refs"
}

resolve_remote_branch_ref() {
  local repo_path="$1"
  local branch_name="$2"

  if git -C "$repo_path" show-ref --verify --quiet "refs/remotes/origin/$branch_name" 2>/dev/null; then
    echo "origin/$branch_name"
    return 0
  fi

  local matches=()
  while IFS= read -r remote_ref; do
    [[ -n "$remote_ref" ]] || continue
    [[ "$remote_ref" == */HEAD ]] && continue
    [[ "${remote_ref#*/}" == "$branch_name" ]] || continue
    matches+=("$remote_ref")
  done < <(git -C "$repo_path" for-each-ref refs/remotes --format='%(refname:short)')

  if (( ${#matches[@]} == 1 )); then
    echo "${matches[0]}"
    return 0
  fi

  return 1
}

# Find an existing worktree that already has the given branch checked out.
find_worktree_for_branch() {
  local repo_path="$1"
  local branch_name="$2"

  git -C "$repo_path" worktree list --porcelain | awk -v branch="refs/heads/$branch_name" '
    /^worktree / { wt = substr($0, 10) }
    /^branch / && $2 == branch { print wt; exit }
  '
}

# Check if a worktree directory is free for reuse.
# Free means: no tmux session, clean working tree, and either detached HEAD,
# branch merged into default, or branch gone from remote.
is_worktree_free() {
  local wt_dir="$1"
  local repo_path="$2"

  # Active tmux session using this directory — never reuse
  if tmux list-sessions -F '#{session_path}' 2>/dev/null | grep -qx "$wt_dir"; then
    return 1
  fi

  # Don't reuse a dirty worktree in place.
  if [[ -n "$(git -C "$wt_dir" status --porcelain 2>/dev/null)" ]]; then
    return 1
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

reuse_worktree() {
  local wt_dir="$1"
  local repo_path="$2"
  local branch_name="$3"
  local branch_source="$4"

  if git -C "$repo_path" show-ref --verify --quiet "refs/heads/$branch_name" 2>/dev/null; then
    git -C "$wt_dir" switch "$branch_name"
  elif [[ -n "$branch_source" ]]; then
    git -C "$wt_dir" switch -c "$branch_name" "$branch_source"
    git -C "$wt_dir" branch --set-upstream-to "$branch_source" "$branch_name"
  else
    local start_point
    refresh_default_branch "$repo_path"
    start_point=$(default_start_point "$repo_path")
    git -C "$wt_dir" switch --detach "$start_point"
    git -C "$wt_dir" switch -c "$branch_name"
  fi
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
  REPO_PATH=$(pick_project) || exit 0
fi

# Validate it's a git repo
if ! git -C "$REPO_PATH" rev-parse --git-dir &>/dev/null; then
  echo "Error: $REPO_PATH is not a git repository" >&2
  exit 1
fi

# Clean up stale worktree entries (directories deleted outside of git)
git -C "$REPO_PATH" worktree prune

REPO_NAME=$(basename "$REPO_PATH")

# Pick an existing branch or type a new one.
# The query is the source of truth; Tab copies the highlighted branch into it.
BRANCH_CANDIDATES=$(list_branch_candidates "$REPO_PATH")

FZF_OUTPUT=$(
  printf '%s\n' "$BRANCH_CANDIDATES" |
  fzf --prompt="branch> " --height=40% --reverse \
    --border-label ' Branches ' \
    --header $'Enter: use input  Tab: copy highlighted branch\nType to filter existing branches or enter a new branch name' \
    --delimiter=$'\t' --with-nth=1 \
    --bind "tab:transform-query:[[ -n {} ]] && printf %s {1} || printf %s \"\$FZF_QUERY\"" \
    --expect=enter \
    --print-query
)
FZF_STATUS=$?

if [[ $FZF_STATUS -ne 0 ]]; then
  if [[ $FZF_STATUS -eq 130 ]]; then
    exit 0
  fi

  echo "Error: fzf exited with status $FZF_STATUS" >&2
  exit "$FZF_STATUS"
fi

FZF_QUERY=""
FZF_KEY=""
FZF_SELECTION=""
{
  IFS= read -r FZF_QUERY
  IFS= read -r FZF_KEY
  IFS= read -r FZF_SELECTION
} <<< "$FZF_OUTPUT"

if [[ "$FZF_KEY" != "enter" && -z "$FZF_SELECTION" ]]; then
  FZF_SELECTION="$FZF_KEY"
  FZF_KEY=""
fi

if [[ -n "$FZF_SELECTION" ]]; then
  IFS=$'\t' read -r BRANCH_NAME BRANCH_SOURCE <<< "$FZF_SELECTION"
else
  BRANCH_NAME="$FZF_QUERY"
  BRANCH_SOURCE=""
fi

if [[ -z "$BRANCH_NAME" ]]; then
  echo "Error: branch name required" >&2
  exit 1
fi

if [[ -z "$BRANCH_SOURCE" ]] \
  && ! git -C "$REPO_PATH" show-ref --verify --quiet "refs/heads/$BRANCH_NAME" 2>/dev/null; then
  BRANCH_SOURCE=$(resolve_remote_branch_ref "$REPO_PATH" "$BRANCH_NAME" || true)
fi

# If the branch is already checked out in an existing worktree, use it.
# Otherwise find a reusable worktree or allocate a new one.
mkdir -p "$WORKTREE_ROOT"
WORKTREE_DIR=$(find_worktree_for_branch "$REPO_PATH" "$BRANCH_NAME")

if [[ -n "$WORKTREE_DIR" ]]; then
  :
else
  REUSE=false
  WORKTREE_DIR=$(find_worktree_dir "$REPO_NAME" "$REPO_PATH") && REUSE=true

  # Reuse in place when possible; otherwise create a new worktree.
  if $REUSE; then
    reuse_worktree "$WORKTREE_DIR" "$REPO_PATH" "$BRANCH_NAME" "$BRANCH_SOURCE"
  elif git -C "$REPO_PATH" show-ref --verify --quiet "refs/heads/$BRANCH_NAME" 2>/dev/null; then
    git -C "$REPO_PATH" worktree add "$WORKTREE_DIR" "$BRANCH_NAME"
  elif [[ -n "$BRANCH_SOURCE" ]]; then
    git -C "$REPO_PATH" worktree add -b "$BRANCH_NAME" "$WORKTREE_DIR" "$BRANCH_SOURCE"
    git -C "$WORKTREE_DIR" branch --set-upstream-to "$BRANCH_SOURCE" "$BRANCH_NAME"
  else
    BASE=$(default_start_point "$REPO_PATH")
    refresh_default_branch "$REPO_PATH"
    BASE=$(default_start_point "$REPO_PATH")
    git -C "$REPO_PATH" worktree add -b "$BRANCH_NAME" "$WORKTREE_DIR" "$BASE"
  fi
fi

# Allow direnv if the worktree has an .envrc
if [[ -f "$WORKTREE_DIR/.envrc" ]]; then
  direnv allow "$WORKTREE_DIR/.envrc"
fi

# Connect via sesh (wildcard config handles window layout)
sesh connect "$WORKTREE_DIR"
