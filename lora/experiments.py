#!/usr/bin/env python3
import argparse
import csv
import random
from dataclasses import dataclass
from pathlib import Path

import yaml

from .channel import LoRaChannel


@dataclass
class State:
    drone_id: int
    x: float
    y: float
    z: float
    latitude: float = 0.0
    longitude: float = 0.0
    altitude: float = 0.0
    velocity: float = 0.0


def load_config(path):
    with Path(path).open() as f:
        return yaml.safe_load(f)


def run_experiments(config_path, output_dir, samples):
    cfg = load_config(config_path)
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    rng = random.Random(int(cfg["radio"]["random_seed"]))
    channel = LoRaChannel(cfg, [], rng)
    distances = [100, 250, 500, 1000, 1500, 2000, 3000, 4000, 5000]
    rows = []

    for distance in distances:
        received = 0
        rssi_values = []
        snr_values = []
        latency_values = []
        for _ in range(samples):
            a = State(1, 0.0, 0.0, 80.0)
            b = State(2, float(distance), 0.0, 80.0)
            result = channel.evaluate(a, b, int(cfg["network"]["payload_bytes"]))
            received += int(result.packet_status == "received")
            rssi_values.append(result.rssi)
            snr_values.append(result.snr)
            latency_values.append(result.latency_ms)
        pdr = received / samples
        rows.append({
            "distance": distance,
            "rssi": sum(rssi_values) / samples,
            "snr": sum(snr_values) / samples,
            "pdr": pdr,
            "latency_ms": sum(latency_values) / samples,
            "packet_loss": 1.0 - pdr,
        })

    csv_path = output / "lora_experiments.csv"
    with csv_path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    plot_specs = [
        ("rssi", "Distance vs RSSI", "RSSI (dBm)", "distance_vs_rssi.svg"),
        ("snr", "Distance vs SNR", "SNR (dB)", "distance_vs_snr.svg"),
        ("pdr", "Distance vs PDR", "PDR", "distance_vs_pdr.svg"),
        ("latency_ms", "Distance vs latency", "Latency (ms)", "distance_vs_latency.svg"),
        ("packet_loss", "Distance vs packet loss", "Packet loss", "distance_vs_packet_loss.svg"),
    ]
    for key, title, ylabel, filename in plot_specs:
        write_svg_plot(output / filename, rows, key, title, ylabel)
    print(f"Wrote experiment CSV and plots to {output}")


def write_svg_plot(path, rows, key, title, ylabel):
    width, height = 900, 520
    left, right, top, bottom = 82, 32, 54, 70
    plot_w = width - left - right
    plot_h = height - top - bottom
    xs = [float(r["distance"]) for r in rows]
    ys = [float(r[key]) for r in rows]
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)
    if abs(max_y - min_y) < 1e-9:
        min_y -= 1
        max_y += 1
    y_pad = (max_y - min_y) * 0.08
    min_y -= y_pad
    max_y += y_pad

    def sx(x):
        return left + (x - min_x) / (max_x - min_x) * plot_w

    def sy(y):
        return top + (max_y - y) / (max_y - min_y) * plot_h

    points = " ".join(f"{sx(x):.1f},{sy(y):.1f}" for x, y in zip(xs, ys))
    circles = "\n".join(f'<circle cx="{sx(x):.1f}" cy="{sy(y):.1f}" r="4" fill="#1f6feb" />' for x, y in zip(xs, ys))
    grid = []
    for i in range(6):
        gy = top + i * plot_h / 5
        value = max_y - i * (max_y - min_y) / 5
        grid.append(f'<line x1="{left}" y1="{gy:.1f}" x2="{width-right}" y2="{gy:.1f}" stroke="#e5e7eb" />')
        grid.append(f'<text x="{left-10}" y="{gy+4:.1f}" text-anchor="end" font-size="12" fill="#555">{value:.2f}</text>')
    for x in xs:
        gx = sx(x)
        grid.append(f'<line x1="{gx:.1f}" y1="{top}" x2="{gx:.1f}" y2="{height-bottom}" stroke="#f1f5f9" />')
        grid.append(f'<text x="{gx:.1f}" y="{height-bottom+24}" text-anchor="middle" font-size="12" fill="#555">{int(x)}</text>')

    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">
  <rect width="100%" height="100%" fill="white"/>
  <text x="{width/2}" y="30" text-anchor="middle" font-size="22" font-family="Arial, sans-serif" fill="#111">{title}</text>
  {''.join(grid)}
  <line x1="{left}" y1="{top}" x2="{left}" y2="{height-bottom}" stroke="#111"/>
  <line x1="{left}" y1="{height-bottom}" x2="{width-right}" y2="{height-bottom}" stroke="#111"/>
  <polyline points="{points}" fill="none" stroke="#1f6feb" stroke-width="3"/>
  {circles}
  <text x="{width/2}" y="{height-20}" text-anchor="middle" font-size="15" font-family="Arial, sans-serif" fill="#111">Distance (m)</text>
  <text x="20" y="{height/2}" text-anchor="middle" font-size="15" font-family="Arial, sans-serif" fill="#111" transform="rotate(-90 20 {height/2})">{ylabel}</text>
</svg>
'''
    path.write_text(svg)


def main():
    parser = argparse.ArgumentParser(description="Run LoRa distance experiments and generate plots.")
    parser.add_argument("--config", default="config/lora.yaml")
    parser.add_argument("--output-dir", default="analysis/output")
    parser.add_argument("--samples", type=int, default=100)
    args = parser.parse_args()
    run_experiments(args.config, args.output_dir, args.samples)


if __name__ == "__main__":
    main()
