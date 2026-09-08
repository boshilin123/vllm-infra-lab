# Phase 4 真实 least-inflight 入口实验设计

> 状态：仅完成仓库内设计与本地 mock 验证。尚未执行集群审计、扩容或真实压测。

## 1. 实验问题

普通 Kubernetes Service 双副本已获得 `332.912 tok/s`，但瞬时 waiting 峰值为 6/4，P95 TTFT/E2E 为 5469/10742 ms。确定性 Pod IP 8/8 对照获得 `334.824 tok/s`，P95 TTFT/E2E 为 525/5544 ms，但它不是动态路由器。

本实验要回答：仓库实现的 least-inflight HTTP/SSE 适配真实接入两个 vLLM Pod 后，能否在保留至少 90%确定性直连吞吐的同时，避免普通 Service 的单波次偏斜并通过 Short SLO？

真实实验通过前，只能说“least-inflight 核心与 HTTP/SSE 适配已通过本地 mock 验证”，不能把确定性直连数据归因于该代理。

## 2. 控制变量与唯一改动

保持不变：

- Qwen3-8B BF16、vLLM 0.9.1、两张 A10、同一节点；
- 每副本 `max-num-seqs=8`、`max-model-len=4096`、`gpu-memory-utilization=0.85`；
- 256 Prompt Token / 128 Output Token、总并发 16；
- 每轮 16 个预热请求、100 个正式请求、共 3 轮；
- 客户端仍为 `phase4-benchmark-client`，不申请 GPU。

唯一架构改动是客户端不再访问普通 Service 或强制拆成两个子客户端，而是访问同一 Pod 网络命名空间中的 `127.0.0.1:18080`。`router/http_proxy.py`再根据实时 in-flight 选择两个 Ready Pod IP之一。

独立场景为 `benchmark/scenarios/phase4-least-inflight.yaml`，使用未被其他正式场景占用的 `seed_offset=700000`。这减少历史 Prefix Cache 污染，但固定随机 Token 负载仍不代表真实线上流量。

## 3. 事前假设与冻结验收线

相对确定性直连中位吞吐 `334.824 tok/s`，90%保留率为：

```text
334.824 × 0.90 = 301.342 tok/s
```

三轮聚合后必须同时检查：

| 条件 | 冻结标准 |
| --- | ---: |
| 正式请求成功率 | ≥99%（计划总数 300） |
| 输出吞吐中位数 | ≥301.342 tok/s |
| P95 TTFT中位数 | ≤600 ms |
| P95 TPOT中位数 | ≤50 ms |
| P95 E2E中位数 | ≤6000 ms |
| 每副本完整流程请求占比 | 40%～60% |
| 路由器最终 in-flight | 两侧均回到 0 |
| 运行时分流 | 不出现已知的“一侧 waiting、另一侧明显空闲” |
| 安全回退 | 最终恢复单副本，临时 GPU 释放，公司服务无变化 |

5 秒采样只能表述为“采样点未观测到 waiting”，不能断言任意毫秒绝对为 0。吞吐达到门槛但任一 Short SLO 失败时，必须记录为部分通过，不能通过追加轮次或修改阈值包装成全部通过。

## 4. 数据与归因要求

客户端证据：

- 三轮原始 `repeat-*.json`；
- `metadata.yaml`、`per-repeat.csv`、`summary.csv`和`aggregate.json`；
- 客户端日志及明确退出码。

路由与后端证据：

- `/_router/status`的前、中、后快照，包括每个后端的 `healthy`、`in_flight`和`selections_total`；
- 按 Pod 保存 running、waiting、KV Cache、完成请求、Prompt Token和Generation Token counter；
- 两张项目 GPU 的 UUID、利用率与显存，及公司 GPU 0不变的证据；
- Pod Ready、restart、Warning Event、OOM、preemption和错误日志审计。

若 TTFT 高于 600 ms，只有在两侧分流近似、采样未见 waiting、TPOT与吞吐稳定时，才能把新增延迟优先归因于代理建连、线程调度和数据复制；否则先检查路由是否仍产生瞬时偏斜。

## 5. 共享环境安全门

以下条件任一不满足就停止，不执行双副本：

1. GPU 0 上公司服务的 Pod、UUID、显存与进程映射不能确认；
2. 第二张 GPU 未同时通过 Kubernetes 资源账本和宿主机进程交叉核对；
3. 已有 Pending GPU Pod、公司工作负载变化或第二张卡有预留用途；
4. 扩容后出现第三个 vLLM Pod，或 `maxSurge`不是 0；
5. 新副本落到未批准设备，或公司 Pod 的 Ready/restart 状态变化；
6. CPU、内存或磁盘余量不足以支持短时第二副本与无 GPU client；
7. 无法保证实验结束后立即恢复 base 单副本。

只允许用户本人执行 `sudo`、`kubectl apply/delete`、commit 和 push。不得安装 KEDA、Metrics Adapter、Volcano、Kueue、vLLM Production Stack 或其他集群级组件。

## 6. tmux 执行约定

SSH 易断，所有长任务必须位于项目专用 tmux，不在前台终端运行。计划使用独立会话 `vllm-phase4-router-real`，分别保留：

- `rollout`：双副本启动与 Ready 等待；
- `router`：在 benchmark client 中运行 `router.http_proxy`；
- `monitor`：5 秒保存路由、两 Pod和四张 GPU 快照；
- `benchmark`：执行三轮正式负载并保留客户端日志。

进入真实执行前，必须根据当时 Pod 名、Pod IP、GPU 物理编号和 UUID生成完整命令，不给带 `<POD_IP>`等未解析占位符的正式执行命令。退出 tmux 使用 `Ctrl-b d`，不得用 `exit`或误杀公司已有会话。只清理本项目明确命名的会话和 Pod。

## 7. 回退优先级

实验完成、失败或 SSH 中断后，第一优先级都是恢复 base 单副本并删除临时 client；路由器和 benchmark 只是 client Pod 内的无 GPU 进程，删除该 Pod即可停止。回退后必须重新确认：

- Deployment `desired/ready/current/available=1/1/1/1`；
- 只剩一个项目 vLLM Pod且 restart 未增加；
- 临时 GPU 回到空闲；
- 公司 GPU 0、对应 Pod与既有 restart 状态不变；
- 没有遗留 Pending Pod或本项目 tmux 长任务。

## 8. 简历表述门槛

若全部验收通过，可以将“确定性对照”和“真实代理”串成一条：

> 定位普通 Kubernetes Service 的连接级瞬时偏斜后，设计并实现 least-inflight HTTP/SSE 路由器；在双 A10、Qwen3-8B、固定 c16 负载下，以不低于 90%的确定性直连吞吐通过 Short SLO，并在实验后恢复单副本。

正式简历必须替换为本轮真实数值。若未全部通过，则分别报告已改善项、失败项和机制证据，不写“生产上线”“自动扩缩容”或“KV Cache 感知路由”。
