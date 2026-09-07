#!/usr/bin/env python3
"""从共享 PromQL 配置生成可导入 Grafana Dashboard JSON。"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
QUERY_CONFIG = REPO_ROOT / "monitoring" / "prometheus_queries.json"
OUTPUT = REPO_ROOT / "monitoring" / "grafana-dashboard.json"

GRAFANA_UNITS = {
    "requests": "short",
    "percent": "percent",
    "tok/s": "suffix: tok/s",
    "ms": "ms",
    "MiB": "suffix: MiB",
    "W": "watt",
    "°C": "celsius",
}


def load_config() -> dict[str, Any]:
    with QUERY_CONFIG.open(encoding="utf-8") as file:
        data = json.load(file)
    if data.get("schema_version") != 1:
        raise ValueError("不支持的 PromQL 配置版本")
    return data


def grafana_query(promql: str) -> str:
    return promql.replace("__NAMESPACE__", "$namespace").replace(
        "__GPU_UUID__", "$gpu_uuid"
    )


def panel(item: dict[str, str], index: int) -> dict[str, Any]:
    return {
        "datasource": {"type": "prometheus", "uid": "${DS_PROMETHEUS}"},
        "fieldConfig": {
            "defaults": {
                "color": {"mode": "palette-classic"},
                "custom": {
                    "axisCenteredZero": False,
                    "axisPlacement": "auto",
                    "drawStyle": "line",
                    "fillOpacity": 12,
                    "lineInterpolation": "linear",
                    "lineWidth": 2,
                    "pointSize": 5,
                    "showPoints": "never",
                    "spanNulls": True,
                },
                "min": 0,
                "unit": GRAFANA_UNITS[item["unit"]],
            },
            "overrides": [],
        },
        "gridPos": {
            "h": 8,
            "w": 8,
            "x": (index % 3) * 8,
            "y": (index // 3) * 8,
        },
        "id": index + 1,
        "options": {
            "legend": {
                "calcs": ["lastNotNull", "max"],
                "displayMode": "table",
                "placement": "bottom",
                "showLegend": True,
            },
            "tooltip": {"mode": "single", "sort": "none"},
        },
        "targets": [
            {
                "datasource": {
                    "type": "prometheus",
                    "uid": "${DS_PROMETHEUS}",
                },
                "editorMode": "code",
                "expr": grafana_query(item["promql"]),
                "legendFormat": item["title"],
                "range": True,
                "refId": "A",
            }
        ],
        "title": item["title"],
        "type": "timeseries",
    }


def main() -> int:
    config = load_config()
    panels = [panel(item, index) for index, item in enumerate(config["queries"])]
    dashboard = {
        "__inputs": [
            {
                "name": "DS_PROMETHEUS",
                "label": "Prometheus",
                "description": "Select the existing cluster Prometheus datasource.",
                "type": "datasource",
                "pluginId": "prometheus",
                "pluginName": "Prometheus",
            }
        ],
        "annotations": {"list": []},
        "description": "vLLM request, latency, KV Cache and single-GPU DCGM timeline.",
        "editable": True,
        "fiscalYearStartMonth": 0,
        "graphTooltip": 1,
        "id": None,
        "links": [],
        "liveNow": False,
        "panels": panels,
        "refresh": "15s",
        "schemaVersion": 39,
        "tags": ["vllm", "ai-infra", "gpu"],
        "templating": {
            "list": [
                {
                    "current": {"selected": True, "text": "vllm-infra-lab", "value": "vllm-infra-lab"},
                    "hide": 0,
                    "label": "Namespace",
                    "name": "namespace",
                    "options": [
                        {"selected": True, "text": "vllm-infra-lab", "value": "vllm-infra-lab"}
                    ],
                    "query": "vllm-infra-lab",
                    "type": "custom",
                },
                {
                    "current": {
                        "selected": True,
                        "text": "GPU-5e5590e5-51de-1c1c-6c72-4cbe1477e116",
                        "value": "GPU-5e5590e5-51de-1c1c-6c72-4cbe1477e116",
                    },
                    "hide": 0,
                    "label": "GPU UUID",
                    "name": "gpu_uuid",
                    "options": [
                        {
                            "selected": True,
                            "text": "GPU-5e5590e5-51de-1c1c-6c72-4cbe1477e116",
                            "value": "GPU-5e5590e5-51de-1c1c-6c72-4cbe1477e116",
                        }
                    ],
                    "query": "GPU-5e5590e5-51de-1c1c-6c72-4cbe1477e116",
                    "type": "custom",
                },
            ]
        },
        "time": {"from": "now-15m", "to": "now"},
        "timepicker": {},
        "timezone": "browser",
        "title": "vLLM Infra Lab - Serving and GPU Timeline",
        "uid": "vllm-infra-lab",
        "version": 1,
        "weekStart": "",
    }
    with OUTPUT.open("w", encoding="utf-8") as file:
        json.dump(dashboard, file, ensure_ascii=False, indent=2)
        file.write("\n")
    print(OUTPUT.relative_to(REPO_ROOT))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
