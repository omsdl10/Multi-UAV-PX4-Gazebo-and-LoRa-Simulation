#!/usr/bin/env python3
import argparse
import json
import math
import sys
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass
class VehicleSummary:
    namespace: str
    position: list
    velocity: list
    altitude: float
    battery: float
    flight_mode: str
    communication_status: str


def distance(a, b):
    return math.sqrt(sum((a.position[i] - b.position[i]) ** 2 for i in range(3)))


def main():
    parser = argparse.ArgumentParser(description="Optional ROS 2 multi-UAV state manager for PX4 topics.")
    parser.add_argument("--output", default="logs/ros2_multi_uav_state.json")
    parser.add_argument("--namespaces", nargs="+", default=["/drone1", "/drone2", "/drone3"])
    args = parser.parse_args()

    try:
        import rclpy
        from rclpy.node import Node
        from px4_msgs.msg import BatteryStatus, VehicleLocalPosition, VehicleStatus
    except Exception as exc:
        Path(args.output).parent.mkdir(parents=True, exist_ok=True)
        Path(args.output).write_text(json.dumps({
            "status": "unsupported",
            "reason": f"ROS 2/px4_msgs import failed: {exc}",
            "required": ["ros2", "rclpy", "px4_msgs", "MicroXRCEAgent"],
        }, indent=2) + "\n")
        print(f"ROS 2 manager unsupported on this machine: {exc}", file=sys.stderr)
        return 2

    class MultiUavManager(Node):
        def __init__(self):
            super().__init__("multi_uav_manager")
            self.states = {
                ns: VehicleSummary(ns, [0.0, 0.0, 0.0], [0.0, 0.0, 0.0], 0.0, -1.0, "unknown", "stale")
                for ns in args.namespaces
            }
            for ns in args.namespaces:
                self.create_subscription(VehicleLocalPosition, f"{ns}/fmu/out/vehicle_local_position", self.local_cb(ns), 10)
                self.create_subscription(BatteryStatus, f"{ns}/fmu/out/battery_status", self.battery_cb(ns), 10)
                self.create_subscription(VehicleStatus, f"{ns}/fmu/out/vehicle_status", self.status_cb(ns), 10)
            self.create_timer(1.0, self.write_state)

        def local_cb(self, ns):
            def cb(msg):
                state = self.states[ns]
                state.position = [float(msg.x), float(msg.y), -float(msg.z)]
                state.velocity = [float(msg.vx), float(msg.vy), float(msg.vz)]
                state.altitude = -float(msg.z)
                state.communication_status = "ok"
            return cb

        def battery_cb(self, ns):
            def cb(msg):
                self.states[ns].battery = float(getattr(msg, "remaining", -1.0))
            return cb

        def status_cb(self, ns):
            def cb(msg):
                self.states[ns].flight_mode = str(getattr(msg, "nav_state", "unknown"))
            return cb

        def write_state(self):
            states = list(self.states.values())
            pairwise = {}
            for i, a in enumerate(states):
                for b in states[i + 1:]:
                    pairwise[f"{a.namespace}-{b.namespace}"] = distance(a, b)
            Path(args.output).parent.mkdir(parents=True, exist_ok=True)
            Path(args.output).write_text(json.dumps({
                "status": "running",
                "vehicles": [asdict(s) for s in states],
                "pairwise_distances": pairwise,
            }, indent=2) + "\n")

    rclpy.init()
    node = MultiUavManager()
    try:
        rclpy.spin(node)
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    sys.exit(main())
