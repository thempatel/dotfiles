#!/usr/bin/env bash

# Validates YAML frontmatter in markdown files using yq

set -e

SCRIPT_DIR=$(dirname $0)

# Check if yq is installed
if ! command -v yq &> /dev/null; then
    echo "Error: yq is not installed. Install it with: brew install yq"
    exit 1
fi

mapfile -t files < <(fd skill.md $SCRIPT_DIR/skills)

has_errors=0

for file in "${files[@]}"; do
    if yq --front-matter='extract' $file &> /dev/null; then
        echo "✓ $file: Valid frontmatter"
    else
        echo "✗ $file: Invalid YAML frontmatter"
        has_errors=1
    fi
done

exit $has_errors
