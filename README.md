# Multi-UAV PX4 + Gazebo Simulation on macOS

This project runs a native macOS PX4 SITL + Gazebo simulation with a custom 5000 m x 5000 m world and three independent PX4 X500 drones.

The default tested network mode is lightweight Python P2P LoRa. Optional ROS 2 and ns-3/LoRaWAN integration hooks are included, but they only run when the required local software is installed.

## Inspected Mac

- macOS: 14.6.1, build 23G93
- CPU architecture: Apple Silicon `arm64`
- Mac: MacBook Air, Apple M1, 8 cores
- RAM: 8 GB
- Homebrew: `/opt/homebrew/bin/brew`
- Xcode Command Line Tools: `/Library/Developer/CommandLineTools`
- Git: 2.55.0
- Python: 3.14.6 at `/opt/homebrew/bin/python3`
- CMake: 4.3.4
- Ninja: 1.13.2
- PX4-Autopilot: `/Users/omsingh/PX4-Autopilot`
- PX4 branch/version inspected: `main`, `v1.18.0-alpha1-461-ga7a6f4c4d7`
- Gazebo: `gz sim` 10.4.0, Homebrew `gz-sim10`

No Ubuntu or `apt` commands are used.

## Files

- `gazebo/worlds/uav_5km_world.sdf`: custom 5 km x 5 km world.
- `scripts/start_simulation.sh`: starts Gazebo and three PX4 instances.
- `scripts/stop_simulation.sh`: stops only PIDs recorded by this project.
- `scripts/mavlink_flight_test.py`: MAVLink verification for arm, takeoff, hover, and land.
- `scripts/generate_world.py`: deterministic generator for the low-poly SDF world.
- `lora/`: standalone Python LoRa peer-to-peer simulation layer.
- `config/lora.yaml`: radio, propagation, loss, routing, and logging settings.
- `config/lora_lorawan.yaml`: lightweight LoRaWAN gateway/server mode.
- `ros2_integration/multi_uav_manager.py`: optional ROS 2 multi-UAV manager, guarded by dependency checks.
- `lora/ns3_lorawan_adapter.py`: optional ns-3/LoRaWAN detector and position-trace adapter.
- `scripts/connectivity_mission.py`: connectivity-aware mission command helper.
- `scripts/profile_simulation.py`: CPU/RAM/Gazebo profiling helper.
- `analysis/output/`: generated distance experiment CSV and SVG plots.

## World Layout

- Center: urban area and UAV base.
- North: hills and rocks.
- South: open agricultural fields.
- East: industrial warehouses.
- West: forest/rural houses.

The world uses simple boxes/cylinders, visual-only dense scenery, simple collision where needed, and no dense 25 km2 terrain mesh.

## Run

```sh
cd /Users/omsingh/Desktop/projects/multi_uav_lora_sim

# Build PX4 SITL if needed
cd /Users/omsingh/PX4-Autopilot
make px4_sitl_default

# Start the custom world, 3 X500 drones, and LoRa network layer
cd /Users/omsingh/Desktop/projects/multi_uav_lora_sim
scripts/start_simulation.sh
```

The drones start at:

- Drone1/System 1/model `x500_0`: `(-15, 0, 0)`
- Drone2/System 2/model `x500_1`: `(0, 0, 0)`
- Drone3/System 3/model `x500_2`: `(15, 0, 0)`

MAVLink ports:

- Drone1: GCS local `18570`, offboard local `14580`, offboard remote `14540`
- Drone2: GCS local `18571`, offboard local `14581`, offboard remote `14541`
- Drone3: GCS local `18572`, offboard local `14582`, offboard remote `14542`

## Verify Flight

```sh
cd /Users/omsingh/Desktop/projects/multi_uav_lora_sim
/Users/omsingh/PX4-Autopilot/.venv/bin/python -u scripts/mavlink_flight_test.py --systems 1 2 3 --altitudes 20 30 40
```

Expected result:

- System 1 arms, takes off, hovers near 20 m AGL, and lands.
- System 2 arms, takes off, hovers near 30 m AGL, and lands.
- System 3 arms, takes off, hovers near 40 m AGL, and lands.

## Stop

```sh
cd /Users/omsingh/Desktop/projects/multi_uav_lora_sim
scripts/stop_simulation.sh
```

The stop script only reads `.run/pids` and stops the processes created by this project. It does not use broad `killall` commands.

## LoRa Simulation

`scripts/start_simulation.sh` also starts:

- 3 lightweight LoRa node identity processes: Drone1, Drone2, Drone3.
- 1 LoRa network manager.
- 1 CSV packet logger inside the manager.

The LoRa layer stays separate from PX4 flight-control internals. It reads live PX4/Gazebo state externally:

- MAVLink provides latitude, longitude, altitude, velocity, battery/status when available.
- Gazebo pose sampling provides common-world `x/y/z` for `x500_0`, `x500_1`, and `x500_2`.

LoRa logs:

- Packet CSV: `logs/lora_packets.csv`
- Pair metrics: `logs/lora_metrics.json`
- Manager log: `logs/lora_manager.log`
- Node logs: `logs/lora_node_1.log`, `logs/lora_node_2.log`, `logs/lora_node_3.log`

The CSV includes distance, RSSI, SNR, LOS, building obstacles, terrain blocking, delivery/drop status, drop reason, latency, packet ID, source, destination, hop count, and TTL.

Configurable radio settings live in `config/lora.yaml`:

- frequency, bandwidth, spreading factor, coding rate
- TX power, receiver sensitivity, noise floor
- path-loss model, path-loss exponent, maximum range
- random seed, building loss, terrain loss, processing delay
- TTL and transmit interval

Supported models:

- 3D distance
- free-space path loss
- log-distance path loss
- RSSI/SNR-based packet delivery
- distance/range loss
- building obstruction using simplified SDF bounding boxes
- terrain/hill obstruction using simplified SDF bounding boxes
- direct peer links and TTL-limited multi-hop relay
- topology-change logging

### P2P Mode

P2P is the default:

```yaml
network:
  network_mode: p2p
```

Run:

```sh
cd /Users/omsingh/Desktop/projects/multi_uav_lora_sim
scripts/start_simulation.sh
```

### Lightweight LoRaWAN Mode

This uses the local Python gateway/server model. It does not require ROS 2 or ns-3.

```sh
cd /Users/omsingh/Desktop/projects/multi_uav_lora_sim
LORA_CONFIG=/Users/omsingh/Desktop/projects/multi_uav_lora_sim/config/lora_lorawan.yaml scripts/start_simulation.sh
```

Logs:

- `logs/lorawan_packets.csv`
- `logs/lorawan_metrics.json`
- `logs/lorawan_topology_changes.csv`

### ns-3 LoRaWAN Adapter

The adapter detects local ns-3 availability and exports a position trace from the LoRa packet log:

```sh
cd /Users/omsingh/Desktop/projects/multi_uav_lora_sim
/Users/omsingh/PX4-Autopilot/.venv/bin/python -m lora.ns3_lorawan_adapter
```

On this Mac, ns-3 is not installed, so the adapter writes `logs/ns3_lorawan_status.json` with `available: false`.

Current API investigation:

- The ns-3 App Store lists LoRaWAN `0.3.7`, released July 15, 2026, as working with ns-3 `3.48`.
- The release notes mention PHY/MAC changes, Class A behavior, retransmission changes, and Network Server support.
- Because ns-3 is not installed locally, no ns-3 LoRaWAN simulation was executed here.

## ROS 2

Local result on this Mac:

- `ros2` command: not installed.
- `rclpy`: not installed.
- `MicroXRCEAgent`: not installed.
- `px4_msgs`: not installed.

PX4 itself does start `uxrce_dds_client` in SITL, but without a local Micro XRCE-DDS Agent and ROS 2 workspace, ROS 2 topics cannot be tested.

The optional manager is:

```sh
/Users/omsingh/PX4-Autopilot/.venv/bin/python ros2_integration/multi_uav_manager.py
```

It expects namespaces:

- `/drone1`
- `/drone2`
- `/drone3`

It tracks position, velocity, altitude, battery, flight mode, communication status, pairwise distances, and writes `logs/ros2_multi_uav_state.json` when ROS 2 dependencies are present.

## Connectivity Mission

Start the stack, then command all three UAVs to take off and spread into different world areas:

```sh
cd /Users/omsingh/Desktop/projects/multi_uav_lora_sim
/Users/omsingh/PX4-Autopilot/.venv/bin/python -u scripts/connectivity_mission.py
```

The LoRa manager continuously logs link quality and topology changes. If direct Drone1 -> Drone3 delivery fails and Drone2 can bridge both links, the P2P manager attempts Drone1 -> Drone2 -> Drone3 with TTL and duplicate filtering.

## AuDiSys Scenario Layer

The AuDiSys layer is a separate mission/event layer for task-assignment handoff experiments. It does not replace the working PX4, Gazebo, or LoRa stack, and it does not implement a final allocation algorithm.

It adds:

- Drone1 role: Scout
- Drone2 role: Relay
- Drone3 role: Designator
- deterministic moving target model: `audisys_target`
- task events: `DETECTION`, `TRACKING`, `RELAY`, `DESIGNATION`
- allocation-interface observation logging with no hard-coded task winner

Configuration:

```sh
config/audisys_scenario.yaml
```

Run:

```sh
cd /Users/omsingh/Desktop/projects/multi_uav_lora_sim
GAZEBO_GUI=1 scripts/start_audisys_simulation.sh
```

This starts the base simulator, the AuDiSys scenario layer, and a default whole-area UAV movement mission. Useful overrides:

```sh
AUDISYS_DURATION=600 AUDISYS_SPEED=18 GAZEBO_GUI=1 scripts/start_audisys_simulation.sh
```

Stop:

```sh
cd /Users/omsingh/Desktop/projects/multi_uav_lora_sim
scripts/stop_audisys_simulation.sh
```

AuDiSys logs:

- `logs/audisys/uav_state.csv`
- `logs/audisys/target_state.csv`
- `logs/audisys/radio.csv`
- `logs/audisys/tasks.csv`
- `logs/audisys/events.csv`
- `logs/audisys/allocation_messages.csv`
- `logs/audisys/flight_positions.csv`

Documentation:

- `docs/README_AUDISYS.md`
- `HANDOFF.md`
- `OPEN_QUESTIONS.md`
- `docs/TASK1_TEST.md`
- `docs/TASK2_TEST.md`
- `docs/TASK3_TEST.md`

## Performance

Profile a running stack:

```sh
cd /Users/omsingh/Desktop/projects/multi_uav_lora_sim
/Users/omsingh/PX4-Autopilot/.venv/bin/python scripts/profile_simulation.py
```

Output:

- `logs/performance_profile.json`

Optimizations already used:

- Low-poly SDF primitives.
- Visual-only dense scenery where collision is not needed.
- Simplified bounding boxes for buildings/hills.
- Periodic, not per-frame, LoRa updates.
- Low-rate Gazebo pose sampling.
- CSV logging only at communication update rate.

## LoRa Experiments

Run distance experiments at 100, 250, 500, 1000, 1500, 2000, 3000, 4000, and 5000 m:

```sh
cd /Users/omsingh/Desktop/projects/multi_uav_lora_sim
/Users/omsingh/PX4-Autopilot/.venv/bin/python -m lora.experiments --samples 100
```

Outputs:

- `analysis/output/lora_experiments.csv`
- `analysis/output/distance_vs_rssi.svg`
- `analysis/output/distance_vs_snr.svg`
- `analysis/output/distance_vs_pdr.svg`
- `analysis/output/distance_vs_latency.svg`
- `analysis/output/distance_vs_packet_loss.svg`

## Final Results

See:

- `logs/final_test_results.md`

Summary:

- P2P LoRa: PASS
- Lightweight LoRaWAN mode: PASS
- ROS 2: FAIL / not installed locally
- ns-3 LoRaWAN: FAIL / ns-3 not installed locally

## Troubleshooting

- If startup says a simulation is already running, run `scripts/stop_simulation.sh`.
- If PX4 cannot find Gazebo plugins, rebuild PX4 with `make px4_sitl_default`.
- If Gazebo stats time out during profiling, CPU/RAM process profiling still works.
- If ROS 2 is desired, install ROS 2 natively for macOS and provide `rclpy`, `px4_msgs`, and `MicroXRCEAgent`; avoid Ubuntu `apt` instructions on this Mac.
- If ns-3 LoRaWAN is desired, install ns-3 3.48 and the matching LoRaWAN 0.3.7 module, then update `config/lora_lorawan.yaml`.

## Known Limitations

- ROS 2 was not tested because it is not installed on this Mac.
- ns-3 LoRaWAN was not tested because ns-3 is not installed on this Mac.
- Lightweight LoRaWAN mode is an analytical Python gateway/server model, not ns-3.
- Gazebo real-time factor sampling timed out through `gz topic` during the profiling run.
- The connectivity mission helper sends mission commands but was not flown end-to-end in this extension pass.

## Verified Result

On this Mac, the final test completed successfully:

- System 1 reached 18.1 m for a 20 m target.
- System 2 reached 28.1 m for a 30 m target.
- System 3 reached 38.0 m for a 40 m target.
- All three systems landed successfully.

The altitude tolerance in the test is 2 m, so these are valid hover verifications.

LoRa live verification also completed successfully:

- The full start command launched Gazebo, 3 PX4 drones, 3 LoRa nodes, the LoRa manager, and packet logging.
- Gazebo-derived starting distances were approximately 15 m, 15 m, and 30 m.
- `logs/lora_packets.csv` and `logs/lora_metrics.json` were generated.
