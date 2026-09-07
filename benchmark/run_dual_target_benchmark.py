#!/usr/bin/env python3
"""并行直连两个 vLLM Pod，执行确定性的 8/8 路由对照实验。"""

from __future__ import annotations

import argparse
import importlib.metadata
import json
import math
import os
import socket
import statistics
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import yaml

from run_benchmark import (
    DEFAULT_TOKENIZER,
    REPO_ROOT,
    benchmark_command,
    check_health,
    find_vllm,
    git_commit,
    load_scenario,
    print_command,
)


DEFAULT_SCENARIO = REPO_ROOT / "benchmark/scenarios/phase4-direct-split.yaml"
PERCENTILES = (50, 95, 99)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "把总并发和请求严格平分到两个直连 vLLM target，并生成可由 "
            "aggregate_results.py 校验的合并结果。"
        )
    )
    parser.add_argument(
        "--target-base-url",
        action="append",
        required=True,
        help="vLLM Pod API 根地址；必须按 Pod 顺序传入两次。",
    )
    parser.add_argument(
        "--target-pod",
        action="append",
        required=True,
        help="与 target-base-url 对应的 Pod 名；必须传入两次。",
    )
    parser.add_argument("--concurrency", type=int, required=True, help="两个 target 的总并发。")
    parser.add_argument("--scenario", type=Path, default=DEFAULT_SCENARIO)
    parser.add_argument("--tokenizer", type=Path, default=DEFAULT_TOKENIZER)
    parser.add_argument("--model", default="Qwen3-8B")
    parser.add_argument("--server-node", required=True)
    parser.add_argument(
        "--server-gpu-physical-index", type=int, action="append", required=True
    )
    parser.add_argument("--server-gpu-uuid", action="append", required=True)
    parser.add_argument("--server-max-num-seqs", type=int, required=True)
    parser.add_argument("--server-max-model-len", type=int, required=True)
    parser.add_argument("--server-gpu-memory-utilization", type=float, required=True)
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def validate_args(args: argparse.Namespace, scenario: dict[str, Any]) -> None:
    pairs = {
        "target-base-url": args.target_base_url,
        "target-pod": args.target_pod,
        "server-gpu-physical-index": args.server_gpu_physical_index,
        "server-gpu-uuid": args.server_gpu_uuid,
    }
    for label, values in pairs.items():
        if len(values) != 2:
            raise ValueError(f"{label} 必须恰好传入两次，实际为 {len(values)}")
        if len(set(values)) != 2:
            raise ValueError(f"{label} 的两个值不能重复")

    if args.concurrency <= 0 or args.concurrency % 2:
        raise ValueError("总 concurrency 必须是可被两个 target 平分的正偶数")
    for field in ("warmup_requests", "measured_requests"):
        if scenario[field] % 2:
            raise ValueError(f"scenario.{field} 必须能被两个 target 平分")
    if any(index < 0 for index in args.server_gpu_physical_index):
        raise ValueError("server-gpu-physical-index 不能为负数")
    if any(not uuid.startswith("GPU-") for uuid in args.server_gpu_uuid):
        raise ValueError("server-gpu-uuid 应以 GPU- 开头")
    if args.server_max_num_seqs <= 0:
        raise ValueError("server-max-num-seqs 必须是正整数")
    if args.server_max_model_len <= 0:
        raise ValueError("server-max-model-len 必须是正整数")
    if not 0 < args.server_gpu_memory_utilization <= 1:
        raise ValueError("server-gpu-memory-utilization 必须在 (0, 1] 范围内")


def percentile(values: list[float], percent: int) -> float:
    """复现 NumPy 默认的线性百分位数，避免依赖 NumPy。"""
    if not values:
        raise ValueError("不能计算空样本的百分位数")
    ordered = sorted(values)
    position = (len(ordered) - 1) * percent / 100
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    fraction = position - lower
    return ordered[lower] + (ordered[upper] - ordered[lower]) * fraction


def metric_block(values_seconds: list[float], label: str) -> dict[str, float]:
    if not values_seconds or any(not math.isfinite(value) for value in values_seconds):
        raise ValueError(f"{label} 包含空值或非有限值")
    values_ms = [value * 1000 for value in values_seconds]
    result = {
        f"mean_{label}_ms": statistics.fmean(values_ms),
        f"median_{label}_ms": statistics.median(values_ms),
        f"std_{label}_ms": statistics.pstdev(values_ms),
    }
    for percent in PERCENTILES:
        result[f"p{percent}_{label}_ms"] = percentile(values_ms, percent)
    return result


def load_child(path: Path, expected_requests: int, expected_concurrency: int) -> dict[str, Any]:
    with path.open(encoding="utf-8") as file:
        data = json.load(file)
    if not isinstance(data, dict):
        raise ValueError(f"子结果顶层必须是对象: {path}")
    if data.get("completed") != expected_requests or data.get("num_prompts") != expected_requests:
        raise ValueError(f"{path.name}: 请求完成数不等于 {expected_requests}")
    if data.get("max_concurrency") != expected_concurrency:
        raise ValueError(f"{path.name}: max_concurrency 不等于 {expected_concurrency}")
    for field in ("input_lens", "output_lens", "ttfts", "itls", "generated_texts", "errors"):
        values = data.get(field)
        if not isinstance(values, list) or len(values) != expected_requests:
            raise ValueError(f"{path.name}.{field} 长度不等于 {expected_requests}")
    if any(str(error).strip() for error in data["errors"]):
        raise ValueError(f"{path.name}: 存在非空 errors")
    return data


def merge_children(
    children: list[dict[str, Any]],
    *,
    total_concurrency: int,
    model: str,
) -> dict[str, Any]:
    """合并逐请求样本；吞吐按两条近同步流中的最长服务端窗口计算。"""
    if len(children) != 2:
        raise ValueError("只能合并两个 target 结果")
    list_fields = ("input_lens", "output_lens", "ttfts", "itls", "generated_texts", "errors")
    merged_lists = {
        field: [item for child in children for item in child[field]]
        for field in list_fields
    }
    completed = sum(int(child["completed"]) for child in children)
    duration = max(float(child["duration"]) for child in children)
    total_input_tokens = sum(int(child["total_input_tokens"]) for child in children)
    total_output_tokens = sum(int(child["total_output_tokens"]) for child in children)

    ttfts = [float(value) for value in merged_lists["ttfts"]]
    itls = [[float(value) for value in request] for request in merged_lists["itls"]]
    if any(not request for request in itls):
        raise ValueError("每个成功请求必须至少包含一个 ITL 样本")
    tpots = [sum(request) / len(request) for request in itls]
    flat_itls = [value for request in itls for value in request]
    e2els = [ttft + sum(request) for ttft, request in zip(ttfts, itls)]

    result: dict[str, Any] = {
        "date": datetime.now().strftime("%Y%m%d-%H%M%S"),
        "endpoint_type": "openai",
        "label": "deterministic-direct-split",
        "model_id": model,
        "tokenizer_id": children[0].get("tokenizer_id"),
        "num_prompts": completed,
        "request_rate": "inf",
        "burstiness": 1.0,
        "max_concurrency": total_concurrency,
        "duration": duration,
        "completed": completed,
        "total_input_tokens": total_input_tokens,
        "total_output_tokens": total_output_tokens,
        "request_throughput": completed / duration,
        "request_goodput:": None,
        "output_throughput": total_output_tokens / duration,
        "total_token_throughput": (total_input_tokens + total_output_tokens) / duration,
        **merged_lists,
    }
    result.update(metric_block(ttfts, "ttft"))
    result.update(metric_block(tpots, "tpot"))
    result.update(metric_block(flat_itls, "itl"))
    result.update(metric_block(e2els, "e2el"))
    result["merge"] = {
        "method": "per-request samples; throughput denominator=max(target durations)",
        "target_durations_seconds": [float(child["duration"]) for child in children],
        "sum_target_output_throughput": sum(
            float(child["output_throughput"]) for child in children
        ),
    }
    return result


def run_pair(
    commands: list[tuple[str, list[str]]], env: dict[str, str]
) -> None:
    processes: list[tuple[str, subprocess.Popen[str]]] = []
    for label, command in commands:
        print_command(label, command)
        process = subprocess.Popen(
            command,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
        processes.append((label, process))

    failures: list[str] = []
    for label, process in processes:
        output, _ = process.communicate()
        if output:
            print(f"\n[{label} output]\n{output.rstrip()}")
        if process.returncode:
            failures.append(f"{label}: exit={process.returncode}")
    if failures:
        raise RuntimeError("并行子任务失败: " + "; ".join(failures))


def main() -> int:
    args = parse_args()
    scenario_path = args.scenario.resolve()
    tokenizer_path = args.tokenizer.resolve()
    scenario = load_scenario(scenario_path, args.concurrency)
    validate_args(args, scenario)
    vllm = find_vllm()

    target_count = 2
    per_target_concurrency = args.concurrency // target_count
    per_target_warmup = scenario["warmup_requests"] // target_count
    per_target_measured = scenario["measured_requests"] // target_count
    scenario_seed_offset = scenario.get("seed_offset", 0)
    seed_offset = scenario_seed_offset + (args.concurrency - 1) * 1_000
    timestamp = datetime.now().astimezone().strftime("%Y%m%d-%H%M%S")
    experiment_id = (
        f"{timestamp}-{scenario['name']}-c{args.concurrency}"
        f"-mns{args.server_max_num_seqs}-r2"
    )
    result_dir = REPO_ROOT / "results" / datetime.now().strftime("%Y-%m-%d") / experiment_id

    all_pairs: list[tuple[list[tuple[str, list[str]]], list[tuple[str, list[str]]]]] = []
    for repeat in range(1, scenario["repeats"] + 1):
        # 两个 target 使用相同 seed，确保接收等价工作量；它们不共享 KV Cache。
        warmup_seed = 10_000 + seed_offset + repeat
        measured_seed = 42 + seed_offset + repeat - 1
        warmups: list[tuple[str, list[str]]] = []
        measured: list[tuple[str, list[str]]] = []
        for target_index, target_url in enumerate(args.target_base_url, start=1):
            warmups.append(
                (
                    f"repeat {repeat} target {target_index} warmup",
                    benchmark_command(
                        vllm=vllm,
                        base_url=target_url,
                        model=args.model,
                        tokenizer=tokenizer_path,
                        scenario=scenario,
                        concurrency=per_target_concurrency,
                        num_prompts=per_target_warmup,
                        seed=warmup_seed,
                    ),
                )
            )
            measured.append(
                (
                    f"repeat {repeat} target {target_index} measured",
                    benchmark_command(
                        vllm=vllm,
                        base_url=target_url,
                        model=args.model,
                        tokenizer=tokenizer_path,
                        scenario=scenario,
                        concurrency=per_target_concurrency,
                        num_prompts=per_target_measured,
                        seed=measured_seed,
                        result_dir=result_dir,
                        result_filename=f"target-{target_index}-repeat-{repeat:02d}.json",
                    ),
                )
            )
        all_pairs.append((warmups, measured))

    if args.dry_run:
        print(f"实验目录（dry-run 不创建）: {result_dir}")
        print(
            f"路由：2 targets × c{per_target_concurrency}；每轮正式请求 "
            f"2 × {per_target_measured} = {scenario['measured_requests']}"
        )
        for warmups, measured in all_pairs:
            for label, command in warmups + measured:
                print_command(label, command)
        return 0

    if not tokenizer_path.is_dir():
        raise FileNotFoundError(f"Tokenizer 目录不存在: {tokenizer_path}")
    for target_url in args.target_base_url:
        check_health(target_url)
    result_dir.mkdir(parents=True, exist_ok=False)

    targets = []
    for index in range(target_count):
        targets.append(
            {
                "pod": args.target_pod[index],
                "base_url": args.target_base_url[index].rstrip("/"),
                "gpu_physical_index": args.server_gpu_physical_index[index],
                "gpu_uuid": args.server_gpu_uuid[index],
                "concurrency": per_target_concurrency,
            }
        )
    metadata = {
        "experiment_id": experiment_id,
        "created_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "git_commit": git_commit(),
        "client_hostname": socket.gethostname(),
        "client_python": sys.executable,
        "client_vllm_version": importlib.metadata.version("vllm"),
        "base_url": "deterministic-direct-pod-split",
        "routing": {
            "mode": "deterministic-direct-split",
            "targets": targets,
            "equal_seed_per_target": True,
            "merge_method": "per-request samples; throughput denominator=max(target durations)",
        },
        "model": args.model,
        "tokenizer": str(tokenizer_path),
        "server": {
            "node": args.server_node,
            "replicas": 2,
            "gpu_physical_indices": args.server_gpu_physical_index,
            "gpu_uuids": args.server_gpu_uuid,
            "engine": {
                "max_num_seqs": args.server_max_num_seqs,
                "max_model_len": args.server_max_model_len,
                "gpu_memory_utilization": args.server_gpu_memory_utilization,
            },
        },
        "scenario_file": str(scenario_path.relative_to(REPO_ROOT)),
        "scenario": scenario,
        "selected_concurrency": args.concurrency,
        "seed_policy": (
            f"scenario_offset={scenario_seed_offset}; "
            "offset=scenario_offset+(total_concurrency-1)*1000; "
            "same seed on both isolated targets; "
            "warmup=10000+offset+repeat; measured=42+offset+repeat-1"
        ),
    }
    with (result_dir / "metadata.yaml").open("w", encoding="utf-8") as file:
        yaml.safe_dump(metadata, file, allow_unicode=True, sort_keys=False)

    env = os.environ.copy()
    no_proxy_hosts = ["127.0.0.1", "localhost"]
    for target_url in args.target_base_url:
        host = urlparse(target_url).hostname
        if host:
            no_proxy_hosts.append(host)
    no_proxy = ",".join(dict.fromkeys(no_proxy_hosts))
    env["NO_PROXY"] = no_proxy
    env["no_proxy"] = no_proxy

    for repeat, (warmups, measured) in enumerate(all_pairs, start=1):
        run_pair(warmups, env)
        run_pair(measured, env)
        child_paths = [
            result_dir / f"target-{target_index}-repeat-{repeat:02d}.json"
            for target_index in range(1, target_count + 1)
        ]
        children = [
            load_child(path, per_target_measured, per_target_concurrency)
            for path in child_paths
        ]
        combined = merge_children(
            children,
            total_concurrency=args.concurrency,
            model=args.model,
        )
        with (result_dir / f"repeat-{repeat:02d}.json").open(
            "w", encoding="utf-8"
        ) as file:
            json.dump(combined, file, ensure_ascii=False, indent=2)
            file.write("\n")

    print(f"\n全部确定性双目标实验完成，结果目录: {result_dir}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (
        json.JSONDecodeError,
        OSError,
        RuntimeError,
        ValueError,
        subprocess.SubprocessError,
    ) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        raise SystemExit(1)
