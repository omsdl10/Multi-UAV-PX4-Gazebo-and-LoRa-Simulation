#!/usr/bin/env python3
import argparse
import json
import shutil
import subprocess
from pathlib import Path


def detect_ns3(config):
    configured = config.get("ns3_path") or ""
    candidates = [configured] if configured else []
    candidates += ["ns3", "ns-3"]
    for candidate in candidates:
        if not candidate:
            continue
        exe = Path(candidate)
        resolved = str(exe) if exe.exists() else shutil.which(candidate)
        if not resolved:
            continue
        try:
            result = subprocess.run([resolved, "--version"], capture_output=True, text=True, timeout=5)
        except Exception:
            result = None
        return {
            "available": True,
            "executable": resolved,
            "version": (result.stdout or result.stderr).strip() if result else "unknown",
        }
    return {"available": False, "reason": "ns-3 executable not found"}


def write_position_trace(packet_csv, output):
    rows = []
    if Path(packet_csv).exists():
        import csv
        with Path(packet_csv).open() as f:
            for row in csv.DictReader(f):
                rows.append({
                    "timestamp": float(row["timestamp"]),
                    "sender": int(row["sender"]),
                    "receiver": int(row["receiver"]),
                    "sender_position": [float(row["sender_x"]), float(row["sender_y"]), float(row["sender_z"])],
                    "receiver_position": [float(row["receiver_x"]), float(row["receiver_y"]), float(row["receiver_z"])],
                    "distance": float(row["distance"]),
                })
    Path(output).parent.mkdir(parents=True, exist_ok=True)
    Path(output).write_text(json.dumps({"position_trace": rows}, indent=2) + "\n")


def main():
    parser = argparse.ArgumentParser(description="Optional ns-3 LoRaWAN adapter/detector.")
    parser.add_argument("--packet-csv", default="logs/lora_packets.csv")
    parser.add_argument("--output", default="logs/ns3_lorawan_status.json")
    parser.add_argument("--ns3-path", default="")
    args = parser.parse_args()
    status = detect_ns3({"ns3_path": args.ns3_path})
    status["lorawan_api_investigation"] = {
        "module": "signetlabdei/lorawan",
        "current_app_store_note": "LoRaWAN 0.3.7 works with ns-3.48",
        "features": [
            "Class A end devices",
            "Network Server implementation",
            "ADR",
            "confirmed messages",
            "multi-gateway support",
            "urban propagation models",
            "realistic gateway chip model",
            "packet tracker",
        ],
        "integration_status": "not_run_locally_without_ns3",
    }
    trace_output = str(Path(args.output).with_name("ns3_position_trace.json"))
    write_position_trace(args.packet_csv, trace_output)
    status["position_trace"] = trace_output
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    Path(args.output).write_text(json.dumps(status, indent=2) + "\n")
    print(json.dumps(status, indent=2))
    return 0 if status.get("available") else 2


if __name__ == "__main__":
    raise SystemExit(main())
