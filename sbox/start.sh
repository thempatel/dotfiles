#!/usr/bin/env bash


if ! command -v claude; then
  curl -fsSL https://claude.ai/install.sh | bash
fi

IS_SANDBOX=1  claude --dangerously-skip-permissions
