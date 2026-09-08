# AuDiSys Scenario Handoff

This repository now contains a separate AuDiSys scenario layer on top of the existing PX4, Gazebo, and lightweight LoRa stack.

## What The Layer Adds

- Fixed UAV roles: Drone1 Scout, Drone2 Relay, Drone3 Designator.
- One deterministic moving target named `audisys_target`.
- Task creation without task allocation.
- Radio observations copied from the existing LoRa packet log.
- Structured AuDiSys logs in `logs/audisys/`.

## Run

```sh
cd /Users/omsingh/Desktop/projects/multi_uav_lora_sim
GAZEBO_GUI=1 scripts/start_audisys_simulation.sh
```

Useful runtime overrides:

```sh
AUDISYS_DURATION=600 AUDISYS_SPEED=18 GAZEBO_GUI=1 scripts/start_audisys_simulation.sh
```

For a shorter deterministic handoff/reproducibility run that creates task events quickly:

```sh
AUDISYS_DURATION=90 AUDISYS_PROFILE=visible_terrain GAZEBO_GUI=0 scripts/start_audisys_simulation.sh
```

To stop:

```sh
cd /Users/omsingh/Desktop/projects/multi_uav_lora_sim
scripts/stop_audisys_simulation.sh
```

## Logs

- `logs/audisys/uav_state.csv`
- `logs/audisys/target_state.csv`
- `logs/audisys/radio.csv`
- `logs/audisys/tasks.csv`
- `logs/audisys/events.csv`
- `logs/audisys/allocation_messages.csv`
- `logs/audisys/scenario.log`
- `logs/audisys/flight_positions.csv`
- `logs/audisys/flight_mission.log`

## Observer Cameras

Four fixed camera sensors are available in the Gazebo world:

- `audisys_camera_overhead_wide`
- `audisys_camera_uav_base`
- `audisys_camera_border_checkpoint`
- `audisys_camera_target_zone`

Open camera streams with:

```sh
scripts/show_audisys_camera.sh overhead
scripts/show_audisys_camera.sh base
scripts/show_audisys_camera.sh checkpoint
scripts/show_audisys_camera.sh target
```

## Task Logic

- `DETECTION`: created when the Scout is within the configured target detection radius.
- `TRACKING`: created after detection remains valid for the configured confirmation time.
- `RELAY`: created when the configured Drone1 to Drone3 link is no longer NORMAL.
- `DESIGNATION`: created after tracking has lasted long enough and the Designator is within the configured range.

The layer does not assign tasks to UAVs.

## Configuration

All roles, target route, task thresholds, radio thresholds, and log locations are in `config/audisys_scenario.yaml`.

## Task 3 Reproducibility Evidence

Task 3 was completed on 2026-09-08 with:

```sh
./scripts/task3_reproducibility_check.py --runs 3 --duration 90
```

Result: PASS.

- Three clean starts completed.
- Three UAVs operated and wrote movement logs.
- Task order was consistent across all runs: `RELAY`, `DETECTION`, `TRACKING`, `DESIGNATION`.
- Radio-condition transition order was consistent across all runs.
- All expected CSV logs were generated and parseable.
- Shutdown left no stale project-tracked PX4/Gazebo/LoRa/scenario processes.

Evidence is saved in:

- `artifacts/task3/summary.json`
- `artifacts/task3/run_1/`
- `artifacts/task3/run_2/`
- `artifacts/task3/run_3/`

## Current Limitations

- The target is a deterministic scripted surrogate, not a computer-vision detection target.
- Task creation uses configured geometric/radio thresholds.
- No final task allocation algorithm is included.
- Task 3 validates repeatability for a 90-second handoff scenario, not a final publication-scale statistical campaign.
