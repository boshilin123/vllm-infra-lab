#!/usr/bin/env python3
"""用已保存的 vLLM 时间线离线回放 1→2→1 副本状态机。"""

from __future__ import annotations

import argparse
import csv
import json
import math
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_POLICY = REPO_ROOT / "analysis" / "autoscaling-policy.json"


@dataclass(frozen=True)
class Policy:
    scrape_interval_seconds: int
    min_replicas: int
    max_replicas: int
    waiting_greater_than: float
    scale_out_consecutive_samples: int
    startup_delay_seconds: int
    waiting_equals: float
    running_at_most: float
    low_load_seconds: int
    minimum_second_replica_ready_seconds: int


@dataclass(frozen=True)
class Sample:
    timestamp: float
    timestamp_utc: str
    running: float
    waiting: float


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="读取 timeline.csv，离线模拟最多两个 vLLM 副本的弹性决策。"
    )
    parser.add_argument("--timeline", type=Path, required=True)
    parser.add_argument("--policy", type=Path, default=DEFAULT_POLICY)
    parser.add_argument(
        "--output-dir",
        type=Path,
        help="默认写入 timeline.csv 同级目录下的 autoscaling-simulation。",
    )
    return parser.parse_args()


def load_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as file:
        data = json.load(file)
    if not isinstance(data, dict):
        raise ValueError(f"JSON 顶层必须是对象: {path}")
    return data


def positive_int(value: Any, label: str) -> int:
    parsed = int(value)
    if parsed <= 0:
        raise ValueError(f"{label} 必须为正整数")
    return parsed


def load_policy(path: Path) -> Policy:
    data = load_json(path)
    if int(data.get("schema_version", 0)) != 1:
        raise ValueError("仅支持 schema_version=1")
    scale_out = data["scale_out"]
    scale_in = data["scale_in"]
    policy = Policy(
        scrape_interval_seconds=positive_int(
            data["scrape_interval_seconds"], "scrape_interval_seconds"
        ),
        min_replicas=positive_int(data["min_replicas"], "min_replicas"),
        max_replicas=positive_int(data["max_replicas"], "max_replicas"),
        waiting_greater_than=float(scale_out["waiting_greater_than"]),
        scale_out_consecutive_samples=positive_int(
            scale_out["consecutive_samples"], "scale_out.consecutive_samples"
        ),
        startup_delay_seconds=positive_int(
            scale_out["startup_delay_seconds"], "scale_out.startup_delay_seconds"
        ),
        waiting_equals=float(scale_in["waiting_equals"]),
        running_at_most=float(scale_in["running_at_most"]),
        low_load_seconds=positive_int(
            scale_in["low_load_seconds"], "scale_in.low_load_seconds"
        ),
        minimum_second_replica_ready_seconds=positive_int(
            scale_in["minimum_second_replica_ready_seconds"],
            "scale_in.minimum_second_replica_ready_seconds",
        ),
    )
    if policy.max_replicas != 2 or policy.min_replicas != 1:
        raise ValueError("本项目安全边界要求 min_replicas=1、max_replicas=2")
    return policy


def parse_metric(row: dict[str, str], key: str) -> float:
    raw = row.get(key, "")
    if raw == "":
        raise ValueError(f"timeline 缺少 {key} 样本")
    value = float(raw)
    if not math.isfinite(value) or value < 0:
        raise ValueError(f"{key} 必须是非负有限数: {raw!r}")
    return value


def load_samples(path: Path, expected_interval: int) -> list[Sample]:
    samples: list[Sample] = []
    with path.open(encoding="utf-8", newline="") as file:
        for row in csv.DictReader(file):
            samples.append(
                Sample(
                    timestamp=parse_metric(row, "timestamp"),
                    timestamp_utc=row["timestamp_utc"],
                    running=parse_metric(row, "running_requests"),
                    waiting=parse_metric(row, "waiting_requests"),
                )
            )
    if not samples:
        raise ValueError(f"timeline 没有数据行: {path}")
    for previous, current in zip(samples, samples[1:]):
        delta = current.timestamp - previous.timestamp
        if delta <= 0:
            raise ValueError("timeline timestamp 必须严格递增")
        if not math.isclose(delta, expected_interval, abs_tol=0.001):
            raise ValueError(
                f"采样间隔 {delta:.3f}s 与策略 {expected_interval}s 不一致"
            )
    return samples


def iso_utc(timestamp: float | None) -> str | None:
    if timestamp is None:
        return None
    return (
        datetime.fromtimestamp(timestamp, tz=timezone.utc)
        .isoformat(timespec="seconds")
        .replace("+00:00", "Z")
    )


def simulate(
    samples: list[Sample], policy: Policy
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    desired = policy.min_replicas
    ready = policy.min_replicas
    waiting_streak = 0
    pending_ready_at: float | None = None
    scale_out_requested_at: float | None = None
    second_scheduled_ready_at: float | None = None
    second_ready_at: float | None = None
    second_ready_since: float | None = None
    second_ready_observed_at: float | None = None
    low_load_since: float | None = None
    scale_in_requested_at: float | None = None
    rows: list[dict[str, Any]] = []

    for sample in samples:
        events: list[str] = []
        if pending_ready_at is not None and sample.timestamp >= pending_ready_at:
            ready = policy.max_replicas
            second_ready_at = pending_ready_at
            second_ready_since = pending_ready_at
            second_ready_observed_at = sample.timestamp
            pending_ready_at = None
            events.append("second_replica_ready_observed")

        if desired == policy.min_replicas:
            if sample.waiting > policy.waiting_greater_than:
                waiting_streak += 1
            else:
                waiting_streak = 0
            if waiting_streak >= policy.scale_out_consecutive_samples:
                desired = policy.max_replicas
                scale_out_requested_at = sample.timestamp
                pending_ready_at = sample.timestamp + policy.startup_delay_seconds
                second_scheduled_ready_at = pending_ready_at
                waiting_streak = 0
                events.append("scale_out_requested")
        else:
            waiting_streak = 0

        low_load = (
            ready == policy.max_replicas
            and sample.waiting == policy.waiting_equals
            and sample.running <= policy.running_at_most
        )
        if low_load:
            if low_load_since is None:
                low_load_since = sample.timestamp
        else:
            low_load_since = None

        low_load_long_enough = (
            low_load_since is not None
            and sample.timestamp - low_load_since >= policy.low_load_seconds
        )
        second_ready_long_enough = (
            second_ready_since is not None
            and sample.timestamp - second_ready_since
            >= policy.minimum_second_replica_ready_seconds
        )
        if (
            desired == policy.max_replicas
            and ready == policy.max_replicas
            and low_load_long_enough
            and second_ready_long_enough
        ):
            desired = policy.min_replicas
            ready = policy.min_replicas
            scale_in_requested_at = sample.timestamp
            low_load_since = None
            second_ready_since = None
            events.append("scale_in_requested")

        rows.append(
            {
                "timestamp": f"{sample.timestamp:.3f}",
                "timestamp_utc": sample.timestamp_utc,
                "running_requests": sample.running,
                "waiting_requests": sample.waiting,
                "desired_replicas": desired,
                "ready_replicas": ready,
                "pending_ready_at_utc": iso_utc(pending_ready_at) or "",
                "event": ";".join(events),
            }
        )

    active = [sample for sample in samples if sample.running > 0 or sample.waiting > 0]
    waiting = [sample for sample in samples if sample.waiting > 0]
    last_active_at = active[-1].timestamp if active else None
    capacity_overlapped_observed_load = (
        second_ready_at is not None
        and last_active_at is not None
        and second_ready_at <= last_active_at
    )
    summary = {
        "schema_version": 1,
        "sample_count": len(samples),
        "trace_start_utc": samples[0].timestamp_utc,
        "trace_end_utc": samples[-1].timestamp_utc,
        "first_waiting_utc": iso_utc(waiting[0].timestamp) if waiting else None,
        "last_observed_active_utc": iso_utc(last_active_at),
        "max_running_requests": max(sample.running for sample in samples),
        "max_waiting_requests": max(sample.waiting for sample in samples),
        "scale_out_requested_utc": iso_utc(scale_out_requested_at),
        "second_replica_scheduled_ready_utc": iso_utc(second_scheduled_ready_at),
        "second_replica_ready_observed_utc": iso_utc(second_ready_observed_at),
        "scale_in_requested_utc": iso_utc(scale_in_requested_at),
        "capacity_overlapped_observed_load": capacity_overlapped_observed_load,
        "conclusion": (
            "second replica would become ready after the observed load ended"
            if scale_out_requested_at is not None
            and not capacity_overlapped_observed_load
            else "inspect event timeline"
        ),
    }
    return rows, summary


def write_outputs(
    output_dir: Path,
    rows: list[dict[str, Any]],
    summary: dict[str, Any],
    policy_path: Path,
    timeline_path: Path,
) -> None:
    def display_path(path: Path) -> str:
        try:
            return str(path.relative_to(REPO_ROOT))
        except ValueError:
            return str(path)

    output_dir.mkdir(parents=True, exist_ok=True)
    fieldnames = list(rows[0])
    with (output_dir / "decision-timeline.csv").open(
        "w", encoding="utf-8", newline=""
    ) as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    payload = {
        **summary,
        "policy_file": display_path(policy_path),
        "source_timeline": display_path(timeline_path),
    }
    with (output_dir / "summary.json").open("w", encoding="utf-8") as file:
        json.dump(payload, file, ensure_ascii=False, indent=2, sort_keys=True)
        file.write("\n")


def main() -> int:
    args = parse_args()
    timeline = args.timeline.resolve()
    policy_path = args.policy.resolve()
    if not timeline.is_file():
        raise FileNotFoundError(f"timeline 不存在: {timeline}")
    if not policy_path.is_file():
        raise FileNotFoundError(f"policy 不存在: {policy_path}")
    policy = load_policy(policy_path)
    samples = load_samples(timeline, policy.scrape_interval_seconds)
    rows, summary = simulate(samples, policy)
    output_dir = (
        args.output_dir.resolve()
        if args.output_dir
        else timeline.parent / "autoscaling-simulation"
    )
    write_outputs(output_dir, rows, summary, policy_path, timeline)
    print(f"已生成: {output_dir / 'decision-timeline.csv'}")
    print(f"已生成: {output_dir / 'summary.json'}")
    print(f"结论: {summary['conclusion']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
