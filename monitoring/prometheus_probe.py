#!/usr/bin/env python3
"""只读探测 Prometheus 中本项目 vLLM 与 DCGM 核心指标。"""

from __future__ import annotations

import argparse
import json
import math
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any


VLLM_SUFFIXES = {
    "num_requests_running",
    "num_requests_waiting",
    "gpu_cache_usage_perc",
    "time_to_first_token_seconds_bucket",
    "e2e_request_latency_seconds_bucket",
    "request_success_total",
    "prompt_tokens_total",
    "generation_tokens_total",
}

DCGM_NAMES = {
    "DCGM_FI_DEV_GPU_UTIL",
    "DCGM_FI_DEV_FB_USED",
    "DCGM_FI_DEV_POWER_USAGE",
    "DCGM_FI_DEV_GPU_TEMP",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="通过本地端口转发只读探测 Prometheus 指标名与标签。"
    )
    parser.add_argument(
        "--base-url",
        default="http://127.0.0.1:29090",
        help="Prometheus 地址，默认 http://127.0.0.1:29090。",
    )
    parser.add_argument("--namespace", default="vllm-infra-lab")
    parser.add_argument(
        "--gpu-uuid",
        help="可选；只保留标签中匹配该 UUID 的 DCGM 时间序列。",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="可选 JSON 输出路径；未指定时只打印到标准输出。",
    )
    return parser.parse_args()


class PrometheusClient:
    def __init__(self, base_url: str) -> None:
        self.base_url = base_url.rstrip("/")
        # 本工具面向 kubectl 的本地端口转发。服务器环境设置了 HTTP(S)
        # 代理；若沿用环境代理，127.0.0.1 请求会被错误发送到代理端口。
        self.opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))

    def get(self, path: str, params: dict[str, str] | None = None) -> Any:
        query = urllib.parse.urlencode(params or {})
        url = f"{self.base_url}{path}"
        if query:
            url = f"{url}?{query}"
        request = urllib.request.Request(
            url,
            headers={"Accept": "application/json"},
            method="GET",
        )
        try:
            with self.opener.open(request, timeout=10) as response:
                payload = json.load(response)
        except urllib.error.URLError as error:
            raise ConnectionError(f"无法访问 Prometheus {url}: {error}") from error
        if payload.get("status") != "success":
            raise RuntimeError(f"Prometheus API 返回失败: {payload!r}")
        return payload["data"]

    def query(self, expression: str) -> list[dict[str, Any]]:
        data = self.get("/api/v1/query", {"query": expression})
        if data.get("resultType") != "vector":
            raise ValueError(
                f"期望 instant vector，实际为 {data.get('resultType')!r}: {expression}"
            )
        return data["result"]


def finite_value(series: dict[str, Any]) -> float:
    value = float(series["value"][1])
    if not math.isfinite(value):
        raise ValueError(f"Prometheus 返回非有限值: {series!r}")
    return value


def metric_names(client: PrometheusClient, matcher: str) -> list[str]:
    series = client.query(f"count by (__name__) ({matcher})")
    return sorted(
        item["metric"]["__name__"]
        for item in series
        if "__name__" in item.get("metric", {})
    )


def compact_series(
    series: list[dict[str, Any]], gpu_uuid: str | None = None
) -> list[dict[str, Any]]:
    compact: list[dict[str, Any]] = []
    for item in series:
        labels = dict(sorted(item.get("metric", {}).items()))
        if gpu_uuid and gpu_uuid not in labels.values():
            continue
        compact.append({"labels": labels, "value": finite_value(item)})
    return compact


def suffix_matches(names: list[str]) -> list[str]:
    return [
        name
        for name in names
        if any(name.endswith(suffix) for suffix in VLLM_SUFFIXES)
    ]


def main() -> int:
    args = parse_args()
    client = PrometheusClient(args.base_url)
    build = client.get("/api/v1/status/buildinfo")

    namespace_matcher = json.dumps(args.namespace)
    up_query = f'up{{namespace={namespace_matcher}}}'
    up = compact_series(client.query(up_query))

    vllm_names = metric_names(client, '{__name__=~"vllm:.*"}')
    vllm_core_names = suffix_matches(vllm_names)
    vllm_core: dict[str, list[dict[str, Any]]] = {}
    for name in vllm_core_names:
        # Histogram bucket 数量较多，只确认名字，不把所有 le 序列打印出来。
        if name.endswith("_bucket"):
            continue
        expression = f'{name}{{namespace={namespace_matcher}}}'
        vllm_core[name] = compact_series(client.query(expression))

    dcgm_names = metric_names(client, '{__name__=~"DCGM_FI_DEV_.*"}')
    dcgm_core: dict[str, list[dict[str, Any]]] = {}
    for name in sorted(DCGM_NAMES.intersection(dcgm_names)):
        dcgm_core[name] = compact_series(client.query(name), args.gpu_uuid)

    result = {
        "prometheus": {
            "version": build.get("version"),
            "revision": build.get("revision"),
            "base_url": args.base_url,
        },
        "scope": {
            "namespace": args.namespace,
            "gpu_uuid": args.gpu_uuid,
        },
        "up": up,
        "vllm_metric_count": len(vllm_names),
        "vllm_core_metric_names": vllm_core_names,
        "vllm_core_series": vllm_core,
        "dcgm_metric_count": len(dcgm_names),
        "dcgm_core_series": dcgm_core,
    }
    rendered = json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True)
    print(rendered)

    if args.output:
        output = args.output.resolve()
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(f"{rendered}\n", encoding="utf-8")
        print(f"已写入: {output}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ConnectionError, KeyError, OSError, RuntimeError, TypeError, ValueError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        raise SystemExit(1)
