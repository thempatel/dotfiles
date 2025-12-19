#!/usr/bin/env bash

set -e

if command -v nvm; then
  exit 0
fi

curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.3/install.sh | bash
