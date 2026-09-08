#!/usr/bin/env python3
"""从已提交的 aggregate.json 生成无第三方依赖的性能 SVG 图表。"""

from __future__ import annotations

import argparse
import html
import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_DIR = REPO_ROOT / "analysis" / "generated"

HISTORICAL_SHORT = {
    1: "results/2026-09-04/20260904-170304-short-c1/aggregate.json",
    2: "results/2026-09-05/20260905-125150-short-c2/aggregate.json",
    4: "results/2026-09-05/20260905-134529-short-c4/aggregate.json",
    8: "results/2026-09-05/20260905-174433-short-c8/aggregate.json",
    16: "results/2026-09-05/20260905-183347-short-c16/aggregate.json",
}

MNS_COMPARISON = {
    "mns8": "results/2026-09-05/20260905-183347-short-c16/aggregate.json",
    "mns16": "results/2026-09-06/20260906-123749-short-c16-mns16/aggregate.json",
}

WORKLOAD_COMPARISON = {
    "Short\n256/128": "results/2026-09-06/20260906-133720-short-c8-mns8/aggregate.json",
    "Prefill\n1024/128": "results/2026-09-06/20260906-134338-prefill-focused-c8-mns8/aggregate.json",
    "Decode\n256/256": "results/2026-09-06/20260906-134907-decode-focused-c8-mns8/aggregate.json",
    "Combined\n1024/256": "results/2026-09-06/20260906-135718-long-context-c8-mns8/aggregate.json",
}

ROUTING_COMPARISON = {
    "Kubernetes\nService": "results/2026-09-07/20260907-153612-phase4-static-c16-mns8-r2/aggregate.json",
    "Direct fixed\n8 / 8": "results/2026-09-07/20260907-023250-phase4-direct-split-c16-mns8-r2/aggregate.json",
    "Least-inflight\nproxy": "results/2026-09-08/20260908-002836-phase4-least-inflight-c16-mns8-r2/aggregate.json",
}

COLORS = ["#2563eb", "#0d9488", "#d97706", "#7c3aed", "#dc2626"]
GRID = "#d8dee9"
TEXT = "#172033"
MUTED = "#64748b"
SLO = "#dc2626"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="读取 aggregate.json 并生成可复现的 SVG 性能图。"
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help="输出目录，默认 analysis/generated。",
    )
    return parser.parse_args()


def load_aggregate(relative_path: str) -> dict[str, Any]:
    path = REPO_ROOT / relative_path
    with path.open(encoding="utf-8") as file:
        data = json.load(file)
    if data.get("validation") != "passed":
        raise ValueError(f"聚合结果未通过校验: {path}")
    if not isinstance(data.get("metrics"), dict):
        raise ValueError(f"聚合结果缺少 metrics: {path}")
    return data


def median(data: dict[str, Any], metric: str) -> float:
    value = float(data["metrics"][metric]["median"])
    if not math.isfinite(value):
        raise ValueError(f"{data['experiment_id']}.{metric} 不是有限数值")
    return value


def assert_identity(
    data: dict[str, Any],
    *,
    scenario: str,
    concurrency: int,
    max_num_seqs: int | None,
) -> None:
    scenario_value = data["scenario"]
    scenario_name = (
        scenario_value["name"] if isinstance(scenario_value, dict) else scenario_value
    )
    actual_base = (scenario_name, data["selected_concurrency"])
    expected_base = (scenario, concurrency)
    if actual_base != expected_base:
        raise ValueError(
            f"{data['experiment_id']} 身份不符: "
            f"actual={actual_base}, expected={expected_base}"
        )
    if max_num_seqs is not None:
        actual_mns = data["server"].get("engine", {}).get("max_num_seqs")
        if actual_mns != max_num_seqs:
            raise ValueError(
                f"{data['experiment_id']} max_num_seqs={actual_mns!r}，"
                f"期望 {max_num_seqs}"
            )


class SVG:
    def __init__(self, width: int, height: int) -> None:
        self.width = width
        self.height = height
        self.items = [
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" '
            f'height="{height}" viewBox="0 0 {width} {height}" role="img">',
            "<style>",
            "text{font-family:Inter,Arial,'Noto Sans CJK SC',sans-serif;fill:#172033}",
            ".title{font-size:26px;font-weight:700}",
            ".subtitle{font-size:14px;fill:#64748b}",
            ".panel{font-size:16px;font-weight:700}",
            ".axis{font-size:12px;fill:#64748b}",
            ".value{font-size:12px;font-weight:600}",
            ".note{font-size:12px;fill:#64748b}",
            "</style>",
            f'<rect width="{width}" height="{height}" fill="#ffffff"/>',
        ]

    def line(
        self,
        x1: float,
        y1: float,
        x2: float,
        y2: float,
        *,
        stroke: str = GRID,
        width: float = 1,
        dash: str | None = None,
    ) -> None:
        dashed = f' stroke-dasharray="{dash}"' if dash else ""
        self.items.append(
            f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" '
            f'y2="{y2:.1f}" stroke="{stroke}" stroke-width="{width}"{dashed}/>'
        )

    def rect(
        self,
        x: float,
        y: float,
        width: float,
        height: float,
        *,
        fill: str,
        radius: float = 0,
        opacity: float = 1,
    ) -> None:
        self.items.append(
            f'<rect x="{x:.1f}" y="{y:.1f}" width="{width:.1f}" '
            f'height="{height:.1f}" rx="{radius}" fill="{fill}" opacity="{opacity}"/>'
        )

    def text(
        self,
        x: float,
        y: float,
        value: str,
        *,
        css: str = "axis",
        anchor: str = "start",
        fill: str | None = None,
    ) -> None:
        color = f' fill="{fill}"' if fill else ""
        escaped = html.escape(value)
        self.items.append(
            f'<text x="{x:.1f}" y="{y:.1f}" class="{css}" '
            f'text-anchor="{anchor}"{color}>{escaped}</text>'
        )

    def circle(self, x: float, y: float, radius: float, *, fill: str) -> None:
        self.items.append(
            f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{radius}" fill="{fill}"/>'
        )

    def polyline(self, points: list[tuple[float, float]], *, stroke: str) -> None:
        value = " ".join(f"{x:.1f},{y:.1f}" for x, y in points)
        self.items.append(
            f'<polyline points="{value}" fill="none" stroke="{stroke}" '
            'stroke-width="3" stroke-linejoin="round" stroke-linecap="round"/>'
        )

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("\n".join([*self.items, "</svg>", ""]), encoding="utf-8")


@dataclass(frozen=True)
class Panel:
    title: str
    metric: str
    unit: str
    digits: int
    threshold: float | None = None
    threshold_label: str | None = None


def nice_max(value: float) -> float:
    if value <= 0:
        return 1.0
    exponent = 10 ** math.floor(math.log10(value))
    scaled = value / exponent
    step = 1 if scaled <= 1 else 2 if scaled <= 2 else 5 if scaled <= 5 else 10
    return step * exponent


def draw_header(svg: SVG, title: str, subtitle: str) -> None:
    svg.text(55, 45, title, css="title")
    svg.text(55, 70, subtitle, css="subtitle")


def draw_line_panel(
    svg: SVG,
    *,
    x: float,
    y: float,
    width: float,
    height: float,
    title: str,
    categories: list[str],
    values: list[float],
    unit: str,
    digits: int,
    threshold: float | None = None,
    threshold_label: str | None = None,
) -> None:
    svg.text(x, y - 14, f"{title} ({unit})", css="panel")
    top_value = max([*values, threshold or 0]) * 1.12
    y_max = nice_max(top_value)
    for index in range(5):
        fraction = index / 4
        grid_y = y + height - fraction * height
        svg.line(x, grid_y, x + width, grid_y)
        svg.text(x - 10, grid_y + 4, f"{y_max * fraction:.{digits}f}", anchor="end")

    x_step = width / max(1, len(categories) - 1)
    points: list[tuple[float, float]] = []
    for index, (category, value) in enumerate(zip(categories, values, strict=True)):
        point_x = x + index * x_step
        point_y = y + height - value / y_max * height
        points.append((point_x, point_y))
        svg.text(point_x, y + height + 22, category, anchor="middle")
    svg.polyline(points, stroke=COLORS[0])
    for point_x, point_y in points:
        svg.circle(point_x, point_y, 5, fill=COLORS[0])
    for (point_x, point_y), value in zip(points, values, strict=True):
        svg.text(
            point_x,
            point_y - 10,
            f"{value:.{digits}f}",
            css="value",
            anchor="middle",
        )

    if threshold is not None:
        threshold_y = y + height - threshold / y_max * height
        svg.line(x, threshold_y, x + width, threshold_y, stroke=SLO, width=1.5, dash="7 5")
        svg.text(
            x + 3,
            threshold_y - 6,
            threshold_label or f"SLO {threshold:g}",
            anchor="start",
            fill=SLO,
        )


def draw_bar_panel(
    svg: SVG,
    *,
    x: float,
    y: float,
    width: float,
    height: float,
    panel: Panel,
    categories: list[str],
    values: list[float],
) -> None:
    svg.text(x, y - 14, f"{panel.title} ({panel.unit})", css="panel")
    top_value = max([*values, panel.threshold or 0]) * 1.15
    y_max = nice_max(top_value)
    for index in range(5):
        fraction = index / 4
        grid_y = y + height - fraction * height
        svg.line(x, grid_y, x + width, grid_y)
        svg.text(x - 10, grid_y + 4, f"{y_max * fraction:.{panel.digits}f}", anchor="end")

    slot = width / len(categories)
    bar_width = slot * 0.56
    for index, (category, value) in enumerate(zip(categories, values, strict=True)):
        bar_x = x + index * slot + (slot - bar_width) / 2
        bar_height = value / y_max * height
        bar_y = y + height - bar_height
        svg.rect(bar_x, bar_y, bar_width, bar_height, fill=COLORS[index], radius=4)
        svg.text(
            bar_x + bar_width / 2,
            bar_y - 7,
            f"{value:.{panel.digits}f}",
            css="value",
            anchor="middle",
        )
        lines = category.split("\n")
        for line_index, line in enumerate(lines):
            svg.text(
                bar_x + bar_width / 2,
                y + height + 20 + line_index * 14,
                line,
                anchor="middle",
            )

    if panel.threshold is not None:
        threshold_y = y + height - panel.threshold / y_max * height
        svg.line(x, threshold_y, x + width, threshold_y, stroke=SLO, width=1.5, dash="7 5")
        svg.text(
            x + 3,
            threshold_y - 6,
            panel.threshold_label or f"SLO {panel.threshold:g}",
            anchor="start",
            fill=SLO,
        )


def generate_concurrency_chart(output_dir: Path) -> Path:
    categories = [str(value) for value in HISTORICAL_SHORT]
    rows = []
    for concurrency, path in HISTORICAL_SHORT.items():
        data = load_aggregate(path)
        # 早期 aggregate schema 尚未记录 engine 字段；mns8 由当时版本化
        # Deployment 与实验 README 证明，脚本这里只验证场景和客户端并发。
        assert_identity(data, scenario="short", concurrency=concurrency, max_num_seqs=None)
        rows.append(data)

    panels = [
        Panel("Output throughput", "output_throughput", "tok/s", 0),
        Panel("Request throughput", "request_throughput", "req/s", 2),
        Panel("P95 TTFT", "p95_ttft_ms", "ms", 0, 600, "Short SLO 600 ms"),
        Panel("P95 E2E", "p95_e2el_ms", "ms", 0, 6000, "Short SLO 6000 ms"),
    ]
    svg = SVG(1280, 780)
    draw_header(
        svg,
        "Short workload concurrency scan",
        "Qwen3-8B BF16 · 256/128 tokens · one A10 · max-num-seqs=8 · median of 3 repeats · historical GPU 3",
    )
    positions = [(85, 130), (685, 130), (85, 455), (685, 455)]
    for panel, (x, y) in zip(panels, positions, strict=True):
        draw_line_panel(
            svg,
            x=x,
            y=y,
            width=500,
            height=220,
            title=panel.title,
            categories=categories,
            values=[median(row, panel.metric) for row in rows],
            unit=panel.unit,
            digits=panel.digits,
            threshold=panel.threshold,
            threshold_label=panel.threshold_label,
        )
    svg.text(640, 765, "Concurrency", css="note", anchor="middle")
    path = output_dir / "concurrency-scan.svg"
    svg.save(path)
    return path


def generate_bar_grid(
    *,
    output_dir: Path,
    filename: str,
    title: str,
    subtitle: str,
    inputs: dict[str, str],
    expected: dict[str, tuple[str, int, int | None]],
    panels: list[Panel],
    footnote: str,
) -> Path:
    categories = list(inputs)
    rows = []
    for category, relative_path in inputs.items():
        data = load_aggregate(relative_path)
        scenario, concurrency, max_num_seqs = expected[category]
        assert_identity(
            data,
            scenario=scenario,
            concurrency=concurrency,
            max_num_seqs=max_num_seqs,
        )
        rows.append(data)

    svg = SVG(1280, 800)
    draw_header(svg, title, subtitle)
    positions = [(85, 130), (685, 130), (85, 465), (685, 465)]
    for panel, (x, y) in zip(panels, positions, strict=True):
        draw_bar_panel(
            svg,
            x=x,
            y=y,
            width=500,
            height=220,
            panel=panel,
            categories=categories,
            values=[median(row, panel.metric) for row in rows],
        )
    svg.text(640, 786, footnote, css="note", anchor="middle")
    path = output_dir / filename
    svg.save(path)
    return path


def main() -> int:
    args = parse_args()
    output_dir = args.output_dir.resolve()
    paths = [generate_concurrency_chart(output_dir)]

    common_panels = [
        Panel("Output throughput", "output_throughput", "tok/s", 0),
        Panel("P95 TTFT", "p95_ttft_ms", "ms", 0, 600, "Short SLO 600 ms"),
        Panel("P95 TPOT", "p95_tpot_ms", "ms", 1, 50, "Short SLO 50 ms"),
        Panel("P95 E2E", "p95_e2el_ms", "ms", 0, 6000, "Short SLO 6000 ms"),
    ]
    paths.append(
        generate_bar_grid(
            output_dir=output_dir,
            filename="max-num-seqs-comparison.svg",
            title="max-num-seqs parameter comparison",
            subtitle="Qwen3-8B BF16 · c16 · 256/128 tokens · one A10 · median of 3 repeats · historical GPU 3",
            inputs=MNS_COMPARISON,
            expected={
                # 早期 c16 aggregate 尚未包含 engine 字段，不能在此伪造断言。
                "mns8": ("short", 16, None),
                "mns16": ("short", 16, 16),
            },
            panels=common_panels,
            footnote="mns16 improves throughput and queueing delay, but P95 TTFT and E2E still miss the pre-registered Short SLO.",
        )
    )

    paths.append(
        generate_bar_grid(
            output_dir=output_dir,
            filename="phase4-routing-comparison.svg",
            title="Phase 4 dual-replica routing comparison",
            subtitle="Qwen3-8B BF16 · c16/mns8 · 256/128 tokens · two A10 · median of 3 repeats · 100 measured requests/repeat",
            inputs=ROUTING_COMPARISON,
            expected={
                "Kubernetes\nService": ("phase4-static", 16, 8),
                "Direct fixed\n8 / 8": ("phase4-direct-split", 16, 8),
                "Least-inflight\nproxy": ("phase4-least-inflight", 16, 8),
            },
            panels=common_panels,
            footnote="Least-inflight matches direct 8/8 throughput within run-to-run noise and restores the pre-registered Short SLO; fixed synthetic workload only.",
        )
    )

    long_panels = [
        Panel("Output throughput", "output_throughput", "tok/s", 0),
        Panel("P95 TTFT", "p95_ttft_ms", "ms", 0, 1500, "Long SLO 1500 ms"),
        Panel("P95 TPOT", "p95_tpot_ms", "ms", 1, 55, "Long SLO 55 ms"),
        Panel("P95 E2E", "p95_e2el_ms", "ms", 0, 13000, "Long SLO 13000 ms"),
    ]
    paths.append(
        generate_bar_grid(
            output_dir=output_dir,
            filename="workload-comparison.svg",
            title="Prefill and Decode workload comparison",
            subtitle="Qwen3-8B BF16 · c8/mns8 · one A10 · median of 3 repeats · current GPU 1 · labels are prompt/output tokens",
            inputs=WORKLOAD_COMPARISON,
            expected={
                "Short\n256/128": ("short", 8, 8),
                "Prefill\n1024/128": ("prefill-focused", 8, 8),
                "Decode\n256/256": ("decode-focused", 8, 8),
                "Combined\n1024/256": ("long-context", 8, 8),
            },
            panels=long_panels,
            footnote="Long SLO lines evaluate the three long workloads; Short keeps its separate 600/50/6000 ms SLO.",
        )
    )

    for path in paths:
        print(path.relative_to(REPO_ROOT))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (KeyError, OSError, TypeError, ValueError, json.JSONDecodeError) as error:
        raise SystemExit(f"ERROR: {error}") from error
