#!/usr/bin/env python3
import argparse
import csv
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description="Extract LoRa packet rows matching a position-log time window.")
    parser.add_argument("--positions", required=True)
    parser.add_argument("--packets", default="logs/lora_packets.csv")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    positions = Path(args.positions)
    packets = Path(args.packets)
    output = Path(args.output)

    rows = list(csv.DictReader(positions.open()))
    if not rows:
        raise SystemExit(f"no position rows in {positions}")
    start = min(float(row["timestamp"]) for row in rows)
    end = max(float(row["timestamp"]) for row in rows)

    output.parent.mkdir(parents=True, exist_ok=True)
    with packets.open() as f, output.open("w", newline="") as g:
        reader = csv.DictReader(f)
        writer = csv.DictWriter(g, fieldnames=reader.fieldnames)
        writer.writeheader()
        kept = 0
        for row in reader:
            try:
                timestamp = float(row["timestamp"])
            except (KeyError, ValueError):
                continue
            if start <= timestamp <= end:
                writer.writerow(row)
                kept += 1
    print(f"created {output} with {kept} packet exchange rows")


if __name__ == "__main__":
    main()
