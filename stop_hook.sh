#!/bin/bash
# stop_hook.sh - Claude Code Stop hook (async)
# Reads user/assistant messages from stdin, writes to buffer in background

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [ ! -t 0 ]; then
    # Read stdin to temp file
    TMPFILE=$(mktemp)
    cat > "$TMPFILE"

    # Run the actual processing in background, exit immediately
    (
        python3 "$SCRIPT_DIR/src/remember_engine.py" --stop-hook "$TMPFILE"
        rm -f "$TMPFILE"
    ) </dev/null >/dev/null 2>&1 &
fi
