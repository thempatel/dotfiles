#!/usr/bin/env bash

export TEMP=$(mktemp -u)
trap 'rm -f "$TEMP"' EXIT

# https://junegunn.github.io/fzf/tips/ripgrep-integration/
# https://github.com/junegunn/fzf/blob/master/ADVANCED.md#controlling-ripgrep-search-and-fzf-search-simultaneously

INITIAL_QUERY="${*:-}"
TRANSFORMER='
  rg_pat={q:1}      # The first word is passed to ripgrep
  fzf_pat={q:2..}   # The rest are passed to fzf

  if ! [[ -r "$TEMP" ]] || [[ $rg_pat != $(cat "$TEMP") ]]; then
    echo "$rg_pat" > "$TEMP"
    printf "reload:sleep 0.1; rg --column --color=always --smart-case %q || true" "$rg_pat"
  fi
  echo "+search:$fzf_pat"
'

 fzf \
  --disabled \
  --ansi \
  --query="$INITIAL_QUERY" \
  --delimiter : \
  --bind "start,change:transform:$TRANSFORMER" \
  --bind 'enter:become(zed '{1}:{2}')' \
  --color "hl:-1:underline,hl+:-1:underline:reverse" \
  --preview 'bat --style=full --color=always --highlight-line {2} {1}' \
  --preview-window '~4,+{2}+4/3,<80(up)'
