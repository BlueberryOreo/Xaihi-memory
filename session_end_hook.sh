#!/bin/bash
# session_end_hook.sh - Claude Code SessionEnd hook
# Summarizes remaining buffer content and cleans up

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_FILE="$SCRIPT_DIR/session_end.log"

# 使用 nohup 和 & 将总结任务彻底推入后台，并防止终端关闭时进程被杀
nohup python3 "$SCRIPT_DIR/src/remember_engine.py" --session-end </dev/null >"$LOG_FILE" 2>&1 &