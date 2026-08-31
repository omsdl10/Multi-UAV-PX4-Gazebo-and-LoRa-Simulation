#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PX4_DIR="${PX4_DIR:-/Users/omsingh/PX4-Autopilot}"
RUN_DIR="$PROJECT_DIR/.run"
LOG_DIR="$PROJECT_DIR/logs"
WORLD_NAME="uav_5km_world"
WORLD_FILE="$PROJECT_DIR/gazebo/worlds/${WORLD_NAME}.sdf"
LORA_CONFIG="${LORA_CONFIG:-$PROJECT_DIR/config/lora.yaml}"

mkdir -p "$RUN_DIR" "$LOG_DIR"

if [[ -s "$RUN_DIR/pids" ]]; then
  echo "Simulation appears to be running. Use scripts/stop_simulation.sh first."
  exit 1
fi

if [[ ! -x "$PX4_DIR/build/px4_sitl_default/bin/px4" ]]; then
  echo "PX4 SITL binary not found. Build it with: cd \"$PX4_DIR\" && make px4_sitl_default"
  exit 1
fi

if [[ ! -f "$WORLD_FILE" ]]; then
  "$PX4_DIR/.venv/bin/python" "$PROJECT_DIR/scripts/generate_world.py" >/dev/null
fi

export GZ_IP="${GZ_IP:-127.0.0.1}"
export GZ_PARTITION="${GZ_PARTITION:-multi_uav_lora_sim}"
export GZ_SIM_RESOURCE_PATH="${GZ_SIM_RESOURCE_PATH:-}"
export GZ_SIM_SYSTEM_PLUGIN_PATH="${GZ_SIM_SYSTEM_PLUGIN_PATH:-}"
export DYLD_FALLBACK_LIBRARY_PATH="${DYLD_FALLBACK_LIBRARY_PATH:-}"
export LANG="${LANG:-en_US.UTF-8}"
export LC_ALL="${LC_ALL:-en_US.UTF-8}"

if [[ -f "$PX4_DIR/build/px4_sitl_default/rootfs/gz_env.sh" ]]; then
  # shellcheck source=/dev/null
  source "$PX4_DIR/build/px4_sitl_default/rootfs/gz_env.sh"
fi

export GZ_SIM_RESOURCE_PATH="$PROJECT_DIR/gazebo/worlds:$GZ_SIM_RESOURCE_PATH"
unset GZ_SIM_SERVER_CONFIG_PATH

echo "Starting Gazebo world: $WORLD_FILE"
nohup gz sim -r -s "$WORLD_FILE" >"$LOG_DIR/gazebo.log" 2>&1 &
gazebo_pid=$!
echo "$gazebo_pid" >> "$RUN_DIR/pids"

sleep 3
if ! kill -0 "$gazebo_pid" 2>/dev/null; then
  echo "Gazebo server exited early. See $LOG_DIR/gazebo.log"
  exit 1
fi

if [[ "${GAZEBO_GUI:-0}" == "1" ]]; then
  echo "Opening Gazebo GUI"
  nohup gz sim -g >"$LOG_DIR/gazebo_gui.log" 2>&1 &
  echo $! >> "$RUN_DIR/pids"
fi

sleep 8

POSES=("-15,0,0,0,0,0" "0,0,0,0,0,0" "15,0,0,0,0,0")
for i in 0 1 2; do
  instance_dir="$RUN_DIR/px4_instance_$i"
  rm -rf "$instance_dir"
  mkdir -p "$instance_dir"
  nohup /bin/bash -c 'cd "$1"; shift; exec "$@"' _ "$instance_dir" \
    env PX4_GZ_STANDALONE=1 \
      PX4_GZ_WORLD="$WORLD_NAME" \
      PX4_SYS_AUTOSTART=4001 \
      PX4_SIM_MODEL=gz_x500 \
      PX4_GZ_MODEL_POSE="${POSES[$i]}" \
      "$PX4_DIR/build/px4_sitl_default/bin/px4" -i "$i" -d "$PX4_DIR/build/px4_sitl_default/etc" \
      >"$LOG_DIR/px4_instance_${i}.log" 2>&1 </dev/null &
  echo $! >> "$RUN_DIR/pids"
  sleep 5
done

cat > "$RUN_DIR/ports.txt" <<'PORTS'
Drone1/System 1: GCS local 18570, offboard local 14580, offboard remote 14540, model x500_0
Drone2/System 2: GCS local 18571, offboard local 14581, offboard remote 14541, model x500_1
Drone3/System 3: GCS local 18572, offboard local 14582, offboard remote 14542, model x500_2
PORTS

echo "Starting LoRa network manager"
nohup "$PX4_DIR/.venv/bin/python" -u -m lora.network_manager \
  --config "$LORA_CONFIG" \
  --project-dir "$PROJECT_DIR" \
  >"$LOG_DIR/lora_manager.log" 2>&1 </dev/null &
echo $! >> "$RUN_DIR/pids"

sleep 1

for drone_id in 1 2 3; do
  nohup "$PX4_DIR/.venv/bin/python" -u "$PROJECT_DIR/lora/lora_node.py" \
    --drone-id "$drone_id" \
    --manager-host 127.0.0.1 \
    --manager-port 19760 \
    >"$LOG_DIR/lora_node_${drone_id}.log" 2>&1 </dev/null &
  echo $! >> "$RUN_DIR/pids"
done

if [[ "${ENABLE_ROS2:-0}" == "1" ]]; then
  echo "Starting optional ROS 2 multi-UAV manager"
  nohup "$PX4_DIR/.venv/bin/python" -u "$PROJECT_DIR/ros2_integration/multi_uav_manager.py" \
    --output "$LOG_DIR/ros2_multi_uav_state.json" \
    >"$LOG_DIR/ros2_manager.log" 2>&1 </dev/null &
  echo $! >> "$RUN_DIR/pids"
fi

if [[ "${RUN_NS3_ADAPTER_ON_START:-0}" == "1" ]]; then
  echo "Running optional ns-3 LoRaWAN adapter detector"
  "$PX4_DIR/.venv/bin/python" -u -m lora.ns3_lorawan_adapter \
    --packet-csv "$PROJECT_DIR/logs/lora_packets.csv" \
    --output "$PROJECT_DIR/logs/ns3_lorawan_status.json" \
    >"$LOG_DIR/ns3_lorawan_adapter.log" 2>&1 || true
fi

echo "Started. Logs are in $LOG_DIR"
echo "Run the 3-drone test with:"
echo "\"$PX4_DIR/.venv/bin/python\" \"$PROJECT_DIR/scripts/mavlink_flight_test.py\" --systems 1 2 3 --altitudes 20 30 40"
echo "LoRa packet log: $PROJECT_DIR/logs/lora_packets.csv"
echo "LoRa config: $LORA_CONFIG"
