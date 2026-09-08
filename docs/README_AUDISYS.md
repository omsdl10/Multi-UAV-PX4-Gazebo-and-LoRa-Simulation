# AuDiSys Scenario Layer

The AuDiSys scenario layer turns the existing multi-UAV PX4/Gazebo/LoRa simulator into a task-event environment for later allocation experiments.

It keeps allocation outside the environment.

## Architecture

```text
Gazebo border world + audisys_target
PX4 Drone1 / Drone2 / Drone3
LoRa network manager
AuDiSys scenario layer
logs/audisys/*.csv
future allocation module
```

## Roles

- Drone1: Scout
- Drone2: Relay
- Drone3: Designator

## Start

```sh
cd /Users/omsingh/Desktop/projects/multi_uav_lora_sim
GAZEBO_GUI=1 scripts/start_audisys_simulation.sh
```

This starts the base simulator, the AuDiSys scenario layer, and a default whole-area UAV movement mission. Set `AUDISYS_RUN_FLIGHT=0` to observe only the scripted target and task/event layer.

Useful overrides:

```sh
AUDISYS_DURATION=600 AUDISYS_SPEED=18 GAZEBO_GUI=1 scripts/start_audisys_simulation.sh
```

For deterministic Task 3 evidence runs:

```sh
AUDISYS_PROFILE=visible_terrain AUDISYS_DURATION=90 GAZEBO_GUI=0 scripts/start_audisys_simulation.sh
```

## Stop

```sh
cd /Users/omsingh/Desktop/projects/multi_uav_lora_sim
scripts/stop_audisys_simulation.sh
```

## Configuration

Edit:

```text
config/audisys_scenario.yaml
```

This file controls the seed, target route, roles, radio thresholds, task thresholds, and log directory.

## Logs

The scenario writes:

- `logs/audisys/uav_state.csv`
- `logs/audisys/target_state.csv`
- `logs/audisys/radio.csv`
- `logs/audisys/tasks.csv`
- `logs/audisys/events.csv`
- `logs/audisys/allocation_messages.csv`
- `logs/audisys/flight_positions.csv`

Task 3 reproducibility artifacts are saved under:

- `artifacts/task3/summary.json`
- `artifacts/task3/run_1/`
- `artifacts/task3/run_2/`
- `artifacts/task3/run_3/`

The latest Task 3 run passed three clean starts with the same seed/configuration, consistent task order, consistent radio-transition order, parseable logs, and no stale project-tracked processes after shutdown.

## Observer Cameras

The Gazebo world includes four fixed observer cameras:

- `audisys_camera_overhead_wide`
- `audisys_camera_uav_base`
- `audisys_camera_border_checkpoint`
- `audisys_camera_target_zone`

Open them with:

```sh
scripts/show_audisys_camera.sh overhead
scripts/show_audisys_camera.sh base
scripts/show_audisys_camera.sh checkpoint
scripts/show_audisys_camera.sh target
```

For recording the whole scenario, use the overhead camera or the normal Gazebo GUI with the camera zoomed out.

The future allocator should consume observations and return assignments through a separate interface. It should not be hard-coded into this scenario layer.
