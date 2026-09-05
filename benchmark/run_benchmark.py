#!/usr/bin/env python3
"""按场景文件运行可复现的 vLLM 在线服务基准测试。"""

from __future__ import annotations

import argparse
import importlib.metadata
import json
import os
import shutil
import socket
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.request import ProxyHandler, build_opener

import yaml


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SCENARIO = REPO_ROOT / "benchmark/scenarios/short.yaml"
DEFAULT_TOKENIZER = REPO_ROOT.parent / "models/Qwen3-8B"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="根据 YAML 场景执行预热和重复的 vLLM serving benchmark。"
    )
    parser.add_argument("--base-url", required=True, help="vLLM API 根地址。")
    parser.add_argument("--concurrency", type=int, required=True, help="本轮最大并发数。")
    parser.add_argument("--scenario", type=Path, default=DEFAULT_SCENARIO)
    parser.add_argument("--tokenizer", type=Path, default=DEFAULT_TOKENIZER)
    parser.add_argument("--model", default="Qwen3-8B")
    parser.add_argument(
        "--server-node",
        required=True,
        help="运行 vLLM Pod 的 Kubernetes 节点名。",
    )
    parser.add_argument(
        "--server-gpu-physical-index",
        type=int,
        required=True,
        help="GPU 在宿主机 nvidia-smi 中的物理编号，仅用于记录。",
    )
    parser.add_argument(
        "--server-gpu-uuid",
        required=True,
        help="容器内外一致的 GPU UUID，用于跨 Pod 重建识别同一设备。",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="只打印命令，不发请求也不创建结果目录。",
    )
    return parser.parse_args()


def load_scenario(path: Path, concurrency: int) -> dict[str, Any]:
    with path.open(encoding="utf-8") as file:
        scenario = yaml.safe_load(file)

    required = (
        "name",
        "prompt_tokens",
        "output_tokens",
        "concurrency",
        "warmup_requests",
        "measured_requests",
        "repeats",
    )
    missing = [key for key in required if key not in scenario]
    if missing:
        raise ValueError(f"场景缺少必要字段: {', '.join(missing)}")
    if concurrency not in scenario["concurrency"]:
        raise ValueError(
            f"并发 {concurrency} 不在场景允许值 {scenario['concurrency']} 中"
        )
    for key in ("prompt_tokens", "output_tokens", "warmup_requests", "measured_requests", "repeats"):
        if not isinstance(scenario[key], int) or scenario[key] <= 0:
            raise ValueError(f"{key} 必须是正整数")
    return scenario


def find_vllm() -> str:
    executable = shutil.which("vllm")
    if executable is None:
        raise RuntimeError("找不到 vllm，请先激活 vllm-qwen3 虚拟环境")
    return executable


def benchmark_command(
    *,
    vllm: str,
    base_url: str,
    model: str,
    tokenizer: Path,
    scenario: dict[str, Any],
    concurrency: int,
    num_prompts: int,
    seed: int,
    result_dir: Path | None = None,
    result_filename: str | None = None,
) -> list[str]:
    command = [
        vllm,
        "bench",
        "serve",
        "--base-url",
        base_url.rstrip("/"),
        "--endpoint",
        "/v1/completions",
        "--endpoint-type",
        "openai",
        "--model",
        model,
        "--served-model-name",
        model,
        "--tokenizer",
        str(tokenizer),
        "--dataset-name",
        "random",
        "--random-input-len",
        str(scenario["prompt_tokens"]),
        "--random-output-len",
        str(scenario["output_tokens"]),
        "--random-range-ratio",
        "0",
        "--num-prompts",
        str(num_prompts),
        "--request-rate",
        "inf",
        "--max-concurrency",
        str(concurrency),
        "--ignore-eos",
        "--seed",
        str(seed),
        "--metric-percentiles",
        "50,95,99",
        "--percentile-metrics",
        "ttft,tpot,itl,e2el",
        "--disable-tqdm",
    ]
    if result_dir is not None and result_filename is not None:
        command.extend(
            [
                "--save-result",
                "--save-detailed",
                "--result-dir",
                str(result_dir),
                "--result-filename",
                result_filename,
            ]
        )
    return command


def print_command(label: str, command: list[str]) -> None:
    print(f"\n[{label}]")
    print(" ".join(command))


def check_health(base_url: str) -> None:
    # 显式禁用环境代理，防止 127.0.0.1 请求被公司代理接管。
    opener = build_opener(ProxyHandler({}))
    with opener.open(f"{base_url.rstrip('/')}/health", timeout=5) as response:
        if response.status != 200:
            raise RuntimeError(f"健康检查失败，HTTP 状态码: {response.status}")


def git_commit() -> str:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def main() -> int:
    args = parse_args()
    scenario_path = args.scenario.resolve()
    tokenizer_path = args.tokenizer.resolve()
    scenario = load_scenario(scenario_path, args.concurrency)
    vllm = find_vllm()
    if args.server_gpu_physical_index < 0:
        raise ValueError("server-gpu-physical-index 不能为负数")
    if not args.server_gpu_uuid.startswith("GPU-"):
        raise ValueError("server-gpu-uuid 应以 GPU- 开头")

    # 每个并发档位和重复轮次使用不同但固定的种子，避免跨实验命中旧的 Prefix Cache。
    # 减 1 使并发 1 继续使用已经建立基线时的 42/43/44 与 10001/10002/10003。
    concurrency_seed_offset = (args.concurrency - 1) * 1_000
    commands: list[tuple[str, list[str]]] = []
    timestamp = datetime.now().astimezone().strftime("%Y%m%d-%H%M%S")
    experiment_id = f"{timestamp}-{scenario['name']}-c{args.concurrency}"
    result_dir = REPO_ROOT / "results" / datetime.now().strftime("%Y-%m-%d") / experiment_id

    for repeat in range(1, scenario["repeats"] + 1):
        warmup_seed = 10_000 + concurrency_seed_offset + repeat
        measured_seed = 42 + concurrency_seed_offset + repeat - 1
        warmup = benchmark_command(
            vllm=vllm,
            base_url=args.base_url,
            model=args.model,
            tokenizer=tokenizer_path,
            scenario=scenario,
            concurrency=args.concurrency,
            num_prompts=scenario["warmup_requests"],
            seed=warmup_seed,
        )
        measured = benchmark_command(
            vllm=vllm,
            base_url=args.base_url,
            model=args.model,
            tokenizer=tokenizer_path,
            scenario=scenario,
            concurrency=args.concurrency,
            num_prompts=scenario["measured_requests"],
            seed=measured_seed,
            result_dir=result_dir,
            result_filename=f"repeat-{repeat:02d}.json",
        )
        commands.extend(((f"repeat {repeat} warmup", warmup), (f"repeat {repeat} measured", measured)))

    if args.dry_run:
        print(f"实验目录（dry-run 不创建）: {result_dir}")
        for label, command in commands:
            print_command(label, command)
        return 0

    if not tokenizer_path.is_dir():
        raise FileNotFoundError(f"Tokenizer 目录不存在: {tokenizer_path}")
    check_health(args.base_url)
    result_dir.mkdir(parents=True, exist_ok=False)

    metadata = {
        "experiment_id": experiment_id,
        "created_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "git_commit": git_commit(),
        "client_hostname": socket.gethostname(),
        "client_python": sys.executable,
        "client_vllm_version": importlib.metadata.version("vllm"),
        "base_url": args.base_url.rstrip("/"),
        "model": args.model,
        "tokenizer": str(tokenizer_path),
        # 物理编号可能在调度后变化，UUID 才是识别 GPU 的稳定字段。
        "server": {
            "node": args.server_node,
            "gpu_physical_index": args.server_gpu_physical_index,
            "gpu_uuid": args.server_gpu_uuid,
        },
        "scenario_file": str(scenario_path.relative_to(REPO_ROOT)),
        "scenario": scenario,
        "selected_concurrency": args.concurrency,
        "seed_policy": (
            "offset=(concurrency-1)*1000; "
            "warmup=10000+offset+repeat; measured=42+offset+repeat-1"
        ),
    }
    with (result_dir / "metadata.yaml").open("w", encoding="utf-8") as file:
        yaml.safe_dump(metadata, file, allow_unicode=True, sort_keys=False)

    env = os.environ.copy()
    env["NO_PROXY"] = "127.0.0.1,localhost"
    env["no_proxy"] = "127.0.0.1,localhost"
    for label, command in commands:
        print_command(label, command)
        subprocess.run(command, check=True, env=env)

    print(f"\n全部重复实验完成，结果目录: {result_dir}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, RuntimeError, ValueError, subprocess.CalledProcessError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        raise SystemExit(1)
