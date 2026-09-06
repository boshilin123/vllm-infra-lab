# Benchmark

目录职责：

- `scenarios/`：与工具无关的负载定义，固定输入/输出 Token、并发和持续时间。
- `run_benchmark.py`：读取场景，执行预热与重复的 vLLM benchmark，并保存原始结果和实验元数据。
- `aggregate_results.py`：校验并汇总重复实验（Phase 2）。

压测客户端与推理服务应尽量分离，避免客户端 CPU 或网络瓶颈污染结果。

## 运行单个并发档位

先激活青海环境中已有的客户端虚拟环境：

```bash
source /home/qhadmin/boshi/vllm/envs/vllm-qwen3/bin/activate
```

先用 dry-run 审核将要执行的命令，不发送请求：

```bash
python benchmark/run_benchmark.py \
  --base-url http://127.0.0.1:28080 \
  --scenario benchmark/scenarios/short.yaml \
  --concurrency 1 \
  --server-node qhvgpu1 \
  --server-gpu-physical-index <本轮宿主机物理编号> \
  --server-gpu-uuid <本轮容器内外一致的GPU-UUID> \
  --server-max-num-seqs 8 \
  --server-max-model-len 4096 \
  --server-gpu-memory-utilization 0.85 \
  --dry-run
```

去掉 `--dry-run` 后，每次重复都会先执行场景定义的预热请求，再执行正式请求。原始 JSON 和 `metadata.yaml` 保存到 `results/YYYY-MM-DD/<experiment-id>/`。目录名包含客户端并发和服务端 `max-num-seqs`，例如 `short-c16-mns8`，便于区分参数实验。

物理 GPU 编号和 UUID 必须在每组实验前从宿主机与容器交叉核对；Pod 重建后不得沿用旧值。三个 `--server-*` 引擎参数只负责把服务端实际配置写入 metadata，并不会远程修改 vLLM；运行前必须用 Deployment args 或 Pod command 核对它们与真实配置一致。

随机种子由场景、并发档位和重复轮次共同决定：同一实验可以复现，不同场景和并发档位不会生成相同 Prompt，从而避免服务端 Prefix Cache 污染控制变量。历史 `short` 场景未设置 `seed_offset`，默认仍为 0，保留既有基线的种子；新增场景必须使用互不重复的非负偏移量。

## Prefill / Decode 单变量对照

Phase 2 在并发 8、`max-num-seqs=8` 下使用四组负载：

| 场景 | 输入/输出 Token | 用途 |
| --- | ---: | --- |
| `short.yaml` | 256/128 | 在当前 Pod 和 GPU 上校准已有基线 |
| `prefill-focused.yaml` | 1024/128 | 只增加输入，主要观察 TTFT 与 Prefill 代价 |
| `decode-focused.yaml` | 256/256 | 只增加输出，主要观察 TPOT 与 Decode 累积代价 |
| `long-context.yaml` | 1024/256 | 同时增加输入输出，观察组合压力、KV Cache 与 E2E |

这组实验不重复完整并发扫描：Short 场景已经确定 mns8 的吞吐拐点约在并发 8；固定该并发可以减少共享公司 GPU 的占用时间，并用单变量对照回答输入/输出长度的影响。Short 校准必须与后三组在同一个 Pod、同一物理 GPU 和相邻时间窗口执行，否则不能把跨 GPU 差异归因于 Token 长度。

Long SLO v1 只用于本项目合成长上下文负载的工程验收，不冒充真实业务需求：成功率不低于 99%，P95 TTFT 不高于 1500 ms，P95 TPOT 不高于 55 ms，P95 E2E 不高于 13 s。与 Short SLO 相比，TTFT 预算从 600 ms 放宽到 1500 ms，以容纳 4 倍 Prompt；E2E 从 6 s 放宽到 13 s，以容纳 2 倍输出和额外 Prefill；TPOT 只从 50 ms 放宽到 55 ms，因为输出长度增加不应让稳定 Decode 的逐 Token 间隔成倍恶化。

## 校验与汇总结果

先使用 `--check-only` 验证轮次数、成功请求数、并发、模型、输入/输出 Token 长度和错误列表，不写文件：

```bash
python benchmark/aggregate_results.py \
  --experiment-dir results/YYYY-MM-DD/<experiment-id> \
  --check-only
```

去掉 `--check-only` 后生成：

- `per-repeat.csv`：每轮原始核心指标，便于横向检查异常轮次。
- `summary.csv`：各指标跨重复实验的均值、中位数、范围、标准差和变异系数。
- `aggregate.json`：保留实验身份、校验状态和结构化汇总，供后续跨并发绘图脚本读取。
