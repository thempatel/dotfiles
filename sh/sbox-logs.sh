#!/usr/bin/env bash
#
# Search macOS system logs for sandbox denial messages.
#
# Usage:
#   sbox-logs [minutes]    # defaults to 5 minutes

set -e

MINUTES="${1:-5}"

/usr/bin/log show --last "${MINUTES}m" 2>/dev/null \
    | grep -i -E "(Sandbox.*deny)" \
    | grep -v "dtracehelper"
