# Project Report: Multi-UAV PX4, Gazebo, and LoRa Simulation

Generated: 2026-08-31

## 1. Project Overview

This project builds a native macOS simulation environment for three PX4 X500 UAVs flying inside a custom Gazebo world. A separate Python-based LoRa communication layer reads live drone positions from PX4/Gazebo and simulates peer-to-peer wireless communication between the drones.

The main goal completed so far is:

- Run a 5 km x 5 km Gazebo terrain world.
- Spawn three independent PX4 SITL X500 drones.
- Control all three drones independently.
- Simulate LoRa-style data sharing between Drone1, Drone2, and Drone3.
- Log positions, RSSI, SNR, packet status, packet loss, latency, and routing data into CSV files.
- Run repeatable terrain and communication missions.

## 2. System Architecture

The current working architecture is:

```text
Gazebo 5 km x 5 km custom world
|
+-- Drone1: PX4 SITL X500, system ID 1, model x500_0
+-- Drone2: PX4 SITL X500, system ID 2, model x500_1
+-- Drone3: PX4 SITL X500, system ID 3, model x500_2
|
+-- Python LoRa Network Manager
    |
    +-- LoRa node 1
    +-- LoRa node 2
    +-- LoRa node 3
    |
    +-- CSV logger
```

The communication system is separate from PX4 flight-control internals. It observes drone position and state externally through MAVLink/Gazebo data, then evaluates radio links in Python.

## 3. Mac and Software Environment

The Mac was inspected before the original setup work.

Known inspected environment:

- macOS: 14.6.1
- Architecture: Apple Silicon arm64
- Machine: MacBook Air, Apple M1
- RAM: 8 GB
- Homebrew: installed at `/opt/homebrew/bin/brew`
- Xcode Command Line Tools: installed
- Git: installed
- Python: Homebrew Python 3.14.6
- CMake: installed
- Ninja: installed
- PX4-Autopilot: `/Users/omsingh/PX4-Autopilot`
- PX4 branch/version observed: `main`, `v1.18.0-alpha1-461-ga7a6f4c4d7`
- Gazebo: `gz sim` 10.4.0

No Ubuntu-specific or `apt` commands were used.

## 4. Gazebo World

Created world:

```text
gazebo/worlds/uav_5km_world.sdf
```

World size:

```text
X: -2500 m to +2500 m
Y: -2500 m to +2500 m
```

World regions:

- Center: urban area and UAV base.
- North: hills and mountains.
- South: open/agricultural terrain.
- East: industrial area with warehouses.
- West: forest/rural area.

World content:

- Terrain and elevation changes.
- Roads and intersections.
- Low-poly buildings.
- Warehouses.
- Houses.
- Trees.
- Rocks.
- Open fields.
- UAV base.

The world is optimized for MacBook performance using simple geometry, simple collision shapes, and low-density terrain rather than a heavy 25 km2 mesh.

## 5. PX4 Multi-Drone Simulation

Implemented three independent PX4 SITL X500 drones:

```text
Drone1: system ID 1, Gazebo model x500_0, start position (-15, 0, 0)
Drone2: system ID 2, Gazebo model x500_1, start position (0, 0, 0)
Drone3: system ID 3, Gazebo model x500_2, start position (15, 0, 0)
```

MAVLink ports:

```text
Drone1: GCS local 18570, offboard local 14580, offboard remote 14540
Drone2: GCS local 18571, offboard local 14581, offboard remote 14541
Drone3: GCS local 18572, offboard local 14582, offboard remote 14542
```

Verified behavior during earlier tests:

- PX4 SITL starts.
- Gazebo starts.
- Three X500 models spawn.
- Drones arm.
- Drones take off.
- Drones hover.
- Drones land.
- Each PX4 instance has a separate system ID and ports.

## 6. Launcher and Shutdown Scripts

Created/updated:

```text
scripts/start_simulation.sh
scripts/stop_simulation.sh
```

The start script launches:

- Gazebo server.
- Optional Gazebo GUI when `GAZEBO_GUI=1`.
- Three PX4 SITL drone instances.
- LoRa network manager.
- Three LoRa node processes.
- Optional ROS 2 manager if enabled.
- Optional ns-3 adapter detector if enabled.

The stop script stops only project-tracked processes from:

```text
.run/pids
```

It does not use broad `killall` commands.

Important fix made:

- Gazebo GUI mode was changed so Gazebo server starts reliably first, then the GUI opens separately.
- `GZ_PARTITION=multi_uav_lora_sim` was added to reduce interference with unrelated Gazebo sessions.
- PX4 instance folders are cleaned before launch to avoid stale runtime state.

## 7. LoRa Communication Layer

Created Python LoRa modules:

```text
lora/lora_node.py
lora/channel.py
lora/propagation.py
lora/packet_loss.py
lora/airtime.py
lora/routing.py
lora/logger.py
lora/network_manager.py
```

Configuration:

```text
config/lora.yaml
```

Implemented features:

- 3D drone-to-drone distance.
- Configurable frequency, bandwidth, spreading factor, coding rate, TX power, sensitivity, noise floor, path-loss exponent, maximum range, and random seed.
- Free-space path loss.
- Log-distance path loss.
- RSSI calculation.
- SNR calculation.
- Packet-delivery probability.
- Packet received/dropped status.
- Drop reasons:
  - `out_of_range`
  - `low_rssi`
  - `low_snr`
  - `channel_loss`
- Latency model:
  - propagation delay
  - LoRa airtime
  - processing delay
- Building obstruction using simplified SDF bounding boxes.
- Terrain/hill obstruction approximation.
- Multi-hop relay with packet ID, source, destination, hop count, TTL, duplicate prevention, and loop prevention.

Main LoRa packet log:

```text
logs/lora_packets.csv
```

At the latest inspection, this file contained:

```text
118201 lines total
```

## 8. RSSI in CSV

RSSI was already present in:

```text
logs/lora_packets.csv
```

The packet CSV includes:

```text
RSSI
SNR
distance
packet_status
drop_reason
latency_ms
```

Additional work was done to also include RSSI/SNR directly in the drone position CSV generated by the mission runner.

New position CSV columns:

```text
rssi_to_drone1_dbm
rssi_to_drone2_dbm
rssi_to_drone3_dbm
snr_to_drone1_db
snr_to_drone2_db
snr_to_drone3_db
link_status_to_drone1
link_status_to_drone2
link_status_to_drone3
```

Example live RSSI values observed:

```text
RSSI around -70 dBm to -82 dBm during spread-out flight
SNR around 37 dB to 50 dB
```

## 9. Mission and Data-Collection Scripts

Created/updated mission/data scripts:

```text
scripts/mavlink_flight_test.py
scripts/connectivity_mission.py
scripts/run_one_minute_terrain_simulation.py
scripts/extract_run_exchange.py
scripts/profile_simulation.py
```

The main reusable mission runner is:

```text
scripts/run_one_minute_terrain_simulation.py
```

Despite its original name, it now supports configurable duration and multiple mission profiles.

Mission profiles added:

```text
terrain
close
visible_terrain
focus_drone1
focus_drone2
focus_drone3
all_directions
```

The most important current profile is:

```text
all_directions
```

It flies all three drones together in one simulation:

- Drone1 moves toward the west/northwest.
- Drone2 moves toward the south/southeast.
- Drone3 moves toward the east/northeast.

This was added because sequential focus runs made the simulation look repetitive.

## 10. Simulations Run So Far

### 10.1 One-Minute Terrain Run

Output files:

```text
logs/one_minute_drone_positions.csv
logs/one_minute_position_exchange.csv
```

Observed results:

```text
Position snapshots: 177 data rows
LoRa exchange packets: 396 data rows
Drone1 moved about 120 m x 180 m
Drone2 moved about 178 m
Drone3 moved about 120 m x 180 m
```

### 10.2 Five-Minute Close-Formation Run

Output files:

```text
logs/five_min_close_drone_positions.csv
logs/five_min_close_position_exchange.csv
```

Observed results:

```text
Position snapshots: 873 data rows
LoRa exchange packets: 1983 data rows
Minimum pair distance: 3.1 m
Maximum pair distance: 24.3 m
Average max pair distance: 19.9 m
```

### 10.3 Five-Minute Visible Terrain Run

Output file:

```text
logs/five_min_visible_terrain_positions.csv
```

This run spread drones farther apart so they were easier to see in Gazebo while flying over terrain.

### 10.4 Three Sequential Focus Runs

These were run to show each drone as the main mover, but later rejected as the desired final behavior because they looked like repeated simulations.

Simulation 1: Drone1 focus

```text
logs/sim1_drone1_focus_positions.csv
logs/sim1_drone1_focus_exchange.csv
Drone1 movement: dx=205.6 m, dy=-252.2 m
LoRa exchange rows: 601 data rows
```

Simulation 2: Drone2 focus

```text
logs/sim2_drone2_focus_positions.csv
logs/sim2_drone2_focus_exchange.csv
Drone2 movement: dx=-264.5 m, dy=105.7 m
LoRa exchange rows: 597 data rows
```

Simulation 3: Drone3 focus

```text
logs/sim3_drone3_focus_positions.csv
logs/sim3_drone3_focus_exchange.csv
Drone3 movement: dx=151.9 m, dy=233.7 m
LoRa exchange rows: 590 data rows
```

### 10.5 Combined All-Directions Run

Output file:

```text
logs/all_directions_positions.csv
```

Later RSSI-enabled output file:

```text
logs/live_all_directions_with_rssi_positions.csv
```

This is the preferred demonstration because all three drones move together in one simulation.

Observed sample from the RSSI-enabled CSV:

```text
Drone1: x=337.720, y=-377.752, z=34.968
Drone2: x=-478.999, y=166.195, z=40.008
Drone3: x=278.638, y=435.948, z=44.975
RSSI examples: -80.027 dBm to -82.080 dBm
```

At latest inspection:

```text
logs/live_all_directions_with_rssi_positions.csv: 511 lines total
```

This file was from an active or partial run at the time of inspection.

## 11. Experiments and Plots

Distance-based LoRa experiments were implemented.

Output files:

```text
analysis/output/lora_experiments.csv
analysis/output/distance_vs_rssi.svg
analysis/output/distance_vs_snr.svg
analysis/output/distance_vs_pdr.svg
analysis/output/distance_vs_latency.svg
analysis/output/distance_vs_packet_loss.svg
```

Experiments cover approximate distances:

```text
100 m
250 m
500 m
1000 m
1500 m
2000 m
3000 m
4000 m
5000 m
```

## 12. ROS 2 and XRCE-DDS Status

ROS 2 integration was investigated and scaffolded but not fully tested because required ROS 2 tools were not installed locally.

Created:

```text
ros2_integration/multi_uav_manager.py
```

Detected status:

- PX4 SITL starts `uxrce_dds_client`.
- Local `ros2` command was not available.
- Local `rclpy` was not available.
- Local Micro XRCE-DDS Agent was not available.
- Local `px4_msgs` workspace was not available.

Therefore, ROS 2 support is present as an optional integration path, but it has not been verified as working on this Mac.

## 13. ns-3 and LoRaWAN Status

Lightweight LoRaWAN mode was added in Python.

Created:

```text
config/lora_lorawan.yaml
lora/ns3_lorawan_adapter.py
```

Generated files:

```text
logs/lorawan_packets.csv
logs/lorawan_metrics.json
logs/lorawan_topology_changes.csv
logs/ns3_lorawan_status.json
logs/ns3_position_trace.json
```

Status:

- Lightweight Python LoRaWAN-style gateway/server mode exists.
- ns-3 adapter detector exists.
- Local ns-3 was not installed at inspection time.
- Full ns-3 LoRaWAN simulation was not executed locally.

## 14. Problems Found and Fixed

Several real runtime issues were found during testing:

1. Gazebo was initially started in headless mode, so the simulation was running but invisible.
2. GUI launch was adjusted so users can run:

```text
GAZEBO_GUI=1 ./scripts/start_simulation.sh
```

3. Gazebo GUI and server were separated for reliability.
4. A private Gazebo partition was added to reduce conflicts with unrelated Gazebo worlds.
5. PX4 instance folders are cleared on startup to avoid stale SITL state.
6. The mission runner initially conflicted with the LoRa manager on MAVLink port `14550`; it was changed to use per-drone MAVLink ports.
7. PX4 sometimes rejected telemetry interval requests; the script now treats those as non-fatal.
8. Takeoff acknowledgement timing was made more tolerant by verifying altitude.
9. Drone movement initially looked like hover-only; route commands were changed to PX4 reposition commands.
10. RSSI/SNR columns were added to the position CSV.

## 15. Current Important Commands

Start visible simulator:

```sh
cd /Users/omsingh/Desktop/projects/multi_uav_lora_sim
GAZEBO_GUI=1 ./scripts/start_simulation.sh
```

Run all three drones together in different directions with RSSI in the position CSV:

```sh
cd /Users/omsingh/Desktop/projects/multi_uav_lora_sim
/Users/omsingh/PX4-Autopilot/.venv/bin/python -u scripts/run_one_minute_terrain_simulation.py \
  --duration 300 \
  --profile all_directions \
  --altitude 35 \
  --output logs/live_all_directions_with_rssi_positions.csv
```

Stop project processes:

```sh
cd /Users/omsingh/Desktop/projects/multi_uav_lora_sim
./scripts/stop_simulation.sh
```

Extract LoRa exchange rows for a position-log time window:

```sh
cd /Users/omsingh/Desktop/projects/multi_uav_lora_sim
/Users/omsingh/PX4-Autopilot/.venv/bin/python scripts/extract_run_exchange.py \
  --positions logs/live_all_directions_with_rssi_positions.csv \
  --output logs/live_all_directions_with_rssi_exchange.csv
```

## 16. Research/Paper Potential

A paper is possible, but the current uniqueness is moderate rather than high.

Common parts in existing research:

- PX4 + Gazebo multi-UAV simulation.
- UAV wireless communication simulation.
- RSSI/SNR/path-loss modeling.
- ns-3/Gazebo/PX4 co-simulation concepts.

More distinctive parts of this project:

- Native macOS-focused workflow.
- 5 km x 5 km custom Gazebo terrain with multiple regions.
- Lightweight Python LoRa layer independent from PX4 internals.
- Real PX4/Gazebo drone positions feeding radio-link calculations.
- Building/terrain obstruction approximation.
- Multi-hop relay behavior.
- Repeatable CSV datasets from live multi-UAV missions.

Estimated uniqueness today:

```text
5/10 as-is
7-8/10 if strengthened with systematic experiments, comparison, and analysis
```

Best paper angle:

```text
Connectivity-aware multi-UAV mission simulation using PX4/Gazebo and lightweight LoRa communication modeling on macOS
```

Recommended improvements before publication:

- Add a clean experiment runner for repeatable 1, 3, and 5 drone-route scenarios.
- Compare close formation, medium separation, and long-range separation.
- Compare direct P2P vs multi-hop relay.
- Compare lightweight P2P vs lightweight LoRaWAN mode.
- Produce final plots for RSSI, SNR, PDR, latency, packet loss, and distance.
- Add a clear table of Mac CPU/RAM/Gazebo performance.
- Add screenshots or screen recordings of the Gazebo runs.
- Write method, experiment design, results, and limitations sections.

## 17. Known Limitations

- ROS 2 integration exists but is not locally verified because ROS 2 dependencies are not installed.
- ns-3 LoRaWAN integration is only an adapter/detector path so far; full ns-3 execution was not locally tested.
- Building and terrain obstruction are simplified approximations, not full geometric/ray-traced RF propagation.
- Some Gazebo GUI behavior depends on macOS window focus and camera view.
- Old orphan PX4 processes can hold ports if a previous run is interrupted; this was observed and handled manually during testing.
- The world is intentionally low-poly for MacBook performance, so it is not photorealistic.
- The current LoRa model is suitable for simulation studies, not hardware certification.

## 18. Files Created or Modified

Major project files:

```text
README.md
PROJECT_REPORT.md
gazebo/worlds/uav_5km_world.sdf
config/lora.yaml
config/lora_lorawan.yaml
lora/airtime.py
lora/channel.py
lora/experiments.py
lora/logger.py
lora/lora_node.py
lora/network_manager.py
lora/ns3_lorawan_adapter.py
lora/packet_loss.py
lora/propagation.py
lora/routing.py
ros2_integration/multi_uav_manager.py
scripts/connectivity_mission.py
scripts/extract_run_exchange.py
scripts/generate_world.py
scripts/mavlink_flight_test.py
scripts/profile_simulation.py
scripts/run_one_minute_terrain_simulation.py
scripts/start_simulation.sh
scripts/stop_simulation.sh
```

Major generated result files:

```text
logs/lora_packets.csv
logs/lora_metrics.json
logs/topology_changes.csv
logs/one_minute_drone_positions.csv
logs/one_minute_position_exchange.csv
logs/five_min_close_drone_positions.csv
logs/five_min_close_position_exchange.csv
logs/five_min_visible_terrain_positions.csv
logs/all_directions_positions.csv
logs/live_all_directions_with_rssi_positions.csv
logs/sim1_drone1_focus_positions.csv
logs/sim1_drone1_focus_exchange.csv
logs/sim2_drone2_focus_positions.csv
logs/sim2_drone2_focus_exchange.csv
logs/sim3_drone3_focus_positions.csv
logs/sim3_drone3_focus_exchange.csv
analysis/output/lora_experiments.csv
analysis/output/distance_vs_rssi.svg
analysis/output/distance_vs_snr.svg
analysis/output/distance_vs_pdr.svg
analysis/output/distance_vs_latency.svg
analysis/output/distance_vs_packet_loss.svg
```

## 19. Summary

The project has progressed from a basic requirement into a working native macOS PX4/Gazebo multi-UAV simulation with an external LoRa communication simulator. It can start three PX4 X500 drones, fly them in coordinated missions, collect live positions, simulate drone-to-drone packet delivery, calculate RSSI/SNR/latency/loss, and write the results into CSV files.

The strongest current demonstration is the combined `all_directions` mission with RSSI-enabled position logging. That is the best base for future experiments and paper development.
