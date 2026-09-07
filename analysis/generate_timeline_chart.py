#!/usr/bin/env python3
"""从 Prometheus timeline.csv 生成无第三方依赖的 Phase 3 SVG。"""

from __future__ import annotations

import argparse
import csv
import html
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Callable


COLORS = ["#2563eb", "#dc2626", "#0d9488"]
GRID = "#d8dee9"
TEXT = "#172033"
MUTED = "#64748b"


@dataclass(frozen=True)
class Series:
    column: str
    label: str
    color: str
    scale: float = 1.0


@dataclass(frozen=True)
class Panel:
    title: str
    unit: str
    maximum: float
    series: tuple[Series, ...]


PANELS = (
    Panel(
        "Scheduler pressure",
        "requests",
        10,
        (
            Series("running_requests", "Running", COLORS[0]),
            Series("waiting_requests", "Waiting", COLORS[1]),
        ),
    ),
    Panel(
        "Token accounting rate ([1m])",
        "tok/s",
        450,
        (
            Series("prompt_throughput_tps", "Prompt", COLORS[0]),
            Series("generation_throughput_tps", "Generation", COLORS[2]),
        ),
    ),
    Panel(
        "GPU and KV Cache",
        "%",
        100,
        (
            Series("gpu_util_pct", "GPU utilization", COLORS[0]),
            Series("kv_cache_usage_pct", "KV Cache", COLORS[2]),
        ),
    ),
    Panel(
        "Server histogram P95 ([1m])",
        "seconds",
        16,
        (
            Series("p95_queue_ms", "Queue", COLORS[1], 0.001),
            Series("p95_ttft_ms", "TTFT", COLORS[0], 0.001),
            Series("p95_e2e_ms", "E2E", COLORS[2], 0.001),
        ),
    ),
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="生成 Phase 3 统一时间线 SVG。")
    parser.add_argument("--experiment-dir", type=Path, required=True)
    parser.add_argument(
        "--output",
        type=Path,
        help="默认写入 <experiment-dir>/monitoring/timeline.svg。",
    )
    return parser.parse_args()


def finite(raw: str) -> float | None:
    if not raw:
        return None
    value = float(raw)
    return value if math.isfinite(value) else None


def load_rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as file:
        rows = list(csv.DictReader(file))
    if len(rows) < 2:
        raise ValueError(f"时间线样本不足: {path}")
    required = {series.column for panel in PANELS for series in panel.series}
    missing = required.difference(rows[0])
    if missing:
        raise ValueError(f"时间线缺少列: {sorted(missing)}")
    return rows


def line(x1: float, y1: float, x2: float, y2: float, **attrs: str) -> str:
    extra = " ".join(f'{key}="{value}"' for key, value in attrs.items())
    return (
        f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" '
        f'y2="{y2:.1f}" {extra}/>'
    )


def text(x: float, y: float, value: str, css: str, anchor: str = "start") -> str:
    return (
        f'<text x="{x:.1f}" y="{y:.1f}" class="{css}" '
        f'text-anchor="{anchor}">{html.escape(value)}</text>'
    )


def segments(
    rows: list[dict[str, str]],
    series: Series,
    x_for: Callable[[float], float],
    y_for: Callable[[float], float],
) -> list[str]:
    paths: list[str] = []
    current: list[str] = []
    for row in rows:
        value = finite(row[series.column])
        if value is None:
            if current:
                paths.append(" ".join(current))
                current = []
            continue
        point = f"{x_for(float(row['timestamp'])):.1f},{y_for(value * series.scale):.1f}"
        current.append(point)
    if current:
        paths.append(" ".join(current))
    return paths


def main() -> int:
    args = parse_args()
    experiment_dir = args.experiment_dir.resolve()
    timeline = experiment_dir / "monitoring" / "timeline.csv"
    rows = load_rows(timeline)
    output = args.output.resolve() if args.output else timeline.with_suffix(".svg")

    timestamps = [float(row["timestamp"]) for row in rows]
    start, end = min(timestamps), max(timestamps)
    duration = end - start
    if duration <= 0:
        raise ValueError("时间线时长必须大于 0")

    width, height = 1280, 920
    left, panel_width, panel_height = 85, 1125, 155
    panel_tops = [120, 315, 510, 705]
    items = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" role="img">',
        "<style>",
        f"text{{font-family:Inter,Arial,'Noto Sans CJK SC',sans-serif;fill:{TEXT}}}",
        ".title{font-size:25px;font-weight:700}",
        f".subtitle{{font-size:13px;fill:{MUTED}}}",
        ".panel{font-size:15px;font-weight:700}",
        f".axis{{font-size:11px;fill:{MUTED}}}",
        ".legend{font-size:11px;font-weight:600}",
        "</style>",
        f'<rect width="{width}" height="{height}" fill="#ffffff"/>',
        text(left, 42, "Unified vLLM serving and GPU timeline", "title"),
        text(
            left,
            67,
            f"{experiment_dir.name} · Prometheus 15 s scrape · 1 minute rate window",
            "subtitle",
        ),
        text(
            left,
            87,
            "Prompt rate is credited near first-token time; histogram P95 is bucket-estimated.",
            "subtitle",
        ),
    ]

    x_for = lambda timestamp: left + (timestamp - start) / duration * panel_width
    for panel, top in zip(PANELS, panel_tops, strict=True):
        items.append(text(left, top - 15, f"{panel.title} ({panel.unit})", "panel"))
        for tick in range(5):
            fraction = tick / 4
            y = top + panel_height - fraction * panel_height
            items.append(line(left, y, left + panel_width, y, stroke=GRID, **{"stroke-width": "1"}))
            label = panel.maximum * fraction
            digits = 0 if panel.maximum >= 10 else 1
            items.append(text(left - 10, y + 4, f"{label:.{digits}f}", "axis", "end"))

        y_for = lambda value, panel=panel, top=top: top + panel_height - min(
            panel.maximum, max(0.0, value)
        ) / panel.maximum * panel_height
        legend_x = left + panel_width
        for series in reversed(panel.series):
            legend_x -= 105
            items.append(
                line(
                    legend_x,
                    top - 20,
                    legend_x + 22,
                    top - 20,
                    stroke=series.color,
                    **{"stroke-width": "3"},
                )
            )
            items.append(text(legend_x + 27, top - 16, series.label, "legend"))

        for series in panel.series:
            for points in segments(rows, series, x_for, y_for):
                items.append(
                    f'<polyline points="{points}" fill="none" stroke="{series.color}" '
                    'stroke-width="2.5" stroke-linejoin="round" stroke-linecap="round"/>'
                )

    for tick in range(6):
        fraction = tick / 5
        x = left + fraction * panel_width
        minute = duration * fraction / 60
        items.append(text(x, 890, f"{minute:.1f}", "axis", "middle"))
    items.append(text(left + panel_width / 2, 912, "Minutes from export window start", "axis", "middle"))
    items.append("</svg>")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("\n".join(items) + "\n", encoding="utf-8")
    print(output)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (KeyError, OSError, TypeError, ValueError) as error:
        print(f"ERROR: {error}")
        raise SystemExit(1)
