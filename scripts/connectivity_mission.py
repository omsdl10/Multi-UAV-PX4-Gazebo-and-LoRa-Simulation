#!/usr/bin/env python3
import argparse
import math
import sys
import time

from pymavlink import mavutil


def heartbeat(conn):
    conn.mav.heartbeat_send(
        mavutil.mavlink.MAV_TYPE_GCS,
        mavutil.mavlink.MAV_AUTOPILOT_INVALID,
        0,
        0,
        mavutil.mavlink.MAV_STATE_ACTIVE,
    )


def wait_systems(conn, systems, timeout=60):
    deadline = time.time() + timeout
    seen = set()
    while time.time() < deadline and seen != set(systems):
        heartbeat(conn)
        msg = conn.recv_match(type="HEARTBEAT", blocking=True, timeout=1)
        if msg and msg.get_srcSystem() in systems:
            seen.add(msg.get_srcSystem())
            print(f"system {msg.get_srcSystem()}: heartbeat")
    missing = set(systems) - seen
    if missing:
        raise RuntimeError(f"missing systems: {sorted(missing)}")


def command(conn, sysid, command_id, params, timeout=10):
    params = list(params) + [0.0] * (7 - len(params))
    conn.mav.command_long_send(sysid, 1, command_id, 0, *params[:7])
    deadline = time.time() + timeout
    while time.time() < deadline:
        heartbeat(conn)
        msg = conn.recv_match(type="COMMAND_ACK", blocking=True, timeout=0.5)
        if msg and msg.get_srcSystem() == sysid and msg.command == command_id:
            if msg.result not in (mavutil.mavlink.MAV_RESULT_ACCEPTED, mavutil.mavlink.MAV_RESULT_IN_PROGRESS):
                raise RuntimeError(f"system {sysid}: command {command_id} rejected result={msg.result}")
            return
    raise RuntimeError(f"system {sysid}: command {command_id} timed out")


def get_global(conn, sysid, timeout=10):
    deadline = time.time() + timeout
    while time.time() < deadline:
        heartbeat(conn)
        msg = conn.recv_match(type="GLOBAL_POSITION_INT", blocking=True, timeout=0.5)
        if msg and msg.get_srcSystem() == sysid:
            return msg.lat / 1e7, msg.lon / 1e7, msg.alt / 1000.0, msg.relative_alt / 1000.0
    raise RuntimeError(f"system {sysid}: no global position")


def offset_latlon(lat, lon, north_m, east_m):
    radius = 6_378_137.0
    new_lat = lat + (north_m / radius) * 180.0 / math.pi
    new_lon = lon + (east_m / (radius * math.cos(math.radians(lat)))) * 180.0 / math.pi
    return new_lat, new_lon


def arm_takeoff(conn, sysid, altitude):
    lat, lon, amsl, _rel = get_global(conn, sysid)
    command(conn, sysid, mavutil.mavlink.MAV_CMD_COMPONENT_ARM_DISARM, [1, 0, 0, 0, 0, 0, 0])
    command(conn, sysid, mavutil.mavlink.MAV_CMD_NAV_TAKEOFF, [0, 0, 0, math.nan, math.nan, math.nan, amsl + altitude])


def reposition(conn, sysid, east_m, north_m, rel_alt):
    lat, lon, amsl, _rel = get_global(conn, sysid)
    target_lat, target_lon = offset_latlon(lat, lon, north_m, east_m)
    command(
        conn,
        sysid,
        mavutil.mavlink.MAV_CMD_DO_REPOSITION,
        [-1, mavutil.mavlink.MAV_DO_REPOSITION_FLAGS_CHANGE_MODE, 0, math.nan, target_lat, target_lon, amsl + rel_alt],
    )


def main():
    parser = argparse.ArgumentParser(description="Connectivity-aware three-UAV mission starter.")
    parser.add_argument("--endpoint", default="udpin:0.0.0.0:14550")
    parser.add_argument("--altitude", type=float, default=60)
    parser.add_argument("--d1-east", type=float, default=-1200)
    parser.add_argument("--d2-east", type=float, default=0)
    parser.add_argument("--d3-east", type=float, default=1200)
    parser.add_argument("--north", type=float, default=800)
    args = parser.parse_args()
    conn = mavutil.mavlink_connection(args.endpoint, source_system=253, source_component=190)
    systems = [1, 2, 3]
    wait_systems(conn, systems)
    for sysid in systems:
        arm_takeoff(conn, sysid, args.altitude)
    time.sleep(10)
    reposition(conn, 1, args.d1_east, args.north, args.altitude)
    reposition(conn, 2, args.d2_east, 0, args.altitude)
    reposition(conn, 3, args.d3_east, args.north, args.altitude)
    print("Connectivity mission commands sent. Watch logs/topology_changes.csv for relay/topology changes.")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
