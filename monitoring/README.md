# Monitoring

本目录存放：

- `servicemonitor.yaml`：让集群现有 Prometheus 每 15 秒抓取一次 vLLM 的 `/metrics`。
- `prometheus_probe.py`：通过本地 Prometheus 端口转发只读发现真实指标名与标签。
- `prometheus_queries.json`：时间线导出器与 Grafana 共用的 PromQL 单一事实来源。
- `generate_dashboard.py` / `grafana-dashboard.json`：生成并保存可导入 Dashboard。
- `kustomization.yaml`：使用 `kubectl apply -k monitoring` 统一加载监控资源。
- PrometheusRule。
- Grafana Dashboard JSON。
- HPA 自定义指标映射。

重点关联请求队列、KV Cache、TTFT/TPOT 与 DCGM GPU 指标。

吞吐口径必须分开解释：

- Prompt throughput：`rate(vllm:prompt_tokens_total[1m])`，表示 vLLM 计入的输入 Token 速率。在当前 vLLM 0.9.1 V1 实现中，一条请求的 `prompt_len` 在产生首个输出 Token 时一次性计入，因此它更接近 Prefill 完成/首 Token 附近的记账速率，不是 GPU 每一时刻处理 Prefill Token 的底层轨迹。
- Generation throughput：`rate(vllm:generation_tokens_total[1m])`，表示全服务每秒生成的输出 Token，计数随 Decode 迭代产生的新 Token 增加。
- Total token throughput：若需要统一口径，定义为 Prompt throughput 与 Generation throughput 之和；它衡量输入加输出的 Token 处理量，不等同于用户实际看到的生成速度。
- benchmark 的 Output throughput 使用“正式请求生成 Token 总数 / 正式阶段耗时”，与上面的 Generation throughput 含义接近但统计窗口不同；Request throughput 则是每秒完成请求数。

由于 Prometheus 使用 15 秒抓取和 1 分钟 `rate` 窗口，时间线展示的是平滑后的计数速率，不能要求上述曲线与瞬时 GPU-Util 逐点同步。

ServiceMonitor 已根据 vLLM 0.9.1 实际暴露的指标，以及青海环境中 Prometheus 的标签选择规则生成。PrometheusRule 和 Dashboard 会继续根据压测数据补充，避免提前写入已变化或不存在的 PromQL。

## Phase 3 指标发现

先把集群 Prometheus 转发到约定的 `127.0.0.1:29090`，再执行：

```bash
python monitoring/prometheus_probe.py \
  --gpu-uuid GPU-5e5590e5-51de-1c1c-6c72-4cbe1477e116
```

脚本不会修改 Prometheus 或 Kubernetes。vLLM 查询限定在 `vllm-infra-lab` namespace；DCGM 只读取 GPU 利用率、显存、功耗和温度四类指标，并可按本轮实验 GPU UUID 过滤。正式 Dashboard 和时间线导出器必须依据探测到的真实 metric/label 编写。

本环境同时由官方 NVIDIA DCGM Exporter 和 HAMi exporter 暴露同一物理 GPU 指标。共享查询显式使用 `job="nvidia-dcgm-exporter"` 和 GPU UUID，避免同一设备被重复聚合。

生成 Dashboard：

```bash
python monitoring/generate_dashboard.py
```

青海环境只读发现结果为 Grafana 9.3.14、`appSubUrl=/ui/insight-grafana`，默认 Prometheus 数据源名为 `Prometheus`、UID 为 `PBFA97CFB590B2093`；现有 Dashboard 使用 `schemaVersion=37`，生成器据此固定兼容版本。13 个 panel 的 PromQL 与统一时间线导出器共享同一配置，并已逐条对真实 Prometheus 验证。

本项目不把 Dashboard 持久化导入公司的 `insight-system` Grafana：直连只读身份对现有 Dashboard 显示 `canSave=false`，而用更高权限导入会写入公司共享 Grafana 数据库，超出“写操作只限项目仓库和 `vllm-infra-lab` namespace”的安全边界。仓库交付可导入 JSON、真实查询验证结果和等价的确定性 SVG；只有在个人/专用 Grafana 环境中才执行持久化导入。

代表性 benchmark 完成且 Prometheus 已抓取最后一个样本后，可按实验目录自动推导起止时间并导出统一时间线：

```bash
python analysis/export_prometheus_timeline.py \
  --experiment-dir results/YYYY-MM-DD/<experiment-id> \
  --gpu-uuid GPU-5e5590e5-51de-1c1c-6c72-4cbe1477e116
```

默认在实验目录的 `monitoring/` 下保存 `timeline.csv`、`metadata.json`、`summary.json` 和 Prometheus 原始 matrix JSON。窗口覆盖实验目录时间到最后一轮结束，并在前后各保留 60 秒空闲基线。
