#!/bin/bash
set -euo pipefail

BREWFILE="$(dirname "$0")/../brew/Brewfile"

usage() {
  echo "Usage: $(basename "$0") add|remove tap|brew|cask <name> [<name>...]"
  exit 1
}

[[ $# -ge 3 ]] || usage

action="$1"; shift
kind="$1"; shift

case "$kind" in
  tap|brew|cask) ;;
  *) echo "Unknown type: $kind (must be tap, brew, or cask)" >&2; exit 1 ;;
esac

for name in "$@"; do
  entry="$kind \"$name\""
  case "$action" in
    add)
      if grep -qxF "$entry" "$BREWFILE"; then
        echo "Already present: $entry"
      else
        echo "Adding: $entry"
        echo "$entry" >> "$BREWFILE"
      fi
      ;;
    remove)
      if grep -qxF "$entry" "$BREWFILE"; then
        echo "Removing: $entry"
        grep -vxF "$entry" "$BREWFILE" > "$BREWFILE.tmp"
        mv "$BREWFILE.tmp" "$BREWFILE"
      else
        echo "Not found: $entry"
      fi
      ;;
    *) usage ;;
  esac
done

# Rebuild file: taps, then brews, then casks, each sorted, separated by blank lines
{
  grep '^tap ' "$BREWFILE" | sort
  echo
  grep '^brew ' "$BREWFILE" | sort
  echo
  grep '^cask ' "$BREWFILE" | sort
} > "$BREWFILE.tmp"
mv "$BREWFILE.tmp" "$BREWFILE"

echo ""
echo "Running brew bundle..."
brew bundle --file "$BREWFILE"
