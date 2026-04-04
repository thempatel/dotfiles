#!/bin/sh
# Fuzzy find tmux windows by session + process label.
#   enter  - switch to selected window
#   ctrl-d - kill selected window(s)
#   ctrl-r - refresh window list

tmux-window-finder lookup >/tmp/tmux-wf-list 2>/tmp/tmux-wf-pos || exit 0

POS=$(cat /tmp/tmux-wf-pos)

TARGET=$(cat /tmp/tmux-wf-list | fzf-tmux -p \
  --with-nth=1 \
  --delimiter="	" \
  --no-sort \
  --track \
  --layout=reverse \
  --multi \
  --header 'ctrl-d: kill · ctrl-r: refresh' \
  --bind "load:pos($POS)" \
  --bind 'esc:transform:[[ -z {q} ]] && echo abort || echo clear-query' \
  --bind "ctrl-r:reload(tmux-window-finder update && tmux-window-finder lookup 2>/dev/null)" \
  --bind "ctrl-d:execute-silent(cat {+f} | cut -f2 | xargs -I{} tmux kill-window -t {})+reload(tmux-window-finder update && tmux-window-finder lookup 2>/dev/null)+clear-multi" \
  --bind 'zero:ignore' \
  | cut -f2)

[ -z "$TARGET" ] && exit 0
echo "$TARGET" | head -1 | xargs -I{} tmux switch-client -t {}
exit 0
