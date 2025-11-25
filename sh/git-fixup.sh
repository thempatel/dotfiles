#!/usr/bin/env bash

set -e

if ! git diff-index --quiet HEAD --; then
    echo "Working tree is dirty"
    exit 1
fi

origin=$(git symbolic-ref refs/remotes/origin/HEAD)
default_branch="${origin##*/}"
base="${1:-$default_branch}"

if [[ -z "$base" ]]; then
  echo "base unknown, aborting"
  exit 1
fi

first_commit=$(git cherry $base | head -n1 | awk '{ print $2 }')

if [[ -z "$first_commit" ]]; then
  echo "no commits to fixup"
  exit 0
fi


git reset $(git commit-tree "HEAD^{tree}" -p "$first_commit^1" -m "init")
