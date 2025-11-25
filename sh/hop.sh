#!/usr/bin/env bash

export TEMP=$(mktemp -d)
trap 'rm -rf "$TEMP"' EXIT

TARGET_DIR="$PWD"
if [[ "h" = "$1" ]]; then
  TARGET_DIR=$HOME
fi

echo -n "$TARGET_DIR" > $TEMP/"1"

TRANSFORMER='
  target_dir={}
  cnt="$(ls -1 $TEMP | wc -l)"
  last="$TEMP/$cnt"
  nxt="$TEMP/$((cnt++))"
  if [[ $FZF_KEY = 'shift-tab' ]]; then
    target_dir=$(cat $last)
    rm $last
  else
    echo "$target_dir" > $nxt
  fi

  printf "reload:fd -t d -d 1 \"\" %q" "$target_dir"
  # echo "+search:"
'

fzf \
  --bind "start:reload:fd -t d -d 1 '' $TARGET_DIR" \
  --bind "tab,shift-tab:transform:$TRANSFORMER" \
  --color "hl:-1:underline,hl+:-1:underline:reverse" \
  --preview "tree {}"
