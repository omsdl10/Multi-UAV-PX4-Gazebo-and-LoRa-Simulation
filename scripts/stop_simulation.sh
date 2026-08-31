#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RUN_DIR="$PROJECT_DIR/.run"

if [[ ! -s "$RUN_DIR/pids" ]]; then
  echo "No project-tracked simulation processes found."
  exit 0
fi

PIDS=()
while IFS= read -r pid; do
  PIDS+=("$pid")
done < "$RUN_DIR/pids"

for pid in "${PIDS[@]}"; do
  if [[ "$pid" =~ ^[0-9]+$ ]] && kill -0 "$pid" 2>/dev/null; then
    kill "$pid" 2>/dev/null || true
  fi
done

sleep 2

for pid in "${PIDS[@]}"; do
  if [[ "$pid" =~ ^[0-9]+$ ]] && kill -0 "$pid" 2>/dev/null; then
    kill -TERM "$pid" 2>/dev/null || true
  fi
done

rm -f "$RUN_DIR/pids"
echo "Stopped project-tracked simulation processes."
