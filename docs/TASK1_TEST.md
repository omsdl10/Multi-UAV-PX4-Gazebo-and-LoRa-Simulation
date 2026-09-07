# Task 1 Test

Status: implementation prepared.

Acceptance items covered by files:

- 5 km x 5 km world: `gazebo/worlds/uav_5km_world.sdf`
- Three X500 UAVs: `scripts/start_simulation.sh`
- Stable IDs and model names: Drone1/System 1 `x500_0`, Drone2/System 2 `x500_1`, Drone3/System 3 `x500_2`
- Roles: `config/audisys_scenario.yaml`
- Deterministic target: `audisys_target` and scripted route in `config/audisys_scenario.yaml`
- Dedicated launcher: `scripts/start_audisys_simulation.sh`
- Shutdown: `scripts/stop_audisys_simulation.sh`

Runtime test still required after launch:

- Confirm target appears and moves in Gazebo.
- Confirm second clean run starts without manual cleanup.
- Confirm default `scripts/start_audisys_simulation.sh` flight mission starts after PX4 heartbeats are available.
