# Task 2 Test

Status: implementation prepared.

Expected logs:

- `logs/audisys/uav_state.csv`
- `logs/audisys/radio.csv`
- `logs/audisys/tasks.csv`
- `logs/audisys/events.csv`
- `logs/audisys/allocation_messages.csv`

Expected task events:

- DETECTION
- TRACKING
- RELAY
- DESIGNATION

Runtime test still required:

- Run the full scenario and confirm the task sequence appears in `tasks.csv` and `events.csv`.
- Confirm radio conditions include observable NORMAL, DEGRADED, or OBSTRUCTED states as configured.
