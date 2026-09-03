# 架构设计

## 数据流

压测客户端通过 Kubernetes Service 访问 vLLM OpenAI-compatible API。vLLM 将请求进行 Continuous Batching 并在 NVIDIA GPU 上执行推理；Prometheus 同时抓取 vLLM 请求指标和 DCGM GPU 指标，Grafana 用统一时间线展示服务与设备状态。

## 模块边界

- 服务层：Kubernetes Deployment、Service、模型挂载和健康检查。
- 压测层：固定工作负载、预热、重复运行和原始结果保存。
- 观测层：vLLM、Kubernetes 与 GPU 指标采集。
- 分析层：客户端延迟、服务队列和 GPU 指标关联。
- 弹性层：多副本流量入口与基于队列信号的 HPA。

## 暂不引入

首版不包含业务前端、应用数据库、RAG、模型训练和 GPU 虚拟化。它们不属于本项目要验证的推理数据面问题。
