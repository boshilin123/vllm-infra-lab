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
  --server-gpu-physical-index 3 \
  --server-gpu-uuid GPU-c9ee2ea8-993d-e7e2-7e3f-7a183b63d573 \
  --dry-run
```

去掉 `--dry-run` 后，每次重复都会先执行场景定义的预热请求，再执行正式请求。原始 JSON 和 `metadata.yaml` 保存到 `results/YYYY-MM-DD/<experiment-id>/`。物理 GPU 编号和 UUID 必须在每组实验前从宿主机与容器交叉核对；Pod 重建后不得沿用旧值。

随机种子由并发档位和重复轮次共同决定：同一实验可以复现，不同并发档位不会生成相同 Prompt，从而避免服务端 Prefix Cache 复用上一档实验的 KV Cache。各档位仍保持相同的输入/输出 Token 长度，因此并发仍是主要控制变量。

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
