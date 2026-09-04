#!/usr/bin/env python3
"""使用 Python 标准库验证 vLLM 的健康状态和 OpenAI 兼容接口。"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from typing import Any


# 服务器配置了 HTTP(S) 代理；本脚本主要访问本机 port-forward 或集群内地址，
# 因此显式禁用环境代理，避免 127.0.0.1 请求被代理转发成 502。
DIRECT_OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def request(
    method: str,
    url: str,
    *,
    timeout: float,
    payload: dict[str, Any] | None = None,
) -> tuple[int, bytes]:
    """发送 HTTP 请求并返回状态码与原始响应体。"""
    body = None if payload is None else json.dumps(payload).encode("utf-8")
    headers = {"Content-Type": "application/json"} if body is not None else {}
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    with DIRECT_OPENER.open(req, timeout=timeout) as response:
        return response.status, response.read()


def read_json(body: bytes, endpoint: str) -> dict[str, Any]:
    """解析 JSON 对象，并为格式错误提供明确的接口名称。"""
    try:
        result = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        preview = body[:200].decode("utf-8", errors="replace")
        raise RuntimeError(
            f"{endpoint} did not return valid JSON; "
            f"body_length={len(body)}, body_prefix={preview!r}"
        ) from exc
    if not isinstance(result, dict):
        raise RuntimeError(f"{endpoint} returned a non-object JSON value")
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--base-url",
        default=os.environ.get("VLLM_BASE_URL", "http://127.0.0.1:8000"),
        help="vLLM server URL without a trailing slash",
    )
    parser.add_argument("--model", default="Qwen3-8B")
    parser.add_argument("--timeout", type=float, default=120.0)
    args = parser.parse_args()
    base_url = args.base_url.rstrip("/")

    try:
        # 第一步只验证进程及推理引擎已经通过健康检查。
        health_status, _ = request(
            "GET", f"{base_url}/health", timeout=args.timeout
        )
        if health_status != 200:
            raise RuntimeError(f"/health returned HTTP {health_status}")
        print("PASS /health")

        # 第二步确认服务暴露的模型名与 Deployment 配置一致。
        models_status, models_body = request(
            "GET", f"{base_url}/v1/models", timeout=args.timeout
        )
        if models_status != 200:
            raise RuntimeError(f"/v1/models returned HTTP {models_status}")
        models = read_json(models_body, "/v1/models")
        model_ids = [item.get("id") for item in models.get("data", [])]
        if args.model not in model_ids:
            raise RuntimeError(
                f"expected model {args.model!r}; server returned {model_ids!r}"
            )
        print(f"PASS /v1/models model={args.model}")

        # 第三步发送一次真实的非流式推理请求，验证完整调用链路。
        completions_status, completions_body = request(
            "POST",
            f"{base_url}/v1/chat/completions",
            timeout=args.timeout,
            payload={
                "model": args.model,
                "messages": [
                    {
                        "role": "user",
                        "content": "Reply with a short confirmation that the service is ready.",
                    }
                ],
                "max_tokens": 32,
                "temperature": 0,
                "stream": False,
            },
        )
        if completions_status != 200:
            raise RuntimeError(
                f"/v1/chat/completions returned HTTP {completions_status}"
            )
        completion = read_json(completions_body, "/v1/chat/completions")
        choices = completion.get("choices")
        if not isinstance(choices, list) or not choices:
            raise RuntimeError("completion response did not contain choices")
        message = choices[0].get("message", {})
        content = message.get("content")
        if not isinstance(content, str):
            raise RuntimeError("completion response did not contain text content")
        print(f"PASS /v1/chat/completions response={content.strip()!r}")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        print(f"FAIL HTTP {exc.code}: {detail}", file=sys.stderr)
        return 1
    except (urllib.error.URLError, TimeoutError, RuntimeError) as exc:
        print(f"FAIL {exc}", file=sys.stderr)
        return 1

    print("Smoke test passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
