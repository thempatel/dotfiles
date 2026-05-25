#!/usr/bin/env bash
set -euo pipefail

TOOLS_FILE="$(dirname "$0")/../uv-tools.txt"

usage() {
  echo "Usage: $(basename "$0") --sync"
  exit 1
}

[[ $# -ge 1 ]] || usage

case "$1" in
  --sync)
    while IFS= read -r tool || [[ -n "$tool" ]]; do
      [[ -z "$tool" || "$tool" == \#* ]] && continue
      echo "Installing: $tool"
      uv tool install "$tool"
    done < "$TOOLS_FILE"
    ;;
  *) usage ;;
esac
