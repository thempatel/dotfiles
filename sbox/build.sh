#!/usr/bin/env bash
#

if [[ -n $QUIET ]]; then
  EXTRA_ARGS='--progress none'
fi

container build $EXTRA_ARGS -t sbox "$(dirname "$0")"
