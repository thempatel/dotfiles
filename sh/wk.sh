#!/usr/bin/env bash
set -e

CODE_ROOT="${CODE_ROOT:-$HOME/src}"
WORKTREE_ROOT="$CODE_ROOT/worktrees"

# Sentinel branch name meaning "check out a detached worktree off latest main"
# rather than creating/switching to a branch. Emitted when the user hits enter
# on a blank branch prompt.
DETACHED_SENTINEL="__WK_DETACHED__"

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

is_worktree_free() {
  local wt_dir="$1"

  if tmux list-sessions -F '#{session_path}' 2>/dev/null | grep -qx "$wt_dir"; then
    return 1
  fi

  if [[ -n "$(git -C "$wt_dir" status --porcelain -uno 2>/dev/null)" ]]; then
    return 1
  fi

  return 0
}

# Find a reusable worktree or the next wk-N suffix for a repo
find_worktree_dir() {
  local repo_name="$1"
  local max=0

  if [[ -d "$WORKTREE_ROOT" ]]; then
    while IFS= read -r dir; do
      [[ -d "$dir" ]] || continue
      local n="${dir##*-wk-}"
      [[ "$n" =~ ^[0-9]+$ ]] || continue
      (( n > max )) && max=$n

      if is_worktree_free "$dir"; then
        echo "$dir"
        return 0
      fi
    done < <(printf '%s\n' "$WORKTREE_ROOT"/"${repo_name}"-wk-* | sort -V)
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

# Interactive branch picker. Prints "BRANCH_NAME\tBRANCH_SOURCE" to stdout.
pick_branch() {
  local repo_path="$1"
  local branch_candidates
  branch_candidates=$(list_branch_candidates "$repo_path")

  local fzf_status=0
  local fzf_output
  fzf_output=$(
    printf '%s\n' "$branch_candidates" |
    fzf --prompt="branch> " --height=40% --reverse \
      --border-label ' Branches ' \
      --header $'Enter: use input (blank = detached off main)  Tab: copy highlighted branch\nType to filter existing branches or enter a new branch name' \
      --delimiter=$'\t' --with-nth=1 \
      --bind "tab:transform-query:[[ -n {} ]] && printf %s {1} || printf %s \"\$FZF_QUERY\"" \
      --expect=enter \
      --print-query
  ) || fzf_status=$?

  if [[ $fzf_status -ne 0 && $fzf_status -ne 1 ]]; then
    return "$fzf_status"
  fi

  local fzf_query="" fzf_key="" fzf_selection=""
  {
    IFS= read -r fzf_query
    IFS= read -r fzf_key
    IFS= read -r fzf_selection
  } <<< "$fzf_output"

  if [[ "$fzf_key" != "enter" && -z "$fzf_selection" ]]; then
    fzf_selection="$fzf_key"
  fi

  local branch_name="" branch_source=""
  if [[ "$fzf_key" == "enter" ]]; then
    branch_name="$fzf_query"
  elif [[ -n "$fzf_selection" ]]; then
    IFS=$'\t' read -r branch_name branch_source <<< "$fzf_selection"
  else
    branch_name="$fzf_query"
  fi

  if [[ -z "$branch_name" ]]; then
    # Blank prompt: caller creates a detached worktree off latest main.
    printf '%s\t%s\n' "$DETACHED_SENTINEL" ""
    return 0
  fi

  if [[ -z "$branch_source" ]] \
    && ! git -C "$repo_path" show-ref --verify --quiet "refs/heads/$branch_name" 2>/dev/null; then
    branch_source=$(resolve_remote_branch_ref "$repo_path" "$branch_name" || true)
  fi

  printf '%s\t%s\n' "$branch_name" "$branch_source"
}

# Ensure a worktree exists for the given branch and print its path.
ensure_worktree() {
  local repo_path="$1"
  local branch_name="$2"
  local branch_source="$3"
  local repo_name
  repo_name=$(basename "$repo_path")

  mkdir -p "$WORKTREE_ROOT"
  local wt_dir
  wt_dir=$(find_worktree_for_branch "$repo_path" "$branch_name")

  if [[ -z "$wt_dir" ]]; then
    local reuse=false
    wt_dir=$(find_worktree_dir "$repo_name") && reuse=true

    if $reuse; then
      reuse_worktree "$wt_dir" "$repo_path" "$branch_name" "$branch_source" >&2
    elif git -C "$repo_path" show-ref --verify --quiet "refs/heads/$branch_name" 2>/dev/null; then
      git -C "$repo_path" worktree add "$wt_dir" "$branch_name" >&2
    elif [[ -n "$branch_source" ]]; then
      git -C "$repo_path" worktree add -b "$branch_name" "$wt_dir" "$branch_source" >&2
      git -C "$wt_dir" branch --set-upstream-to "$branch_source" "$branch_name" >&2
    else
      local base
      refresh_default_branch "$repo_path"
      base=$(default_start_point "$repo_path")
      git -C "$repo_path" worktree add -b "$branch_name" "$wt_dir" "$base" >&2
    fi
  fi

  echo "$wt_dir"
}

# Ensure a detached worktree checked out at latest main and print its path.
ensure_detached_worktree() {
  local repo_path="$1"
  local repo_name
  repo_name=$(basename "$repo_path")

  mkdir -p "$WORKTREE_ROOT"

  local base
  refresh_default_branch "$repo_path"
  base=$(default_start_point "$repo_path")

  local wt_dir
  if wt_dir=$(find_worktree_dir "$repo_name"); then
    git -C "$wt_dir" switch --detach "$base" >&2
  else
    git -C "$repo_path" worktree add --detach "$wt_dir" "$base" >&2
  fi

  echo "$wt_dir"
}

main() {
  local TMUX_MODE=false
  local REPO_PATH=""

  while [[ $# -gt 0 ]]; do
    case "$1" in
      --tmux) TMUX_MODE=true; shift ;;
      -h|--help) usage ;;
      *) REPO_PATH="$1"; shift ;;
    esac
  done

  if [[ -z "$REPO_PATH" ]]; then
    REPO_PATH=$(pick_project) || exit 0
  fi

  if ! git -C "$REPO_PATH" rev-parse --git-dir &>/dev/null; then
    echo "Error: $REPO_PATH is not a git repository" >&2
    exit 1
  fi

  git -C "$REPO_PATH" worktree prune

  local branch_line
  branch_line=$(pick_branch "$REPO_PATH") || exit 0

  local BRANCH_NAME BRANCH_SOURCE
  IFS=$'\t' read -r BRANCH_NAME BRANCH_SOURCE <<< "$branch_line"

  local WORKTREE_DIR
  if [[ "$BRANCH_NAME" == "$DETACHED_SENTINEL" ]]; then
    WORKTREE_DIR=$(ensure_detached_worktree "$REPO_PATH")
  else
    WORKTREE_DIR=$(ensure_worktree "$REPO_PATH" "$BRANCH_NAME" "$BRANCH_SOURCE")
  fi

  if [[ -f "$WORKTREE_DIR/.envrc" ]]; then
    direnv allow "$WORKTREE_DIR/.envrc"
  fi

  sesh connect "$WORKTREE_DIR"
}

if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
  main "$@"
fi
