#!/usr/bin/env python3
"""校验并汇总同一实验目录中的多轮 vLLM benchmark 结果。"""

from __future__ import annotations

import argparse
import csv
import json
import math
import statistics
import sys
from pathlib import Path
from typing import Any

import yaml


# 这些字段覆盖吞吐、首 Token、逐 Token 和端到端延迟四类核心指标。
METRICS = {
    "duration": "s",
    "request_throughput": "req/s",
    "output_throughput": "tok/s",
    "total_token_throughput": "tok/s",
    "mean_ttft_ms": "ms",
    "p50_ttft_ms": "ms",
    "p95_ttft_ms": "ms",
    "p99_ttft_ms": "ms",
    "mean_tpot_ms": "ms",
    "p50_tpot_ms": "ms",
    "p95_tpot_ms": "ms",
    "p99_tpot_ms": "ms",
    "mean_itl_ms": "ms",
    "p95_itl_ms": "ms",
    "mean_e2el_ms": "ms",
    "p50_e2el_ms": "ms",
    "p95_e2el_ms": "ms",
    "p99_e2el_ms": "ms",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="校验 repeat-*.json，并生成 per-repeat.csv、summary.csv 和 aggregate.json。"
    )
    parser.add_argument("--experiment-dir", type=Path, required=True)
    parser.add_argument(
        "--check-only",
        action="store_true",
        help="只校验和打印摘要，不写入汇总文件。",
    )
    return parser.parse_args()


def load_yaml(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as file:
        data = yaml.safe_load(file)
    if not isinstance(data, dict):
        raise ValueError(f"YAML 顶层必须是对象: {path}")
    return data


def load_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as file:
        data = json.load(file)
    if not isinstance(data, dict):
        raise ValueError(f"JSON 顶层必须是对象: {path}")
    return data


def require_positive_int(value: Any, label: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
        raise ValueError(f"{label} 必须是正整数，实际为 {value!r}")
    return value


def require_finite_number(value: Any, label: str) -> float:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise ValueError(f"{label} 必须是数值，实际为 {value!r}")
    number = float(value)
    if not math.isfinite(number):
        raise ValueError(f"{label} 必须是有限数值，实际为 {value!r}")
    return number


def validate_repeat(
    path: Path,
    data: dict[str, Any],
    metadata: dict[str, Any],
) -> dict[str, Any]:
    scenario = metadata["scenario"]
    expected_requests = require_positive_int(
        scenario["measured_requests"], "scenario.measured_requests"
    )
    expected_input = require_positive_int(
        scenario["prompt_tokens"], "scenario.prompt_tokens"
    )
    expected_output = require_positive_int(
        scenario["output_tokens"], "scenario.output_tokens"
    )
    expected_concurrency = require_positive_int(
        metadata["selected_concurrency"], "selected_concurrency"
    )

    completed = require_positive_int(data.get("completed"), f"{path.name}.completed")
    num_prompts = require_positive_int(
        data.get("num_prompts"), f"{path.name}.num_prompts"
    )
    if completed != expected_requests or num_prompts != expected_requests:
        raise ValueError(
            f"{path.name}: 期望 {expected_requests} 个请求，"
            f"num_prompts={num_prompts}, completed={completed}"
        )
    if data.get("max_concurrency") != expected_concurrency:
        raise ValueError(
            f"{path.name}: max_concurrency={data.get('max_concurrency')}，"
            f"期望 {expected_concurrency}"
        )
    if data.get("model_id") != metadata.get("model"):
        raise ValueError(
            f"{path.name}: model_id={data.get('model_id')!r}，"
            f"期望 {metadata.get('model')!r}"
        )

    input_lens = data.get("input_lens")
    output_lens = data.get("output_lens")
    errors = data.get("errors")
    for values, label in (
        (input_lens, "input_lens"),
        (output_lens, "output_lens"),
        (errors, "errors"),
    ):
        if not isinstance(values, list) or len(values) != expected_requests:
            actual_length = len(values) if isinstance(values, list) else "非列表"
            raise ValueError(
                f"{path.name}.{label} 长度应为 {expected_requests}，实际为 {actual_length}"
            )

    if any(length != expected_input for length in input_lens):
        raise ValueError(f"{path.name}: 存在不等于 {expected_input} 的输入长度")
    if any(length != expected_output for length in output_lens):
        raise ValueError(f"{path.name}: 存在不等于 {expected_output} 的输出长度")
    nonempty_errors = [error for error in errors if str(error).strip()]
    if nonempty_errors:
        raise ValueError(f"{path.name}: 发现 {len(nonempty_errors)} 个非空错误")

    row: dict[str, Any] = {
        "repeat": int(path.stem.split("-")[-1]),
        "file": path.name,
        "completed": completed,
        "failed": 0,
        "total_input_tokens": require_finite_number(
            data.get("total_input_tokens"), f"{path.name}.total_input_tokens"
        ),
        "total_output_tokens": require_finite_number(
            data.get("total_output_tokens"), f"{path.name}.total_output_tokens"
        ),
    }
    for metric in METRICS:
        row[metric] = require_finite_number(data.get(metric), f"{path.name}.{metric}")
    return row


def summarize(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    summaries: list[dict[str, Any]] = []
    for metric, unit in METRICS.items():
        values = [float(row[metric]) for row in rows]
        mean = statistics.fmean(values)
        median = statistics.median(values)
        stdev = statistics.stdev(values) if len(values) > 1 else 0.0
        summaries.append(
            {
                "metric": metric,
                "unit": unit,
                "repeat_count": len(values),
                "mean": mean,
                "median": median,
                "min": min(values),
                "max": max(values),
                "stdev": stdev,
                "cv_percent": (stdev / mean * 100.0) if mean else 0.0,
            }
        )
    return summaries


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as file:
        # csv 模块默认使用 CRLF；仓库统一写 LF，避免 Git 将 \r 识别成行尾空白。
        writer = csv.DictWriter(
            file,
            fieldnames=list(rows[0]),
            lineterminator="\n",
        )
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    args = parse_args()
    experiment_dir = args.experiment_dir.resolve()
    metadata_path = experiment_dir / "metadata.yaml"
    if not metadata_path.is_file():
        raise FileNotFoundError(f"缺少实验元数据: {metadata_path}")

    metadata = load_yaml(metadata_path)
    expected_repeats = require_positive_int(
        metadata["scenario"]["repeats"], "scenario.repeats"
    )
    repeat_paths = sorted(experiment_dir.glob("repeat-*.json"))
    if len(repeat_paths) != expected_repeats:
        raise ValueError(
            f"期望 {expected_repeats} 份 repeat JSON，实际找到 {len(repeat_paths)} 份"
        )

    rows = [validate_repeat(path, load_json(path), metadata) for path in repeat_paths]
    summaries = summarize(rows)
    core_metrics = {
        row["metric"]: row["median"]
        for row in summaries
        if row["metric"]
        in {
            "request_throughput",
            "output_throughput",
            "total_token_throughput",
            "mean_ttft_ms",
            "mean_tpot_ms",
            "mean_e2el_ms",
        }
    }

    print(
        f"PASS: {metadata['experiment_id']}，{len(rows)} 轮，"
        f"每轮 {metadata['scenario']['measured_requests']} 个请求，失败 0"
    )
    for metric, value in core_metrics.items():
        print(f"  median {metric}={value:.6f}")

    if args.check_only:
        print("check-only: 未写入汇总文件")
        return 0

    write_csv(experiment_dir / "per-repeat.csv", rows)
    write_csv(experiment_dir / "summary.csv", summaries)
    aggregate = {
        "validation": "passed",
        "experiment_id": metadata["experiment_id"],
        "git_commit": metadata["git_commit"],
        "model": metadata["model"],
        "server": metadata["server"],
        "scenario": metadata["scenario"],
        "selected_concurrency": metadata["selected_concurrency"],
        "repeat_files": [path.name for path in repeat_paths],
        "metrics": {row["metric"]: row for row in summaries},
    }
    with (experiment_dir / "aggregate.json").open("w", encoding="utf-8") as file:
        json.dump(aggregate, file, ensure_ascii=False, indent=2)
        file.write("\n")

    print("已生成: per-repeat.csv, summary.csv, aggregate.json")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (KeyError, OSError, ValueError, json.JSONDecodeError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        raise SystemExit(1)
