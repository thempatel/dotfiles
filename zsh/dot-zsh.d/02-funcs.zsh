# https://gist.github.com/welldan97/5127861

pb-kill-whole-line () {
  zle kill-whole-line
  echo -n $CUTBUFFER | pbcopy
}

pb-yank () {
  CUTBUFFER=$(pbpaste)
  zle yank
}

fzf-search() {
  local query="$BUFFER"
  BUFFER=""
  zle redisplay
  fzf-rg $query
}

z() {
  local dir=$(
    _z 2>&1 |
    fzf --height 40% --layout reverse --info inline \
        --nth 2.. --tac --no-sort --query "$*" \
        --accept-nth 2..
  ) && cd "$dir"
}

cc-no-commit() {
  local dir=".claude"
  local file="$dir/settings.local.json"
  mkdir -p "$dir"

  if [[ ! -f "$file" ]]; then
    echo '{}' > "$file"
  fi

  jq '.includeCoAuthoredBy = false' "$file" | sponge "$file"
}

zle -N pb-kill-whole-line
zle -N pb-yank
zle -N fzf-search

bindkey '^U' pb-kill-whole-line
bindkey '^Y' pb-yank
bindkey '^F' fzf-search
