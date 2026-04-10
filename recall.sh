#!/bin/bash
# recall.sh - Claude Code UserPromptSubmit hook
# Reads user prompt from stdin, queries ChromaDB for relevant memories, outputs context

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [ ! -t 0 ]; then
    TMPFILE=$(mktemp)
    cat > "$TMPFILE"
    PROMPT=$(python3 -c "import sys,json; print(json.load(open('$TMPFILE')).get('prompt',''))" 2>/dev/null)
    rm -f "$TMPFILE"

    if [ -n "$PROMPT" ]; then
        python3 "$SCRIPT_DIR/src/recall_engine.py" "$PROMPT"
    fi
fi
