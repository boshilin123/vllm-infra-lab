# Monitoring

本目录将存放：

- vLLM ServiceMonitor。
- PrometheusRule。
- Grafana Dashboard JSON。
- HPA 自定义指标映射。

重点关联请求队列、KV Cache、TTFT/TPOT 与 DCGM GPU 指标。

清单会在首次部署后根据 vLLM 0.9.1 实际暴露的指标名生成，避免提前写入已变化或不存在的 PromQL。
