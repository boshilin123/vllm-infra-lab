# 架构设计

## 数据流

压测客户端通过 Kubernetes Service 访问 vLLM OpenAI-compatible API。vLLM 将请求进行 Continuous Batching 并在 NVIDIA GPU 上执行推理；Prometheus 同时抓取 vLLM 请求指标和 DCGM GPU 指标，Grafana 用统一时间线展示服务与设备状态。

## 模块边界

- 服务层：Kubernetes Deployment、Service、模型挂载和健康检查。
- 压测层：固定工作负载、预热、重复运行和原始结果保存。
- 观测层：vLLM、Kubernetes 与 GPU 指标采集。
- 分析层：客户端延迟、服务队列和 GPU 指标关联。
- 路由层：实时 least-inflight 负责新请求选路，最小 HTTP/SSE 适配已通过本地 mock 验证；Prometheus 不进入逐请求热路径。
- 弹性层：waiting 趋势驱动 1↔2 容量状态机；共享集群缺少所需指标 API，因此当前仅离线回放，不声称已部署 HPA/KEDA。

## 暂不引入

首版不包含业务前端、应用数据库、RAG、模型训练和 GPU 虚拟化。路由适配也暂不包含 EndpointSlice 服务发现、生产级连接池、认证、指标和 Token-aware 权重。它们不属于当前离线验证要回答的问题。
