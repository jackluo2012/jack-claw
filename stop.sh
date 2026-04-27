#!/usr/bin/env bash
# stop.sh — 停止 jackclaw 服务
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PID_FILE="$SCRIPT_DIR/.jackclaw.pid"

# Try PID file first
if [ -f "$PID_FILE" ]; then
    PID=$(cat "$PID_FILE")
    if kill -0 "$PID" 2>/dev/null; then
        echo "Stopping jackclaw (PID $PID)..."
        kill "$PID"
        # Wait up to 5s for graceful shutdown
        for i in $(seq 1 10); do
            if ! kill -0 "$PID" 2>/dev/null; then
                echo "Stopped."
                rm -f "$PID_FILE"
                exit 0
            fi
            sleep 0.5
        done
        # Force kill if still running
        echo "Force killing..."
        kill -9 "$PID" 2>/dev/null || true
        rm -f "$PID_FILE"
        echo "Force stopped."
        exit 0
    else
        echo "PID $PID from $PID_FILE is not running, cleaning up."
        rm -f "$PID_FILE"
    fi
fi

# Fallback: find by process name
PIDS=$(pgrep -f "\.venv/bin/python3 -m jackclaw.main" 2>/dev/null || true)
if [ -n "$PIDS" ]; then
    echo "Found running jackclaw processes: $PIDS"
    for PID in $PIDS; do
        echo "Killing PID $PID..."
        kill "$PID" 2>/dev/null || true
    done
    sleep 1
    # Verify
    PIDS=$(pgrep -f "\.venv/bin/python3 -m jackclaw.main" 2>/dev/null || true)
    if [ -n "$PIDS" ]; then
        echo "Force killing remaining processes..."
        kill -9 $PIDS 2>/dev/null || true
    fi
    echo "Stopped."
else
    echo "No running jackclaw process found."
fi
