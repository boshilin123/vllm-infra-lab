#!/usr/bin/env python3
"""按 benchmark 实验窗口导出 Prometheus 统一时间线。"""

from __future__ import annotations

import argparse
import csv
import json
import math
import statistics
import sys
from datetime import datetime, timedelta, timezone, tzinfo
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from monitoring.prometheus_probe import PrometheusClient  # noqa: E402


DEFAULT_QUERIES = REPO_ROOT / "monitoring" / "prometheus_queries.json"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="读取实验时间和 Prometheus query_range，生成 JSON/CSV 统一时间线。"
    )
    parser.add_argument("--experiment-dir", type=Path, required=True)
    parser.add_argument("--gpu-uuid", required=True)
    parser.add_argument("--namespace", default="vllm-infra-lab")
    parser.add_argument("--base-url", default="http://127.0.0.1:29090")
    parser.add_argument("--queries", type=Path, default=DEFAULT_QUERIES)
    parser.add_argument(
        "--buffer-seconds",
        type=int,
        default=60,
        help="实验前后额外导出的空闲窗口，默认各 60 秒。",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        help="默认写入 <experiment-dir>/monitoring。",
    )
    return parser.parse_args()


def load_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as file:
        data = json.load(file)
    if not isinstance(data, dict):
        raise ValueError(f"JSON 顶层必须是对象: {path}")
    return data


def metadata_timezone(experiment_dir: Path) -> tzinfo:
    metadata_path = experiment_dir / "metadata.yaml"
    if not metadata_path.is_file():
        raise FileNotFoundError(f"实验目录缺少 metadata.yaml: {experiment_dir}")
    created_at: str | None = None
    with metadata_path.open(encoding="utf-8") as file:
        for line in file:
            if line.startswith("created_at:"):
                created_at = line.split(":", 1)[1].strip().strip("'\"")
                break
    if not created_at:
        raise ValueError(f"metadata.yaml 缺少 created_at: {metadata_path}")
    parsed = datetime.fromisoformat(created_at)
    if parsed.tzinfo is None:
        raise ValueError(f"created_at 必须包含 UTC offset: {created_at!r}")
    return parsed.tzinfo


def parse_benchmark_datetime(value: str, experiment_timezone: tzinfo) -> datetime:
    parsed = datetime.strptime(value, "%Y%m%d-%H%M%S")
    return parsed.replace(tzinfo=experiment_timezone)


def experiment_window(experiment_dir: Path, buffer_seconds: int) -> tuple[float, float]:
    if buffer_seconds < 0:
        raise ValueError("buffer-seconds 不能为负数")
    experiment_timezone = metadata_timezone(experiment_dir)
    try:
        start = parse_benchmark_datetime(experiment_dir.name[:15], experiment_timezone)
    except ValueError as error:
        raise ValueError(f"实验目录名不含有效时间: {experiment_dir.name}") from error

    repeat_paths = sorted(experiment_dir.glob("repeat-*.json"))
    if not repeat_paths:
        raise ValueError(f"实验目录没有 repeat-*.json: {experiment_dir}")
    ends: list[datetime] = []
    for path in repeat_paths:
        repeat = load_json(path)
        # vLLM bench writes ``date`` when it finishes and serializes the result,
        # so this is the repeat end timestamp rather than its start timestamp.
        repeat_end = parse_benchmark_datetime(
            str(repeat["date"]), experiment_timezone
        )
        duration = float(repeat["duration"])
        if not math.isfinite(duration) or duration <= 0:
            raise ValueError(f"{path.name}.duration 无效: {duration!r}")
        ends.append(repeat_end)
    buffer = timedelta(seconds=buffer_seconds)
    return (start - buffer).timestamp(), (max(ends) + buffer).timestamp()


def render_query(template: str, namespace: str, gpu_uuid: str) -> str:
    if not gpu_uuid.startswith("GPU-"):
        raise ValueError("gpu-uuid 应以 GPU- 开头")
    for label, value in (("namespace", namespace), ("gpu_uuid", gpu_uuid)):
        if any(character in value for character in ('"', "\\", "\n")):
            raise ValueError(f"{label} 含不安全的 PromQL 标签字符")
    return template.replace("__NAMESPACE__", namespace).replace("__GPU_UUID__", gpu_uuid)


def query_range(
    client: PrometheusClient,
    expression: str,
    start: float,
    end: float,
    step: int,
) -> list[dict[str, Any]]:
    data = client.get(
        "/api/v1/query_range",
        {
            "query": expression,
            "start": f"{start:.3f}",
            "end": f"{end:.3f}",
            "step": str(step),
        },
    )
    if data.get("resultType") != "matrix":
        raise ValueError(f"query_range 未返回 matrix: {expression}")
    result = data.get("result", [])
    if len(result) > 1:
        raise ValueError(f"聚合查询返回 {len(result)} 条时间序列: {expression}")
    return result


def sample_map(result: list[dict[str, Any]]) -> dict[float, float | None]:
    if not result:
        return {}
    samples: dict[float, float | None] = {}
    for timestamp, raw_value in result[0].get("values", []):
        value = float(raw_value)
        samples[float(timestamp)] = value if math.isfinite(value) else None
    return samples


def summarize(values: list[float | None]) -> dict[str, float | int | None]:
    finite = [value for value in values if value is not None and math.isfinite(value)]
    if not finite:
        return {"samples": 0, "min": None, "max": None, "mean": None}
    return {
        "samples": len(finite),
        "min": min(finite),
        "max": max(finite),
        "mean": statistics.fmean(finite),
    }


def iso_utc(timestamp: float) -> str:
    return datetime.fromtimestamp(timestamp, tz=timezone.utc).isoformat().replace("+00:00", "Z")


def main() -> int:
    args = parse_args()
    experiment_dir = args.experiment_dir.resolve()
    if not experiment_dir.is_dir():
        raise FileNotFoundError(f"实验目录不存在: {experiment_dir}")
    query_config_path = args.queries.resolve()
    query_config = load_json(query_config_path)
    step = int(query_config["scrape_interval_seconds"])
    if step <= 0:
        raise ValueError("scrape_interval_seconds 必须为正整数")
    start, end = experiment_window(experiment_dir, args.buffer_seconds)

    client = PrometheusClient(args.base_url)
    build = client.get("/api/v1/status/buildinfo")
    raw: dict[str, Any] = {}
    samples_by_key: dict[str, dict[float, float | None]] = {}
    rendered_queries: list[dict[str, str]] = []
    for item in query_config["queries"]:
        expression = render_query(item["promql"], args.namespace, args.gpu_uuid)
        result = query_range(client, expression, start, end, step)
        raw[item["key"]] = result
        samples_by_key[item["key"]] = sample_map(result)
        rendered_queries.append({**item, "promql": expression})

    timestamps = sorted(
        {timestamp for samples in samples_by_key.values() for timestamp in samples}
    )
    if not timestamps:
        raise ValueError("所有查询均未返回样本，请检查时间窗口和标签")

    output_dir = (
        args.output_dir.resolve()
        if args.output_dir
        else experiment_dir / "monitoring"
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    keys = [item["key"] for item in query_config["queries"]]
    with (output_dir / "timeline.csv").open(
        "w", encoding="utf-8", newline=""
    ) as file:
        writer = csv.DictWriter(
            file,
            fieldnames=["timestamp", "timestamp_utc", *keys],
            lineterminator="\n",
        )
        writer.writeheader()
        for timestamp in timestamps:
            writer.writerow(
                {
                    "timestamp": f"{timestamp:.3f}",
                    "timestamp_utc": iso_utc(timestamp),
                    **{
                        key: samples_by_key[key].get(timestamp)
                        if samples_by_key[key].get(timestamp) is not None
                        else ""
                        for key in keys
                    },
                }
            )

    metadata = {
        "schema_version": 1,
        "experiment_id": experiment_dir.name,
        "prometheus_version": build.get("version"),
        "namespace": args.namespace,
        "gpu_uuid": args.gpu_uuid,
        "start_utc": iso_utc(start),
        "end_utc": iso_utc(end),
        "step_seconds": step,
        "buffer_seconds": args.buffer_seconds,
        "query_config": str(query_config_path.relative_to(REPO_ROOT)),
        "queries": rendered_queries,
    }
    summary = {
        key: summarize([samples_by_key[key].get(timestamp) for timestamp in timestamps])
        for key in keys
    }
    for filename, payload in (
        ("metadata.json", metadata),
        ("raw.json", raw),
        ("summary.json", summary),
    ):
        with (output_dir / filename).open("w", encoding="utf-8") as file:
            json.dump(payload, file, ensure_ascii=False, indent=2, sort_keys=True)
            file.write("\n")

    print(f"experiment: {experiment_dir.name}")
    print(f"window: {metadata['start_utc']} -> {metadata['end_utc']}")
    for key in keys:
        values = summary[key]
        print(f"{key}: samples={values['samples']} max={values['max']}")
    print(f"output: {output_dir}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (
        ConnectionError,
        KeyError,
        OSError,
        RuntimeError,
        TypeError,
        ValueError,
        json.JSONDecodeError,
    ) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        raise SystemExit(1)
