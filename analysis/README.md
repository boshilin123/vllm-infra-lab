# Analysis

本目录在 Phase 2 存放结果校验、统计与绘图逻辑。分析脚本只读取脱敏后的实验元数据、客户端结果和 Prometheus 导出数据，不直接依赖集群凭据。

首批图表：

- 并发量—吞吐量与 P95 延迟；
- TTFT/TPOT 与输入输出长度；
- waiting requests、KV Cache 与 GPU 利用率时间线；
- 扩缩容期间副本数、P95 和错误率时间线。
