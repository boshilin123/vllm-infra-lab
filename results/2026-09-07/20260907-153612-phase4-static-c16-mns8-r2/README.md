# Phase 4 静态双副本 c16-mns8

## 实验问题

在每副本 `max-num-seqs=8`、客户端总并发 16 时，两个 Qwen3-8B BF16/A10 副本能否同时提高输出吞吐并通过 Short SLO？Kubernetes ClusterIP Service 的连接级分流能否稳定形成每副本约 8 个并发？

## 环境与控制变量

- Git commit：`2b9ecf6cde71b68c082b0367707471fed581adb9`
- 服务端：vLLM 0.9.1，两个副本，同一节点 `qhvgpu1`
- GPU：物理 GPU 1 与 2；UUID 见 `metadata.yaml`
- 每副本：`max-num-seqs=8`、`max-model-len=4096`、`gpu-memory-utilization=0.85`
- 负载：256 Prompt Token / 128 Output Token，并发 16
- 正式请求：每轮 100、共 3 轮；独立 seed offset 500000
- 客户端：无 GPU 的集群内 Pod，通过 `http://qwen3-8b:8000`访问 ClusterIP Service
- 持久性：正式任务在宿主机 root tmux `vllm-phase4-static`中运行，退出码 0

新副本从创建到 Ready 用时 155 秒。扩容前确认 GPU 0 为公司 Pod、GPU 1 为本项目，GPU 2/3 同时在宿主机和 Kubernetes 账本中空闲；新副本实际落到 GPU 2。运行后两个 vLLM Pod均 0 restart，无 ERROR、OOM、Traceback 或 preemption。回退后 Deployment 恢复单副本，GPU 2释放至约 1 MiB，公司 GPU 0/Pod 状态不变。

## 三轮正式结果

| Repeat | 成功 | Output throughput (tok/s) | P95 TTFT (ms) | P95 TPOT (ms) | P95 E2E (ms) |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | 100/100 | 291.506 | 5577.892 | 42.568 | 10937.776 |
| 2 | 100/100 | 332.912 | 5337.382 | 42.484 | 10708.202 |
| 3 | 100/100 | 333.434 | 5469.014 | 42.407 | 10741.813 |
| **中位数** | **300/300** | **332.912** | **5469.014** | **42.484** | **10741.813** |

输出吞吐 CV 为 7.53%，明显高于此前稳定的单副本基线，主要来自三轮连接分配差异；P95 TPOT CV 仅 0.19%，Decode 单 Token 节奏稳定。

## 与已有基线对照

| 配置 | Output throughput (tok/s) | P95 TTFT (ms) | P95 TPOT (ms) | P95 E2E (ms) |
| --- | ---: | ---: | ---: | ---: |
| 单副本 c8-mns8（历史） | 178.796 | 524.927 | 42.740 | 5554.010 |
| 单副本 c16-mns8 | 179.285 | 6015.515 | 42.703 | 11095.317 |
| 单副本 c16-mns16 | 305.434 | 976.838 | 46.768 | 6152.403 |
| **双副本 c16-mns8** | **332.912** | **5469.014** | **42.484** | **10741.813** |

- 相对单副本 c16-mns8，双副本输出吞吐提高 **85.69%**。
- 相对单副本 c16-mns16，输出吞吐仍提高 **9.00%**。
- 相对两倍历史 c8 吞吐的线性上界，扩展效率为 **93.10%**。
- 相对单副本 c16-mns8，P95 TTFT 仅改善 9.08%，P95 E2E 仅改善 3.19%，仍远未恢复到单副本 c8。

跨 GPU 对照存在硬件个体和时间窗口差异，因此大幅吞吐变化可作为容量证据，小幅差异不包装成参数收益。

## 每副本证据与根因

`live-monitor.log`以 5 秒间隔抓取两个 Pod 的 scheduler/KV counter 和四张 GPU。正式 tmux 全流程包含 3×100 正式请求、3×16 预热请求，以及 vLLM 每次 benchmark 的初始单请求探测，共 354 个完成请求：

| Pod / GPU | 完成请求增量 | 占比 | Peak running | Peak waiting | Peak KV Cache |
| --- | ---: | ---: | ---: | ---: | ---: |
| 原副本 / GPU 1 | 179 | 50.56% | 8 | 6 | 13.525% |
| 新副本 / GPU 2 | 175 | 49.44% | 8 | 4 | 13.525% |

整场累计流量近似 50/50，满足预注册的 40%～60%分布标准；但单个并发波次曾出现 `8 running/6 waiting`对`1 running/0 waiting`等瞬时偏斜。ClusterIP Service 在 L4/连接级分配，无法感知 vLLM scheduler queue；客户端又会复用连接，因此“累计均衡”不保证“每一波并发 8/8”。少数请求等待一个完整 Decode 批次，P50 TTFT 仍约 352 ms，而 P95 跃升到约 5.47 秒；TPOT 不包含这段完整排队，所以保持约 42.48 ms。

## 预注册验收

| 条件 | 结果 | 判定 |
| --- | --- | --- |
| 成功率 ≥99% | 300/300，100% | PASS |
| 输出吞吐 ≥268.93 tok/s | 332.912 tok/s | PASS |
| 每副本请求占比 40%～60% | 50.56% / 49.44% | PASS（累计） |
| P95 TTFT ≤600 ms | 5469.014 ms | **FAIL** |
| P95 TPOT ≤50 ms | 42.484 ms | PASS |
| P95 E2E ≤6000 ms | 10741.813 ms | **FAIL** |
| 公司服务与两卡安全边界 | 无影响，已恢复单副本 | PASS |

**总判定：静态双副本的容量扩展有效，但当前普通 Service 分流下的 Short SLO 未通过。** 下一步不应继续加 GPU 或增加 mns，而应做一个确定性 8/8 分流对照，将“两卡计算容量”与“入口负载均衡策略”分开验证。自动弹性也不能修复已经存在的单波次分流偏斜。

## 首次客户端失败说明

首次启动在 warmup 发请求前失败：非 root UID 1000 在镜像 passwd 中无条目，PyTorch `getpass.getuser()`抛出 `KeyError`。监控确认两个服务端请求/Token counter 没有新增；该无效目录未提交，已移到 `/tmp`。修复采用显式 `USER/LOGNAME/HOME/TORCHINDUCTOR_CACHE_DIR`，没有提升为 root。正式三轮使用修复后的 tmux 任务，退出码为 0。

## 文件

- `repeat-01.json`～`repeat-03.json`：客户端逐请求原始结果
- `metadata.yaml`：Git、客户端、两副本/GPU 和场景元数据
- `per-repeat.csv`、`summary.csv`、`aggregate.json`：校验与聚合
- `per-pod-summary.csv`：完整 tmux 流程的每副本 counter 增量与峰值
- `client.log`：正式 tmux 客户端日志
- `live-monitor.log`：5 秒 Pod/GPU 原始监控
