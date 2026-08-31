#!/usr/bin/env python3
import argparse
import math
import sys
import time

from pymavlink import mavutil


MAV_FRAME_LOCAL_NED = 1


def wait_for_systems(conn, system_ids, timeout):
    deadline = time.time() + timeout
    seen = {}

    while time.time() < deadline and set(seen) != set(system_ids):
        msg = conn.recv_match(type="HEARTBEAT", blocking=True, timeout=1)
        if not msg:
            send_gcs_heartbeat(conn)
            continue

        sysid = msg.get_srcSystem()
        if sysid in system_ids:
            seen[sysid] = msg
            print(f"system {sysid}: heartbeat")

    missing = sorted(set(system_ids) - set(seen))
    if missing:
        raise RuntimeError(f"missing heartbeat from system(s): {missing}")


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
    conn.mav.command_long_send(
        sysid,
        1,
        command,
        0,
        *padded[:7],
    )

    deadline = time.time() + timeout
    while time.time() < deadline:
        send_gcs_heartbeat(conn)
        msg = conn.recv_match(type="COMMAND_ACK", blocking=True, timeout=0.5)
        if not msg:
            continue
        if msg.get_srcSystem() == sysid and msg.command == command:
            if msg.result not in (
                mavutil.mavlink.MAV_RESULT_ACCEPTED,
                mavutil.mavlink.MAV_RESULT_IN_PROGRESS,
            ):
                raise RuntimeError(f"system {sysid}: command {command} rejected with result {msg.result}")
            return msg

    raise RuntimeError(f"system {sysid}: command {command} timed out")


def armed_from_heartbeat(msg):
    return bool(msg.base_mode & mavutil.mavlink.MAV_MODE_FLAG_SAFETY_ARMED)


def wait_armed(conn, sysid, desired, timeout=15):
    deadline = time.time() + timeout
    while time.time() < deadline:
        send_gcs_heartbeat(conn)
        msg = conn.recv_match(type="HEARTBEAT", blocking=True, timeout=0.5)
        if msg and msg.get_srcSystem() == sysid and armed_from_heartbeat(msg) == desired:
            return
    raise RuntimeError(f"system {sysid}: armed={desired} not observed")


def wait_altitude(conn, sysid, target_m, tolerance_m=2.0, timeout=70):
    deadline = time.time() + timeout
    best = None

    while time.time() < deadline:
        send_gcs_heartbeat(conn)
        msg = conn.recv_match(type="GLOBAL_POSITION_INT", blocking=True, timeout=0.5)
        if not msg or msg.get_srcSystem() != sysid:
            continue

        alt_m = msg.relative_alt / 1000.0
        best = alt_m
        if abs(alt_m - target_m) <= tolerance_m:
            print(f"system {sysid}: reached {alt_m:.1f} m")
            return alt_m

    raise RuntimeError(f"system {sysid}: altitude target {target_m} m not reached; last={best}")


def get_relative_altitude(conn, sysid, timeout=15):
    deadline = time.time() + timeout
    while time.time() < deadline:
        send_gcs_heartbeat(conn)
        msg = conn.recv_match(type="GLOBAL_POSITION_INT", blocking=True, timeout=0.5)
        if msg and msg.get_srcSystem() == sysid:
            return msg.relative_alt / 1000.0
    raise RuntimeError(f"system {sysid}: no relative altitude received")


def get_amsl_altitude(conn, sysid, timeout=15):
    deadline = time.time() + timeout
    while time.time() < deadline:
        send_gcs_heartbeat(conn)
        msg = conn.recv_match(type="GLOBAL_POSITION_INT", blocking=True, timeout=0.5)
        if msg and msg.get_srcSystem() == sysid:
            return msg.alt / 1000.0
    raise RuntimeError(f"system {sysid}: no AMSL altitude received")


def wait_landed(conn, sysid, timeout=90):
    deadline = time.time() + timeout

    while time.time() < deadline:
        send_gcs_heartbeat(conn)
        msg = conn.recv_match(type="EXTENDED_SYS_STATE", blocking=True, timeout=0.5)
        if not msg or msg.get_srcSystem() != sysid:
            continue
        if msg.landed_state == mavutil.mavlink.MAV_LANDED_STATE_ON_GROUND:
            print(f"system {sysid}: landed")
            return

    raise RuntimeError(f"system {sysid}: landing not observed")


def request_streams(conn, sysid):
    for msg_id, hz in (
        (mavutil.mavlink.MAVLINK_MSG_ID_GLOBAL_POSITION_INT, 10),
        (mavutil.mavlink.MAVLINK_MSG_ID_EXTENDED_SYS_STATE, 2),
    ):
        command_long(
            conn,
            sysid,
            mavutil.mavlink.MAV_CMD_SET_MESSAGE_INTERVAL,
            [msg_id, 1_000_000 / hz, 0, 0, 0, 0, 0],
            timeout=5,
        )


def configure_vehicle(conn, sysid):
    print(f"system {sysid}: configuring telemetry")
    request_streams(conn, sysid)


def arm_vehicle(conn, sysid):
    print(f"system {sysid}: arming")
    command_long(conn, sysid, mavutil.mavlink.MAV_CMD_COMPONENT_ARM_DISARM, [1, 0, 0, 0, 0, 0, 0])
    wait_armed(conn, sysid, True)


def takeoff_vehicle(conn, sysid, relative_altitude):
    amsl_target = get_amsl_altitude(conn, sysid) + relative_altitude
    print(f"system {sysid}: takeoff to {relative_altitude} m AGL")
    command_long(conn, sysid, mavutil.mavlink.MAV_CMD_NAV_TAKEOFF, [0, 0, 0, math.nan, math.nan, math.nan, amsl_target])


def verify_hover(conn, sysid, altitude):
    wait_altitude(conn, sysid, altitude)
    print(f"system {sysid}: hover verified")


def land_vehicle(conn, sysid):
    print(f"system {sysid}: landing")
    command_long(conn, sysid, mavutil.mavlink.MAV_CMD_NAV_LAND, [0, 0, 0, math.nan, 0, 0, 0])
    wait_landed(conn, sysid)
    wait_armed(conn, sysid, False, timeout=30)


def test_vehicle(conn, sysid, altitude, land):
    configure_vehicle(conn, sysid)
    arm_vehicle(conn, sysid)
    takeoff_vehicle(conn, sysid, altitude)
    verify_hover(conn, sysid, altitude)

    if land:
        land_vehicle(conn, sysid)


def main():
    parser = argparse.ArgumentParser(description="PX4 MAVLink arm/takeoff/land verification.")
    parser.add_argument("--endpoint", default="udpin:0.0.0.0:14550")
    parser.add_argument("--systems", nargs="+", type=int, required=True)
    parser.add_argument("--altitudes", nargs="+", type=float, required=True)
    parser.add_argument("--no-land", action="store_true")
    args = parser.parse_args()

    if len(args.systems) != len(args.altitudes):
        parser.error("--systems and --altitudes must have the same count")

    conn = mavutil.mavlink_connection(args.endpoint, source_system=255, source_component=190)
    send_gcs_heartbeat(conn)
    wait_for_systems(conn, args.systems, timeout=60)

    if len(args.systems) == 1:
        test_vehicle(conn, args.systems[0], args.altitudes[0], land=not args.no_land)
    else:
        for sysid in args.systems:
            configure_vehicle(conn, sysid)
        for sysid in args.systems:
            arm_vehicle(conn, sysid)
        for sysid, altitude in zip(args.systems, args.altitudes):
            takeoff_vehicle(conn, sysid, altitude)
        for sysid, altitude in zip(args.systems, args.altitudes):
            verify_hover(conn, sysid, altitude)
        if not args.no_land:
            for sysid in args.systems:
                land_vehicle(conn, sysid)

    print("flight test complete")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
