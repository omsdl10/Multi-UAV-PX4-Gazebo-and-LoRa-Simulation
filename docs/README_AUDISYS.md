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

The future allocator should consume observations and return assignments through a separate interface. It should not be hard-coded into this scenario layer.
