#!/usr/bin/env bash
set -e

PLUGINS=(
  jeffarese/herdr-bar
)

for plugin in "${PLUGINS[@]}"; do
  herdr plugin install -y "$plugin"
done
