#!/usr/bin/env python3
import argparse
import json
import subprocess
import time
from pathlib import Path


def run(cmd):
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=8, check=False)
    except subprocess.TimeoutExpired as exc:
        return subprocess.CompletedProcess(cmd, 124, stdout=exc.stdout or "", stderr=f"timeout after {exc.timeout}s")


def read_pids(run_dir):
    path = Path(run_dir) / "pids"
    if not path.exists():
        return []
    return [line.strip() for line in path.read_text().splitlines() if line.strip().isdigit()]


def ps_snapshot(pids):
    if not pids:
        return []
    result = run(["ps", "-p", ",".join(pids), "-o", "pid,ppid,%cpu,rss,command"])
    lines = result.stdout.splitlines()[1:]
    return [line.rstrip() for line in lines]


def vm_stat():
    result = run(["vm_stat"])
    return result.stdout


def gazebo_stats(world_name):
    topic = f"/world/{world_name}/stats"
    result = run(["gz", "topic", "-e", "-t", topic, "-n", "1"])
    return result.stdout if result.returncode == 0 else result.stderr


def main():
    parser = argparse.ArgumentParser(description="Profile project PX4/Gazebo/networking processes.")
    parser.add_argument("--run-dir", default=".run")
    parser.add_argument("--world", default="uav_5km_world")
    parser.add_argument("--output", default="logs/performance_profile.json")
    args = parser.parse_args()
    pids = read_pids(args.run_dir)
    snapshot = {
        "timestamp": time.time(),
        "pids": pids,
        "processes": ps_snapshot(pids),
        "vm_stat": vm_stat(),
        "gazebo_stats": gazebo_stats(args.world),
    }
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    Path(args.output).write_text(json.dumps(snapshot, indent=2) + "\n")
    print(json.dumps(snapshot, indent=2))


if __name__ == "__main__":
    main()
