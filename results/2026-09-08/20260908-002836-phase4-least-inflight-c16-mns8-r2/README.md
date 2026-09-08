# Phase 4 least-inflight 真实双副本结果

## 实验配置

- Qwen3-8B BF16，vLLM 0.9.1
- 同节点两张 NVIDIA A10，物理 GPU 1/2
- 每副本 `max-num-seqs=8`、`max-model-len=4096`
- 256 Prompt Token / 128 Output Token，总并发16
- 每轮16个预热、100个正式请求，共3轮
- client 访问同 Pod 内 `127.0.0.1:18080`，代理按完整请求生命周期执行 least-inflight

## 预注册门槛与结果

| 指标 | 门槛 | 三轮中位数 | 判定 |
| --- | ---: | ---: | --- |
| 成功率 | ≥99% | 300/300，100% | 通过 |
| 输出吞吐 | ≥301.342 tok/s | 335.349 tok/s | 通过 |
| P95 TTFT | ≤600 ms | 456.041 ms | 通过 |
| P95 TPOT | ≤50 ms | 42.438 ms | 通过 |
| P95 E2E | ≤6000 ms | 5527.425 ms | 通过 |

正式窗口51个五秒采样点中，两侧最大 `running=8/8`，`waiting=0/0`；路由选择增量约48.5%/51.5%，结束后 `in_flight=0/0`。吞吐相对确定性8/8直连的334.824 tok/s保留约100.16%，应解释为持平而非代理提升。

实验后 Deployment 已恢复 `1/1`和 `Recreate`，临时 client 删除，物理GPU2释放；公司GPU0显存始终5901 MiB且对应Pod Ready/restart基线未变化。

## 证据

- `repeat-01.json`～`repeat-03.json`：vLLM原始逐请求结果
- `metadata.yaml`：Git提交、场景、GPU UUID和服务端参数
- `per-repeat.csv`、`summary.csv`、`aggregate.json`：校验与三轮聚合
- `evidence/README.md`：由本机原始日志提取的脱敏路由状态与五秒运行时摘要；含内部 Pod 名称/IP 的 `.log` 按仓库规则不提交
- [`analysis/generated/phase4-routing-comparison.svg`](../../../analysis/generated/phase4-routing-comparison.svg)：普通 Service、确定性8/8直连与 least-inflight 的同口径对比图

边界：这是固定成本合成负载下的实验性验证，不代表生产部署、自动扩缩容、长短混合请求效果或KV Cache感知路由。
