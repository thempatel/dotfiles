#!/usr/bin/env bash

if ! command -v uv &> /dev/null; then
    curl -LsSf https://astral.sh/uv/install.sh | sh
    source "$HOME/.local/bin/env"
fi

if ! npm list -g | grep -q '@anthropic-ai/claude-code'; then
    npm install -g @anthropic-ai/claude-code &> /dev/null
fi

IS_SANDBOX=1  claude --dangerously-skip-permissions
