#!/usr/bin/env python3
import argparse
import csv
import math
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path

import yaml
from pymavlink import mavutil


@dataclass
class UAVState:
    uav_id: int
    role: str
    capability: str
    port: int
    x: float = 0.0
    y: float = 0.0
    z: float = 0.0
    latitude: float = 0.0
    longitude: float = 0.0
    altitude: float = 0.0
    velocity: float = 0.0
    battery: float = -1.0
    mode: str = "unknown"
    status: str = "unknown"
    armed: bool = False
    last_update: float = 0.0


@dataclass
class Task:
    task_id: str
    task_type: str
    creation_time: float
    priority: int
    reward: float
    deadline: str
    required_capability: str
    target_id: str
    status: str = "CREATED"
    assigned_uav: str = ""
    completion_time: str = ""


@dataclass
class TargetRoute:
    points: list
    speed_mps: float
    segment_lengths: list = field(init=False)
    total_length: float = field(init=False)

    def __post_init__(self):
        self.segment_lengths = []
        for a, b in zip(self.points, self.points[1:]):
            self.segment_lengths.append(distance_xyz(a, b))
        self.total_length = sum(self.segment_lengths)

    def pose_at(self, elapsed_s):
        if not self.points:
            return 0.0, 0.0, 0.0, 0.0
        if len(self.points) == 1 or self.total_length <= 0:
            x, y, z = self.points[0]
            return x, y, z, 0.0
        progress = (elapsed_s * self.speed_mps) % self.total_length
        for index, length in enumerate(self.segment_lengths):
            if progress <= length:
                a = self.points[index]
                b = self.points[index + 1]
                t = progress / length if length else 0.0
                x = a[0] + (b[0] - a[0]) * t
                y = a[1] + (b[1] - a[1]) * t
                z = a[2] + (b[2] - a[2]) * t
                yaw = math.atan2(b[1] - a[1], b[0] - a[0])
                return x, y, z, yaw
            progress -= length
        x, y, z = self.points[-1]
        return x, y, z, 0.0


STATUS_BY_STATE = {
    mavutil.mavlink.MAV_STATE_UNINIT: "uninit",
    mavutil.mavlink.MAV_STATE_BOOT: "boot",
    mavutil.mavlink.MAV_STATE_CALIBRATING: "calibrating",
    mavutil.mavlink.MAV_STATE_STANDBY: "standby",
    mavutil.mavlink.MAV_STATE_ACTIVE: "active",
    mavutil.mavlink.MAV_STATE_CRITICAL: "critical",
    mavutil.mavlink.MAV_STATE_EMERGENCY: "emergency",
    mavutil.mavlink.MAV_STATE_POWEROFF: "poweroff",
}


def distance_xyz(a, b):
    return math.sqrt((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2 + (a[2] - b[2]) ** 2)


def load_yaml(path):
    with Path(path).open() as handle:
        return yaml.safe_load(handle)


def project_path(project_dir, path):
    value = Path(path)
    return value if value.is_absolute() else Path(project_dir) / value


def send_gcs_heartbeat(conn):
    conn.mav.heartbeat_send(
        mavutil.mavlink.MAV_TYPE_GCS,
        mavutil.mavlink.MAV_AUTOPILOT_INVALID,
        0,
        0,
        mavutil.mavlink.MAV_STATE_ACTIVE,
    )


def update_uav_from_message(state, msg):
    msg_type = msg.get_type()
    now = time.time()
    if msg_type == "HEARTBEAT":
        state.mode = mavutil.mode_string_v10(msg)
        state.status = STATUS_BY_STATE.get(msg.system_status, str(msg.system_status))
        state.armed = bool(msg.base_mode & mavutil.mavlink.MAV_MODE_FLAG_SAFETY_ARMED)
        state.last_update = now
    elif msg_type == "LOCAL_POSITION_NED":
        state.x = float(msg.x)
        state.y = float(msg.y)
        state.z = -float(msg.z)
        state.velocity = math.sqrt(float(msg.vx) ** 2 + float(msg.vy) ** 2 + float(msg.vz) ** 2)
        state.last_update = now
    elif msg_type == "GLOBAL_POSITION_INT":
        state.latitude = float(msg.lat) / 1e7
        state.longitude = float(msg.lon) / 1e7
        state.altitude = float(msg.relative_alt) / 1000.0
        state.last_update = now
    elif msg_type in ("SYS_STATUS", "BATTERY_STATUS") and getattr(msg, "battery_remaining", -1) != -1:
        state.battery = float(msg.battery_remaining)
        state.last_update = now


def drain_mavlink(connections, states):
    for conn in connections.values():
        send_gcs_heartbeat(conn)
    for uav_id, conn in connections.items():
        while True:
            msg = conn.recv_match(blocking=False)
            if not msg:
                break
            if msg.get_srcSystem() == uav_id:
                update_uav_from_message(states[uav_id], msg)


def set_gazebo_target_pose(world_name, model_name, x, y, z, yaw):
    request = (
        f'name: "{model_name}" '
        f'position {{ x: {x:.3f} y: {y:.3f} z: {z:.3f} }} '
        f'orientation {{ z: {math.sin(yaw / 2):.8f} w: {math.cos(yaw / 2):.8f} }}'
    )
    subprocess.run(
        [
            "gz",
            "service",
            "-s",
            f"/world/{world_name}/set_pose",
            "--reqtype",
            "gz.msgs.Pose",
            "--reptype",
            "gz.msgs.Boolean",
            "--timeout",
            "200",
            "--req",
            request,
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )


def read_new_radio_rows(path, offset):
    if not path.exists():
        return offset, []
    rows = []
    with path.open(newline="") as handle:
        handle.seek(offset)
        if offset == 0:
            header = handle.readline()
            offset = handle.tell()
            if not header:
                return offset, rows
        reader = csv.DictReader(handle, fieldnames=[
            "timestamp", "sender", "receiver", "sender_x", "sender_y", "sender_z",
            "receiver_x", "receiver_y", "receiver_z", "distance", "RSSI", "SNR",
            "LOS", "building_obstacles", "terrain_blocked", "packet_status",
            "drop_reason", "latency_ms", "packet_id", "source", "destination",
            "hop_count", "TTL",
        ])
        rows.extend(reader)
        offset = handle.tell()
    return offset, rows


def read_latest_flight_states(path, states):
    if not path.exists():
        return
    latest = {}
    try:
        with path.open(newline="") as handle:
            for row in csv.DictReader(handle):
                try:
                    latest[int(row["drone_id"])] = row
                except (KeyError, ValueError):
                    continue
    except OSError:
        return
    for uav_id, row in latest.items():
        if uav_id not in states:
            continue
        state = states[uav_id]
        try:
            state.x = float(row.get("x_m") or state.x)
            state.y = float(row.get("y_m") or state.y)
            state.z = float(row.get("z_m") or state.z)
            state.latitude = float(row.get("latitude") or state.latitude)
            state.longitude = float(row.get("longitude") or state.longitude)
            state.altitude = float(row.get("altitude_m") or state.altitude)
            state.velocity = float(row.get("velocity_m_s") or state.velocity)
            state.battery = float(row.get("battery_percent") or state.battery)
            state.mode = row.get("mode") or state.mode
            state.status = row.get("status") or state.status
            state.armed = row.get("armed") == "1"
            state.last_update = time.time()
        except ValueError:
            continue


def classify_radio(row, cfg, pdr):
    rssi = float(row.get("RSSI") or -999)
    snr = float(row.get("SNR") or -999)
    obstructed = row.get("LOS") == "0" or bool(row.get("building_obstacles")) or row.get("terrain_blocked") == "1"
    normal = cfg["normal"]
    degraded = cfg["degraded"]
    if obstructed:
        return "OBSTRUCTED"
    if rssi >= float(normal["rssi_threshold_dbm"]) and snr >= float(normal["snr_threshold_db"]) and pdr >= float(normal["pdr_threshold"]):
        return "NORMAL"
    if rssi >= float(degraded["rssi_threshold_dbm"]) and snr >= float(degraded["snr_threshold_db"]) and pdr >= float(degraded["pdr_threshold"]):
        return "DEGRADED"
    return "DEGRADED"


class ScenarioLogger:
    def __init__(self, logs_dir):
        self.logs_dir = Path(logs_dir)
        self.logs_dir.mkdir(parents=True, exist_ok=True)
        self.files = {}
        self.writers = {}
        self._open("uav_state", "uav_state.csv", [
            "time", "uav_id", "role", "x", "y", "z", "latitude", "longitude",
            "altitude", "velocity", "battery", "mode", "status", "armed",
        ])
        self._open("target", "target_state.csv", ["time", "target_id", "x", "y", "z", "yaw"])
        self._open("radio", "radio.csv", [
            "time", "source", "destination", "rssi_dbm", "snr_db", "packet_received",
            "pdr", "latency_ms", "drop_reason", "condition",
        ])
        self._open("tasks", "tasks.csv", [
            "time", "task_id", "task_type", "status", "priority", "reward",
            "deadline", "required_capability", "target_id", "assigned_uav", "completion_time",
        ])
        self._open("events", "events.csv", ["time", "event_type", "entity_id", "details"])
        self._open("allocation", "allocation_messages.csv", ["time", "message_type", "payload"])

    def _open(self, key, filename, columns):
        path = self.logs_dir / filename
        file_obj = path.open("w", newline="")
        writer = csv.DictWriter(file_obj, fieldnames=columns)
        writer.writeheader()
        file_obj.flush()
        self.files[key] = file_obj
        self.writers[key] = writer

    def row(self, key, values):
        self.writers[key].writerow(values)
        self.files[key].flush()

    def event(self, timestamp, event_type, entity_id, details):
        self.row("events", {
            "time": f"{timestamp:.3f}",
            "event_type": event_type,
            "entity_id": entity_id,
            "details": details,
        })

    def close(self):
        for file_obj in self.files.values():
            file_obj.close()


class TaskStore:
    def __init__(self, logger, target_id):
        self.logger = logger
        self.target_id = target_id
        self.tasks = {}
        self.counter = 0

    def create_once(self, task_type, timestamp, cfg):
        if task_type in self.tasks:
            return self.tasks[task_type]
        self.counter += 1
        task = Task(
            task_id=f"T{self.counter:03d}",
            task_type=task_type,
            creation_time=timestamp,
            priority=int(cfg["priority"]),
            reward=float(cfg.get("reward", 0)),
            deadline=str(cfg.get("deadline", "")),
            required_capability=str(cfg["required_capability"]),
            target_id=self.target_id,
        )
        self.tasks[task_type] = task
        self.logger.row("tasks", task_row(task))
        self.logger.event(timestamp, "TaskCreated", task.task_id, f"{task.task_type} created for {task.target_id}")
        return task


def task_row(task):
    return {
        "time": f"{task.creation_time:.3f}",
        "task_id": task.task_id,
        "task_type": task.task_type,
        "status": task.status,
        "priority": task.priority,
        "reward": task.reward,
        "deadline": task.deadline,
        "required_capability": task.required_capability,
        "target_id": task.target_id,
        "assigned_uav": task.assigned_uav,
        "completion_time": task.completion_time,
    }


def run(args):
    project_dir = Path(args.project_dir)
    cfg = load_yaml(args.config)
    logs_dir = project_path(project_dir, cfg["scenario"]["logs_dir"])
    logger = ScenarioLogger(logs_dir)
    route = TargetRoute([tuple(p) for p in cfg["target"]["route"]], float(cfg["target"]["speed_mps"]))
    states = {
        int(item["id"]): UAVState(
            uav_id=int(item["id"]),
            role=str(item["role"]),
            capability=str(item["capability"]),
            port=int(item["mavlink_port"]),
        )
        for item in cfg["uavs"]
    }
    state_source = cfg["scenario"].get("state_source", "mavlink")
    conns = {}
    if state_source == "mavlink":
        conns = {
            uav_id: mavutil.mavlink_connection(f"udpin:0.0.0.0:{state.port}", source_system=251, source_component=190)
            for uav_id, state in states.items()
        }
    flight_positions_csv = project_path(project_dir, cfg["scenario"].get("flight_positions_csv", "logs/audisys/flight_positions.csv"))
    task_store = TaskStore(logger, str(cfg["target"]["id"]))
    radio_csv = project_path(project_dir, cfg["communication"]["radio_csv"])
    radio_offset = radio_csv.stat().st_size if radio_csv.exists() else 0
    radio_window = []
    start = time.time()
    detection_started = None
    tracking_started = None
    last_allocation_log = 0.0
    step_s = 1.0 / float(cfg["scenario"]["update_rate_hz"])

    logger.event(start, "ScenarioStarted", "audisys", f"seed={cfg['scenario']['seed']}")
    try:
        while time.time() - start < float(args.duration or cfg["scenario"]["duration_s"]):
            now = time.time()
            elapsed = now - start
            if conns:
                drain_mavlink(conns, states)
            else:
                read_latest_flight_states(flight_positions_csv, states)
            tx, ty, tz, yaw = route.pose_at(elapsed)
            if cfg["target"].get("enabled", True):
                set_gazebo_target_pose(cfg["scenario"]["world_name"], cfg["target"]["model_name"], tx, ty, tz, yaw)
            logger.row("target", {
                "time": f"{now:.3f}",
                "target_id": cfg["target"]["id"],
                "x": f"{tx:.3f}",
                "y": f"{ty:.3f}",
                "z": f"{tz:.3f}",
                "yaw": f"{yaw:.3f}",
            })

            for state in states.values():
                logger.row("uav_state", {
                    "time": f"{now:.3f}",
                    "uav_id": state.uav_id,
                    "role": state.role,
                    "x": f"{state.x:.3f}",
                    "y": f"{state.y:.3f}",
                    "z": f"{state.z:.3f}",
                    "latitude": f"{state.latitude:.8f}",
                    "longitude": f"{state.longitude:.8f}",
                    "altitude": f"{state.altitude:.3f}",
                    "velocity": f"{state.velocity:.3f}",
                    "battery": f"{state.battery:.1f}",
                    "mode": state.mode,
                    "status": state.status,
                    "armed": int(state.armed),
                })
                logger.event(now, "UAVStateChanged", f"uav_{state.uav_id}", f"role={state.role}, x={state.x:.1f}, y={state.y:.1f}, z={state.z:.1f}")

            radio_offset, rows = read_new_radio_rows(radio_csv, radio_offset)
            for row in rows:
                if not row.get("sender"):
                    continue
                key = (row["sender"], row["receiver"])
                radio_window.append((key, row.get("packet_status") == "received"))
                radio_window = radio_window[-int(cfg["communication"]["pdr_window_packets"]):]
                pair_rows = [received for pair, received in radio_window if pair == key]
                pdr = sum(pair_rows) / len(pair_rows) if pair_rows else 0.0
                condition = classify_radio(row, cfg["communication"], pdr)
                logger.row("radio", {
                    "time": row["timestamp"],
                    "source": row["sender"],
                    "destination": row["receiver"],
                    "rssi_dbm": row["RSSI"],
                    "snr_db": row["SNR"],
                    "packet_received": int(row.get("packet_status") == "received"),
                    "pdr": f"{pdr:.3f}",
                    "latency_ms": row["latency_ms"],
                    "drop_reason": row["drop_reason"],
                    "condition": condition,
                })
                logger.event(now, "RadioObservation", f"{row['sender']}->{row['receiver']}", f"condition={condition}, rssi={row['RSSI']}, snr={row['SNR']}, pdr={pdr:.2f}")
                relay_cfg = cfg["tasks"]["relay"]
                if int(row["sender"]) == int(relay_cfg["link_source"]) and int(row["receiver"]) == int(relay_cfg["link_destination"]) and condition != "NORMAL":
                    task_store.create_once("RELAY", now, relay_cfg)

            scout = states[1]
            target_distance = distance_xyz((scout.x, scout.y, scout.z), (tx, ty, tz))
            if target_distance <= float(cfg["tasks"]["detection"]["detection_radius_m"]):
                if detection_started is None:
                    detection_started = now
                    task_store.create_once("DETECTION", now, cfg["tasks"]["detection"])
                if now - detection_started >= float(cfg["tasks"]["tracking"]["confirmation_s"]):
                    task_store.create_once("TRACKING", now, cfg["tasks"]["tracking"])
                    if tracking_started is None:
                        tracking_started = now

            if "TRACKING" in task_store.tasks:
                if tracking_started is None:
                    tracking_started = now
                designator = states[3]
                designator_distance = distance_xyz((designator.x, designator.y, designator.z), (tx, ty, tz))
                if (
                    now - tracking_started >= float(cfg["tasks"]["designation"]["tracking_required_s"])
                    and designator_distance <= float(cfg["tasks"]["designation"]["designator_radius_m"])
                ):
                    task_store.create_once("DESIGNATION", now, cfg["tasks"]["designation"])

            if cfg["allocation_interface"].get("enabled", True) and now - last_allocation_log >= 1.0:
                last_allocation_log = now
                open_tasks = [task.task_id for task in task_store.tasks.values() if not task.assigned_uav]
                logger.row("allocation", {
                    "time": f"{now:.3f}",
                    "message_type": "ObservationPublished",
                    "payload": f"open_tasks={open_tasks}; allocator_connected=false",
                })

            time.sleep(step_s)
    finally:
        logger.event(time.time(), "ScenarioStopped", "audisys", "runner exiting")
        logger.close()


def main():
    parser = argparse.ArgumentParser(description="AuDiSys scenario layer: target, task events, radio observations, and handoff logs.")
    parser.add_argument("--config", default="config/audisys_scenario.yaml")
    parser.add_argument("--project-dir", default=".")
    parser.add_argument("--duration", type=float, default=None)
    args = parser.parse_args()
    run(args)


if __name__ == "__main__":
    main()
