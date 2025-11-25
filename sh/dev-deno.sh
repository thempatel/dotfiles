#!/usr/bin/env bash
script_path=$(realpath $1)
shift
exec deno run -A --config $DOTFILES_HOME/deno.json "$script_path" "$@"
