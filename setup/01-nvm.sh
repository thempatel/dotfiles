#!/usr/bin/env bash

set -e

if [[ -n $NVM_DIR && -s $NVM_DIR/nvm.sh ]]; then
  echo "nvm installed"
  exit 0
fi

PROFILE=/dev/null bash -c \
  'curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.3/install.sh | bash'
