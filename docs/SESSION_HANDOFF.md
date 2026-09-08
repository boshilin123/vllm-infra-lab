# 新会话接力摘要

> 更新时间：2026-09-08（Asia/Shanghai）  
> 用途：新开 Codex 会话时先让 Agent 完整阅读本文件，再阅读 `PROJECT_JOURNAL.md`、`PROJECT_PLAN.md`、`PHASE4_POLICY.md` 和 `RESUME_DRAFT.md`。本文件不记录任何密码、私钥或 kubeconfig 内容。

## 1. 项目目标不能偏离

项目名称：**vLLM 大模型推理服务性能与弹性优化**。

这是面向 AI Infra / 推理基础设施岗位的个人简历项目，主线是：

```text
Kubernetes 单副本服务
→ 可复现性能基准与参数实验
→ Prometheus/DCGM 可观测性
→ 多副本容量与请求分流
→ 冷启动约束下的弹性策略
```

项目不是模型应用 Demo，不做 RAG、业务前端、微调或训练；也不把 HAMi/GPU 虚拟化作为标题和主线。不能声称自研 PagedAttention、Continuous Batching 或修改了 vLLM 内核。项目亮点是控制变量实验、SLO、运行时证据、因果对照、共享环境风险控制和可复现交付物，不是提出新推理算法。

## 2. 公司共享环境硬边界

以下规则优先级最高：

1. 任何时刻最多使用两张 GPU；默认只保持一个项目副本。
2. 不停止、迁移、重启、修改或抢占任何公司已有服务。
3. 集群写操作只允许在 `vllm-infra-lab` namespace；文件写操作只允许在本项目仓库。
4. GPU 0 上存在公司服务，绝不触碰。历史上项目单副本使用 GPU 1，短时第二副本使用 GPU 2，但资源状态是动态的，每次扩容前必须重新从 Kubernetes 账本和宿主机交叉核对。
5. 第二张卡只用于 Phase 4 短时、受控、事前审计的实验；结束后必须恢复单副本并确认临时 GPU 回到空闲。
6. 双副本覆盖层必须保证不会出现第三个 GPU Pod；当前使用 `maxSurge=0`。
7. 集群没有可用的 Metrics API、custom/external metrics API 或 KEDA。不得为个人项目安装或修改公司集群级 Adapter/KEDA。
8. 共享 Grafana 身份只读，不能为了截图或项目完整性写入公司 `insight-system`。
9. 不保存、不复述、不自动使用用户曾经输入的 sudo 密码。需要 sudo/kubectl 写操作时，把命令交给用户本人执行。
10. 用户本人执行关键外部动作：Git commit/push、sudo、kubectl apply/delete/scale、凭据输入。Agent 可以完成仓库编辑、离线测试、只读检查和用户明确授权范围内的监测。

资源上限是安全边界，不是必须使用两张卡的目标。无法确认第二张 GPU 安全时，应停止真实双副本实验并如实记录共享环境限制。

## 3. 环境与当前服务基线

- 仓库：`/home/qhadmin/boshi/vllm/vllm-infra-lab`
- GitHub：`boshilin123/vllm-infra-lab`
- 分支：`main`，跟踪 `origin/main`
- Kubernetes：v1.28.15，节点 `qhvgpu1`、`qhvgpu2`
- `qhvgpu1`：4 张 NVIDIA A10，每张 `23028 MiB`，标准 `nvidia.com/gpu`整卡资源
- 模型：Qwen3-8B BF16，本地只读模型目录
- vLLM：0.9.1
- 单副本基线：`max-model-len=4096`、`max-num-seqs=8`、`gpu-memory-utilization=0.85`
- Deployment base：1 个副本，`Recreate`
- 精确 KV Cache 池：约 `3.14 GiB`、`22,832 tokens`、`1427 blocks`
- 项目 Pod 空闲时 DCGM framebuffer 常驻约 `20,212 MiB`，主要是权重、KV block 池、CUDA Graph 等预分配；它不是实时业务负载，因此不能作为 HPA/KEDA 主信号。

Pod 名称、Pod IP、物理 GPU 编号都可能在重建后改变。必须通过容器内外 GPU UUID、Deployment args、Endpoint 和真实 labels重新核对，不能沿用历史值。正确 Pod label 是 `app.kubernetes.io/name=qwen3-8b`，不是 `app=qwen3-8b`。

## 4. 阶段状态

| Phase | 状态 | 核心交付 |
| --- | --- | --- |
| Phase 0 环境与安全 | 已完成 | 集群、GPU、模型、共享负载、Git 与硬安全边界 |
| Phase 1 单副本服务 | 已完成 | Deployment/Service、三类探针、OpenAI API、Pod 自愈 |
| Phase 2 性能与参数 | 已完成 | 并发扫描、mns8/16、Prefill/Decode、三轮聚合、确定性 SVG |
| Phase 3 可观测性 | 已完成 | ServiceMonitor、13 条 PromQL、Grafana schema 37 JSON、统一时间线 |
| Phase 4 多副本与弹性 | 已完成当前安全范围 | 静态双副本、确定性8/8、离线弹性回放、least-inflight HTTP/SSE真实双副本验证与安全回退；未部署自动控制器 |

## 5. 已冻结的 SLO

Short 场景（256 Prompt / 128 Output）：

- 成功率 ≥99%
- P95 TTFT ≤600 ms
- P95 TPOT ≤50 ms
- P95 E2E ≤6000 ms

Long 场景：

- 成功率 ≥99%
- P95 TTFT ≤1500 ms
- P95 TPOT ≤55 ms
- P95 E2E ≤13 s

吞吐 CV ≤3%是重复性门槛，不是用户体验 SLO。不能把吞吐提高等价为 SLO 达标，也不能用事后修改阈值包装实验结果。

## 6. Phase 2 关键数据

### 6.1 Short 并发扫描，单卡 mns8

| 并发 | Output tok/s | P95 TTFT ms | P95 TPOT ms | P95 E2E ms |
| ---: | ---: | ---: | ---: | ---: |
| 1 | 28.355 | 77.905 | 约 35 | 4528.059 |
| 2 | 51.054 | 168.884 | — | 5025.727 |
| 4 | 98.464 | 288.335 | — | 5215.564 |
| 8 | 178.796 | 524.927 | 42.740 | 5554.010 |
| 16 | 179.285 | 6015.515 | 42.703 | 11095.317 |

c8→c16 吞吐只增加 0.27%，但 waiting 从 0变为约 8，TTFT/E2E 大幅恶化。首先命中的是 `max-num-seqs=8` 配置上限，不是 KV Cache 耗尽，也不能由 GPU-Util 单指标推断全局物理峰值。

### 6.2 固定 c16，mns8→mns16

- 输出吞吐：179.285→305.434 tok/s，`+70.36%`
- P95 TTFT：6015.515→976.838 ms，`-83.76%`
- P95 TPOT：约 42.70→46.77 ms，计算竞争有所增加
- P95 E2E：11095.317→6152.403 ms，仍略高于 6 s SLO
- mns16：`running=16、waiting=0`，KV Cache 采样峰值约 24.18%

这证明 179 tok/s 不是单卡全局峰值，但 mns16 也没有同时满足 TTFT/E2E SLO，所以不能只继续扩大批宽。

### 6.3 Prefill / Decode 控制变量

- 256/128：当前 GPU 1相邻 Short 校准
- 1024/128：Prompt 增长使 P95 TTFT 上升约 201%，输出吞吐下降约 23%
- 256/256：输出翻倍使 P95 E2E 增加约 5.10 s，P95 TPOT基本不变
- 1024/256：KV Cache 峰值约 44.36%，P95 E2E 12.789 s，Long SLO 通过但只剩约 211 ms余量

输出吞吐只统计生成 Token；总 Token 吞吐同时包括 Prompt Token，不能用更长输入制造“生成能力提高”的结论。

## 7. Phase 3 可观测性结论

代表性 c16-mns8 统一时间线：

- 240/240 正式请求成功
- 输出吞吐约 186.87 tok/s
- `running=8、waiting=8`
- KV Cache 峰值 13.525%
- GPU-Util 峰值 97%
- 负载结束后 waiting/running/GPU 恢复空闲

DCGM framebuffer 全程约 20,212 MiB 是预分配常驻显存；vLLM KV usage 百分比表示已使用的预分配 KV block 比例，两者语义不同。PromQL 是 Prometheus Query Language，用于查询和聚合时间序列。

共享 Grafana 版本为 9.3.14、schema 37；Dashboard JSON 和真实 PromQL 已验证，但没有持久化导入共享 Grafana，简历不能写成“发布线上 Dashboard”。

## 8. Phase 4 最重要的因果证据

### 8.1 普通 Service 静态双副本

- 两张 A10，每副本 mns8，总 c16
- 300/300 成功
- 输出吞吐中位数：332.912 tok/s，相对单副本 c16-mns8 `+85.69%`
- P95 TTFT/TPOT/E2E：5469.014 / 42.484 / 10741.813 ms
- 累计请求约 50/50，但瞬时 waiting 峰值为 6/4
- 直接观察到一侧 `8 running/6 waiting`、另一侧仍有空槽

结论：双卡容量有效，但 ClusterIP 的连接级分流不感知 vLLM queue；客户端连接复用导致单波次偏斜，尾延迟仍失败。累计 50/50 不能证明瞬时均衡。

### 8.2 确定性 8/8 直连对照

- 300/300 成功
- 输出吞吐中位数：334.824 tok/s
- P95 TTFT/TPOT/E2E：524.631 / 42.706 / 5543.586 ms，Short SLO 全通过
- 两侧正式请求 150/150
- 两侧全流程 request/Prompt/Generation counter 完全相同
- Peak running 8/8；所有 5 秒采样点均未观测到 waiting
- 相对普通 Service：吞吐只变化 `+0.57%`，P95 TTFT `-90.41%`，P95 E2E `-48.39%`

结论：相同计算容量和总并发下，仅改变请求目标就恢复尾延迟，因此普通 Service 的瞬时分流是此前失败的主要原因。严格说法是“采样点未观测到 waiting”，不能由 5 秒采样断言任意毫秒绝对为 0。

直连 Pod IP 是因果对照，不是生产方案；它没有服务发现、故障转移或动态负载感知。该实验没有扫描 c24/c32，不能声称达到双副本峰值。

### 8.3 弹性离线回放

策略：waiting 连续两个 15 秒采样点触发 1→2，实测冷启动 155 秒；缩容要求 waiting=0、running≤4持续 300 秒，且第二副本 Ready 至少 300 秒。

历史回放：

```text
02:44:29Z  请求扩容
02:46:44Z  最后一个有负载的采样点
02:47:04Z  第二副本计划 Ready
```

新容量晚于最后负载采样约 20 秒，说明 `minReplicas=1` 的纯反应式扩容无法挽救这次短突发。它更适合持续压力、预测预热，或者用长期第二副本换响应时间。离线回放不代表 Kubernetes 中真实发生过自动扩容。

## 9. 本轮新增的 least-inflight 路由与 HTTP 适配

本轮已新增：

- `router/least_inflight.py`
- `router/http_proxy.py`
- `router/README.md`
- `tests/test_least_inflight.py`
- `tests/test_http_proxy.py`
- 相关架构、策略、项目日志和简历文档更新

`in-flight`表示已经被路由器接收并转发、但完整生命周期尚未结束的请求，包含后端 waiting、Prefill、Decode 和仍在传输的流式响应。

已实现：

- 只选择健康后端
- 原子选择 in-flight 最小者并立即加一
- 相同负载时轮询打破平局
- `BackendLease`在完整结束或异常时释放，重复 release 幂等
- 后端摘除只影响新请求，不中断已有 lease
- 所有后端不可用时快速失败
- 16 个同时持有的等成本请求形成 8/8
- 最小 HTTP/1.0 代理转发 GET/POST/PUT/PATCH/DELETE
- 非流式写完和 SSE 流结束后才释放 lease
- 客户端断开、上游异常路径通过 `finally` 清理，不泄漏计数
- 固定 `/health` 探测支持摘除与恢复；全不可用返回 503
- 已发送请求不自动改投另一后端；16 个同时持有的 HTTP 请求形成 8/8
- least-inflight 核心 7 个、HTTP 适配 9 个、弹性回放 4 个，全仓当前 20 个测试通过
- `/_router/status`只读返回每个后端的健康、in-flight 和累计选择数，不把状态查询转发到后端

尚未实现：Kubernetes EndpointSlice 服务发现、生产级连接池/背压/限流、认证与指标、优雅摘流、Token-aware 权重。客户端断开在下一次下游写入时被发现；若上游长时间没有新 chunk，取消感知会延后。当前已通过一次固定256/128 Token真实双副本实验，仍不能称为“已部署的生产队列感知负载均衡器”。

流式请求不能在收到响应头时释放 in-flight，因为此时后端通常仍在 Decode。必须等流正常结束、客户端断开或异常清理。后端不健康时，新请求应转向其他健康后端；已开始且连接正常的请求继续，生成中途失败不能盲目重试，否则可能重复或改变输出。

仅按请求数量在固定 256/128 场景是合理第一版，但长短混合时一个 2048/512 和一个 256/32 都只记作 1，无法表达不同 Prefill、Decode、KV 和连接占用；Token 估算或完成时长 EWMA 是后续扩展，不要提前声称已经实现。

## 10. 简历可写主故事

推荐按以下逻辑讲，而不是罗列工具：

```text
建立可恢复单副本服务
→ 并发扫描发现 mns8 排队拐点
→ mns8/16 单变量证明配置上限不等于物理峰值
→ SLO 证明更高吞吐仍不代表优化完成
→ Prefill/Decode 实验解释延迟来源
→ Prometheus/DCGM 时间线补齐运行时证据
→ 静态双副本证明容量、同时暴露连接级瞬时偏斜
→ 确定性 8/8 反事实对照证明请求分流是尾延迟主因
→ 真实 least-inflight 代理在保持吞吐时恢复 Short SLO
→ 155 秒冷启动回放界定反应式弹性的适用流量
```

平台/弹性方向最强的一条可表述为：

> 定位普通 Kubernetes Service 在双 A10、c16 下的连接级瞬时偏斜后，设计并实现 least-inflight HTTP/SSE 路由器；三轮300/300请求成功，以335.35 tok/s保留约100.2%的确定性8/8直连吞吐，将 P95 TTFT 从5.47 s降至0.456 s、P95 E2E从10.74 s降至5.53 s，并在实验后恢复单副本、释放临时 GPU。

可以辅助说明离线弹性策略，但必须明确“离线回放”；真实代理也只能表述为固定成本合成负载下的受控实验，不能写成 HPA/KEDA 或生产代理已经上线。

## 11. 简历和面试不能越界

- 不能声称 HPA/KEDA、自定义指标自动扩容已经部署。
- 不能声称普通 ClusterIP 双副本满足 Short SLO。
- 不能声称 least-inflight 核心已经成为生产 HTTP 路由器。
- 不能声称找到单卡或双卡全局峰值/最优参数。
- 不能把固定合成负载推广为真实线上流量结果。
- 不能把 1024/256 结果推广到模型最大上下文。
- 不能把跨不同物理 GPU 的小差异包装成参数收益。
- 不能声称修改或自研了 vLLM 内部算法。
- 不能声称完成整卡与 HAMi/vGPU 对比。
- 不能为了故事连贯修改真实日期、补造监控数据或忽略失败实验。

面试回答使用“问题 → 假设 → 控制变量 → 指标证据 → 结论 → 限制”，避免只说“GPU 97%所以跑满”“KV 很低所以还能扩”等单指标判断。

## 12. 已遇到的工程问题

- SSH 易断：长任务使用 tmux；普通用户和 root tmux 是两套会话列表。
- 不使用 `sudo git`：历史上曾导致仓库所有权不一致。
- port-forward Service 可能固定到单个后端，不能用它验证负载均衡；多副本压测客户端应位于集群内。
- benchmark client UID 1000不在镜像 passwd：通过显式 `USER/LOGNAME/HOME/XDG_CACHE_HOME/TORCHINDUCTOR_CACHE_DIR`修复，不提升为 root。
- 系统 Python 与 venv vLLM 可能混用：不仅检查 Python 路径，也检查子进程找到的 `vllm`版本。
- 随机 Prompt 会包含 error/traceback 等词：日志审计要看日志级别、字段和 HTTP 状态，不能把关键词命中直接当故障。
- 不同并发使用独立随机种子，避免 Prefix Cache 污染控制变量。
- 容器时区可能是 `-07:00`，宿主机是 Asia/Shanghai；必须依赖带 offset 的 metadata 对齐，不能凭目录小时判断时钟错误。
- Pod 内 GPU 0只是 Device Plugin 注入后的逻辑编号；物理设备必须看 UUID。

## 13. Git 与本轮状态

本轮真实实验开始时已推送的远端 HEAD：

```text
878c97a bench: prepare least-inflight router experiment
```

该提交已位于 `origin/main`且真实实验开始前工作区干净。当前工作区新增2026-09-08真实结果、脱敏运行时摘要及待用户检查的文档更新；包含内部 Pod 名称/IP 的原始 `.log` 仅留在实验主机并由 `.gitignore` 排除。新会话仍应以 Git 实际状态为准。提交前校验命令为：

```bash
python3 -m unittest discover -s tests -p 'test_*.py'
python3 -m py_compile router/__init__.py router/least_inflight.py router/http_proxy.py
ruff check router tests
git diff --check
git status --short
```

用户提交成功后，新会话必须先运行 `git status --short`和 `git log -3 --oneline --decorate`确认真实状态，不要假定本文件中的 HEAD 仍是最新。

## 14. 下一步建议

最小 HTTP/流式适配层已完成本地 CPU/mock 与真实双副本验证；冻结验收线及结果为：

1. 非流式响应完成后释放 lease；
2. SSE 流完整结束后释放，不能在响应头到达时释放；
3. 客户端中断、连接错误和取消路径不泄漏计数；
4. 健康后端摘除与恢复；
5. 所有后端不可用时明确返回 503；
6. 已发送并开始生成的请求不做盲目自动重试；
7. 16 个固定成本请求仍形成接近 8/8；
8. 输出吞吐中位数至少保留确定性直连的 90%，即 `301.342 tok/s`；
9. Short P95 TTFT/TPOT/E2E 必须分别不高于 600/50/6000 ms。

2026-09-08 安全审计确认公司 Pod 位于物理GPU0、原项目副本位于GPU1，GPU2/3同时满足宿主机无进程和Kubernetes未分配。用户执行双副本 apply 后，新副本落在GPU2；三轮300/300正式请求成功，中位输出吞吐335.349 tok/s，P95 TTFT/TPOT/E2E为456.041/42.438/5527.425 ms。正式窗口51个五秒采样点两侧最大running为8/8、waiting均为0；路由选择占比约48.5%/51.5%，最终in-flight为0/0。用户随后恢复base单副本并删除client，GPU2回到1 MiB，公司GPU0和Pod状态未变化。

真实结果、文档和 `analysis/generated/phase4-routing-comparison.svg` 已固化，下一步仅需用户检查后提交并推送；不再为了“完成自动扩缩容”重新占用公司GPU。若继续技术扩展，优先做纯离线长短混合权重模拟或 EndpointSlice 设计评审，而非在共享集群安装控制器。

不要立即执行真实自动扩缩容。当前 Phase 4 最有价值的已完成证据是“容量、分流、冷启动”三者的拆分；真实弹性实验是否值得做，要同时考虑共享环境、155 秒启动和可持续流量场景，不能为了简历形式勉强占用公司资源。
