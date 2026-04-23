#!/usr/bin/env bash
script_path=$(realpath "$1")
shift

dir=$(dirname "$script_path")
config=""
while [[ "$dir" != "/" ]]; do
  for f in deno.json deno.jsonc; do
    if [[ -f "$dir/$f" ]]; then
      config="$dir/$f"
      break 2
    fi
  done
  dir=$(dirname "$dir")
done

if [[ -n "$config" ]]; then
  exec deno run -A --config "$config" "$script_path" "$@"
else
  exec deno run -A "$script_path" "$@"
fi
