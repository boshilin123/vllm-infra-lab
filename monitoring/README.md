# Monitoring

本目录存放：

- `servicemonitor.yaml`：让集群现有 Prometheus 每 15 秒抓取一次 vLLM 的 `/metrics`。
- `kustomization.yaml`：使用 `kubectl apply -k monitoring` 统一加载监控资源。
- PrometheusRule。
- Grafana Dashboard JSON。
- HPA 自定义指标映射。

重点关联请求队列、KV Cache、TTFT/TPOT 与 DCGM GPU 指标。

ServiceMonitor 已根据 vLLM 0.9.1 实际暴露的指标，以及青海环境中 Prometheus 的标签选择规则生成。PrometheusRule 和 Dashboard 会继续根据压测数据补充，避免提前写入已变化或不存在的 PromQL。
