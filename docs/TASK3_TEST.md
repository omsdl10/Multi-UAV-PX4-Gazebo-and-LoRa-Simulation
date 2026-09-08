# Task 3 Test

Status: completed on 2026-09-08.

Task 3 covers reproducibility, robustness, and handoff readiness for the AuDiSys scenario layer.

## Command

```sh
cd /Users/omsingh/Desktop/projects/multi_uav_lora_sim
./scripts/task3_reproducibility_check.py --runs 3 --duration 90
```

The checker runs three clean headless starts with the same seed and configuration. For this evidence run it uses `AUDISYS_PROFILE=visible_terrain` so task creation happens within the 90-second window.

## Result

Overall status: PASS

- Run 1: PASS
- Run 2: PASS
- Run 3: PASS
- Task order consistent: PASS
- Radio-transition order consistent: PASS
- Stale project processes after shutdown: PASS
- Expected logs generated and parseable: PASS

## Evidence

Summary:

```text
artifacts/task3/summary.json
```

Copied run logs:

```text
artifacts/task3/run_1/
artifacts/task3/run_2/
artifacts/task3/run_3/
```

Each run includes:

- `uav_state.csv`
- `target_state.csv`
- `radio.csv`
- `tasks.csv`
- `events.csv`
- `allocation_messages.csv`
- `flight_positions.csv`
- `lora_packets.csv`
- `topology_changes.csv`
- `lora_metrics.json`
- `scenario.log`
- `flight_mission.log`
- `gazebo.log`

## Repeatability Summary

All three runs created the same task lifecycle:

```text
RELAY:CREATED
DETECTION:CREATED
TRACKING:CREATED
DESIGNATION:CREATED
```

All three runs used the same seed/configuration and produced the same major radio-condition transition order.

Packet totals and PDR were stable:

- Run 1: 970 packets, PDR 0.9134
- Run 2: 970 packets, PDR 0.9134
- Run 3: 970 packets, PDR 0.9134

## Notes

- The test is a reproducibility handoff run, not a final statistical experiment.
- The final task-allocation algorithm remains intentionally unimplemented.
- ROS 2 and ns-3 LoRaWAN remain optional integrations and are not required for this Task 3 pass.
