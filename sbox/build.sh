#!/usr/bin/env bash
#

if [[ -n $QUIET ]]; then
  EXTRA_ARGS='-q'
fi

docker build $EXTRA_ARGS -t sbox "$(dirname "$0")"
