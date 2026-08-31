#!/usr/bin/env python3
import argparse
import json
import math
import random
import re
import select
import signal
import socket
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path

import yaml
from pymavlink import mavutil

from .channel import LoRaChannel
from .logger import PacketLogger
from .propagation import load_obstacles_from_sdf
from .routing import DuplicateFilter, new_packet


@dataclass
class DroneState:
    drone_id: int
    timestamp: float = 0.0
    x: float = 0.0
    y: float = 0.0
    z: float = 0.0
    latitude: float = 0.0
    longitude: float = 0.0
    altitude: float = 0.0
    velocity: float = 0.0
    battery: float = -1.0
    status: str = "unknown"
    has_global: bool = False


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


def load_config(path):
    with Path(path).open() as f:
        cfg = yaml.safe_load(f)
    return cfg


def resolve_project_path(project_dir, path):
    p = Path(path)
    return p if p.is_absolute() else Path(project_dir) / p


def latlon_to_xy(latitude, longitude, origin_latitude, origin_longitude):
    radius = 6_378_137.0
    lat = math.radians(latitude)
    lon = math.radians(longitude)
    origin_lat = math.radians(origin_latitude)
    origin_lon = math.radians(origin_longitude)
    x = (lon - origin_lon) * math.cos(origin_lat) * radius
    y = (lat - origin_lat) * radius
    return x, y


class NetworkManager:
    def __init__(self, config_path, project_dir):
        self.project_dir = Path(project_dir)
        self.config = load_config(config_path)
        self.network = self.config["network"]
        self.drone_ids = [int(v) for v in self.network["drone_ids"]]
        self.states = {drone_id: DroneState(drone_id=drone_id) for drone_id in self.drone_ids}
        self.network_mode = self.network.get("network_mode", "p2p")
        self.lorawan = self.config.get("lorawan", {})
        self.gateway_state = DroneState(
            drone_id=int(self.lorawan.get("gateway_id", 0)),
            x=float(self.lorawan.get("gateway_x", 0.0)),
            y=float(self.lorawan.get("gateway_y", 0.0)),
            z=float(self.lorawan.get("gateway_z", 35.0)),
            timestamp=time.time(),
            status="gateway",
        )
        self.server_state = DroneState(
            drone_id=int(self.lorawan.get("network_server_id", -1)),
            x=self.gateway_state.x,
            y=self.gateway_state.y,
            z=self.gateway_state.z,
            timestamp=time.time(),
            status="network_server",
        )
        self.registered_nodes = set()
        self.rng = random.Random(int(self.config["radio"]["random_seed"]))
        sdf_path = resolve_project_path(self.project_dir, self.config["world"]["sdf_path"])
        self.obstacles = load_obstacles_from_sdf(sdf_path)
        self.origin_latitude = float(self.config["world"].get("origin_latitude_deg", 47.397971057728974))
        self.origin_longitude = float(self.config["world"].get("origin_longitude_deg", 8.546163739800146))
        self.channel = LoRaChannel(self.config, self.obstacles, self.rng)
        self.logger = PacketLogger(
            resolve_project_path(self.project_dir, self.config["logging"]["packet_csv"]),
            resolve_project_path(self.project_dir, self.config["logging"].get("topology_csv", "logs/topology_changes.csv")),
        )
        self.duplicates = DuplicateFilter()
        self.running = True

        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.bind((self.network["manager_host"], int(self.network["manager_port"])))
        self.sock.setblocking(False)

        self.mav = mavutil.mavlink_connection(self.network["mavlink_endpoint"], source_system=254, source_component=190)
        self.last_tx = 0.0
        self.last_gz_pose_poll = 0.0

    def close(self):
        self.logger.write_metrics(resolve_project_path(self.project_dir, self.config["logging"]["metrics_json"]))
        self.logger.close()
        self.sock.close()

    def stop(self, *_args):
        self.running = False

    def send_gcs_heartbeat(self):
        self.mav.mav.heartbeat_send(
            mavutil.mavlink.MAV_TYPE_GCS,
            mavutil.mavlink.MAV_AUTOPILOT_INVALID,
            0,
            0,
            mavutil.mavlink.MAV_STATE_ACTIVE,
        )

    def read_node_heartbeats(self):
        while True:
            try:
                data, _addr = self.sock.recvfrom(4096)
            except BlockingIOError:
                return
            try:
                msg = json.loads(data.decode("utf-8"))
            except json.JSONDecodeError:
                continue
            if msg.get("type") == "node_heartbeat":
                drone_id = int(msg.get("drone_id"))
                if drone_id in self.states:
                    self.registered_nodes.add(drone_id)

    def read_mavlink(self):
        while True:
            ready, _, _ = select.select([self.mav.fd], [], [], 0)
            if not ready:
                return
            msg = self.mav.recv_match(blocking=False)
            if msg is None:
                return
            sysid = msg.get_srcSystem()
            if sysid not in self.states:
                continue
            state = self.states[sysid]
            msg_type = msg.get_type()
            now = time.time()
            if msg_type == "HEARTBEAT":
                state.status = STATUS_BY_STATE.get(msg.system_status, str(msg.system_status))
            elif msg_type == "LOCAL_POSITION_NED":
                if not state.has_global:
                    state.x = float(msg.x)
                    state.y = float(msg.y)
                state.z = -float(msg.z)
                state.velocity = (float(msg.vx) ** 2 + float(msg.vy) ** 2 + float(msg.vz) ** 2) ** 0.5
                state.timestamp = now
            elif msg_type == "GLOBAL_POSITION_INT":
                state.latitude = float(msg.lat) / 1e7
                state.longitude = float(msg.lon) / 1e7
                state.altitude = float(msg.relative_alt) / 1000.0
                state.x, state.y = latlon_to_xy(
                    state.latitude,
                    state.longitude,
                    self.origin_latitude,
                    self.origin_longitude,
                )
                state.z = state.altitude
                state.has_global = True
                state.timestamp = now
            elif msg_type == "SYS_STATUS":
                if msg.battery_remaining != -1:
                    state.battery = float(msg.battery_remaining)
            elif msg_type == "BATTERY_STATUS":
                if msg.battery_remaining != -1:
                    state.battery = float(msg.battery_remaining)

    def read_gazebo_poses(self):
        if not self.config["world"].get("enable_gazebo_pose", True):
            return
        now = time.time()
        if now - self.last_gz_pose_poll < float(self.network["transmit_interval_s"]):
            return
        self.last_gz_pose_poll = now
        world_name = self.config["world"].get("name", "uav_5km_world")
        topic = f"/world/{world_name}/pose/info"
        try:
            completed = subprocess.run(
                ["gz", "topic", "-e", "-t", topic, "-n", "1"],
                capture_output=True,
                text=True,
                timeout=2.0,
                check=False,
            )
        except (subprocess.SubprocessError, FileNotFoundError):
            return
        if completed.returncode != 0:
            return
        for model_name, x, y, z in parse_gazebo_pose_info(completed.stdout):
            if not model_name.startswith("x500_"):
                continue
            try:
                drone_id = int(model_name.rsplit("_", 1)[1]) + 1
            except (IndexError, ValueError):
                continue
            if drone_id in self.states:
                state = self.states[drone_id]
                state.x = x
                state.y = y
                state.z = z
                state.timestamp = now

    def positions_ready(self):
        timeout = float(self.network["position_timeout_s"])
        now = time.time()
        return all(now - self.states[drone_id].timestamp <= timeout for drone_id in self.drone_ids)

    def payload_for(self, drone_id):
        state = self.states[drone_id]
        return {
            "drone_id": state.drone_id,
            "timestamp": time.time(),
            "x": state.x,
            "y": state.y,
            "z": state.z,
            "latitude": state.latitude,
            "longitude": state.longitude,
            "altitude": state.altitude,
            "velocity": state.velocity,
            "battery": state.battery,
            "status": state.status,
        }

    def attempt_link(self, packet, sender_id, receiver_id):
        sender = self.endpoint_state(sender_id)
        receiver = self.endpoint_state(receiver_id)
        result = self.channel.evaluate(sender, receiver, int(self.network["payload_bytes"]))
        self.logger.log_link(time.time(), packet, result, sender, receiver)
        return result.packet_status == "received"

    def endpoint_state(self, endpoint_id):
        if endpoint_id == self.gateway_state.drone_id:
            return self.gateway_state
        if endpoint_id == self.server_state.drone_id:
            return self.server_state
        return self.states[endpoint_id]

    def transmit_packet(self, source, destination):
        packet = new_packet(source, destination, int(self.network["ttl"]))
        if self.duplicates.seen_before(packet.packet_id, source):
            return

        if self.attempt_link(packet, source, destination):
            self.logger.log_topology_change(time.time(), source, destination, f"{source}->{destination}", "direct", "")
            return

        if not self.network.get("enable_multihop", True):
            self.logger.log_topology_change(time.time(), source, destination, f"{source}->{destination}", "down", "direct_failed")
            return

        for relay in self.drone_ids:
            if relay in (source, destination) or relay in packet.visited:
                continue
            if packet.ttl <= 1:
                return
            packet.hop_count = 1
            packet.ttl -= 1
            packet.visited.add(relay)
            if not self.attempt_link(packet, source, relay):
                continue
            if self.duplicates.seen_before(packet.packet_id, relay):
                continue
            packet.hop_count = 2
            packet.ttl -= 1
            if self.attempt_link(packet, relay, destination):
                self.logger.log_topology_change(
                    time.time(),
                    source,
                    destination,
                    f"{source}->{relay}->{destination}",
                    "relay",
                    "direct_failed",
                )
            else:
                self.logger.log_topology_change(
                    time.time(),
                    source,
                    destination,
                    f"{source}->{relay}->{destination}",
                    "down",
                    "relay_failed",
                )
            return

        self.logger.log_topology_change(time.time(), source, destination, f"{source}->{destination}", "down", "no_relay")

    def transmit_lorawan_uplink(self, source):
        gateway_id = self.gateway_state.drone_id
        server_id = int(self.lorawan.get("network_server_id", -1))
        packet = new_packet(source, gateway_id, int(self.network["ttl"]))
        if self.attempt_link(packet, source, gateway_id):
            self.logger.log_topology_change(time.time(), source, server_id, f"{source}->gateway->server", "uplink", "")
            server_packet = new_packet(gateway_id, server_id, int(self.network["ttl"]))
            server_packet.packet_id = packet.packet_id
            server_packet.source = source
            server_packet.destination = server_id
            server_packet.hop_count = 1
            server_packet.ttl = max(0, packet.ttl - 1)
            self.logger.log_link(
                time.time(),
                server_packet,
                self.channel.evaluate(self.gateway_state, self.server_state, int(self.network["payload_bytes"])),
                self.gateway_state,
                self.server_state,
            )
        else:
            self.logger.log_topology_change(time.time(), source, server_id, f"{source}->gateway->server", "down", "gateway_link_failed")

    def transmit_round(self):
        if self.network_mode == "lorawan":
            for source in self.drone_ids:
                self.payload_for(source)
                self.transmit_lorawan_uplink(source)
        else:
            for source in self.drone_ids:
                self.payload_for(source)
                for destination in self.drone_ids:
                    if source != destination:
                        self.transmit_packet(source, destination)

    def run(self):
        signal.signal(signal.SIGTERM, self.stop)
        signal.signal(signal.SIGINT, self.stop)
        print("LoRa network manager started")
        print(f"Network mode: {self.network_mode}")
        print(f"Loaded {len(self.obstacles)} simplified obstruction boxes")
        try:
            while self.running:
                self.send_gcs_heartbeat()
                self.read_node_heartbeats()
                self.read_mavlink()
                self.read_gazebo_poses()
                now = time.time()
                if now - self.last_tx >= float(self.network["transmit_interval_s"]):
                    self.last_tx = now
                    if self.positions_ready():
                        self.transmit_round()
                    else:
                        missing = [drone_id for drone_id, state in self.states.items() if now - state.timestamp > float(self.network["position_timeout_s"])]
                        print(f"Waiting for fresh PX4 positions: {missing}")
                time.sleep(0.05)
        finally:
            self.close()
            print("LoRa network manager stopped")


def main():
    parser = argparse.ArgumentParser(description="PX4-backed LoRa network manager.")
    parser.add_argument("--config", default="config/lora.yaml")
    parser.add_argument("--project-dir", default=".")
    args = parser.parse_args()
    NetworkManager(args.config, args.project_dir).run()


def parse_gazebo_pose_info(text):
    results = []
    blocks = re.split(r"\n(?=pose\s*\{)", text)
    for block in blocks:
        name_match = re.search(r'name:\s*"([^"]+)"', block)
        if not name_match:
            continue
        position_match = re.search(
            r"position\s*\{[^}]*?x:\s*([-+0-9.eE]+)[^}]*?y:\s*([-+0-9.eE]+)[^}]*?z:\s*([-+0-9.eE]+)",
            block,
            re.DOTALL,
        )
        if not position_match:
            continue
        results.append((
            name_match.group(1),
            float(position_match.group(1)),
            float(position_match.group(2)),
            float(position_match.group(3)),
        ))
    return results


if __name__ == "__main__":
    main()
