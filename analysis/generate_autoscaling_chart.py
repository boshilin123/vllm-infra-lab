#!/usr/bin/env python3
"""从离线弹性决策 CSV 生成确定性 SVG。"""

from __future__ import annotations

import argparse
import csv
import json
from datetime import datetime
from pathlib import Path
from typing import Any
from xml.sax.saxutils import escape


WIDTH = 1200
HEIGHT = 650
LEFT = 90
RIGHT = 40
PLOT_WIDTH = WIDTH - LEFT - RIGHT
COLORS = {
    "running": "#2563eb",
    "waiting": "#dc2626",
    "desired": "#7c3aed",
    "ready": "#059669",
    "grid": "#dbe3ef",
    "text": "#1f2937",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="读取 autoscaling-simulation 输出并生成离线回放 SVG。"
    )
    parser.add_argument("--simulation-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    return parser.parse_args()


def load_rows(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8", newline="") as file:
        for row in csv.DictReader(file):
            rows.append(
                {
                    "timestamp": float(row["timestamp"]),
                    "running": float(row["running_requests"]),
                    "waiting": float(row["waiting_requests"]),
                    "desired": int(row["desired_replicas"]),
                    "ready": int(row["ready_replicas"]),
                }
            )
    if len(rows) < 2:
        raise ValueError("decision-timeline.csv 至少需要两个采样点")
    return rows


def load_summary(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as file:
        data = json.load(file)
    if not isinstance(data, dict):
        raise ValueError("summary.json 顶层必须是对象")
    return data


def parse_iso(value: str | None) -> float | None:
    if value is None:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()


def points(
    rows: list[dict[str, Any]], key: str, x_coord: Any, y_coord: Any
) -> str:
    return " ".join(
        f"{x_coord(row['timestamp']):.2f},{y_coord(float(row[key])):.2f}"
        for row in rows
    )


def step_points(
    rows: list[dict[str, Any]], key: str, x_coord: Any, y_coord: Any
) -> str:
    values: list[tuple[float, float]] = []
    for index, row in enumerate(rows):
        x_value = x_coord(row["timestamp"])
        y_value = y_coord(float(row[key]))
        if index:
            values.append((x_value, values[-1][1]))
        values.append((x_value, y_value))
    return " ".join(f"{x:.2f},{y:.2f}" for x, y in values)


def text(x: float, y: float, value: str, **attrs: str) -> str:
    attributes = " ".join(f'{key}="{escape(item)}"' for key, item in attrs.items())
    return f'<text x="{x:.2f}" y="{y:.2f}" {attributes}>{escape(value)}</text>'


def generate(rows: list[dict[str, Any]], summary: dict[str, Any]) -> str:
    start = rows[0]["timestamp"]
    end = rows[-1]["timestamp"]

    def x_coord(timestamp: float) -> float:
        return LEFT + (timestamp - start) / (end - start) * PLOT_WIDTH

    top_y = 155
    top_height = 210
    bottom_y = 455
    bottom_height = 100
    max_requests = max(
        8.0,
        max(row["running"] for row in rows),
        max(row["waiting"] for row in rows),
    )

    def request_y(value: float) -> float:
        return top_y + top_height - value / max_requests * top_height

    def replica_y(value: float) -> float:
        return bottom_y + bottom_height - (value - 1.0) * bottom_height

    output = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" '
        f'height="{HEIGHT}" viewBox="0 0 {WIDTH} {HEIGHT}">',
        '<rect width="100%" height="100%" fill="white"/>',
        '<g font-family="DejaVu Sans, sans-serif" fill="#1f2937">',
        text(LEFT, 42, "Reactive autoscaling offline replay", **{"font-size": "24", "font-weight": "700"}),
        text(
            LEFT,
            70,
            "15 s samples · 2 consecutive waiting samples · 155 s startup · simulation only",
            **{"font-size": "14", "fill": "#4b5563"},
        ),
        text(LEFT, 118, "Observed single-replica scheduler pressure", **{"font-size": "17", "font-weight": "700"}),
        text(LEFT, 418, "Simulated replica state", **{"font-size": "17", "font-weight": "700"}),
    ]

    for tick in range(0, int(max_requests) + 1, 2):
        y_value = request_y(float(tick))
        output.append(
            f'<line x1="{LEFT}" y1="{y_value:.2f}" x2="{WIDTH - RIGHT}" '
            f'y2="{y_value:.2f}" stroke="{COLORS["grid"]}"/>'
        )
        output.append(text(LEFT - 16, y_value + 5, str(tick), **{"font-size": "12", "text-anchor": "end"}))

    for tick in (1, 2):
        y_value = replica_y(float(tick))
        output.append(
            f'<line x1="{LEFT}" y1="{y_value:.2f}" x2="{WIDTH - RIGHT}" '
            f'y2="{y_value:.2f}" stroke="{COLORS["grid"]}"/>'
        )
        output.append(text(LEFT - 16, y_value + 5, str(tick), **{"font-size": "12", "text-anchor": "end"}))

    for minute in range(0, int((end - start) // 60) + 1):
        x_value = x_coord(start + minute * 60)
        output.append(
            f'<line x1="{x_value:.2f}" y1="{top_y}" x2="{x_value:.2f}" '
            f'y2="{bottom_y + bottom_height}" stroke="{COLORS["grid"]}" '
            'stroke-dasharray="3 5"/>'
        )
        output.append(text(x_value, 590, f"{minute} min", **{"font-size": "12", "text-anchor": "middle"}))

    output.extend(
        [
            f'<polyline points="{points(rows, "running", x_coord, request_y)}" '
            f'fill="none" stroke="{COLORS["running"]}" stroke-width="3"/>',
            f'<polyline points="{points(rows, "waiting", x_coord, request_y)}" '
            f'fill="none" stroke="{COLORS["waiting"]}" stroke-width="3"/>',
            f'<polyline points="{step_points(rows, "desired", x_coord, replica_y)}" '
            f'fill="none" stroke="{COLORS["desired"]}" stroke-width="4"/>',
            f'<polyline points="{step_points(rows, "ready", x_coord, replica_y)}" '
            f'fill="none" stroke="{COLORS["ready"]}" stroke-width="4"/>',
        ]
    )

    events = [
        (parse_iso(summary.get("scale_out_requested_utc")), "Scale-out requested", COLORS["waiting"]),
        (parse_iso(summary.get("second_replica_scheduled_ready_utc")), "Replica 2 scheduled Ready", COLORS["ready"]),
    ]
    for timestamp, label, color in events:
        if timestamp is None:
            continue
        x_value = x_coord(timestamp)
        label_on_left = x_value > WIDTH - 260
        output.append(
            f'<line x1="{x_value:.2f}" y1="95" x2="{x_value:.2f}" y2="565" '
            f'stroke="{color}" stroke-width="2" stroke-dasharray="7 5"/>'
        )
        output.append(
            text(
                x_value - 6 if label_on_left else x_value + 6,
                92,
                label,
                **{
                    "font-size": "12",
                    "fill": color,
                    "font-weight": "700",
                    "text-anchor": "end" if label_on_left else "start",
                },
            )
        )

    last_active = parse_iso(summary.get("last_observed_active_utc"))
    scheduled_ready = parse_iso(summary.get("second_replica_scheduled_ready_utc"))
    if last_active is not None and scheduled_ready is not None:
        delay = int(scheduled_ready - last_active)
        output.append(
            text(
                LEFT,
                625,
                f"Result: replica 2 is scheduled Ready {delay} s after the last observed active sample.",
                **{"font-size": "14", "fill": "#991b1b", "font-weight": "700"},
            )
        )

    legends = [
        ("Running", COLORS["running"], 720, 118),
        ("Waiting", COLORS["waiting"], 840, 118),
        ("Desired", COLORS["desired"], 720, 418),
        ("Ready", COLORS["ready"], 840, 418),
    ]
    for label, color, x_value, y_value in legends:
        output.append(
            f'<line x1="{x_value}" y1="{y_value - 5}" x2="{x_value + 30}" '
            f'y2="{y_value - 5}" stroke="{color}" stroke-width="4"/>'
        )
        output.append(text(x_value + 38, y_value, label, **{"font-size": "12"}))

    output.extend(["</g>", "</svg>"])
    return "\n".join(output) + "\n"


def main() -> int:
    args = parse_args()
    simulation_dir = args.simulation_dir.resolve()
    rows = load_rows(simulation_dir / "decision-timeline.csv")
    summary = load_summary(simulation_dir / "summary.json")
    output = args.output.resolve() if args.output else simulation_dir / "timeline.svg"
    output.write_text(generate(rows, summary), encoding="utf-8")
    print(f"已生成: {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
