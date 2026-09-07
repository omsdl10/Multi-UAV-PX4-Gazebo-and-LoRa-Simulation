#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PX4_DIR="${PX4_DIR:-/Users/omsingh/PX4-Autopilot}"
RUN_DIR="$PROJECT_DIR/.run"
LOG_DIR="$PROJECT_DIR/logs"
AUDISYS_CONFIG="${AUDISYS_CONFIG:-$PROJECT_DIR/config/audisys_scenario.yaml}"

mkdir -p "$RUN_DIR" "$LOG_DIR/audisys"

if [[ "${AUDISYS_START_BASE:-1}" == "1" ]]; then
  GZ_IP="${GZ_IP:-127.0.0.1}" \
  GZ_PARTITION="${GZ_PARTITION:-multi_uav_lora_sim}" \
  GAZEBO_GUI="${GAZEBO_GUI:-1}" \
  "$PROJECT_DIR/scripts/start_simulation.sh"
fi

echo "Starting AuDiSys scenario layer"
nohup "$PX4_DIR/.venv/bin/python" -u "$PROJECT_DIR/scripts/run_audisys_scenario.py" \
  --config "$AUDISYS_CONFIG" \
  --project-dir "$PROJECT_DIR" \
  --duration "${AUDISYS_DURATION:-300}" \
  >"$LOG_DIR/audisys/scenario.log" 2>&1 </dev/null &
echo $! >> "$RUN_DIR/pids"

if [[ "${AUDISYS_RUN_FLIGHT:-1}" == "1" ]]; then
  sleep "${AUDISYS_FLIGHT_START_DELAY_S:-15}"
  echo "Starting AuDiSys UAV movement mission"
  nohup "$PX4_DIR/.venv/bin/python" -u "$PROJECT_DIR/scripts/run_one_minute_terrain_simulation.py" \
    --duration "${AUDISYS_DURATION:-300}" \
    --altitude "${AUDISYS_ALTITUDE:-12}" \
    --speed "${AUDISYS_SPEED:-18}" \
    --profile whole_area \
    --output "$LOG_DIR/audisys/flight_positions.csv" \
    --no-land \
    >"$LOG_DIR/audisys/flight_mission.log" 2>&1 </dev/null &
  echo $! >> "$RUN_DIR/pids"
fi

echo "AuDiSys logs: $LOG_DIR/audisys"
echo "Stop with: $PROJECT_DIR/scripts/stop_audisys_simulation.sh"
