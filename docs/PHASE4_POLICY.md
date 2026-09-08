# Phase 4 请求路由与弹性策略

## 1. 两个控制环

Phase 4 将多副本治理拆成两个职责，不把“副本数变成 2”误认为“流量自然均衡”。

### 1.1 容量控制环

容量控制环回答“应该有几个 Ready 副本”。它读取 15 秒 Prometheus 时间线，最多只在 1 和 2 个副本之间切换：

- 扩容：`waiting_requests > 0` 连续两个采样点；
- 冷启动：按实测 155 秒模拟第二副本从请求扩容到 Ready；
- 缩容：`waiting_requests == 0` 且 `running_requests <= 4` 持续 300 秒；
- 最短驻留：第二副本 Ready 后至少保留 300 秒；
- 安全边界：`minReplicas=1`、`maxReplicas=2`。

连续两个 15 秒采样点表示在相邻 scrape 中重复观测到压力，两个样本本身横跨约 15 秒；从真实压力首次发生到控制器确认的最坏检测时间还取决于它落在 scrape 周期的哪个位置。缩容窗口比扩容窗口长，是为了避免刚支付 155 秒冷启动成本就删除第二副本，并降低负载短暂回落造成的 1↔2 抖动。

### 1.2 请求路由控制环

请求路由控制环回答“新请求应该去哪个 Ready 副本”。最小方案由路由器维护每个后端的实时 in-flight 计数：

1. 只选择健康且 Ready 的后端；
2. 请求转发前原子增加目标后端的 in-flight；
3. 普通响应完成、流式响应关闭或请求失败时都必须减少计数；
4. 选择 in-flight 最小的后端，相同时轮询打破平局；
5. 后端失败时停止发送新请求，是否重试必须区分请求尚未发送和生成已经开始，避免重复生成。

Prometheus 15 秒采样适合容量趋势和审计，不适合逐请求选路。它的延迟足以让一个 c16 波次在下一次 scrape 前已经分配完。路由器本地 in-flight 能在每次接收请求时立即更新，但它也不是完整的计算成本：长 Prompt、不同 `max_tokens` 和流式连接可能让相同请求数对应不同工作量。后续可用估算 Token 成本或完成时长 EWMA 加权，本项目第一版先验证 least-inflight。

已经进入某个 vLLM waiting 队列的请求不会因扩容自动迁移。第二副本 Ready 后，路由器只能把后续新请求送过去；这也是扩容和路由必须协同、但职责不能混淆的原因。

路由选择与生命周期记账核心已在 `router/least_inflight.py` 实现，使用线程锁保证“选择最小值并加一”是一个原子操作；`BackendLease`保证正常完成、异常和重复释放路径不会泄漏计数。16 个同时持有的等成本请求测试得到 8/8，健康后端摘除、全部不可用、平局轮询和并发 acquire 均有单元测试。

`router/http_proxy.py`已增加标准库最小 HTTP/SSE 适配，并通过本地 mock backend 验证：lease 覆盖完整非流式响应与 SSE 流；客户端断开、连接异常和全后端不可用路径不会泄漏计数；健康检查支持摘除/恢复；已发送请求失败后不会盲目重试；16 个同时持有的 HTTP 请求形成 8/8。

该适配仍未连接真实 vLLM 或 Kubernetes，也没有 EndpointSlice 服务发现、生产级连接池/背压/限流、认证、指标、优雅摘流或 Token-aware 权重，因此不能称为已部署的生产队列感知负载均衡器。客户端断开是在下一次下游写入时被感知；上游长时间不产生 chunk 时，取消传播会相应延后。

## 2. 离线策略配置

版本化策略位于 `analysis/autoscaling-policy.json`，回放器位于 `analysis/simulate_autoscaling.py`。它只读取已提交的 `timeline.csv`，不会连接 Kubernetes、Prometheus 或公司服务：

```bash
python analysis/simulate_autoscaling.py \
  --timeline results/2026-09-07/20260907-104314-observability-burst-c16-mns8/monitoring/timeline.csv

python analysis/generate_autoscaling_chart.py \
  --simulation-dir results/2026-09-07/20260907-104314-observability-burst-c16-mns8/monitoring/autoscaling-simulation
```

输出：

- `decision-timeline.csv`：每个采样点的 running/waiting、desired/ready 副本数和事件；
- `summary.json`：触发、计划 Ready、实际采样观察和压力窗口结论。
- `timeline.svg`：scheduler 压力与模拟 desired/ready 副本数的确定性图表。

单元测试覆盖偶发 waiting 不扩容、连续 waiting 触发延迟扩容，以及缩容同时满足低负载窗口和最短驻留时间：

```bash
python -m unittest tests/test_simulate_autoscaling.py
```

## 3. Phase 3 历史时间线回放

代表性 c16-mns8 时间线中，`02:43:44Z` 首次出现 waiting，但下一点恢复为 0，因此没有误触发。`02:44:14Z` 和 `02:44:29Z` 连续出现 waiting，状态机在后一点请求扩容；加上 155 秒冷启动，第二副本计划于 `02:47:04Z` Ready。

最后一个 running/waiting 非零的采样点为 `02:46:44Z`。也就是说，新容量计划在最后负载采样之后约 20 秒才出现，无法改善该次约 3 分钟压力窗口前部已经发生的 TTFT/E2E。下一采样点在 `02:47:14Z` 才观察到模拟 Ready；时间线只剩 15 秒，未满足 300 秒缩容观察窗口，因此正确地不触发缩容。

## 4. 能证明和不能证明的内容

离线回放已经证明：按当前 15 秒采样和 155 秒冷启动，纯反应式 1→2 策略无法及时覆盖这次短突发；连续样本门槛能够过滤已出现的一次偶发 waiting。

它没有证明真实 Deployment 已自动扩容，也没有模拟第二副本 Ready 后的请求吞吐和延迟。历史单副本时间线无法凭空生成反事实双副本指标；真实收益仍要依赖已经完成的静态/确定性双副本实验，或后续一次受控的自动弹性实验。

## 5. 适用策略

- 不可预测且短于约 3 分钟的突发：`minReplicas=1` 的纯反应式扩容无法保证本次 SLO，只能接受早期排队、提前预热或长期保留第二副本。
- 持续压力：扩容 Ready 后可改善剩余窗口，但必须同时使用请求级路由。
- 周期性高峰：可以在预测高峰前至少 155 秒并预留检测/调度余量启动第二副本。
- 当前共享环境：默认保持一个副本；离线验证完成前不再次占用第二张 GPU，不安装集群级 KEDA/Adapter。
