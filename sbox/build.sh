#!/usr/bin/env bash
#

EXTRA_ARGS=()

while getopts "fq" opt; do
  case $opt in
    f) EXTRA_ARGS+=(--no-cache) ;;
    q) EXTRA_ARGS+=(-q) ;;
    *) echo "Usage: $0 [-f] [-q]" >&2; exit 1 ;;
  esac
done

container build "${EXTRA_ARGS[@]}" -t sbox "$(dirname "$0")"
