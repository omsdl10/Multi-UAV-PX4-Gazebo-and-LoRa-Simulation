#!/usr/bin/env python3
import argparse
import csv
import math
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

from pymavlink import mavutil


@dataclass
class VehicleState:
    sysid: int
    timestamp: float = 0.0
    latitude: float = 0.0
    longitude: float = 0.0
    amsl_altitude: float = 0.0
    altitude: float = 0.0
    x: float = 0.0
    y: float = 0.0
    z: float = 0.0
    velocity: float = 0.0
    battery: float = -1.0
    mode: str = "unknown"
    status: str = "unknown"
    armed: bool = False
    home_latitude: float = 0.0
    home_longitude: float = 0.0
    samples: int = 0
    last_message_time: float = field(default_factory=time.time)


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


CSV_COLUMNS = [
    "timestamp",
    "elapsed_s",
    "drone_id",
    "latitude",
    "longitude",
    "altitude_m",
    "x_m",
    "y_m",
    "z_m",
    "velocity_m_s",
    "battery_percent",
    "mode",
    "status",
    "armed",
    "peer_positions_sent",
    "recent_lora_packets",
    "rssi_to_drone1_dbm",
    "rssi_to_drone2_dbm",
    "rssi_to_drone3_dbm",
    "snr_to_drone1_db",
    "snr_to_drone2_db",
    "snr_to_drone3_db",
    "link_status_to_drone1",
    "link_status_to_drone2",
    "link_status_to_drone3",
]


def send_gcs_heartbeat(conn):
    conn.mav.heartbeat_send(
        mavutil.mavlink.MAV_TYPE_GCS,
        mavutil.mavlink.MAV_AUTOPILOT_INVALID,
        0,
        0,
        mavutil.mavlink.MAV_STATE_ACTIVE,
    )


def command_long(conn, sysid, command, params=None, timeout=10):
    params = params or []
    padded = list(params) + [0.0] * (7 - len(params))
    conn.mav.command_long_send(sysid, 1, command, 0, *padded[:7])
    deadline = time.time() + timeout
    while time.time() < deadline:
        send_gcs_heartbeat(conn)
        msg = conn.recv_match(type="COMMAND_ACK", blocking=True, timeout=0.5)
        if msg and msg.get_srcSystem() == sysid and msg.command == command:
            accepted = (
                mavutil.mavlink.MAV_RESULT_ACCEPTED,
                mavutil.mavlink.MAV_RESULT_IN_PROGRESS,
            )
            if msg.result not in accepted:
                raise RuntimeError(f"system {sysid}: command {command} rejected with result {msg.result}")
            return
    raise RuntimeError(f"system {sysid}: command {command} timed out")


def wait_for_systems(conns, system_ids, timeout=60):
    seen = set()
    deadline = time.time() + timeout
    while time.time() < deadline and seen != set(system_ids):
        for conn in conns.values():
            send_gcs_heartbeat(conn)
        for sysid, conn in conns.items():
            msg = conn.recv_match(type="HEARTBEAT", blocking=False)
            if msg and msg.get_srcSystem() == sysid:
                seen.add(sysid)
                print(f"system {sysid}: heartbeat")
        time.sleep(0.1)
    missing = sorted(set(system_ids) - seen)
    if missing:
        raise RuntimeError(f"missing heartbeat from system(s): {missing}")


def update_state_from_msg(states, msg):
    sysid = msg.get_srcSystem()
    if sysid not in states:
        return
    state = states[sysid]
    msg_type = msg.get_type()
    now = time.time()
    if msg_type == "HEARTBEAT":
        state.mode = mavutil.mode_string_v10(msg)
        state.status = STATUS_BY_STATE.get(msg.system_status, str(msg.system_status))
        state.armed = bool(msg.base_mode & mavutil.mavlink.MAV_MODE_FLAG_SAFETY_ARMED)
    elif msg_type == "GLOBAL_POSITION_INT":
        state.latitude = msg.lat / 1e7
        state.longitude = msg.lon / 1e7
        state.amsl_altitude = msg.alt / 1000.0
        state.altitude = msg.relative_alt / 1000.0
        state.z = state.altitude
        state.timestamp = now
        state.samples += 1
        state.last_message_time = now
    elif msg_type == "LOCAL_POSITION_NED":
        state.x = float(msg.x)
        state.y = float(msg.y)
        state.z = -float(msg.z)
        state.velocity = math.sqrt(float(msg.vx) ** 2 + float(msg.vy) ** 2 + float(msg.vz) ** 2)
        state.timestamp = now
        state.samples += 1
        state.last_message_time = now
    elif msg_type in ("SYS_STATUS", "BATTERY_STATUS"):
        if getattr(msg, "battery_remaining", -1) != -1:
            state.battery = float(msg.battery_remaining)


def drain_messages(conns, states, duration_s):
    deadline = time.time() + duration_s
    while time.time() < deadline:
        for conn in conns.values():
            send_gcs_heartbeat(conn)
        for conn in conns.values():
            while True:
                msg = conn.recv_match(blocking=False)
                if not msg:
                    break
                update_state_from_msg(states, msg)
        time.sleep(0.05)


def request_streams(conn, sysid):
    for msg_id, hz in (
        (mavutil.mavlink.MAVLINK_MSG_ID_HEARTBEAT, 1),
        (mavutil.mavlink.MAVLINK_MSG_ID_GLOBAL_POSITION_INT, 10),
        (mavutil.mavlink.MAVLINK_MSG_ID_LOCAL_POSITION_NED, 10),
        (mavutil.mavlink.MAVLINK_MSG_ID_SYS_STATUS, 1),
    ):
        try:
            command_long(
                conn,
                sysid,
                mavutil.mavlink.MAV_CMD_SET_MESSAGE_INTERVAL,
                [msg_id, 1_000_000 / hz, 0, 0, 0, 0, 0],
                timeout=5,
            )
        except Exception as exc:
            print(f"system {sysid}: telemetry interval request for msg {msg_id} skipped: {exc}")


def set_ground_speed(conn, sysid, speed_m_s):
    if speed_m_s <= 0:
        return
    print(f"system {sysid}: set ground speed to {speed_m_s:.1f} m/s")
    try:
        command_long(
            conn,
            sysid,
            mavutil.mavlink.MAV_CMD_DO_CHANGE_SPEED,
            [1, speed_m_s, -1, 0, 0, 0, 0],
            timeout=5,
        )
    except Exception as exc:
        print(f"system {sysid}: speed command skipped: {exc}")


def wait_altitude(conns, states, sysid, target_m, timeout=45, tolerance=3.0):
    deadline = time.time() + timeout
    best = None
    while time.time() < deadline:
        drain_messages(conns, states, 0.2)
        best = states[sysid].altitude
        if best >= target_m - tolerance:
            print(f"system {sysid}: airborne at {best:.1f} m")
            return
    raise RuntimeError(f"system {sysid}: takeoff altitude not reached; last={best:.1f} m")


def arm_and_takeoff(conn, conns, states, sysid, altitude_m):
    print(f"system {sysid}: arm and takeoff to {altitude_m:.1f} m")
    command_long(conn, sysid, mavutil.mavlink.MAV_CMD_COMPONENT_ARM_DISARM, [1, 0, 0, 0, 0, 0, 0])
    drain_messages(conns, states, 1.0)
    amsl_target = states[sysid].amsl_altitude + altitude_m
    try:
        command_long(conn, sysid, mavutil.mavlink.MAV_CMD_NAV_TAKEOFF, [0, 0, 0, math.nan, math.nan, math.nan, amsl_target])
    except Exception as exc:
        print(f"system {sysid}: takeoff acknowledgement missing, verifying altitude instead: {exc}")


def offset_latlon(lat, lon, north_m, east_m):
    radius = 6_378_137.0
    new_lat = lat + (north_m / radius) * 180.0 / math.pi
    new_lon = lon + (east_m / (radius * math.cos(math.radians(lat)))) * 180.0 / math.pi
    return new_lat, new_lon


def reposition_from_home(conn, state, east_m, north_m, rel_alt_m, speed_m_s=0.0):
    reference_lat = state.home_latitude or state.latitude
    reference_lon = state.home_longitude or state.longitude
    target_lat, target_lon = offset_latlon(reference_lat, reference_lon, north_m, east_m)
    target_amsl = state.amsl_altitude - state.altitude + rel_alt_m
    command_long(
        conn,
        state.sysid,
        mavutil.mavlink.MAV_CMD_DO_REPOSITION,
        [
            speed_m_s if speed_m_s > 0 else -1,
            mavutil.mavlink.MAV_DO_REPOSITION_FLAGS_CHANGE_MODE,
            0,
            math.nan,
            target_lat,
            target_lon,
            target_amsl,
        ],
        timeout=5,
    )


def write_snapshot(writer, start_time, states, recent_lora_packets, latest_links):
    now = time.time()
    for sysid in sorted(states):
        state = states[sysid]
        row = {
            "timestamp": f"{now:.3f}",
            "elapsed_s": f"{now - start_time:.1f}",
            "drone_id": sysid,
            "latitude": f"{state.latitude:.8f}",
            "longitude": f"{state.longitude:.8f}",
            "altitude_m": f"{state.altitude:.3f}",
            "x_m": f"{state.x:.3f}",
            "y_m": f"{state.y:.3f}",
            "z_m": f"{state.z:.3f}",
            "velocity_m_s": f"{state.velocity:.3f}",
            "battery_percent": f"{state.battery:.1f}",
            "mode": state.mode,
            "status": state.status,
            "armed": int(state.armed),
            "peer_positions_sent": "1",
            "recent_lora_packets": recent_lora_packets,
        }
        for peer_id in sorted(states):
            link = latest_links.get((sysid, peer_id), {})
            row[f"rssi_to_drone{peer_id}_dbm"] = link.get("RSSI", "") if peer_id != sysid else ""
            row[f"snr_to_drone{peer_id}_db"] = link.get("SNR", "") if peer_id != sysid else ""
            row[f"link_status_to_drone{peer_id}"] = link.get("packet_status", "") if peer_id != sysid else ""
        writer.writerow(row)


def count_recent_lora_packets(packet_csv, start_time):
    if not packet_csv.exists():
        return 0
    count = 0
    try:
        with packet_csv.open() as f:
            for row in csv.DictReader(f):
                try:
                    if float(row["timestamp"]) >= start_time:
                        count += 1
                except (KeyError, ValueError):
                    continue
    except OSError:
        return 0
    return count


def latest_lora_links(packet_csv, start_time):
    latest = {}
    if not packet_csv.exists():
        return latest
    try:
        with packet_csv.open() as f:
            for row in csv.DictReader(f):
                try:
                    timestamp = float(row["timestamp"])
                    sender = int(row["sender"])
                    receiver = int(row["receiver"])
                except (KeyError, ValueError):
                    continue
                if timestamp >= start_time:
                    latest[(sender, receiver)] = row
    except OSError:
        return {}
    return latest


def mission_targets(profile, altitude_m):
    if profile == "close":
        return {
            1: [(-8, 0, altitude_m), (-10, 10, altitude_m), (-4, 18, altitude_m), (-12, 6, altitude_m)],
            2: [(0, 0, altitude_m + 2), (0, 12, altitude_m + 2), (8, 20, altitude_m + 2), (0, 8, altitude_m + 2)],
            3: [(8, 0, altitude_m + 4), (10, 10, altitude_m + 4), (16, 18, altitude_m + 4), (12, 6, altitude_m + 4)],
        }
    if profile == "visible_terrain":
        return {
            1: [(-80, 40, altitude_m), (-160, 120, altitude_m), (-240, 200, altitude_m), (-320, 280, altitude_m)],
            2: [(0, -60, altitude_m + 5), (40, -160, altitude_m + 5), (80, -260, altitude_m + 5), (120, -360, altitude_m + 5)],
            3: [(80, 40, altitude_m + 10), (180, 120, altitude_m + 10), (280, 200, altitude_m + 10), (380, 280, altitude_m + 10)],
        }
    if profile == "focus_drone1":
        return {
            1: [(-100, 80, altitude_m), (-220, 180, altitude_m), (-360, 300, altitude_m), (-520, 420, altitude_m)],
            2: [(0, -50, altitude_m + 5), (30, -90, altitude_m + 5), (60, -130, altitude_m + 5), (90, -170, altitude_m + 5)],
            3: [(90, 30, altitude_m + 10), (140, 60, altitude_m + 10), (190, 90, altitude_m + 10), (240, 120, altitude_m + 10)],
        }
    if profile == "focus_drone2":
        return {
            1: [(-80, 30, altitude_m), (-130, 60, altitude_m), (-180, 90, altitude_m), (-230, 120, altitude_m)],
            2: [(40, -120, altitude_m + 5), (100, -260, altitude_m + 5), (180, -420, altitude_m + 5), (260, -620, altitude_m + 5)],
            3: [(80, 40, altitude_m + 10), (130, 80, altitude_m + 10), (180, 120, altitude_m + 10), (230, 160, altitude_m + 10)],
        }
    if profile == "focus_drone3":
        return {
            1: [(-90, 20, altitude_m), (-140, 40, altitude_m), (-190, 60, altitude_m), (-240, 80, altitude_m)],
            2: [(0, -80, altitude_m + 5), (40, -120, altitude_m + 5), (80, -160, altitude_m + 5), (120, -200, altitude_m + 5)],
            3: [(120, 80, altitude_m + 10), (280, 180, altitude_m + 10), (460, 300, altitude_m + 10), (680, 440, altitude_m + 10)],
        }
    if profile == "all_directions":
        return {
            1: [(-120, 120, altitude_m), (-280, 260, altitude_m), (-480, 420, altitude_m), (-720, 620, altitude_m)],
            2: [(40, -160, altitude_m + 5), (120, -360, altitude_m + 5), (220, -620, altitude_m + 5), (340, -920, altitude_m + 5)],
            3: [(160, 100, altitude_m + 10), (380, 240, altitude_m + 10), (660, 420, altitude_m + 10), (980, 640, altitude_m + 10)],
        }
    if profile == "whole_area":
        return {
            1: [
                (-2200, 1800, altitude_m + 55), (-1400, 2260, altitude_m + 80),
                (-300, 1800, altitude_m + 65), (900, 2160, altitude_m + 85),
                (2140, 1180, altitude_m + 60), (2260, 120, altitude_m + 55),
                (1500, -1180, altitude_m + 50), (460, -2140, altitude_m + 55),
                (-920, -1780, altitude_m + 45), (-2140, -980, altitude_m + 48),
                (-2260, 160, altitude_m + 58), (-1560, 960, altitude_m + 72),
            ],
            2: [
                (-1800, 1080, altitude_m + 65), (-780, 1480, altitude_m + 75),
                (120, 260, altitude_m + 48), (980, 60, altitude_m + 52),
                (2100, 540, altitude_m + 65), (1740, 1560, altitude_m + 78),
                (640, 2240, altitude_m + 82), (-540, 2020, altitude_m + 76),
                (-1660, 740, altitude_m + 60), (-760, -720, altitude_m + 45),
                (520, -1540, altitude_m + 52), (1880, -1800, altitude_m + 56),
            ],
            3: [
                (2200, -1620, altitude_m + 58), (1440, -920, altitude_m + 50),
                (420, -460, altitude_m + 45), (-680, -720, altitude_m + 48),
                (-1760, -1420, altitude_m + 56), (-2240, -120, altitude_m + 62),
                (-1840, 1320, altitude_m + 76), (-760, 2260, altitude_m + 88),
                (520, 1880, altitude_m + 70), (1580, 960, altitude_m + 66),
                (2240, -40, altitude_m + 60), (860, -2060, altitude_m + 54),
            ],
        }
    return {
        1: [(-180, 120, altitude_m), (-360, 260, altitude_m), (-520, 360, altitude_m)],
        2: [(0, -160, altitude_m + 5), (80, -360, altitude_m + 5), (0, -560, altitude_m + 5)],
        3: [(180, 120, altitude_m + 10), (380, 220, altitude_m + 10), (560, 340, altitude_m + 10)],
    }


def run_collection(conns, states, output_csv, lora_packet_csv, duration_s, altitude_m, profile, speed_m_s=0.0):
    targets = mission_targets(profile, altitude_m)
    output_csv.parent.mkdir(parents=True, exist_ok=True)
    start_time = time.time()
    next_sample = start_time
    next_target = start_time
    target_interval_s = 50.0 if profile == "whole_area" else 20.0
    target_index = 0
    with output_csv.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS)
        writer.writeheader()
        while time.time() - start_time < duration_s:
            for conn in conns.values():
                send_gcs_heartbeat(conn)
            for conn in conns.values():
                while True:
                    msg = conn.recv_match(blocking=False)
                    if not msg:
                        break
                    update_state_from_msg(states, msg)

            now = time.time()
            if now >= next_target:
                for sysid, path in targets.items():
                    east_m, north_m, z_m = path[target_index % len(path)]
                    try:
                        reposition_from_home(conns[sysid], states[sysid], east_m, north_m, z_m, speed_m_s)
                        print(f"system {sysid}: new target east={east_m:.0f} north={north_m:.0f} alt={z_m:.0f}")
                    except Exception as exc:
                        print(f"system {sysid}: reposition skipped: {exc}")
                target_index += 1
                next_target = now + target_interval_s

            if now >= next_sample:
                recent_lora_packets = count_recent_lora_packets(lora_packet_csv, start_time)
                latest_links = latest_lora_links(lora_packet_csv, start_time)
                write_snapshot(writer, start_time, states, recent_lora_packets, latest_links)
                f.flush()
                print(f"logged {now - start_time:4.1f}s, LoRa packets this run: {recent_lora_packets}")
                next_sample = now + 1.0
            time.sleep(0.05)


def land_all(conns, systems):
    for sysid in systems:
        try:
            print(f"system {sysid}: land")
            command_long(conns[sysid], sysid, mavutil.mavlink.MAV_CMD_NAV_LAND, [0, 0, 0, math.nan, 0, 0, 0], timeout=5)
        except Exception as exc:
            print(f"system {sysid}: landing command failed: {exc}", file=sys.stderr)


def main():
    parser = argparse.ArgumentParser(description="Run a 60-second three-drone terrain movement and position-exchange capture.")
    parser.add_argument("--endpoint", default=None, help="single MAVLink endpoint; omitted uses per-drone PX4 ports")
    parser.add_argument("--ports", nargs=3, type=int, default=[14540, 14541, 14542])
    parser.add_argument("--duration", type=float, default=60.0)
    parser.add_argument("--altitude", type=float, default=35.0)
    parser.add_argument("--speed", type=float, default=0.0, help="optional PX4 ground speed command in m/s")
    parser.add_argument(
        "--profile",
        choices=[
            "terrain",
            "close",
            "visible_terrain",
            "focus_drone1",
            "focus_drone2",
            "focus_drone3",
            "all_directions",
            "whole_area",
        ],
        default="terrain",
    )
    parser.add_argument("--output", default="logs/one_minute_drone_positions.csv")
    parser.add_argument("--lora-packets", default="logs/lora_packets.csv")
    parser.add_argument("--no-land", action="store_true")
    args = parser.parse_args()

    systems = [1, 2, 3]
    states = {sysid: VehicleState(sysid=sysid) for sysid in systems}
    if args.endpoint:
        shared = mavutil.mavlink_connection(args.endpoint, source_system=252, source_component=190)
        conns = {sysid: shared for sysid in systems}
    else:
        conns = {
            sysid: mavutil.mavlink_connection(f"udpin:0.0.0.0:{port}", source_system=252, source_component=190)
            for sysid, port in zip(systems, args.ports)
        }
    for conn in conns.values():
        send_gcs_heartbeat(conn)
    wait_for_systems(conns, systems)
    for sysid in systems:
        request_streams(conns[sysid], sysid)
    for sysid in systems:
        set_ground_speed(conns[sysid], sysid, args.speed)
    drain_messages(conns, states, 3.0)
    for state in states.values():
        state.home_latitude = state.latitude
        state.home_longitude = state.longitude

    for sysid in systems:
        arm_and_takeoff(conns[sysid], conns, states, sysid, args.altitude + (sysid - 1) * 5.0)
    for sysid in systems:
        wait_altitude(conns, states, sysid, args.altitude + (sysid - 1) * 5.0)

    output_csv = Path(args.output)
    lora_packet_csv = Path(args.lora_packets)
    print(f"collecting moving drone positions for {args.duration:.0f}s into {output_csv}")
    run_collection(conns, states, output_csv, lora_packet_csv, args.duration, args.altitude, args.profile, args.speed)

    if not args.no_land:
        land_all(conns, systems)
    print(f"complete: {output_csv}")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
