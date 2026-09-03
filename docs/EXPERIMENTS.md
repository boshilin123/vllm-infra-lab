# 实验设计

## 1. 基线配置

首轮建议基线：

- 模型：Qwen3-8B BF16
- GPU：NVIDIA A10 23 GiB
- vLLM：0.9.1
- `max-model-len=8192`
- `max-num-seqs=16`
- `gpu-memory-utilization=0.85`
- 单副本、单 GPU

实际启动后，以显存余量和稳定性结果调整基线，并在所有报告中记录变更。

## 2. 工作负载

### 短请求

- 输入 256 tokens
- 输出 128 tokens
- 并发 1、2、4、8、16

### 长上下文

- 输入 1024 tokens
- 输出 256 tokens
- 并发 1、2、4、8

### 突发流量

- 低负载稳定运行后快速提升请求速率
- 持续到副本扩容完成并恢复稳定
- 记录扩容前、扩容中、扩容后的指标

## 3. 参数实验

使用单变量法，其他参数保持基线不变：

- `gpu-memory-utilization`：0.80、0.85、0.90
- `max-num-seqs`：8、16、32
- `max-model-len`：4096、8192
- 并发数：1、2、4、8、16

若某项配置 OOM 或无法稳定启动，同样记录为运行边界，不静默删除失败结果。

## 4. 指标

客户端指标：

- TTFT
- TPOT / inter-token latency
- 端到端延迟
- P50、P95、P99
- requests/s
- input/output/total tokens/s
- 成功率与错误率

服务端指标：

- running requests
- waiting requests
- KV Cache 使用率
- prompt/generation token throughput
- 请求失败与重启次数

GPU 指标：

- GPU utilization
- framebuffer memory used
- power usage
- temperature

具体 Prometheus 指标名称以实际 vLLM 与 DCGM 版本为准，首次部署后固化查询表达式。

## 5. 运行规范

- 每个场景先预热，再进行正式采样。
- 每个配置至少重复三次，默认报告中位数，同时保留所有原始结果。
- 同一组对照实验尽量在相同节点和相近时间完成。
- 记录测试时间、Git commit、镜像版本、模型版本、节点和并存负载。
- 不只报告最高吞吐；同时报告尾延迟、错误率和资源代价。

## 6. 简历数据门槛

只有满足以下条件的数据才能写进简历：

- 可以从仓库脚本重新运行。
- 有原始结果文件和对应配置。
- 至少三次重复结果方向一致。
- 结论明确说明基线、变量和适用范围。
