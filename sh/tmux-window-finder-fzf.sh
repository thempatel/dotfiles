#!/bin/sh
# Fuzzy find tmux windows by session + process label.
#   enter  - switch to selected window
#   ctrl-d - kill selected window(s)

tmux-window-finder lookup >/tmp/tmux-wf-list 2>/tmp/tmux-wf-pos || exit 0

POS=$(cat /tmp/tmux-wf-pos)

OUTPUT=$(cat /tmp/tmux-wf-list | fzf-tmux -p \
  --with-nth=1 \
  --delimiter="	" \
  --no-sort \
  --track \
  --layout=reverse \
  --multi \
  --expect=ctrl-d \
  --header 'ctrl-d: kill' \
  --bind "load:pos($POS)" \
  --bind "ctrl-c:clear-query")

[ -z "$OUTPUT" ] && exit 0

KEY=$(echo "$OUTPUT" | head -1)
TARGETS=$(echo "$OUTPUT" | tail -n +2 | cut -f2)

case "$KEY" in
  ctrl-d)
    echo "$TARGETS" | while read -r t; do
      tmux kill-window -t "$t"
    done
    ;;
  *)
    echo "$TARGETS" | head -1 | xargs -I{} tmux switch-client -t {}
    ;;
esac
exit 0
