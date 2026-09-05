# vLLM Infra Lab 项目总档案

> 更新时间：2026-09-05（Asia/Shanghai）
>
> 用途：记录求职定位、青海环境、项目设计、实际执行、故障排查、实验结果、学习问答和下一步计划。
>
> 原则：只把能够从代码、集群输出或原始实验数据复验的内容写成已完成事实。

## 0. 如何使用这份文档

这不是一份只展示最终结果的 README，而是整个个人项目的“实验日志 + 学习笔记 + 面试底稿”。后续每完成一次部署、实验或故障排查，都应继续追加记录。

文中使用三种状态：

- **已完成**：仓库、集群输出或实验文件能够证明。
- **进行中**：已经开始，但交付物尚未全部完成或提交。
- **计划中**：尚未实施，不能写成简历成果。

Pod 名称、Pod IP、GPU 占用和磁盘余量都会变化。文中的这类数据属于当时的**观测快照**，下一次实验前必须重新检查，不能直接沿用。

本文不会记录服务器密码、SSH 私钥、GitHub Token 或一次性验证码。曾经出现在聊天记录中的服务器密码应当轮换。

## 1. 求职与面试背景

### 1.1 为什么要做这个项目

本项目服务于 AI Infra / LLM Serving / 推理基础设施方向的秋招准备。它不是为了证明“会运行一个模型”，而是补足以下能力证据：

1. 能把本地模型工程化为 Kubernetes 上的稳定推理服务。
2. 理解 TTFT、TPOT、吞吐、尾延迟、KV Cache 和 Continuous Batching 等推理指标与机制。
3. 能用控制变量、重复实验和原始数据得出可复验的性能结论。
4. 能把 vLLM 服务指标、GPU 指标、故障恢复和弹性扩缩容串成完整系统。

项目正式名称确定为：

> **vLLM 大模型推理服务性能与弹性优化**

选择在标题中直接写 `vLLM`，是因为它更明确地指向推理引擎和 Serving 岗位；“可观测性”是核心模块，但不必把所有技术名词都堆进标题。

### 1.2 与实习项目的边界

为了避免个人项目和“聚时 AI 推理资源管理平台”实习经历都围绕 HAMi/vGPU，两个项目要形成清晰分工：

| 经历 | 核心视角 | 重点能力 |
| --- | --- | --- |
| 本个人项目 | 推理数据面 | vLLM Serving、请求负载、KV Cache、性能、可观测性、多副本和弹性 |
| 聚时实习 | 算力控制面 | GPU/NPU 接入、Device Plugin、HAMi/vGPU、资源抽象、容量与调度治理 |
| KubeEdge / 开源经历 | 云边基础设施 | 云边协同、多架构、离线环境、源码和社区协作 |

HAMi 可以作为个人项目的可选扩展实验，但不进入标题和当前主线。只有形成例如“某算力配额下保留多少吞吐、提升多少实例密度”这样的实测结论，才值得写入简历。

### 1.3 面试官应当看到的项目闭环

```text
需求与资源盘点
  → Kubernetes 单副本部署
  → API 与自愈验收
  → Prometheus 持续采集
  → 可复现并发压测
  → 性能曲线和饱和点分析
  → 参数优化
  → 多副本与弹性实验
  → 有证据的简历描述
```

项目不宣称自主实现 vLLM 的 Continuous Batching、PagedAttention 或 KV Cache。准确说法是：**配置、观测并分析这些引擎机制对服务性能的影响**。

## 2. 协作和学习方式

这是个人实习型项目，关键操作必须由项目本人实际执行，而不是由 Agent 一次性完成。

### 2.1 分工约定

**项目本人负责：**

- 阅读配置和脚本，确认自己能解释重要参数。
- 在服务器上执行 `kubectl apply/delete/get/logs`、端口转发和压测。
- 在实验前给出假设，在实验后先尝试解释结果。
- 检查 `git diff`，亲自提交并推送关键里程碑。
- 面试前从原始数据独立复算结论。

**Agent 负责：**

- 盘点代码和环境，设计分阶段实施方案。
- 编写带中文注释的清单、脚本和文档，并逐模块解释。
- 对用户执行后的输出进行诊断，不擅自修改共享集群。
- 在 SSH 易断场景下通过只读命令监督 tmux、Pod、Prometheus 和 GPU 状态。
- 校验实验数据、生成报告，并用追问帮助理解而不是只给答案。

### 2.2 每轮实验的学习闭环

每个关键实验遵循：

1. **先预测**：吞吐、TTFT、TPOT、E2E、waiting requests 会如何变化？
2. **本人执行**：使用 tmux 后台运行，保留原始 JSON 和环境元数据。
3. **过程观测**：检查客户端进度、vLLM 指标、GPU 利用率、显存和错误。
4. **本人先解释**：先回答算术、原因、稳定性和边界问题。
5. **校正与总结**：用数据修正直觉，写入实验 README。
6. **检查后提交**：`git diff --check`、查看 diff、本人 commit/push。

以后仍应保留这种“先提问、再作答、最后校正”的方式。

## 3. 青海环境事实清单

### 3.1 代码与 Git

| 项目 | 当前事实 |
| --- | --- |
| 仓库路径 | `/home/qhadmin/boshi/vllm/vllm-infra-lab` |
| GitHub 仓库 | `boshilin123/vllm-infra-lab` |
| 远端地址 | `git@github-vllm-infra:boshilin123/vllm-infra-lab.git` |
| 默认分支 | `main`，跟踪 `origin/main` |
| SSH Host 别名 | `github-vllm-infra` |
| 专用密钥 | `~/.ssh/id_ed25519_vllm_infra_lab`（只记录路径，不记录私钥） |

服务器不能打开图形浏览器，因此没有继续依赖 GitHub CLI 的浏览器/device-flow 登录，而是使用 GitHub SSH 密钥和 `~/.ssh/config` Host 别名。验证成功的表现是：

```text
Hi boshilin123/vllm-infra-lab! You've successfully authenticated...
Everything up-to-date
```

GitHub 的提示“does not provide shell access”是正常现象，表示 SSH 鉴权成功但 GitHub 不提供交互式 shell。

曾遇到 `.git/config: Permission denied`，原因是此前用 `sudo` 造成仓库文件所有权不一致。修复所有权后，以普通用户执行 Git 操作。后续不要用 `sudo git ...`。

截至 `max-num-seqs` 参数实验准备前，远端最新提交为：

```text
9cd6718 data: add concurrency-16 saturation baseline
```

并发 16 原始结果、报告和复盘均已推送；当前开始准备 `max-num-seqs=8→16` 控制变量实验。

### 3.2 Kubernetes 集群

| 项目 | 盘点结果 |
| --- | --- |
| Kubernetes | v1.28.15 |
| 节点 | `qhvgpu1`、`qhvgpu2`，盘点时均为 Ready |
| 单节点 CPU / 内存 | 约 32 vCPU / 125 GiB |
| `qhvgpu1` | 4 张 NVIDIA A10，以 `nvidia.com/gpu` 暴露整卡 |
| `qhvgpu2` | 4 张 NVIDIA A10，通过 HAMi 暴露 40 个 `nvidia.com/vgpu` 调度份额 |
| 监控基础 | Prometheus、Grafana、DCGM Exporter、ServiceMonitor CRD |
| 当前实验 namespace | `vllm-infra-lab` |

HAMi 版本盘点为 v2.5.2，具备 `nvidia.com/vgpu`、`nvidia.com/gpucores` 和 `nvidia.com/gpumem` 等资源能力，但当前单副本基线使用 `qhvgpu1` 的原生整卡，不以 HAMi 为主线。

### 3.3 模型和 Python 环境

| 项目 | 当前事实 |
| --- | --- |
| 模型 | Qwen3-8B，BF16，5 个 safetensors 分片 |
| 宿主机模型路径 | `/home/qhadmin/boshi/vllm/models/Qwen3-8B` |
| 模型大小 | 约 16 GiB |
| 模型声明最大上下文 | 40,960 tokens |
| 实验服务最大上下文 | 4,096 tokens，作为 A10 单卡保守基线 |
| Python 虚拟环境 | `/home/qhadmin/boshi/vllm/envs/vllm-qwen3` |
| Python | 3.10.12 |
| vLLM 客户端 | 0.9.1 |
| PyTorch | 2.7.0+cu126 |
| Transformers | 4.53.3 |
| OpenAI SDK | 3.3.1 |

虚拟环境必须注意：当前模型服务运行在 Kubernetes 容器内；宿主机虚拟环境主要用于执行 `vllm bench serve` 和本地辅助脚本。激活虚拟环境不会再启动一份模型，也不会额外占用实验 GPU。

```bash
source /home/qhadmin/boshi/vllm/envs/vllm-qwen3/bin/activate
```

### 3.4 容量快照

盘点时宿主机约有：

- 磁盘：1006 GiB 总量、785 GiB 已用、170 GiB 可用，使用率约 83%。
- 内存：125 GiB 总量、约 82 GiB 可用。
- Swap：未配置。

官方 `vllm/vllm-openai:v0.9.1` 的 linux/amd64 镜像压缩层约 10.31 GB，实际首次拉取耗时约 11 分 17 秒。镜像现已缓存，但磁盘已用率较高，后续引入更多镜像或量化模型前要重新检查空间。

**模型权重和运行镜像不是同一个东西：**

- 本地 Qwen3-8B 权重提供神经网络参数。
- vLLM 镜像提供 Python、CUDA 依赖、vLLM 引擎和 OpenAI API Server。
- Deployment 通过 `hostPath` 把本地模型只读挂载到运行容器。

### 3.5 GPU 分配与编号

当前 vLLM Pod 由 Kubernetes Device Plugin 分配到宿主机物理 GPU 3：

```text
物理 GPU：3
GPU UUID：GPU-c9ee2ea8-993d-e7e2-7e3f-7a183b63d573
容器内可见编号：GPU 0
```

容器里显示 `GPU 0` 并不表示使用宿主机物理 GPU 0。Device Plugin 只把分配到的那张卡暴露给容器，并在容器内部重新编号为 0。应以 UUID 交叉核对：

```bash
nvidia-smi -L

sudo kubectl exec \
  -n vllm-infra-lab \
  deployment/qwen3-8b \
  -- nvidia-smi -L
```

不在 Pod 中强行写 `CUDA_VISIBLE_DEVICES: "3"`，原因是容器通常只看得到由 Device Plugin 注入的逻辑设备 0，物理编号 3 在容器设备命名空间中可能不存在；硬编码还会破坏 Kubernetes 调度和 Pod 重建后的可迁移性。

盘点时宿主机物理 GPU 0 有 Qwen3-TTS Python 进程，约占 5.9 GiB；该工作负载与本项目无关，不能停止。实验前必须重新检查全部 GPU 和共存进程。

vLLM 空闲时物理 GPU 3 仍占约 19.8 GiB 显存是正常的，主要包括：

- Qwen3-8B BF16 权重，日志显示约 15.27 GiB。
- 按 `gpu-memory-utilization=0.85` 预算预留的 KV Cache。
- CUDA Context、CUDA Graph 和算子工作区。

`gpu-memory-utilization=0.85` 是显存预算，不代表 GPU 计算利用率为 85%；`nvidia-smi` 的 GPU-Util 也只是采样窗口内 GPU 忙碌时间比例，不等于有效 FLOPS、Tensor Core 利用率或已达到最大吞吐。

## 4. 当前服务架构与文件说明

### 4.1 请求和指标链路

```text
压测客户端（宿主机 venv）
  → 127.0.0.1:28080（kubectl port-forward）
  → Service qwen3-8b:8000
  → 单副本 vLLM Pod
  → 物理 A10 GPU 3

vLLM Pod /metrics
  → ServiceMonitor（每 15 秒）
  → insight-system 中的 Prometheus
  → 127.0.0.1:29090（Prometheus port-forward）
  → PromQL 查询 / 后续 Grafana Dashboard
```

端口约定：

| 本地端口 | 用途 | 注意事项 |
| --- | --- | --- |
| `28080` | vLLM Service 端口转发 | 当前压测和冒烟测试使用 |
| `29090` | Prometheus API 端口转发 | 用于 PromQL 验证和采样 |
| `18000` | 公司 BlueDot 产品测试端口 | **禁止占用或用于本项目测试** |

### 4.2 主要文件和模块

| 文件/目录 | 作用 |
| --- | --- |
| `deploy/kubernetes/namespace.yaml` | 创建隔离的 `vllm-infra-lab` namespace |
| `deploy/kubernetes/deployment.yaml` | 单副本 vLLM 服务、GPU、模型挂载、探针和资源配置 |
| `deploy/kubernetes/service.yaml` | 用 ClusterIP 和命名端口 `http` 暴露 8000 |
| `deploy/kubernetes/kustomization.yaml` | 组合部署资源，支持 `kubectl apply -k` |
| `scripts/smoke_test.py` | 从客户端检查 health、模型列表和 Chat Completions；显式绕过代理 |
| `monitoring/servicemonitor.yaml` | 告诉 Prometheus 持续抓取 Service 的 `/metrics` |
| `benchmark/scenarios/short.yaml` | 固定 256/128 Token、并发档位、请求数和重复次数 |
| `benchmark/run_benchmark.py` | 校验环境、预热、执行三轮压测并保存原始数据和元数据 |
| `benchmark/aggregate_results.py` | 校验结果并生成逐轮 CSV、中位数汇总和 aggregate JSON |
| `results/.../README.md` | 每一档实验的假设、结果、解释和边界 |
| `docs/EXPERIMENTS.md` | 总体实验设计和复盘问题规范 |
| 本文 | 项目全过程、环境事实、学习记录和后续接力入口 |

新增代码和 YAML 保持中文注释；如果第三方格式不适合行内注释，则必须在对应 README 或本文解释模块职责和关键参数。

### 4.3 Deployment 关键设计

当前单副本配置：

- `replicas: 1`：先建立单卡基线。
- `strategy: Recreate`：避免更新时新旧 Pod 同时占两张 GPU。
- `nodeSelector: qhvgpu1`：模型目前只存在该节点的本地目录。
- 镜像固定为 `vllm/vllm-openai:v0.9.1`，不使用 `latest`。
- 显式传入 `--model /models/Qwen3-8B` 和 `--served-model-name Qwen3-8B`。
- `--max-model-len 4096`、`--max-num-seqs 8`、`--gpu-memory-utilization 0.85`。
- CPU request/limit 为 2/4 核，内存 request/limit 为 16/32 GiB，GPU 为 1 张。
- 模型目录只读挂载；`/dev/shm` 和 cache 使用 Pod 临时目录。
- startup probe 最多容许约 10 分钟加载模型；readiness 控制流量；liveness 检测失去响应的进程。

`hostPath` 能快速完成单节点基线，但不支持模型自动跨节点访问。多副本或迁移到 `qhvgpu2` 前，需要共享存储、复制模型，或其他模型分发方案。

## 5. 已完成的部署与监控验收

### 5.1 Kubernetes 单副本服务

已完成：

- Namespace、Deployment、Service 的 client/server dry-run。
- 分步创建 namespace，并正式应用服务和 Deployment。
- Pod 在 `qhvgpu1` 启动，Service 获得 Endpoint。
- `/health`、`/v1/models`、`/v1/chat/completions` 冒烟测试通过。
- 手动删除 Pod 后，Deployment 自动重建；新 Pod 约 3 分 49 秒 Ready，Endpoint 自动切换，冒烟测试再次通过。

模型权重加载日志约为 71.63 秒；Pod 达到 Ready 还包含容器创建、引擎初始化、CUDA Graph、探针周期等时间。因此“模型加载时间”和“Pod 冷启动到 Ready 时间”不能混为一个指标。

### 5.2 vLLM 指标接口

`/metrics` 由 vLLM 官方镜像中的同一个 OpenAI API Server 暴露，不需要额外后台启动 Python 文件：

```text
同一个容器进程
├── /health
├── /v1/models
├── /v1/chat/completions
└── /metrics
```

宿主机上的 `smoke_test.py` 和 `vllm bench serve` 都是客户端，不是服务端进程。

手动观测到的指标包括：

- `vllm:num_requests_running`
- `vllm:num_requests_waiting`
- KV Cache 使用率
- prompt / generation token 计数或吞吐
- 请求完成原因

空闲时 running/waiting 为 0；一次限制输出为 32 Token 的测试请求以 length 原因结束是预期行为，不是错误。

### 5.3 Prometheus 自动采集

集群 Prometheus 位于 `insight-system`，版本盘点为 v2.53.5。其 ServiceMonitor selector 要求标签：

```yaml
operator.insight.io/managed-by: insight
```

已创建 `vllm-infra-lab/qwen3-8b` ServiceMonitor：

- 选择带 `app.kubernetes.io/name=qwen3-8b` 和 `component=inference-server` 的 Service。
- 通过 Service 命名端口 `http` 抓取 `/metrics`。
- 抓取周期 15 秒，超时 10 秒。

Prometheus API 查询已验证：

```promql
up{namespace="vllm-infra-lab"}
```

返回 `1`，说明抓取目标正常；真实 vLLM 指标查询也返回 Qwen3-8B 的时间序列：

```promql
vllm:num_requests_running{namespace="vllm-infra-lab"}
```

空闲值为 `0`，说明不是只有 target 存活，而是 vLLM 指标也已真正进入 Prometheus。

当前集群尚未确认存在 Prometheus Adapter、KEDA 或自定义指标 API，因此“使用 waiting requests 驱动 HPA”仍属于 Phase 4 计划，不能写成已完成。

## 6. 可复现压测方法

### 6.1 当前 short 场景

| 参数 | 值 |
| --- | ---: |
| 输入长度 | 256 tokens |
| 输出长度 | 128 tokens |
| 并发档位 | 1、2、4、8、16 |
| 每轮预热 | 10 requests |
| 每轮正式请求 | 100 requests |
| 重复次数 | 3 |
| 请求速率 | `inf`，由最大并发限制活跃请求数 |
| EOS | 忽略，保证固定输出长度 |

每档正式实验共 300 个请求。报告中使用三轮中位数，同时保留每轮数据和 CV。

初始方案曾考虑 GuideLLM，实际基线选择了虚拟环境中与服务端同版本的 `vllm bench serve`。这样不必先引入新的压测依赖，并且可以直接获得 TTFT、TPOT、ITL、E2E 和吞吐指标。GuideLLM 仍可作为后续交叉验证工具，但在实际安装和运行前不能写成已使用。

### 6.2 随机种子隔离

最初并发 1 使用正式种子 `42/43/44`，预热种子 `10001/10002/10003`。后来发现如果不同并发档位复用相同随机 Prompt，可能命中上一档实验残留的 Prefix Cache，因此修改为：

```python
concurrency_seed_offset = (concurrency - 1) * 1000
```

因此：

| 并发 | 正式种子 |
| ---: | --- |
| 1 | 42 / 43 / 44 |
| 2 | 1042 / 1043 / 1044 |
| 4 | 3042 / 3043 / 3044 |
| 8 | 7042 / 7043 / 7044 |
| 16 | 15042 / 15043 / 15044 |

这样同一实验可复现，不同并发不生成完全相同 Prompt；各档输入/输出 Token 长度仍一致，并发仍是主要控制变量。

### 6.3 tmux 后台执行

青海环境 SSH 经常断开，所以压测不直接依赖前台 SSH。每档建立独立 tmux 会话，例如 `vllm-c4`、`vllm-c8`，至少包含两个窗口：

- `port-forward`：维持 `28080:8000` 服务端口转发。
- `benchmark`：激活虚拟环境并运行压测。

不要进入、停止或复用不属于本项目的 `qwen3-tts-stage3` 会话。

tmux 只保证进程在 SSH 断开后继续运行，不会自动保证实验正确。仍要检查端口、健康接口、Git commit、GPU UUID、共存负载和结果文件。

### 6.4 指标公式

```text
请求吞吐 = 成功请求数 ÷ Benchmark duration

输出 Token 吞吐
  = 输出 Token 总数 ÷ Benchmark duration
  = 请求吞吐 × 单请求输出 Token 数

总 Token 吞吐
  = 请求吞吐 ×（单请求输入 Token 数 + 单请求输出 Token 数）

E2E ≈ TTFT +（输出 Token 数 - 1）× TPOT
```

单位检查非常重要：

```text
requests/s × tokens/request = tokens/s
```

“单请求耗时 × 输出 Token 数”不能得到吞吐，单位会变成 `s·token/request`，不是 `token/s`。

### 6.5 客户端并发与服务端排队

`--max-concurrency=N` 限制压测客户端最多同时发送 N 个未完成请求。超过 N 的待发请求可能先在客户端排队，尚未到达 vLLM，因此不一定出现在：

```promql
vllm:num_requests_waiting
```

要观察服务端 waiting，客户端需要制造超过引擎即时接纳能力的到达压力。当前服务 `max-num-seqs=8`，因此并发 8 预计可能看到 running 接近 8、waiting 仍接近 0；并发 16 更可能暴露服务端等待，但仍要以实测为准。

## 7. 当前压测结果

### 7.1 五档汇总

| 指标 | 并发 1 | 并发 2 | 并发 4 | 并发 8 | 并发 16 |
| --- | ---: | ---: | ---: | ---: | ---: |
| 请求吞吐（req/s） | 0.221521 | 0.398863 | 0.769253 | 1.396846 | 1.400668 |
| 输出吞吐（tok/s） | 28.354627 | 51.054496 | 98.464412 | 178.796299 | 179.285466 |
| 总吞吐（tok/s） | 85.063881 | 153.163487 | 295.393237 | 536.388898 | 537.856399 |
| Mean TTFT（ms） | 73.899712 | 134.906244 | 238.705613 | 452.407425 | 5471.729266 |
| P95 TTFT（ms） | 77.905028 | 168.884430 | 288.334959 | 524.926883 | 6015.514603 |
| Mean TPOT（ms） | 34.963472 | 38.413134 | 39.078182 | 39.898263 | 40.260742 |
| P95 TPOT（ms） | 35.062790 | 38.728518 | 40.163452 | 42.740084 | 42.703375 |
| Mean E2E（ms） | 4513.756706 | 5013.367304 | 5198.595218 | 5516.847473 | 10583.944401 |
| P95 E2E（ms） | 4528.058606 | 5025.727483 | 5215.563536 | 5554.009860 | 11095.316810 |
| 正式请求成功数 | 300/300 | 300/300 | 300/300 | 300/300 | 300/300 |

并发 1、2、4、8 的原始结果和报告均已提交到远端；并发 16 已完成并生成报告，尚待项目本人检查和提交。

### 7.2 并发 1 → 2

- 请求和输出 Token 吞吐提高约 80.1%。
- Mean TTFT 提高约 82.6%。
- Mean TPOT 提高约 9.9%。
- Mean E2E 提高约 11.1%。

结论：Continuous Batching 带来明显总吞吐收益，但单请求响应变慢。若更重视单请求延迟，并发 1 更好；若更重视系统总吞吐，并发 2 更好。最终选择仍要结合业务 SLO，而不是只看吞吐。

### 7.3 并发 2 → 4

- 请求和输出 Token 吞吐提高约 92.9%，比事前猜测的 80% 更接近翻倍。
- Mean TTFT 提高约 76.9%。
- Mean TPOT 只提高约 1.7%。
- Mean E2E 只提高约 3.7%。
- 实时采样主要看到 running=4、waiting=0、KV Cache 约 5%–7%。
- GPU-Util 约 96%–97%，功耗约 149 W，温度约 67–70°C。

为什么 GPU-Util 都很高，吞吐还能接近翻倍：并发 2 和 4 都能让 GPU 长时间忙碌，但并发 4 时，同一轮权重读取和内核执行可以推进更多序列，单位时间完成更多 Token。GPU-Util 不是“计算能力已使用百分比”。

为什么 TPOT 基本不变，总吞吐却增加：TPOT 是单个请求相邻输出 Token 的间隔；总体 Decode 调度能够同时推进约 4 个序列，所以单请求节奏变化小，而全系统每秒生成 Token 数显著增加。

网络波动不支持作为主要解释：客户端、Service 和 Pod 在同一环境内，流量很小，且三轮吞吐 CV 只有约 0.12%。

### 7.4 E2E 延迟拆解

并发 2 → 4：

```text
TTFT 增量 ≈ 238.71 - 134.91 ≈ 104 ms
TPOT 增量 ≈ 39.08 - 38.41 ≈ 0.67 ms/token
Decode 累积增量 ≈ 127 × 0.67 ≈ 85 ms
预计 E2E 增量 ≈ 104 + 85 ≈ 189 ms
实际 E2E 增量约 185 ms
```

两者接近，说明 TTFT、TPOT 和 E2E 数据在算术上自洽。TTFT 上升很多并不意味着 E2E 一定同比例上升，因为 128 Token 输出的大部分时间来自 127 个 TPOT 的累积，而 TPOT 只增加了很少。

### 7.5 并发 4 → 8

- 请求和输出 Token 吞吐提高约 81.58%，低于 c2→c4 的 92.9%，但绝对输出吞吐增量从约 47.41 增加到 80.33 tok/s。
- Mean TTFT 提高约 89.53%，是延迟指标中变化最明显的一项。
- Mean TPOT 只提高约 2.10%，Mean E2E 提高约 6.12%，P95 E2E 提高约 6.49%。
- 正式阶段主要看到 running=8、waiting=0；尾批 running 降到 4、1 属于请求逐步完成。
- KV Cache 峰值约 13.52%，GPU-Util 约 97%，功耗约 149–150 W，最高温度约 71°C。

吞吐尚未进入平台期，因此 c8 还不能判定为容量饱和点。基于 Qwen3-8B BF16 配置、16 tokens/block 和指标步长估算，本实例约有 1427 个 GPU KV blocks，即约 22832 Token slot、3.14 GiB KV Cache；c8 峰值约使用 193 blocks、3088 Token slot、0.424 GiB。该容量来自配置和指标反推，后续若能取得启动日志中的 block 数，应以直接记录交叉验证。

### 7.6 并发 8 → 16

- 请求和输出 Token 吞吐只提高约 0.27%，输出吞吐绝对值只增加约 0.49 tok/s，已基本进入当前配置的平台。
- Mean TTFT 提高约 1109.47%，P95 TTFT 提高约 1045.97%。
- Mean TPOT 只提高约 0.91%，P95 TPOT 反而微降约 0.09%，可视为基本不变。
- Mean E2E 提高约 91.85%，P95 E2E 提高约 99.77%。
- 稳定阶段观察到 `running=8、waiting=8`；KV Cache 峰值仍约 13.52%，GPU-Util 约 96%–97%。

吞吐持平的根因是 `max-num-seqs=8` 没有扩大实际运行批宽，不是单纯因为统计口径包含 waiting。c8 已能持续让约 8 条序列执行，c16 主要把排队位置从客户端移到服务端。waiting 请求尚未进入 Prefill，也通常没有完整占用 GPU KV Cache，因此 KV Cache 使用率没有随客户端并发翻倍。

P95 TPOT 仍约 42.70 ms，说明请求一旦进入 Decode，逐 Token 节奏基本不变；但第二波请求要等待第一波释放调度名额，P95 TTFT 增加约一个服务波次，最终使 P95 E2E 接近翻倍。

SLO v1 的首次前瞻性验证结果是：成功率和 P95 TPOT 通过，P95 TTFT `6015.515 ms` 与 P95 E2E `11.095 s` 失败。当前 `max-num-seqs=8` 配置下，吞吐拐点约在 c8，Short 场景推荐最大客户端并发为 8。

### 7.7 CV 的含义和边界

```text
CV = 标准差 ÷ 平均值 × 100%
```

CV 衡量多轮结果相对波动。低于约 1.1%说明：在这三轮、这一时段、这一硬件和这一固定负载下，结果重复性较好，报告的中位数不是某一轮偶然尖峰。

低 CV **不能**说明：

- 结果在其他日期、模型、GPU、输入长度或共享负载下仍相同。
- 指标测量没有系统偏差。
- 三轮样本足以给出严格统计置信区间。
- 当前参数已经最优。
- 服务已经或尚未达到业务 SLO。

简而言之：CV 更接近“精密度/重复性”，不是“准确性”和“普适性”。

### 7.8 当前饱和判断

c8→c16 吞吐只增加约 0.27%，并稳定观察到 `running=8、waiting=8`，说明当前 `max-num-seqs=8` 配置下的吞吐拐点约在 c8。c16 不是 KV Cache 饱和：KV Cache 峰值仍仅约 13.52%，且无请求失败；这里饱和的是配置允许的同时运行序列数，排队导致 TTFT 和 E2E 急剧恶化。

Short SLO v1 从 c16 起正式生效：请求成功率 ≥99%、P95 TTFT ≤600 ms、P95 TPOT ≤50 ms、P95 E2E ≤6 s；吞吐 CV ≤3%是重复性门槛，不属于服务体验 SLO。c16 的成功率和 P95 TPOT 通过，但 P95 TTFT 与 P95 E2E 失败。按同一阈值回看 c8 全部通过，因此当前测试范围内推荐最大客户端并发为 8。

这个结论只适用于当前参数。KV Cache 仍有明显余量，后续可通过把 `max-num-seqs` 提高到 16 的控制变量实验，判断更宽运行批次能否继续提升吞吐；在完成该实验前，不能声称已经找到单张 A10 的全局物理峰值。

## 8. 关键互动与实际执行记录

这一节按实际发生顺序记录重要操作和认知变化，不逐字复制聊天，而是保留每次互动中可复用的工程事实。

### 8.1 项目定位与仓库准备

1. 分析 AI Infra 秋招背景，决定个人项目重点从 GPU 资源调度转向 vLLM 推理数据面。
2. 在青海服务器盘点 Kubernetes、A10、HAMi、监控、本地模型和旧虚拟环境。
3. 确认仓库克隆到 `/home/qhadmin/boshi/vllm/vllm-infra-lab`。
4. 核对仓库是否关联 `boshilin123` GitHub 账户。
5. 因服务器无浏览器，放弃依赖网页自动打开的登录方式，改用专用 SSH 密钥和 Host 别名。
6. 遇到 `.git/config` 权限错误，修复仓库所有权；SSH 鉴权和 `git push --dry-run` 验证通过。

### 8.2 Phase 1 部署

1. Agent 编写带中文注释的 Namespace、Deployment、Service 和 smoke test。
2. 用户先查看 YAML，再执行 `kubectl apply --dry-run=client -k deploy/kubernetes`。
3. 用户单独正式创建 namespace，并用 `kubectl get namespace` 验证 Active。
4. 用户应用 Service。`get service` 看到 ClusterIP 只证明稳定访问入口已创建；`get endpoints` 当时为 `<none>`，说明还没有 Ready Pod 可接流量。
5. 用户应用 Deployment 并 watch Pod；首次需要拉取约 10.31 GB 的 vLLM 镜像，等待较久。
6. 首次容器启动报 `unrecognized arguments: /models/Qwen3-8B`。定位为 v0.9.1 镜像入口需要 `--model` 显式参数，修正清单并重新部署。
7. Pod Ready 后，Service Endpoint 指向 Pod IP。
8. 首次端口转发选择 18000，冒烟测试 `/health` 通过但 `/v1/models` 返回 BlueDot Admin HTML。原因不是 vLLM JSON 错误，而是 18000 已被公司产品占用。
9. 改用空闲的 28080，health、models 和 chat completions 全部通过。
10. 删除 Pod 验证自愈；Deployment 自动重建，约 3 分 49 秒恢复 Ready，Endpoint 和冒烟测试均通过。

### 8.3 Phase 3 监控的已完成部分

1. 手动 `curl /metrics` 验证 vLLM 自带指标接口。
2. 解释 `/metrics` 来自容器内同一个 API Server，不需要额外启动 Python 后台。
3. 检查集群 Prometheus CR 的 ServiceMonitor selector。
4. Agent 编写带中文注释的 ServiceMonitor；用户先执行 server dry-run，再正式 apply。
5. 用户转发 Prometheus 到 29090。
6. PromQL 查询 `up=1`，并查询到真实的 `vllm:num_requests_running` 时间序列，完成自动采集验收。

### 8.4 Phase 2 压测

1. 用户激活已有 `vllm-qwen3` 虚拟环境，先手动运行 5 请求、并发 1 的小型 `vllm bench serve`，验证工具链。
2. Agent 编写 `run_benchmark.py` 和中文说明；用户检查后提交 `2193547`。
3. 核对物理 GPU 3 与容器逻辑 GPU 0 的 UUID，解释为什么不硬编码 `CUDA_VISIBLE_DEVICES=3`。
4. 因 SSH 易断，改用 tmux 两窗口维持 port-forward 和 benchmark。
5. 完成并发 1 三轮基线；增加聚合脚本和报告。`git diff --check` 发现 CSV 使用 CRLF，修正为 LF 后再提交。
6. 发现不同并发可能复用随机 Prompt 和 Prefix Cache，修改种子按并发隔离，提交 `4f443cd`。
7. 完成并发 2 三轮实验，用户本人检查并提交 `6c5cf89`。
8. 完成并发 4 三轮实验；Agent 校验并生成报告，用户检查后提交为 `905e970`。
9. 用户完成 c8 事前回答；Agent 修正文档行尾空格并把校正后的假设记录为提交 `13b0343`。
10. c8 首次由 Agent 启动时未激活虚拟环境 PATH，runner 误用系统 vLLM，参数校验失败且没有发出请求；清理仅含 metadata 的无效目录后，使用 vLLM 0.9.1 客户端重新启动。
11. 完成并发 8 三轮实验，300/300 请求成功；Agent 监督 running/waiting、KV Cache 和 GPU 状态并生成汇总，用户检查后提交为 `000f8c3`。
12. 用户检查并提交 c16 事前假设为 `fc55fea`；随后由 Agent 建立 tmux、启动 c16 并监督三轮正式实验，稳定观察到 `running=8、waiting=8`、KV Cache 约 13.52%，300/300 请求成功。
13. c16 数据显示吞吐较 c8 仅增加 0.27%，但 P95 TTFT 和 P95 E2E 分别增至约 6.02 秒、11.10 秒；报告已经生成，等待用户检查和提交。

### 8.5 关键 Git 里程碑

| Commit | 内容 | 意义 |
| --- | --- | --- |
| `7fe78e1` | 初始化项目文档和目录 | 建立项目骨架 |
| `60f341b` | 完善结构和实验方案 | 明确 Phase 0–4 与控制变量法 |
| `4776829` | 增加集群隔离配置 | 建立独立 namespace 和单副本部署基础 |
| `1b51565` | 增加 Prometheus 抓取 | ServiceMonitor 进入版本控制 |
| `2193547` | 增加可复现 benchmark runner | 固定预热、请求数、元数据和结果目录 |
| `24c1a97` | 增加聚合脚本和并发 1 基线 | 建立第一份正式性能基线 |
| `1bd1edd` | 修正 benchmark CSV 换行 | 保证 Git diff 和跨平台文件格式稳定 |
| `4f443cd` | 隔离不同并发的随机种子 | 避免 Prefix Cache 污染控制变量 |
| `6c5cf89` | 增加并发 2 基线 | 形成第一组并发对照 |
| `905e970` | 增加并发 4 基线和项目总档案 | 固化 c4 数据并建立长期接力文档 |
| `13b0343` | 记录并发 8 事前假设 | 修复文档格式并在实验前冻结判断 |
| `000f8c3` | 增加并发 8 基线和 SLO v1 | 固化 c8 数据并为 c16 建立前瞻性延迟标准 |
| `fc55fea` | 记录并发 16 事前假设 | 在 c16 实验前冻结排队、吞吐、延迟和 KV Cache 判断 |
| `9cd6718` | 增加并发 16 饱和基线 | 固化当前 `max-num-seqs=8` 下的吞吐平台与排队代价 |

以上条目均已提交到 `origin/main`。当前工作进入 `max-num-seqs` 参数实验准备阶段。

## 9. 已遇到的故障与面试价值

| 现象 | 根因 | 修复 | 可讲的工程点 |
| --- | --- | --- | --- |
| GitHub device login 无法打开浏览器 | 服务器无 GUI/浏览器 | 使用专用 SSH key 和 Host 别名 | 服务器 Git 认证与最小权限 |
| `.git/config: Permission denied` | `sudo` 导致文件所有权混乱 | 恢复普通用户所有权，禁止 `sudo git` | Linux 权限与仓库安全 |
| Pod 长时间 ContainerCreating | 首次拉取 10 GB 级镜像 | 查 Events/镜像进度并等待，后续利用缓存 | 镜像与模型权重的区别、冷启动拆解 |
| vLLM 参数无法识别 | v0.9.1 API Server 要求显式 `--model` | 修正 Deployment args | 固定版本并根据真实入口校验参数 |
| `/v1/models` 返回 HTML | 误用了公司产品端口 18000 | 换成已确认空闲的 28080 | 先看响应体再定位，不把所有失败归因于模型 |
| Chat 回复含 `<think>` | Qwen3 默认推理输出行为 | 冒烟目标改为验证有效生成，不强求精确文本 | 健康验收应验证协议与功能，不依赖脆弱文案 |
| 容器显示 GPU 0 | Device Plugin 设备重映射 | 用 GPU UUID 交叉核对 | 物理编号、逻辑编号与调度器职责 |
| 空闲显存仍约 19.8 GiB | 权重、KV Cache、CUDA Graph 等常驻 | 视为服务预分配设计，不误判内存泄漏 | 显存容量与 GPU 计算利用率不同 |
| CSV diff 出现 `^M` | Python CSV 默认 CRLF | 显式设置 LF 并用 `git diff --check` | 可复现实验也包括稳定文件格式 |
| 跨并发 Prompt 可能重复 | 固定种子只按轮次变化 | 加入并发种子偏移 | Prefix Cache 是控制变量污染源 |
| c8 首次启动参数不兼容 | 只直接调用虚拟环境 Python，runner 的 PATH 找到系统 vLLM | 显式激活 venv 后重跑，确认客户端为 0.9.1 | Python 解释器正确不代表子进程可执行文件也正确 |

面试时不要只说“最后跑通了”。更有价值的表达结构是：**现象 → 收集什么证据 → 排除什么 → 根因 → 修复 → 如何防止复发**。

## 10. 小白问答与认知校正

### 10.1 Service 和 Endpoints 有什么区别

- Service 是稳定的访问入口、虚拟 IP、端口和标签选择规则。
- Endpoints 是当前真正可接收流量的后端 Pod IP 列表。
- Service 存在但 Endpoints 为 `<none>`，通常意味着 Pod 未 Ready、selector 不匹配或目标 Pod 不存在。

### 10.2 为什么本地有模型还要拉 vLLM 镜像

模型权重相当于“数据”，镜像相当于“运行程序和依赖”。只有模型文件，没有 vLLM、PyTorch、CUDA 用户态依赖和 API Server，Kubernetes 容器无法提供服务。

### 10.3 为什么没请求仍占大量显存

Serving 系统为了避免每次请求重新加载 16 GiB 权重，并为了快速接收请求，会常驻模型并预分配 KV Cache 等空间。空闲时“显存高、GPU-Util 低”可以同时成立。

### 10.4 为什么不指定物理 GPU 3

Kubernetes 用 `nvidia.com/gpu: 1` 请求一张卡，由 Device Plugin 分配设备并注入容器。容器只看到所分配的逻辑 GPU 0；硬编码宿主机编号会与调度器冲突。若确实要稳定选择某块硬件，应使用受支持的调度标签/设备策略，而不是在容器里写宿主机编号。

### 10.5 为什么 E2E 没有跟 TTFT 一样上涨 80%

E2E 包含一次 TTFT 和约 127 次 TPOT。TTFT 虽然相对涨幅大，但绝对增量只有约百毫秒；Decode 部分占总耗时主体，而 TPOT 增幅较小，因此 E2E 只小幅增加。

### 10.6 怎样判断系统饱和

不能只看一个指标：

- 吞吐边际收益趋近 0。
- waiting requests 持续增加。
- TTFT/P95/P99 急剧恶化。
- KV Cache 接近容量边界。
- 错误、抢占、OOM 或超时出现。
- GPU 指标显示资源瓶颈，但要避免只用 GPU-Util 下结论。

此外还要区分“物理容量饱和”和“已经违反业务延迟 SLO”。

### 10.7 已经形成的答题技巧

1. 先写公式并带单位，不凭感觉乘除。
2. 相对涨幅和绝对增量都要看。
3. 不把上一段曲线的百分比线性外推到下一档并发。
4. 区分客户端排队和服务端 waiting。
5. 区分单请求 TPOT 与全系统 Token 吞吐。
6. 区分显存占用、GPU 忙碌时间和有效吞吐。
7. 每个结论都补一句“它不能说明什么”。

## 11. 后续每轮应继续提的问题

### 11.1 并发 8 之前

请先书面回答：

1. 并发从 4 到 8，请求吞吐预计提高多少？为什么不能直接假设翻倍？
2. `max-num-seqs=8` 对 running、waiting 和吞吐曲线可能有什么影响？
3. 如果 GPU-Util 仍约 97%，用什么证据判断批处理效率是否继续提高？
4. 哪一个指标最可能最先触碰业务 SLO：TTFT、TPOT 还是 E2E？

### 11.2 并发 8 结束后（已完成）

1. 用 `requests/s × 128` 复算输出 Token 吞吐，误差是多少？
2. 用 `TTFT + 127 × TPOT` 复算 E2E，是否自洽？
3. c4→c8 的吞吐边际收益是否低于 c2→c4？
4. running 是否达到 8，waiting 是否出现？客户端是否可能先排队？
5. 三轮 CV 是否仍低？若变高，查看共享负载、温度、功耗和请求错误。
6. 当前是容量饱和、SLO 饱和，还是仍未饱和？证据分别是什么？

复盘结论：输出吞吐复算误差仅来自小数截断；E2E 公式误差约 2.64 ms。c4→c8 相对吞吐增益下降，但绝对增量增加，尚未出现容量平台。running 达到 8、waiting 为 0，三轮主要指标 CV 很低。容量尚未饱和；旧实验没有预先定义 SLO，因此不能事后宣称 SLO 是否饱和。

### 11.3 并发 16 之前

请项目本人先书面回答：

1. c16 时客户端最多有 16 个未完成请求，而 `max-num-seqs=8`，预计 running 和 waiting 各是多少？
2. 吞吐相对 c8 还会提高多少？为什么可能明显低于并发翻倍？
3. TTFT、TPOT 和 P95 E2E 中，哪些最可能突破 SLO v1？
4. KV Cache 峰值会接近翻倍，还是仍与 c8 接近？为什么？

实验执行者原始回答：预计 running=8、waiting=8，并询问额外请求是否在 Prefill block 上等待；预计吞吐提高 20%–40%；预计三个延迟 SLO 都会突破；预计 KV Cache 因 waiting 存在而仍接近 c8。

校正后的可检验假设：额外请求位于调度器 waiting 队列，尚未进入 Prefill；c8 已基本填满 8 条运行序列，因此 c16 吞吐预计持平或仅提高约 0%–10%，而不是 20%–40%；排队最可能使 P95 TTFT 和 P95 E2E 越过 SLO，P95 TPOT 预计仍接近 c8 并可能继续达标；只有约 8 条序列占用运行时 KV Cache，因此峰值预计仍约 13%–15%。

### 11.4 并发 16 结束后（已完成）

1. 为什么 c16 相比 c8 的吞吐基本持平？
2. 为什么 c16 的 KV Cache 峰值仍与 c8 接近？
3. 为什么 TPOT 基本不变，而 E2E 接近翻倍？
4. 若在 c8 和 c16 中选择当前 Short 场景运行点，应选哪一个？

实验执行者原始回答：吞吐持平是因为 waiting 请求被计算进去；KV Cache 保持与 c8 一样；TPOT 只与单个请求的 Decode 阶段有关，而 E2E 把等待的 8 个请求算进去所以正好约翻倍；下一档选择 c16，因为 KV Cache 仍富足。

校正后的理解：吞吐持平的直接原因是 `max-num-seqs=8` 使实际运行批宽没有增加，统计覆盖 waiting 只是完整反映了排队结果；TPOT 不包含调度前的完整等待时间，因此保持稳定，而 TTFT 和 E2E 会包含等待。KV Cache 富余说明显存容量不是当前瓶颈，但 c16 已违反 P95 TTFT 和 P95 E2E SLO，因此当前推荐并发是 8，而不是 16。

若只把 `max-num-seqs` 提高到 16，预计 running 上限提高、waiting 减少，短请求 KV Cache 峰值可能从约 13.5%提高到约 27%；随后瓶颈更可能转向计算吞吐和更宽批次的调度开销，TPOT 也可能恶化。该判断需要控制变量实验验证，不能仅凭 KV Cache 余量下结论。

### 11.5 `max-num-seqs=16` 参数实验之前

固定客户端并发 16、256/128 Token、Qwen3-8B BF16、同一张 A10、`max-model-len=4096` 和 `gpu-memory-utilization=0.85`，只把服务端 `max-num-seqs` 从 8 改成 16。请项目本人先书面回答：

1. 稳定阶段预计 running、waiting 各是多少？为什么？
2. 输出吞吐相对 `c16-mns8` 的 179.29 tok/s 预计提高多少？不要只回答“翻倍”，请给出一个区间及依据。
3. P95 TTFT、P95 TPOT、P95 E2E 分别可能改善还是恶化？哪些指标有机会重新满足 SLO v1？
4. KV Cache 峰值预计是多少？若实测明显低于或高于约 27%，分别可能说明什么？
5. 如果吞吐提高但 P95 TPOT 或 E2E 仍违反 SLO，应如何在 `mns8` 与 `mns16` 之间选择？

实验执行者原始回答：预计 `running=0、waiting=0`，理由是客户端并发和服务端并发上限都是 16；预计输出吞吐提高 80%–90%；预计 TTFT 和 E2E 改善并满足 SLO；预计 KV Cache 约 27%，认为高于该值说明性能或批处理瓶颈、低于则说明批处理效果较好；若吞吐提高但延迟仍违反 SLO，选择 mns8。

校正后的可检验假设：

1. 稳定阶段应为 `running≈16、waiting≈0`。客户端有 16 个未完成请求，服务端最多允许 16 条序列运行；只有轮次尾部请求逐渐完成时 running 才会下降。
2. 不预设 80%–90%的近翻倍收益。mns8 已使 GPU-Util 约 96%–97%，mns16 虽扩大批宽，但单条序列 TPOT 很可能因共享计算资源而上升。暂以输出吞吐提高 **20%–60%**作为宽范围假设，即约 **215–287 tok/s**，最终以实测为准。
3. P95 TTFT 会因服务端 waiting 减少而比 mns8 的 6015 ms 显著改善，但 16 条序列同时 Prefill 仍可能使它高于 600 ms，因此不预设一定通过 TTFT SLO。P95 TPOT 可能高于 mns8 的 42.70 ms，并存在越过 50 ms 的风险；P95 E2E 同时受 TTFT 改善和 TPOT 累积恶化影响，可能下降，但也不预设一定低于 6 秒。
4. 若 16 条请求完整并行且长度分布相同，KV Cache 峰值初步预计约为 mns8 的两倍，即 **25%–30%**。明显低于该范围可能意味着采样未捕获峰值、请求没有同时达到最长状态、实际 running 未到 16 或发生调度/抢占；明显高于则应检查 block 对齐、Prefix Cache 残留、额外序列或指标口径。KV Cache 百分比表示显存块占用，不直接等价于计算性能或批处理效率。
5. 若 c16 流量下 mns16 吞吐提高但仍违反 SLO，mns8 也不能作为该负载的合格方案，因为它已经在 c16 下违反 TTFT/E2E SLO。应限制单副本入口并发到约 8，或通过多副本扩容分担 16 并发；只有在业务明确接受更宽松延迟目标时，才可根据吞吐优先考虑 mns16。

## 12. 当前阶段与下一步

### 12.1 阶段状态

| 阶段 | 状态 | 已完成 | 尚缺 |
| --- | --- | --- | --- |
| Phase 0 环境与安全边界 | 已完成 | 软硬件、模型、共享工作负载、Git 认证盘点 | 每次实验前刷新动态资源快照 |
| Phase 1 单副本服务 | 已完成 | Deployment/Service/探针、API、删除 Pod 自愈 | 后续将冷启动指标自动化 |
| Phase 2 基准与参数实验 | 进行中 | 工具链、聚合、Short 并发 1/2/4/8/16 扫描 | 执行 `max-num-seqs=16`、长输入等参数实验 |
| Phase 3 可观测性 | 进行中 | `/metrics`、ServiceMonitor、Prometheus 查询 | Grafana Dashboard、统一时间线、故障场景 |
| Phase 4 多副本与弹性 | 计划中 | 架构和指标方向 | 第二张可用 GPU、共享模型、Adapter/KEDA、HPA 与突发流量实验 |

Phase 2 和 Phase 3 可以交叉推进：当前 ServiceMonitor 已完成，但 Dashboard 尚未完成；当前并发扫描可以继续使用 PromQL 和 `nvidia-smi` 观测。

### 12.2 紧接着要做什么

第一步，补全参数实验的可复现记录：benchmark runner 必须把 `max-num-seqs`、`max-model-len` 和 `gpu-memory-utilization` 写入 metadata，并在实验目录名中标识 `mns16`。由项目本人检查并提交该工具改动及事前假设。

第二步，在修改集群前回答 11.5 的五个问题，冻结对吞吐、延迟、waiting 和 KV Cache 的预测。只改变 `max-num-seqs`，其他服务端与负载变量保持不变。

第三步，由项目本人先把 `deploy/kubernetes/deployment.yaml` 中 `--max-num-seqs` 从 `8` 改为 `16`，执行 client/server dry-run、检查 diff 并提交配置，再正式 apply。Deployment 使用 Recreate，应用后旧 Pod 会退出并重新加载模型，期间服务暂时不可用。

第四步，等待新 Pod Ready 后重新核对 Pod args、Endpoint、GPU UUID 和共享负载，再建立端口转发并运行 `c16-mns16` 三轮实验。实验完成后是否保留 mns16 作为部署默认值，要依据 SLO 和吞吐实测决定，不能因为 KV Cache 有余量就提前决定。

事前容量估算是：若 16 条短请求同时运行，KV Cache 峰值可能约为当前的两倍，即约 27%，仍低于容量边界；但吞吐不会因此必然翻倍，TPOT 还可能因批次更宽而上升。完成参数实验后，再进入长输入场景，避免同时改变请求长度和服务端参数。

## 13. 当前可用于面试的表述边界

### 13.1 已经有证据支撑

- 在 Kubernetes 1.28 双节点 GPU 集群上，以固定 vLLM 0.9.1 镜像部署 Qwen3-8B BF16 单卡服务，配置模型只读挂载、GPU 资源声明和三类健康探针，并验证 Pod 删除后的自动恢复。
- 将 vLLM `/metrics` 通过 ServiceMonitor 接入既有 Prometheus，验证 target 存活和真实请求指标持续入库。
- 构建固定 Token 长度、预热、三轮重复、种子隔离和 JSON/CSV 汇总的可复现压测流程；在单张 A10、256/128 Token、`max-num-seqs=8` 场景下，并发 1→8 的输出吞吐从 28.35 提高到 178.80 tok/s；继续提高到 c16 时吞吐仅为 179.29 tok/s，而 P95 E2E 增至 11.10 s，定位出当前配置的平台与排队代价。五档实验均为 300/300 请求成功。

第三条的 c1–c16 原始数据和报告均已提交，可作为已固化的远端证据；面试前仍应从原始 JSON 独立复算一次。

### 13.2 目前不能声称

- 不能声称已经完成 HPA、自定义指标弹性或多副本路由。
- 不能声称已经找到全局最优参数或单卡饱和点。
- 不能把 vLLM 自带 Continuous Batching、KV Cache 说成自己实现。
- 不能把当前结果推广到其他模型、长上下文、量化模型或其他 GPU。
- 不能声称完成整卡与 HAMi/vGPU 对比。
- 不能为了故事连贯而倒填项目时间；项目日期必须与真实实施时间一致。

### 13.3 面试回答模板

回答每一个性能结论时使用：

```text
实验问题是什么
→ 固定了哪些变量
→ 改变了哪个变量
→ 原始数据和重复性如何
→ 结果是多少
→ 用什么机制解释
→ 有哪些限制
→ 下一步如何验证
```

这比只背“吞吐提升 X%”更能体现 AI Infra 工程能力。

## 14. 文档维护规则

以后每完成一个里程碑，在本文同步更新：

1. 更新时间和最新 Git commit。
2. 阶段状态表。
3. 新增或变化的环境事实；动态信息必须注明观测时间。
4. 实际执行记录和故障链路。
5. 实验前假设、三轮汇总、CV、Prometheus/GPU 证据。
6. 本人对复盘问题的原始回答，以及校正后的理解。
7. 哪些新结论可以进入简历，哪些仍然不能。

结果目录必须保留原始 JSON、metadata、逐轮 CSV、汇总文件和实验 README。不要只保存截图或手工抄写的最终数字。
