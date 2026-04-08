#!/usr/bin/env bash

set -e

pull=false
while getopts "p" opt; do
  case "$opt" in
    p) pull=true ;;
    *) exit 1 ;;
  esac
done
shift $((OPTIND - 1))

ref="${1:-HEAD}"

if $pull; then
  if [ "$ref" = "HEAD" ]; then
    ref=$(git symbolic-ref --short HEAD)
  fi
  remote=$(git config "branch.${ref}.remote" || echo "origin")
  git fetch "$remote" "$ref"
  git checkout --detach "${remote}/${ref}"
  # Fast-forward the local ref to match remote so it doesn't go stale.
  # git branch -f will fail if another worktree has it checked out, which is fine.
  git branch -f "$ref" "${remote}/${ref}" 2>/dev/null || true
else
  git checkout --detach "$ref"
fi
