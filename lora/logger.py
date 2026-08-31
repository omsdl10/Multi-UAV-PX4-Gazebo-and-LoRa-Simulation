import csv
import json
from collections import defaultdict
from pathlib import Path


CSV_COLUMNS = [
    "timestamp",
    "sender",
    "receiver",
    "sender_x",
    "sender_y",
    "sender_z",
    "receiver_x",
    "receiver_y",
    "receiver_z",
    "distance",
    "RSSI",
    "SNR",
    "LOS",
    "building_obstacles",
    "terrain_blocked",
    "packet_status",
    "drop_reason",
    "latency_ms",
    "packet_id",
    "source",
    "destination",
    "hop_count",
    "TTL",
]


class PacketLogger:
    def __init__(self, csv_path, topology_path=None):
        self.csv_path = Path(csv_path)
        self.csv_path.parent.mkdir(parents=True, exist_ok=True)
        self.file = self.csv_path.open("w", newline="")
        self.writer = csv.DictWriter(self.file, fieldnames=CSV_COLUMNS)
        self.writer.writeheader()
        self.file.flush()
        self.rows = []
        self.last_topology = {}
        self.topology_file = None
        self.topology_writer = None
        if topology_path:
            topology_path = Path(topology_path)
            topology_path.parent.mkdir(parents=True, exist_ok=True)
            self.topology_file = topology_path.open("w", newline="")
            self.topology_writer = csv.DictWriter(
                self.topology_file,
                fieldnames=["timestamp", "source", "destination", "route", "state", "reason"],
            )
            self.topology_writer.writeheader()
            self.topology_file.flush()

    def close(self):
        self.file.close()
        if self.topology_file:
            self.topology_file.close()

    def log_link(self, timestamp, packet, result, sender_state, receiver_state):
        row = {
            "timestamp": f"{timestamp:.3f}",
            "sender": result.sender,
            "receiver": result.receiver,
            "sender_x": f"{sender_state.x:.3f}",
            "sender_y": f"{sender_state.y:.3f}",
            "sender_z": f"{sender_state.z:.3f}",
            "receiver_x": f"{receiver_state.x:.3f}",
            "receiver_y": f"{receiver_state.y:.3f}",
            "receiver_z": f"{receiver_state.z:.3f}",
            "distance": f"{result.distance:.3f}",
            "RSSI": f"{result.rssi:.3f}",
            "SNR": f"{result.snr:.3f}",
            "LOS": int(result.los),
            "building_obstacles": "|".join(result.building_obstacles),
            "terrain_blocked": int(result.terrain_blocked),
            "packet_status": result.packet_status,
            "drop_reason": result.drop_reason,
            "latency_ms": f"{result.latency_ms:.3f}",
            "packet_id": packet.packet_id,
            "source": packet.source,
            "destination": packet.destination,
            "hop_count": packet.hop_count,
            "TTL": packet.ttl,
        }
        self.writer.writerow(row)
        self.file.flush()
        self.rows.append(row)

    def metrics(self):
        grouped = defaultdict(list)
        for row in self.rows:
            pair = tuple(sorted((int(row["sender"]), int(row["receiver"]))))
            grouped[pair].append(row)

        output = {}
        for pair, rows in grouped.items():
            received = [r for r in rows if r["packet_status"] == "received"]
            total = len(rows)
            output[f"{pair[0]}-{pair[1]}"] = {
                "packets": total,
                "received": len(received),
                "pdr": len(received) / total if total else 0.0,
                "packet_loss": 1.0 - (len(received) / total if total else 0.0),
                "average_rssi": sum(float(r["RSSI"]) for r in rows) / total if total else 0.0,
                "average_snr": sum(float(r["SNR"]) for r in rows) / total if total else 0.0,
                "average_latency_ms": sum(float(r["latency_ms"]) for r in received) / len(received) if received else 0.0,
            }
        return output

    def log_topology_change(self, timestamp, source, destination, route, state, reason):
        key = (source, destination, route)
        value = (state, reason)
        if self.last_topology.get(key) == value:
            return
        self.last_topology[key] = value
        if not self.topology_writer:
            return
        self.topology_writer.writerow({
            "timestamp": f"{timestamp:.3f}",
            "source": source,
            "destination": destination,
            "route": route,
            "state": state,
            "reason": reason,
        })
        self.topology_file.flush()

    def write_metrics(self, path):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        Path(path).write_text(json.dumps(self.metrics(), indent=2) + "\n")
