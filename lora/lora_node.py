#!/usr/bin/env python3
import argparse
import json
import socket
import time


def main():
    parser = argparse.ArgumentParser(description="Lightweight LoRa peer identity process.")
    parser.add_argument("--drone-id", type=int, required=True)
    parser.add_argument("--manager-host", default="127.0.0.1")
    parser.add_argument("--manager-port", type=int, default=19760)
    parser.add_argument("--interval", type=float, default=1.0)
    args = parser.parse_args()

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    target = (args.manager_host, args.manager_port)
    while True:
        payload = {
            "type": "node_heartbeat",
            "drone_id": args.drone_id,
            "timestamp": time.time(),
        }
        sock.sendto(json.dumps(payload).encode("utf-8"), target)
        time.sleep(args.interval)


if __name__ == "__main__":
    main()
