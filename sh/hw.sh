#!/usr/bin/env bash
set -e

usage() {
  echo "Usage: hw [<dir>]"
  echo "  Switch to the herdr workspace for <dir> (default: current directory),"
  echo "  or create one with agent/term/nvim tabs labelled with the directory's"
  echo "  basename. An open workspace is found by the path hash hw tags it with,"
  echo "  or by label for an untagged workspace (which then gets tagged)."
  exit 1
}

ensure_herdr_server() {
  herdr status server --json 2>/dev/null | jq -e '.running' >/dev/null && return 0

  nohup herdr server >/dev/null 2>&1 &
  disown

  local i
  for (( i = 0; i < 50; i++ )); do
    herdr status server --json 2>/dev/null | jq -e '.running' >/dev/null && return 0
    sleep 0.1
  done

  echo "Error: herdr server did not start" >&2
  exit 1
}

create_workspace() {
  local dir="$1"
  local label="$2"

  local ws_json
  ws_json=$(herdr workspace create --cwd "$dir" --label "$label" --focus)
  local ws_id agent_tab agent_pane
  ws_id=$(jq -r '.result.workspace.workspace_id' <<< "$ws_json")
  agent_tab=$(jq -r '.result.tab.tab_id' <<< "$ws_json")
  agent_pane=$(jq -r '.result.root_pane.pane_id' <<< "$ws_json")

  herdr tab rename "$agent_tab" agent >/dev/null
  herdr pane run "$agent_pane" "clear && sbox-agent" >/dev/null

  herdr tab create --workspace "$ws_id" --cwd "$dir" --label term --no-focus >/dev/null

  local nvim_pane
  nvim_pane=$(
    herdr tab create --workspace "$ws_id" --cwd "$dir" --label nvim --no-focus |
      jq -r '.result.root_pane.pane_id'
  )
  herdr pane run "$nvim_pane" nvim >/dev/null

  herdr tab focus "$agent_tab" >/dev/null
  tag_path "$ws_id" "$dir"
}

# herdr cuts metadata token values at 80 characters, so tag with a fixed-length
# hash of the path rather than the path itself.
path_hash() {
  printf '%s' "$1" | shasum | cut -d' ' -f1
}

tag_path() {
  herdr workspace report-metadata "$1" --source hw --token "path_sha1=$(path_hash "$2")" >/dev/null
}

main() {
  local dir="."
  case "${1:-}" in
    -h|--help) usage ;;
    "") ;;
    *) dir="$1" ;;
  esac

  if [[ ! -d "$dir" ]]; then
    echo "Error: $dir is not a directory" >&2
    exit 1
  fi
  dir=$(cd "$dir" && pwd)
  local label
  label=$(basename "$dir")

  ensure_herdr_server

  # A workspace tagged with another path is a different directory with the same
  # basename, so the label fallback only considers untagged workspaces.
  local ws_id
  ws_id=$(
    herdr workspace list | jq -r --arg h "$(path_hash "$dir")" --arg l "$label" '
      .result.workspaces as $w
      | first($w[] | select(.tokens.path_sha1? == $h))
        // first($w[] | select(.label == $l and .tokens.path_sha1? == null))
        // empty
      | .workspace_id'
  )

  if [[ -n "$ws_id" ]]; then
    tag_path "$ws_id" "$dir"
    herdr workspace focus "$ws_id" >/dev/null
  else
    create_workspace "$dir" "$label"
  fi

  # Outside herdr, the workspace exists but nothing shows it: attach this terminal.
  if [[ "${HERDR_ENV:-}" != 1 ]]; then
    exec herdr
  fi
}

main "$@"
