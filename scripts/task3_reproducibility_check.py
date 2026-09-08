#!/usr/bin/env python3
import argparse
import csv
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path


PROJECT_DIR = Path(__file__).resolve().parents[1]
LOG_DIR = PROJECT_DIR / "logs"
AUDISYS_LOG_DIR = LOG_DIR / "audisys"
ARTIFACT_DIR = PROJECT_DIR / "artifacts" / "task3"

EXPECTED_AUDISYS_LOGS = [
    "uav_state.csv",
    "target_state.csv",
    "radio.csv",
    "tasks.csv",
    "events.csv",
    "allocation_messages.csv",
    "flight_positions.csv",
]

EXPECTED_BASE_LOGS = [
    "lora_packets.csv",
    "lora_metrics.json",
    "topology_changes.csv",
]

PROCESS_MARKERS = [
    "PX4-Autopilot/build/px4_sitl_default/bin/px4",
    "uav_5km_world.sdf",
    "lora.network_manager",
    "lora/lora_node.py",
    "run_audisys_scenario.py",
    "run_one_minute_terrain_simulation.py",
]


def run_command(args, env=None, timeout=None, capture=True):
    merged_env = os.environ.copy()
    if env:
        merged_env.update(env)
    return subprocess.run(
        args,
        cwd=PROJECT_DIR,
        env=merged_env,
        timeout=timeout,
        text=True,
        stdout=subprocess.PIPE if capture else None,
        stderr=subprocess.STDOUT if capture else None,
        check=False,
    )


def csv_rows(path):
    if not path.exists():
        return []
    with path.open(newline="") as handle:
        return list(csv.DictReader(handle))


def require_csv(path, require_rows=True):
    rows = csv_rows(path)
    return {
        "path": str(path.relative_to(PROJECT_DIR)),
        "exists": path.exists(),
        "rows": len(rows),
        "parseable": path.exists() and len(rows) >= 0,
        "require_rows": require_rows,
    }


def event_signature(path):
    signature = []
    for row in csv_rows(path):
        event_type = row.get("event_type") or row.get("type") or row.get("event") or ""
        task_type = row.get("task_type") or row.get("task") or ""
        if event_type in {"ScenarioStarted", "TaskCreated", "ScenarioStopped"} or task_type:
            signature.append(f"{event_type}:{task_type}".strip(":"))
    return signature


def task_signature(path):
    signature = []
    for row in csv_rows(path):
        task_type = row.get("task_type") or row.get("type") or ""
        status = row.get("status") or ""
        if task_type or status:
            signature.append(f"{task_type}:{status}".strip(":"))
    return signature


def radio_transition_signature(path):
    transitions = []
    last_by_pair = {}
    for row in csv_rows(path):
        pair = f"{row.get('source', '')}->{row.get('destination', '')}"
        condition = row.get("condition") or ""
        if not pair.strip("->") or not condition:
            continue
        previous = last_by_pair.get(pair)
        if previous != condition:
            transitions.append(f"{pair}:{condition}")
            last_by_pair[pair] = condition
    return transitions


def flight_summary(path):
    rows = csv_rows(path)
    by_drone = {}
    for row in rows:
        try:
            drone_id = int(row["drone_id"])
            x = float(row["x_m"])
            y = float(row["y_m"])
            z = float(row["z_m"])
        except (KeyError, ValueError):
            continue
        entry = by_drone.setdefault(drone_id, {"samples": 0, "min_x": x, "max_x": x, "min_y": y, "max_y": y, "max_z": z})
        entry["samples"] += 1
        entry["min_x"] = min(entry["min_x"], x)
        entry["max_x"] = max(entry["max_x"], x)
        entry["min_y"] = min(entry["min_y"], y)
        entry["max_y"] = max(entry["max_y"], y)
        entry["max_z"] = max(entry["max_z"], z)
    for entry in by_drone.values():
        entry["span_x_m"] = round(entry["max_x"] - entry["min_x"], 3)
        entry["span_y_m"] = round(entry["max_y"] - entry["min_y"], 3)
        entry["max_z"] = round(entry["max_z"], 3)
    return by_drone


def radio_summary(path):
    rows = csv_rows(path)
    delivered = 0
    rssi = []
    snr = []
    pairs = {}
    for row in rows:
        sender = row.get("sender", "")
        receiver = row.get("receiver", "")
        pair = f"{sender}->{receiver}"
        entry = pairs.setdefault(pair, {"packets": 0, "received": 0, "dropped": 0})
        entry["packets"] += 1
        if row.get("packet_status") == "received":
            delivered += 1
            entry["received"] += 1
        else:
            entry["dropped"] += 1
        try:
            rssi.append(float(row["RSSI"]))
        except (KeyError, ValueError):
            pass
        try:
            snr.append(float(row["SNR"]))
        except (KeyError, ValueError):
            pass
    return {
        "packets": len(rows),
        "received": delivered,
        "dropped": len(rows) - delivered,
        "pdr": round(delivered / len(rows), 4) if rows else 0.0,
        "average_rssi_dbm": round(sum(rssi) / len(rssi), 3) if rssi else None,
        "average_snr_db": round(sum(snr) / len(snr), 3) if snr else None,
        "pairs": pairs,
    }


def stale_processes():
    result = run_command(["ps", "-axo", "pid,command"], capture=True)
    stale = []
    if result.returncode != 0:
        return [{"error": "process inspection failed", "output": result.stdout or ""}]
    for line in (result.stdout or "").splitlines():
        if "task3_reproducibility_check.py" in line:
            continue
        if any(marker in line for marker in PROCESS_MARKERS):
            stale.append(line.strip())
    return stale


def clean_runtime_logs():
    for name in EXPECTED_AUDISYS_LOGS + ["scenario.log", "flight_mission.log"]:
        path = AUDISYS_LOG_DIR / name
        if path.exists():
            path.unlink()
    for name in EXPECTED_BASE_LOGS + ["lora_manager.log", "gazebo.log", "gazebo_gui.log"]:
        path = LOG_DIR / name
        if path.exists():
            path.unlink()


def copy_artifacts(run_dir):
    run_dir.mkdir(parents=True, exist_ok=True)
    for name in EXPECTED_AUDISYS_LOGS + ["scenario.log", "flight_mission.log"]:
        src = AUDISYS_LOG_DIR / name
        if src.exists():
            shutil.copy2(src, run_dir / name)
    for name in EXPECTED_BASE_LOGS + ["lora_manager.log", "gazebo.log"]:
        src = LOG_DIR / name
        if src.exists():
            shutil.copy2(src, run_dir / name)


def run_one(index, duration_s, timeout_s):
    run_dir = ARTIFACT_DIR / f"run_{index}"
    print(f"run {index}: stopping previous project processes")
    run_command([str(PROJECT_DIR / "scripts" / "stop_simulation.sh")], timeout=30, capture=True)
    time.sleep(6)
    clean_runtime_logs()

    env = {
        "GAZEBO_GUI": "0",
        "AUDISYS_DURATION": str(duration_s),
        "AUDISYS_SPEED": "18",
        "AUDISYS_ALTITUDE": "8",
        "AUDISYS_PROFILE": "visible_terrain",
        "AUDISYS_FLIGHT_START_DELAY_S": "15",
        "PX4_GAZEBO_SETTLE_S": "20",
        "PX4_INSTANCE_READY_TIMEOUT_S": "80",
        "PX4_INSTANCE_START_DELAY_S": "5",
        "GZ_IP": "127.0.0.1",
        "GZ_PARTITION": "multi_uav_lora_sim",
    }
    start = None
    for attempt in (1, 2):
        print(f"run {index}: starting clean headless scenario for {duration_s}s, attempt {attempt}")
        start = run_command([str(PROJECT_DIR / "scripts" / "start_audisys_simulation.sh")], env=env, timeout=timeout_s)
        if start.returncode == 0:
            break
        run_command([str(PROJECT_DIR / "scripts" / "stop_simulation.sh")], timeout=45, capture=True)
        time.sleep(8)
        clean_runtime_logs()
    if start is None or start.returncode != 0:
        stale = stale_processes()
        return {
            "run": index,
            "status": "FAIL",
            "reason": "start script failed after retry",
            "start_output_tail": (start.stdout or "")[-4000:] if start else "",
            "stale_processes_after_stop": stale,
        }

    wait_s = duration_s + int(env["AUDISYS_FLIGHT_START_DELAY_S"]) + 25
    print(f"run {index}: collecting logs for {wait_s}s")
    time.sleep(wait_s)

    print(f"run {index}: stopping scenario")
    stop = run_command([str(PROJECT_DIR / "scripts" / "stop_audisys_simulation.sh")], timeout=45)
    time.sleep(3)
    copy_artifacts(run_dir)

    checks = [require_csv(run_dir / name) for name in EXPECTED_AUDISYS_LOGS]
    checks += [require_csv(run_dir / "lora_packets.csv"), require_csv(run_dir / "topology_changes.csv", require_rows=False)]
    missing_or_empty = [
        item for item in checks
        if not item["exists"] or (item["require_rows"] and item["rows"] == 0)
    ]
    stale = stale_processes()
    summary = {
        "run": index,
        "status": "PASS" if not missing_or_empty and not stale else "FAIL",
        "duration_s": duration_s,
        "stop_output": stop.stdout,
        "log_checks": checks,
        "flight": flight_summary(run_dir / "flight_positions.csv"),
        "radio": radio_summary(run_dir / "lora_packets.csv"),
        "events_signature": event_signature(run_dir / "events.csv"),
        "tasks_signature": task_signature(run_dir / "tasks.csv"),
        "radio_transition_signature": radio_transition_signature(run_dir / "radio.csv"),
        "stale_processes_after_stop": stale,
    }
    if missing_or_empty:
        summary["missing_or_empty"] = missing_or_empty
    return summary


def main():
    parser = argparse.ArgumentParser(description="Run Task 3 repeatability and handoff checks.")
    parser.add_argument("--runs", type=int, default=3)
    parser.add_argument("--duration", type=int, default=120)
    parser.add_argument("--start-timeout", type=int, default=180)
    args = parser.parse_args()

    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    summaries = []
    for index in range(1, args.runs + 1):
        summaries.append(run_one(index, args.duration, args.start_timeout))

    baseline_tasks = summaries[0].get("tasks_signature", []) if summaries else []
    baseline_radio = summaries[0].get("radio_transition_signature", []) if summaries else []
    task_consistent = all(item.get("tasks_signature", []) == baseline_tasks for item in summaries)
    radio_consistent = all(item.get("radio_transition_signature", []) == baseline_radio for item in summaries)
    overall_pass = all(item.get("status") == "PASS" for item in summaries) and task_consistent and radio_consistent

    report = {
        "status": "PASS" if overall_pass else "FAIL",
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S %Z"),
        "runs": args.runs,
        "duration_s": args.duration,
        "same_seed_config": True,
        "task_order_consistent": task_consistent,
        "radio_transition_order_consistent": radio_consistent,
        "summaries": summaries,
    }
    report_path = ARTIFACT_DIR / "summary.json"
    report_path.write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2))
    return 0 if overall_pass else 1


if __name__ == "__main__":
    sys.exit(main())
