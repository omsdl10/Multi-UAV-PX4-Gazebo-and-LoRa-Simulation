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
  if [[ "$pid" =~ ^[0-9]+$ ]]; then
    PIDS+=("$pid")
  fi
done < "$RUN_DIR/pids"

collect_descendants() {
  local parent="$1"
  local child
  pgrep -P "$parent" 2>/dev/null | while IFS= read -r child; do
    echo "$child"
    collect_descendants "$child"
  done
}

ALL_PIDS=()
for pid in "${PIDS[@]}"; do
  ALL_PIDS+=("$pid")
  while IFS= read -r child; do
    if [[ "$child" =~ ^[0-9]+$ ]]; then
      ALL_PIDS+=("$child")
    fi
  done < <(collect_descendants "$pid")
done

for pid in "${ALL_PIDS[@]}"; do
  if kill -0 "$pid" 2>/dev/null; then
    kill "$pid" 2>/dev/null || true
  fi
done

sleep 2

for pid in "${ALL_PIDS[@]}"; do
  if kill -0 "$pid" 2>/dev/null; then
    kill -KILL "$pid" 2>/dev/null || true
  fi
done

rm -f "$RUN_DIR/pids"
echo "Stopped project-tracked simulation processes."
