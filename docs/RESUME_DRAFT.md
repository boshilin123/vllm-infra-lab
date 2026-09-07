# 简历与面试底稿

> 状态：持续更新。只使用仓库已有原始数据、清单和报告能够复验的事实；Phase 4 未完成内容不得提前写成成果。

## 1. 项目名称与定位

**vLLM 大模型推理服务性能与弹性优化**

技术栈：Kubernetes、vLLM、Qwen3-8B、NVIDIA A10、Prometheus、Grafana、Python

项目不是模型应用 Demo，也不声称实现了 PagedAttention 或 Continuous Batching。项目价值在于：把推理服务部署、负载建模、性能分析、SLO、可观测性和后续弹性串成可复验的工程闭环。

## 2. 当前可写的三条简历描述

以下版本只引用已经完成的 Phase 1/2 和 ServiceMonitor 事实：

1. 基于 Kubernetes 与 vLLM 0.9.1 部署 Qwen3-8B BF16 单卡推理服务，配置只读模型挂载、startup/readiness/liveness 探针及 ServiceMonitor，完成 OpenAI 兼容 API、Pod 删除自愈和 Prometheus target 验收。
2. 构建固定 Token 长度、预热、独立随机种子、三轮重复与 JSON/CSV 聚合的压测流程；在单张 A10 的 256/128 Token 场景中观察到 `max-num-seqs=8` 下 c8→c16 吞吐仅增 0.27%，并量化 P95 TTFT 从约 525 ms 恶化至 6.02 s 的排队代价。
3. 通过 `max-num-seqs=8→16` 单变量实验将 c16 输出吞吐从 179.29 提升至 305.43 tok/s（+70.36%），P95 E2E 从 11.10 s 降至 6.15 s；结合预注册 SLO 识别 TTFT/E2E 仍未达标，提出“每副本约 8 并发、后续用受控双副本扩容”而非继续扩大单卡批宽的方案。

若版面允许，可将第三条之后补成第四条：

4. 设计 256/128、1024/128、256/256、1024/256 同卡对照以拆分 Prefill/Decode：Prompt 增长使 P95 TTFT 上升约 201%，输出翻倍使 P95 E2E 增加约 5.10 s 而 P95 TPOT 基本不变，组合长上下文 180/180 请求成功并通过预注册 P95 Long SLO。

可观测性方向岗位可用下面一条替换第四条：

4. 将 vLLM scheduler/KV Cache/服务端延迟直方图与 DCGM GPU 指标对齐到 15 秒统一时间线；在 c16-mns8 压力下观测 `running=8、waiting=8`、KV Cache 峰值 13.52%、GPU-Util 峰值 97%，并验证负载结束后队列与 GPU 恢复空闲，补齐配置排队瓶颈的运行时证据。

## 3. 项目亮点而非算法创新

### 3.1 可复现证据链

不是只贴一张 benchmark 截图，而是保存场景 YAML、Git commit、GPU UUID、原始请求 JSON、逐轮 CSV、聚合中位数、CV、实验 README 和确定性 SVG。不同场景使用独立种子，降低 Prefix Cache 对控制变量实验的污染。

### 3.2 区分配置瓶颈、物理瓶颈和 SLO 瓶颈

- c8→c16 在 mns8 下吞吐仅增加 0.27%，同时 waiting 和 TTFT 激增：证明先遇到运行序列配置上限。
- mns8→mns16 后吞吐增加 70.36%，证明 179 tok/s 不是单卡全局物理峰值。
- mns16 仍违反 TTFT/E2E SLO：证明“吞吐更高”不等于“优化完成”。
- KV Cache 仍有余量：不能把所有饱和现象都归因于显存容量。

这种分层判断比“GPU-Util 100%，所以 GPU 已跑满”更有工程价值。

进一步形成了可复用的容量决策链：先用 waiting 判断是否存在接纳压力，再用 KV Cache 排除显存块耗尽，用 GPU 与 TPOT 判断扩大单卡批宽的计算竞争，最后以预注册 SLO 决定继续调参还是横向扩容。它避免把任一指标机械地等价为扩容动作；该诊断方法已经由 Phase 2/3 数据支持，双副本收益仍需 Phase 4 实测后才能写成结果。

### 3.3 将延迟拆成可解释机制

- waiting 主要进入 queue、TTFT 和 E2E，而不完整进入 TPOT。
- Prompt 增长主要增加 Prefill 与 TTFT 压力。
- 输出长度增长主要通过更多 Decode 步数累积 E2E，TPOT 本身不随长度翻倍。
- 输出吞吐与总 Token 吞吐统计口径不同，不能用更多输入 Token 制造“生成性能提升”。

### 3.4 生产约束意识

项目在公司共享环境中设定最多两张 GPU 的硬上限，Phase 0–3 默认单卡；不停止、迁移或修改公司服务。使用 GPU UUID 而不是容器逻辑编号识别设备，处理过端口冲突、代理误路由、Pod 标签误筛、系统/venv vLLM 混用和随机 Prompt 造成日志关键词误报。

这不是一个新的推理算法，但体现 AI Infra 岗位需要的实验设计、瓶颈定位、可观测性、风险控制和证据表达能力。

## 4. 三张 Phase 2 图如何解读

### 4.1 Short 并发扫描

输出吞吐约为 28、51、98、179、179 tok/s，对应并发 1、2、4、8、16；c8→c16 几乎进入平台。与此同时 P95 TTFT 从约 525 ms 跃升到 6016 ms，P95 E2E 从 5.55 s 升到 11.10 s。结论是：mns8 下 c8 是当前 Short 负载的推荐运行点；c16 主要增加排队而非有效吞吐。

### 4.2 max-num-seqs 参数对照

固定 c16，只把 mns8 改为 mns16：输出吞吐增加 70.36%，P95 TTFT 下降 83.76%，P95 E2E 下降 44.55%，但 P95 TPOT 上升 9.52%。红色 SLO 线显示 TTFT 977 ms 仍高于 600 ms、E2E 6.152 s 仍高于 6 s。结论是：扩大批宽消除了主要 queue，但增加 Decode 资源竞争，且尚未同时满足体验目标。

### 4.3 Prefill / Decode 负载对照

- Short 256/128 是同卡基线。
- Prefill 1024/128 的输出吞吐降至 139 tok/s、P95 TTFT 升至 1464 ms，显示长 Prompt 的 Prefill 代价。
- Decode 256/256 的输出吞吐仍约 183 tok/s、P95 TPOT 仍约 41 ms，但 P95 E2E 升至 10.59 s，显示额外输出步数的累积代价。
- Combined 1024/256 的 P95 E2E 为 12.789 s，距离 13 s Long SLO 只剩约 211 ms；通过不等于余量充足。

前两张图使用历史物理 GPU 3，第三张图使用 Pod 重建后的物理 GPU 1。可以在各自控制变量组内比较，不能把跨 GPU 的小差异包装成参数收益。

## 5. 面试时的主故事

可以按以下顺序讲述：

```text
先建立可恢复的单副本服务
→ 用并发扫描观察到 mns8 下 c8→c16 的吞吐平台与排队症状
→ 固定 c16、只改变 mns8/16，确认首先命中的是配置上限而非单卡物理/KV 容量上限
→ 用 SLO 发现单卡更高吞吐仍不能满足尾延迟
→ 用 Prefill/Decode 对照解释延迟来自哪里
→ 用 Prometheus/DCGM 统一时间线补齐运行时因果证据
→ 最后在安全前提下验证最多两副本的容量方案
```

面试官若问“创新在哪里”，准确回答是：没有修改 vLLM 内核或提出新算法；创新性体现在实验方法和工程闭环——将配置饱和、KV 容量、排队、Prefill/Decode 和 SLO 分开验证，并让每个结论都能从版本化原始数据复算。

## 6. 当前不能写进简历的内容

- Grafana Dashboard JSON 已按公司现有 Grafana 9.3.14/schema 37 生成，13 条 PromQL 已对真实数据源验证；但没有持久化导入公司的共享 Grafana，不能声称完成了线上 Dashboard 发布。
- 尚未完成双副本、负载均衡、HPA/KEDA 或自定义指标扩缩容。
- 尚未证明 mns16、305 tok/s 是单卡全局最优或物理峰值。
- 尚未验证更长上下文、量化模型、其他 GPU 或真实线上流量。
- 不能声称自研或优化了 vLLM 内部 PagedAttention/Continuous Batching 算法。
