# vLLM Infra Lab 项目总档案

> 更新时间：2026-09-08（Asia/Shanghai）
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

### 2.3 共享公司环境的硬安全边界

- 本个人项目在任何时刻最多使用两张 GPU，Phase 0–3 默认只使用当前单张实验 GPU。
- 不停止、迁移或修改任何公司已有服务；写操作限定在本项目仓库和 `vllm-infra-lab` namespace。
- 已知 GPU 0 上存在公司 Qwen3-TTS 进程，绝不停止或抢占。第二副本不能仅凭“其他卡看起来空闲”就启动，必须先确认 Kubernetes 的设备分配不会落到该卡。
- Phase 4 最多使用两个副本、两张 GPU，`maxReplicas` 不得超过 2；只在短时受控实验窗口运行，结束后恢复单副本。
- 如果无法用受支持的调度/隔离方式保证第二张 GPU 安全，则停止双副本实施，把它如实记录为共享环境约束，不用冒险换取项目结果。

资源上限是安全边界，不是必须把两张卡都用满的目标。项目仍以可复现的 vLLM Serving 性能、可观测性与弹性证据为主线。

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

截至 Phase 4 least-inflight 路由核心实现前，远端最新提交为：

```text
3643d27 analysis: add offline autoscaling policy replay
```

Phase 2、Phase 3、Phase 4 双副本对照和弹性状态机离线回放均已推送。当前只在仓库中实现 least-inflight 路由核心，尚未再次扩容、访问或修改集群。

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
- 并发扫描基线使用 `--max-model-len 4096`、`--max-num-seqs 8`、`--gpu-memory-utilization 0.85`。
- `max-num-seqs` 参数实验只把该值改为 16；当前已应用并由新 Pod 启动日志确认生效。
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

Phase 3 当时尚未确认 Prometheus Adapter、KEDA 或自定义指标 API；Phase 4 后续只读审计已确认 resource/custom/external metrics API 与 KEDA 均不存在。因此“使用 waiting requests 驱动 HPA/KEDA”仍不能写成已完成，也不为个人项目安装公司集群级组件。

### 5.4 Phase 3 指标发现

2026-09-07 通过 `insight-agent-kube-prometh-prometheus:9090` 的本地端口转发重新探测 Prometheus：

- Prometheus 版本为 2.53.5；本项目 target `up=1`。
- 实际发现 68 个 `vllm:*` 指标，running、waiting、KV Cache、Token counter、queue/TTFT/TPOT/E2E histogram 均存在。
- 实际发现 28 个 `DCGM_FI_DEV_*` 指标；GPU UUID、物理编号、节点和 vLLM Pod 标签能够关联。
- 同一 GPU 同时被官方 `nvidia-dcgm-exporter` 和 `hami-webui-dcgm-exporter` 采集。查询固定 `job="nvidia-dcgm-exporter"` 和 GPU UUID，避免同一设备双计。
- 服务器设置了 HTTP(S) 代理；访问 `127.0.0.1` 端口转发必须显式绕过代理，否则请求会超时。
- 对过去 48 小时执行 range query 时，本项目现存样本只覆盖最近约 4 小时；昨天的 benchmark 时间线已经不在 TSDB 中。因此统一时间线必须在新代表性负载结束后立即导出，不能依赖长期保留。

13 条共享 PromQL 已在空闲状态逐条验证语法和聚合唯一性。running、waiting、KV Cache、Token throughput 与四项 DCGM 查询均返回单一序列；延迟 histogram 在空闲 1 分钟窗口返回 `NaN`是没有新请求的预期结果，不是查询失败。

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

要观察服务端 waiting，客户端需要制造超过引擎即时接纳能力的到达压力。并发扫描基线使用 `max-num-seqs=8`，因此并发 8 看到 running 接近 8、waiting 接近 0；并发 16 则实测出现 `running=8、waiting=8`。

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

吞吐尚未进入平台期，因此 c8 还不能判定为容量饱和点。基于 Qwen3-8B BF16 配置、16 tokens/block 和指标步长曾反推本实例约有 1427 个 GPU KV blocks，即约 22832 Token slot、3.14 GiB KV Cache；c8 峰值约使用 193 blocks、3088 Token slot、0.424 GiB。后续 mns16 新 Pod 的启动日志直接报告 `1427 blocks`、`22,832 tokens` 和 `3.14 GiB`，验证了这项反推。

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

这个结论只适用于 mns8。后续 mns16 控制变量实验确认更宽运行批次还能继续提升吞吐，因此 mns8 平台不是单张 A10 的全局物理峰值；mns16 仍有 KV Cache 余量且尚未扫描更多参数，同样不能声称是全局峰值。

### 7.9 `max-num-seqs` 8 → 16

固定客户端并发 16 和其他服务端/负载变量，只提高服务端运行序列上限：

| 指标 | c16-mns8 | c16-mns16 | 相对变化 |
| --- | ---: | ---: | ---: |
| 输出吞吐（tok/s） | 179.285466 | 305.434290 | +70.36% |
| P95 TTFT（ms） | 6015.514603 | 976.837920 | -83.76% |
| P95 TPOT（ms） | 42.703375 | 46.768354 | +9.52% |
| P95 E2E（ms） | 11095.316810 | 6152.403065 | -44.55% |
| 正式请求成功数 | 300/300 | 300/300 | 不变 |

mns16 正式阶段达到 `running=16、waiting=0`，KV Cache 采样峰值约 24.18%。吞吐提高 70.36%说明 mns8 的平台主要受同时运行序列上限约束；吞吐没有翻倍，同时 P95 TPOT 上升 9.52%，说明更宽批次增加了单请求 Decode 的资源竞争。

TTFT 虽显著改善但仍未通过 600 ms。启动日志显示 Chunked Prefill 的 `max_num_batched_tokens=2048`；16 个 256-token Prompt 合计 4096 tokens，需要分块推进，因此 `waiting=0`不等于 Prefill 没有调度延迟。P95 E2E 降至 6.152 秒，距 6 秒 SLO 仍高约 152 ms。

三轮均为 100/100 请求成功，吞吐 CV 为 0.308%；未观察到 OOM、CUDA error 或 preemption。mns16 提升了单卡吞吐，但尚未同时满足 TTFT/E2E SLO。

### 7.10 Prefill / Decode 单变量对照

为避免 Pod 重建后物理 GPU 从 3 变成 1 所造成的硬件与时间窗口混淆，先在当前 GPU 上重跑 256/128 c8-mns8 校准，再依次执行三种负载。四组均固定 Qwen3-8B BF16、单张 A10、客户端并发 8、服务端 `max-num-seqs=8`、`max-model-len=4096` 和 `gpu-memory-utilization=0.85`。

| 场景 | 输入/输出 | 输出吞吐 tok/s | P95 TTFT ms | P95 TPOT ms | P95 E2E ms | 成功请求 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Short 校准 | 256/128 | 180.649355 | 486.414863 | 41.948177 | 5496.814455 | 300/300 |
| Prefill 对照 | 1024/128 | 139.004387 | 1464.013822 | 53.146928 | 7354.942444 | 180/180 |
| Decode 对照 | 256/256 | 182.642375 | 525.220729 | 41.041296 | 10593.704943 | 180/180 |
| 组合长上下文 | 1024/256 | 158.051827 | 1426.444415 | 47.145184 | 12788.776909 | 180/180 |

只增加 Prompt 时，输出吞吐下降 23.05%，P95 TTFT 上升 200.98%，P95 TPOT 也上升 26.70%。首波 `8 × 1024=8192` Prompt tokens 高于 `max_num_batched_tokens=2048`，Chunked Prefill 需要分块推进；即使客户端并发等于 `max-num-seqs`，token budget 仍可能使请求短暂出现在 waiting 状态。

只增加输出时，P95 TPOT 从 41.948 ms 变为 41.041 ms，基本不变；P95 E2E 增加 5096.890 ms，与事前估算的 `128 × 40 ms≈5.1 s`几乎一致。请求吞吐下降 49.45%，但输出吞吐小幅增加 1.10%，说明更长输出主要延长单请求占用时间，并未显著改变稳定 Decode 的生成 Token 速率。

组合长上下文相对 Short 的输出吞吐下降 12.51%，P95 TTFT、TPOT、E2E 分别上升 193.26%、12.39%、132.66%。其 KV Cache 采样峰值 44.36%，接近 `8 × (1024+256) / 22832≈44.85%` 的满长度简单上界，未触及 KV 容量上限。

四种负载均无请求失败。三种长负载按实验前冻结的 Long SLO v1（成功率 ≥99%、P95 TTFT ≤1500 ms、P95 TPOT ≤55 ms、P95 E2E ≤13 s）全部通过；但 Prefill 场景的 P95 TTFT 仅剩约 36 ms 余量，组合场景的 P95 E2E 仅剩约 211 ms，且组合场景 P99 E2E 为 13033.939 ms。P95 判定通过不等于更严格尾延迟或更长上下文也能通过。

输出吞吐只统计生成 Token，Prompt 变长会因 Prefill 占用 GPU 时间而使它下降。总 Token 吞吐同时统计输入和输出，例如 Prefill 对照达到 1251.039 tok/s，不能把这个更大的数解释为 Decode 生成能力提高。类似地，Prefill 对照到组合场景的输出吞吐增加 13.70%，主要是固定 Prefill 成本被更多输出 Token 摊薄，而非 TPOT 必然改善。

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
13. c16 数据显示吞吐较 c8 仅增加 0.27%，但 P95 TTFT 和 P95 E2E 分别增至约 6.02 秒、11.10 秒；用户检查并提交结果为 `9cd6718`。
14. 为参数实验补充服务端引擎参数 metadata 和 `mns` 目录标识，记录用户事前回答与校正假设；用户检查并提交为 `d9e4a0e`。
15. 用户完成 mns16 Deployment 的 client/server dry-run，提交并推送为 `842b5af`，随后正式 apply。新 Pod `qwen3-8b-77cf6cb556-76wbm` Ready、0 次重启，Endpoint 为 `10.244.64.213:8000`；启动参数确认 `max_num_seqs=16`，GPU UUID 与基线一致。
16. mns16 启动日志直接报告可用 KV Cache `3.14 GiB`、`22,832 tokens`、`1427 blocks`，与此前基于指标步长的估算完全一致；模型加载、torch.compile、CUDA Graph 和 API Server 启动均成功，未发现 OOM/CUDA 错误。
17. 用户提交 mns16 部署验收记录为 `ca85714`；Agent 随后建立端口转发并执行 `c16-mns16` 三轮正式实验，300/300 请求成功，稳定观察到 `running=16、waiting=0`，KV Cache 采样峰值约 24.18%。
18. mns16 将输出吞吐提高到 305.43 tok/s，但 P95 TTFT 976.84 ms、P95 E2E 6.152 s 仍违反 SLO；用户据此选择每副本限制约 8 并发、以两个副本分担总并发 16 作为后续架构方向。
19. 用户检查并提交 mns16 原始结果和报告为 `5776be0`；随后重新确认项目仍处于 Phase 2，决定先恢复单副本 mns8、完成长输入与可观测性交付，再进入最多两副本的 Phase 4。
20. 用户提交恢复清单和共享环境安全边界为 `cac1a7a` 并正式 apply；新 Pod `qwen3-8b-8fc88c5c9-5bmsd` Ready、0 次重启，Endpoint 指向 `10.244.64.214:8000`，启动参数确认 `max_num_seqs=8`，KV Cache 容量仍为 3.14 GiB、22,832 tokens、1427 blocks。
21. 新 Pod 被 Device Plugin 分配到宿主机物理 GPU 1（`GPU-5e5590e5-51de-1c1c-6c72-4cbe1477e116`），不再是历史基线使用的物理 GPU 3。只读审计确认 GPU 0 上的公司 Qwen3-TTS 进程占用约 5.9 GiB，GPU 1 上本项目 vLLM 占用约 19.8 GiB，两者没有重叠；同时 `default/magic-pdf-gpu-api` 仍声明一张整卡，因此不能把其余空闲卡直接认定为可用于个人项目。
22. 用户完成 Prefill/Decode 事前回答，Agent 校正 TTFT 方向、E2E 估算和 KV Cache 上界解释，定义 Long SLO v1；用户检查并提交实验设计为 `da604fe`。
23. 在同一 Pod、物理 GPU 1 和相邻时间窗口完成 Short 校准、Prefill、Decode、组合长上下文四组实验，共 840/840 个正式请求成功。
24. 单变量结果验证：Prompt 从 256 增至 1024 使 P95 TTFT 上升约 201%；输出从 128 增至 256 使 P95 E2E 增加约 5.097 秒而 P95 TPOT 基本不变；组合场景 KV Cache 峰值约 44.36%。
25. 实验结束后 GPU 回到空闲、vLLM metrics 仍正常返回；Agent 只关闭本项目的 benchmark、monitor 和 port-forward tmux，会话列表确认公司 `qwen3-tts-stage3` 未受影响。
26. 最终审计确认 Pod `Ready=true`、Running、0 次重启，近两小时严格系统故障、HTTP 4xx/5xx 和 namespace Warning Event 均为 0。宽泛搜索 `error|exception|traceback` 曾命中数百条随机 Prompt 文本，并非服务故障；同时发现正确 Pod 标签是 `app.kubernetes.io/name=qwen3-8b`，旧 selector `app=qwen3-8b` 会返回空表。
27. 用户检查并提交四组结果为 `c3524fb`；Agent 随后增加纯 Python 标准库 SVG 生成器，直接读取聚合中位数并验证场景身份，生成 Short 并发扫描、mns8/16 参数对照和 Prefill/Decode 四负载对照三张图。连续两次生成的 SHA256 一致，SVG 通过 XML 解析并完成 PNG 转换后的视觉检查。
28. Phase 3 统一时间线捕获 `running=8、waiting=8`、KV Cache 峰值 13.525%与 GPU-Util 峰值 97%；兼容 Grafana 9.3/schema 37 的 Dashboard、PromQL 和报告先后提交为 `49d0434`、`7be526b`。
29. Phase 4 先通过安全审计和静态覆盖层短时扩至两个 A10 副本；普通 Service 三轮吞吐中位数 332.912 tok/s，但瞬时 waiting 峰值 6/4，P95 TTFT/E2E 仍为 5469/10742 ms。结果提交为 `3265e24`，随后恢复单副本。
30. 确定性双目标工具与 8/8 事前标准提交为 `9d0f499`。正式实验让两个 Pod 各自以 c8 处理相同请求，三轮 300/300 成功；两侧全流程 counter 增量均为 180、Peak waiting 均为 0。
31. 确定性分流输出吞吐中位数为 334.824 tok/s，P95 TTFT/TPOT/E2E 为 524.631/42.706/5543.586 ms，预注册门槛全部通过。实验后 Deployment 恢复 `1/1/1/1`，GPU 2释放到 1 MiB，公司 GPU 0保持不变。

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
| `d9e4a0e` | 准备 `max-num-seqs` 参数实验 | 记录服务端参数、实验标识和事前假设 |
| `842b5af` | 将 `max-num-seqs` 提高到 16 | 固化参数实验 Deployment 配置 |
| `ca85714` | 记录 mns16 部署验收 | 固化精确 KV Cache 容量和新 Pod 启动证据 |
| `5776be0` | 增加 mns16 参数实验结果 | 固化 70.36%吞吐收益和仍未通过 TTFT/E2E SLO 的边界 |
| `cac1a7a` | 恢复单副本 mns8 基线 | 固化 Phase 0–3 单卡默认值和最多两卡的共享环境安全边界 |
| `da604fe` | 准备 Prefill/Decode 对照 | 固化四场景、独立种子、事前假设和 Long SLO v1 |
| `c3524fb` | 增加 Prefill/Decode 正式结果 | 固化 840/840 成功请求、Long SLO 结果和单变量结论 |
| `6f8cad8` | 增加可复现 Phase 2 图表 | 从聚合数据确定性生成三张性能 SVG |
| `49d0434` | 增加统一 serving/GPU 时间线 | 固化 Phase 3 运行时排队、KV 与 GPU 证据 |
| `7be526b` | 对齐共享 Grafana 版本 | 验证 schema 37、数据源和只读安全边界 |
| `2b9ecf6` | 准备静态双副本实验 | 固化最多两卡的覆盖层与集群内客户端 |
| `3265e24` | 增加静态双副本结果 | 证明容量扩展并发现连接级瞬时偏斜 |
| `9d0f499` | 准备确定性双副本路由对照 | 固化双目标 runner、合并口径与验收标准 |
| `394d3f7` | 增加确定性双副本路由结果 | 固化 8/8 分流、Short SLO 全部通过与安全回退证据 |
| `3643d27` | 增加弹性策略离线回放 | 固化 155 秒冷启动对短突发的限制和 1→2→1 状态机 |

以上条目均已提交到 `origin/main`。当前工作区从路由与弹性控制环的离线设计开始。

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
| 错误日志搜索出现数百条命中 | 随机 Prompt 被 INFO 日志原样记录，文本自然包含 Error/Traceback 等词 | 排除 `Received request`，按日志级别、明确故障短语和 HTTP 状态码分类 | 关键词命中不等于异常，日志审计要识别字段语义与日志级别 |
| 带 `app=qwen3-8b` 的 Pod 查询为空 | 清单使用标准标签 `app.kubernetes.io/name`，并无 `app` 标签 | 先不加 selector 查看真实 labels，再使用标准标签 | 空查询结果不等于工作负载消失，应先验证筛选条件 |

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

### 11.6 `c16-mns16` 参数实验结束后（已完成）

实验执行者原始回答：吞吐未翻倍可能因为批处理效率没有完全跑满；TTFT 从 6000 多毫秒降到 900 多毫秒已经非常可观；TPOT 上升是因为并发 8→16 后处理内容更多；KV Cache 低于 27%得益于 PagedAttention；最终选择单副本限制到并发 8、通过两个副本承接总并发 16，因为部分指标仍超过 SLO，回退 mns8 又不能增加高并发容量。

校正后的理解：

1. 吞吐未翻倍可以由 P95 TPOT 上升约 9.52%直接量化：更宽批次推进更多序列，但单条序列会因共享计算与内存带宽而变慢，所以吞吐扩展不是线性的。
2. TTFT 的绝对改善很大，但 SLO 仍按 600 ms 判断。`waiting=0`只表示请求已进入调度；16 个 Prompt 合计 4096 tokens，超过 `max_num_batched_tokens=2048`，Chunked Prefill 和资源竞争仍产生首 Token 延迟。
3. PagedAttention 支持按 block 动态分配并降低连续显存要求，但不能把 24.18%低于理论 26.91%完全归因于它。更直接的原因是序列进度不同以及 3 秒采样没有捕获瞬时上界。
4. 两副本方案是正确的容量扩展方向，但目前只是计划。需要验证第二张 GPU、模型可访问性、每副本 mns8、负载均衡以及总并发 16 时每个副本是否各承接约 8 请求。

### 11.7 Prefill / Decode 单变量实验前（已完成）

实验执行者原始回答：输入从 256 增至 1024、输出保持 128 时，预计输出吞吐下降、TTFT 下降、TPOT 不变，因为输入 Token 变多；输出从 128 增至 256 时，预计 TPOT 不会明显变化，E2E 增加约一倍 TPOT 时间；KV Cache 实测低于理论上界，是因为采样未捕获峰值且序列进度不同；长上下文应该单独定义 SLO。

校正后的事前假设：

1. `256/128 → 1024/128`只增加 Prompt。输出吞吐可能下降，因为更多 GPU 时间用于 Prefill；P95 TTFT 应上升而不是下降，因为首 Token 前必须处理更多输入；进入稳定 Decode 后，P95 TPOT 预计接近基线或仅小幅上升。
2. `256/128 → 256/256`只增加输出。TPOT 是相邻输出 Token 的时间，预计不会因为输出长度翻倍而自身翻倍；E2E 增量近似为新增 128 个输出 Token 乘以 TPOT。按 Short c8 的约 40 ms/token 粗估，P95 E2E 可能增加约 `128 × 40 ms ≈ 5.1 s`。
3. 以 22,832 Token slot 为分母、8 条序列都同时达到最大长度作为理论上界，`1024/128`、`256/256`、`1024/256` 的 KV Cache 分别约为 40.4%、17.9%、44.9%。实测可能更低，因为请求不会完全同步达到最长状态，三秒级采样也可能错过瞬时峰值；低于上界本身不代表性能未到峰值。
4. Long SLO v1 定义为：成功率 ≥99%、P95 TTFT ≤1500 ms、P95 TPOT ≤55 ms、P95 E2E ≤13 s。它是缺少真实业务需求时的项目工程验收线：TTFT 相对 Short 的 600 ms 放宽以容纳 4 倍 Prompt，E2E 相对 6 s 放宽以容纳 2 倍输出，TPOT 只小幅放宽，因为输出变长不应使逐 Token 节奏成倍恶化。

上述阈值在实验前冻结；实验后无论通过或失败都不回改阈值，只解释证据与适用范围。

### 11.8 Phase 3 统一时间线实验前（已完成）

代表性负载固定为单副本 mns8、256/128 Token、客户端并发 16、240 个正式请求和单轮执行。它只用于建立 Prometheus/DCGM 指标关联，不替代三轮性能基线。执行前请先回答：

1. 稳定阶段 running 和 waiting 分别预计接近多少？它们与 `max-num-seqs=8`是什么关系？
2. KV Cache 峰值预计接近 c8/c16-mns8 的约 13.5%，还是接近 27%？为什么？
3. GPU-Util、Prompt Token throughput 和 Generation Token throughput 在时间线上会完全同步吗？各自代表什么？
4. P95 queue、TTFT、TPOT、E2E 中，哪些预计因 waiting 显著上升，哪个预计仍接近 c8？
5. 为什么观测负载要持续超过 1 分钟，并在实验前后各保留 60 秒空闲窗口？

实验执行者原始回答：不清楚本轮与上一步测试的区别；预计稳定阶段 running=8、waiting=8；KV Cache 仍约 13.5%，因为 mns 只有 8；认为 GPU-Util 与 Generation Token throughput 同步、Prompt Token throughput 降低；认为除 E2E 接近 c8 外其他延迟都上升；尚不理解 1 分钟负载和前后空闲窗口的意义。

校正后的事前假设：

1. Phase 2 回答“配置或负载改变后，最终吞吐和客户端 P95 是多少”；Phase 3 本轮不再寻找新的性能提升，而是用已知会排队的 c16-mns8 复现实验，把请求调度、KV Cache、服务端 histogram 和 GPU 指标放到同一时间轴，回答“瓶颈何时出现、各指标以什么顺序变化、结束后是否恢复”。单轮数据只作为可观测性证据，不替代三轮性能基线。
2. 稳定阶段预计 `running≈8、waiting≈8`；轮次开始、批次补入和尾部收敛时会波动，不要求每个 15 秒采样点都精确等于 8/8。
3. KV Cache 峰值预计仍约 13%–15%，因为 mns8 同时运行约 8 条序列；waiting 请求尚未完整进入 Prefill/Decode，不会像运行序列一样占用整段 KV Cache。
4. GPU-Util 会在 Prefill 和 Decode 计算期间整体升高，但它不能区分两阶段，也不会与 Token throughput 严格同步。当前 vLLM 0.9.1 V1 在请求产生首个输出 Token 时一次性把整段 `prompt_len` 计入 Prompt counter，因此 Prompt throughput 更接近 Prefill 完成/首 Token 附近的记账波峰；Generation throughput 随 Decode 迭代产生的新 Token 增加，在 Decode 稳态更接近平台。15 秒 scrape 和 1 分钟 rate 窗口还会使曲线被平滑、产生视觉滞后。
5. P95 queue、TTFT 和 E2E 预计因第二波请求 waiting 而显著上升；TPOT 从首 Token 后开始度量，不包含完整排队时间，预计仍接近 c8 的约 42 ms。原回答把 E2E 和 TPOT 的角色写反了。
6. Token rate 和 histogram P95 使用 `[1m]` rate 窗口，负载持续超过 1 分钟才能形成足够的非空窗口；15 秒 scrape 在一分钟内约有 4 个样本。前后各 60 秒空闲基线用于显示 `0→压力平台→0`，证明曲线对应本轮负载并确认 waiting、running 和 GPU 利用率能够恢复，而不是只截取一个无法定位的峰值。

实验执行者进一步质疑 120 个请求是否过少。按已有 c16-mns8 约 1.4 req/s 估算，120 个请求只持续约 86 秒：扣除 `[1m]` 窗口形成时间后，稳态有效采样点太少。因此在正式执行前把请求数修正为 240，预计持续约 171 秒，约有 11 个抓取点，其中约 7 个处于完整 1 分钟窗口形成后的负载期。并发和请求形状不变，所以没有加大瞬时 GPU 压力，只延长了单轮观测时间；总正式请求数仍少于 Phase 2 单场景三轮的 300 个。

### 11.9 Phase 3 实验后复盘（已完成）

实验执行者原始回答：当 `running=8、waiting>0、GPU≈97%、KV≈15%` 时倾向直接增加 mns；能够判断有 waiting 的场景 TTFT/E2E 更差并更需要扩容，但认为输出吞吐也必然降低；尚不理解 HPA/KEDA；把 Phase 3 概括为“找到 mns8，并通过设置 mns16 明显好转”。同时追问 Phase 3 重复负载的必要性、PromQL、Grafana 数据源命名、整阶段图表含义，以及 20,212 MiB DCGM 显存中实际 KV block 池的大小。

校正后的理解：

1. Phase 2 用客户端精确分位数回答“性能结果是多少”；Phase 3 用 scheduler、KV、服务端 histogram 和 DCGM 统一时间线回答“为什么出现该结果、何时出现与恢复、哪个指标可以驱动运维动作”。重复 c16-mns8 是复现已知症状以建立运行时因果证据，不是再次寻找性能提升。
2. `GPU-Util≈97%`只表示采样窗口内 GPU 大部分时间有 kernel 执行，不等于 Tensor Core、显存带宽或单卡吞吐达到理论峰值；`KV≈13.5%`排除了 KV block 容量耗尽。两者结合 `running=8、waiting=8`说明 mns8 下运行批次令 GPU 持续繁忙且入口排队。增加 mns 是可测试的单卡调优动作，但已有 mns16 结果显示 TPOT 上升且 TTFT/E2E 仍违反 SLO，因此当前 c16 目标更适合验证“每副本约 8 并发、两副本分担”，不能仅凭单一指标决定。
3. `running=8、waiting=0`与`running=8、waiting=8`可以有相近的稳态 Generation throughput；后者不必然降低吞吐，但额外请求在队列中显著增加 TTFT/E2E，扩容紧迫性更高。
4. 15 秒 scrape 解释指标被发现的离散滞后；Token rate 与 histogram P95 还使用 `[1m]`滑动窗口，所以请求结束后可继续保留最多约一分钟的尾迹。跨 Prometheus/DCGM exporter 与 remote-write 到 VictoriaMetrics 还会造成采样点和峰值略有差异。
5. DCGM framebuffer 的约 20,212 MiB 包含模型权重、完整预分配 KV 池、CUDA context/graph、workspace 和 allocator 保留空间；它从服务启动后基本恒定，不适合作为流量弹性信号。`gpu_cache_usage_perc`才是预分配 KV block 池中当前被序列使用的比例。
6. 当前 Qwen3-8B BF16 每个 Token 的 KV 为 `2 × 36 layers × 8 KV heads × 128 head_dim × 2 bytes = 144 KiB`。启动日志确认 1427 个 block、每 block 16 Token，即 22,832 slots、约 3.14 GiB 完整 KV 池；每 block 2.25 MiB。本轮 13.525%峰值对应 193 blocks、3088 slots、约 434.25 MiB 实际占用。
7. SLO 使用客户端逐请求精确 P95；Prometheus histogram P95用于运行时趋势和告警。PromQL 是 Prometheus Query Language；VictoriaMetrics 提供 Prometheus 兼容 API，因此 Grafana 中名为、类型为 Prometheus 的数据源可以实际指向 vmselect。两套后端的核心峰值一致，小幅数值差异来自抓取、remote-write 和查询对齐，不应解释为实验不稳定。
8. HPA 是 Kubernetes 原生水平副本伸缩控制器；KEDA 从 Prometheus等外部事件源读取信号，并通常借助HPA调整副本。本项目后续若实施，优先考虑持续 waiting/queue 与 SLO，而不是几乎恒定的DCGM显存占用；副本数硬限制为1–2，且必须考虑Qwen3-8B约数分钟冷启动。
9. Phase 3自身没有把 mns8改为mns16；该单变量优化属于Phase 2。Phase 3的结论是：c16-mns8的尾延迟恶化来自8 running/8 waiting的配置排队而非KV耗尽，`waiting_requests`可作为Phase 4候选弹性信号，负载结束后服务能够恢复空闲。

### 11.10 Phase 4 事前判断与安全审计（进行中）

实验执行者的事前判断：约 3～4 分钟的模型冷启动无法改善只持续约 2～3 分钟的同一波突发请求，基于 waiting 的反应式扩容更适用于持续需求；自动弹性前应先获得静态双副本的容量数据。固定总并发 16 时，理想状态为每副本约 `running=8、waiting=0`，但请求完成时间差异、入口负载均衡策略以及两张卡的实际性能差异都可能造成不均衡。`minReplicas` 应保留为 1，以常驻一张卡换取基础服务的低启动等待；项目最多使用两张卡。实施前必须确认不修改公司服务、CPU/内存/GPU 仍有余量，且本项目启动不会影响已有工作负载。

Phase 4 的实施顺序据此冻结为：

1. 先做宿主机与 Kubernetes 的只读容量、现有占用、设备分配及弹性组件审计。
2. 若能确定第二副本不会落到公司占用的 GPU，先短时部署静态双副本，验证路由、每副本 running/waiting、吞吐、SLO 和负载均衡。
3. 只有静态双副本有明确收益，且集群已有安全可用的 custom metrics/KEDA 通路时，才测试 `minReplicas=1、maxReplicas=2` 的自动扩缩容。
4. waiting 触发必须使用持续窗口而非单个采样点，以降低 15 秒抓取离散性和瞬态抖动导致的误扩容；具体阈值在静态数据后确定。
5. 若模型冷启动晚于负载结束，则如实记录纯反应式扩容对短突发无效，并把适用条件限定为持续流量、预热副本或可预测流量。

弹性决策不能只看单一指标。当前已经由 Phase 2/3 证据支持的判断链是：`waiting>0` 表明需求超过当前接纳上限，但也可能先提示调整 mns；KV Cache 仍低说明不是 KV 容量耗尽；GPU-Util 约 97%且 mns16 的 TPOT 上升说明继续扩大单卡批宽会增加计算竞争；最终由预注册 SLO 判定 mns16 仍不合格。因此，本项目选择验证横向容量，而不是把“有 waiting”机械地等价为增加 mns 或扩容。

2026-09-07 宿主机初步只读快照显示 4 张 NVIDIA A10：GPU 0 有公司 Python 进程并占约 5901 MiB，明确排除；GPU 1 为本项目现有服务并占约 20213 MiB；GPU 2、3 当时各约 1 MiB、无计算进程。随后完成 Kubernetes 侧交叉核对：节点 `qhvgpu1` 的 `nvidia.com/gpu` capacity/allocatable 均为 4，当前两个 Running 整卡 Pod 分别是公司 `default/magic-pdf-gpu-api` 和本项目 `vllm-infra-lab/qwen3-8b`；容器内 UUID 进一步确认前者对应物理 GPU 0、后者对应物理 GPU 1。节点资源账本为 GPU request/limit `2/4`，因此当时 GPU 2/3 同时满足“宿主机无进程”和“Kubernetes 未分配”两项条件。共享环境状态会变化，正式扩容前必须再次执行相同快照。

节点静态资源账本显示 CPU requests 约 76%、memory requests 约 40%，新增一个副本的 2 CPU/16 GiB request 后预计约为 82%/53%；宿主机快照还有约 82 GiB available memory、CPU idle 约 91%～93%。但 memory limits 已约 96%，新增 32 GiB limit 后会超过节点容量；这不是立即占用，却意味着发生并发内存峰值时缺少 limit 层面的硬容量保证。Metrics API 未安装，`kubectl top`不可用，所以只能把宿主机快照与 requests 共同作为短时实验前提，不能声称已有完整资源监控。

集群有标准 NVIDIA Device Plugin，并以 UUID/envvar 方式向容器注入设备；HAMi v2.5.2 虽已安装，但本项目当前使用标准整卡资源 `nvidia.com/gpu: 1`，没有使用 `nvidia.com/vgpu`。KEDA CRD、resource Metrics API、custom metrics API 和 external metrics API 均不存在；现有 HPA 的 target 也显示 `<unknown>`。因此不能在不修改公司集群基础设施的前提下直接实现 Prometheus → KEDA/HPA。Phase 4 先完成静态双副本；后续弹性优先考虑仅作用于本 namespace、可审计且可回退的最小控制器或离线策略回放，不安装集群级组件。

流量入口还存在一个实验设计限制：`kubectl port-forward service/qwen3-8b`会选择一个后端 Pod 建立转发，不能证明 Service 对两副本做了负载均衡。静态双副本实验必须从能够直接访问 ClusterIP 的宿主机或集群内客户端请求 Service，并用 `pod` 标签分别检查两个副本。请求一旦分配给某个 Pod，其执行中状态和该 Pod 内的 waiting 不会迁移到另一 Pod；只有后续新连接/新请求可能被分配给空闲副本。长连接复用、连接级哈希、随机分配和两卡速率差异都可能导致短时不均衡。

宿主机对 Service ClusterIP `10.244.25.38:8000` 的健康检查超时，因此静态实验不能直接从宿主机访问 Service。项目新增独立的 `deploy/phase4-static` Kustomize 覆盖层：base 继续安全地保持单副本；覆盖层才把副本数设为 2，并以 `maxSurge=0、maxUnavailable=1`确保滚动更新时不会短暂创建第三个 GPU Pod。覆盖层同时创建无 GPU、250m CPU/512 MiB request 的 `phase4-benchmark-client`，从集群内通过 `http://qwen3-8b:8000`压测。客户端使用 UID/GID 1000 写入本项目 hostPath，模型目录只读挂载，不修改公司 namespace。

在静态实验准备检查点，benchmark runner 已能够记录 `server-replicas` 和按顺序重复传入的 GPU 物理编号/UUID，并把 Service DNS 主机名加入 `NO_PROXY`；新增 `phase4-static.yaml` 固定 256/128 Token、c16、16 个预热请求、每轮 100 个正式请求、3 轮和独立 seed offset。该检查点只完成本地渲染/dry-run，随后才按下文记录执行 server dry-run 和正式实验。

覆盖层实际应用后，新副本从 `2026-09-07T07:25:16Z`创建到 `07:27:51Z` Ready，冷启动 155 秒；原副本全程可用。新副本分配物理 GPU 2，GPU 3保持空闲；两个 Service endpoint 均 Ready，集群内 client 健康检查返回 HTTP 200。新副本仍有 3.14 GiB KV 池、22,832 Token slots，未发现真实 ERROR/OOM/Traceback。公司 Pod 的历史 restart=1 发生在 2026-07-24，与本次扩容无关。

首次从 benchmark client 启动正式压测时，在第一轮 warmup 发请求前失败：client 以 UID/GID 1000 非 root 运行，但 vLLM 镜像的 `/etc/passwd`没有该 UID；PyTorch 导入阶段的 `getpass.getuser()`因此抛出 `KeyError: getpwuid(): uid not found`。监控确认两个副本请求/Token counter 均无新增，不能把该次失败计入正式实验。修复为显式设置 `USER=benchmark`、`LOGNAME=benchmark`、`HOME=/tmp`、`XDG_CACHE_HOME=/tmp/.cache`和`TORCHINDUCTOR_CACHE_DIR=/tmp/torchinductor`，不以提升到 root 回避问题。正式长任务改由 tmux 承载，避免 SSH 断开中止客户端。

### 11.11 Phase 4 静态双副本事前假设

实验执行者原始回答：理想吞吐是单副本 c8 的两倍，实际预计达到理想值的 80%～90%；两副本延迟应更接近单副本 c8；判断均衡时还要看输出吞吐和 TTFT/TPOT/E2E；若请求按 10/6 分配，则两个副本分别约为 `running=8、waiting=2`和`running=6、waiting=0`，整体 P95 会显著上升；验收要求吞吐至少增加 50%、SLO 达标、成功率至少 99%。

校正并冻结为以下可检验假设与标准：

1. 以历史 c8 的 178.796288 tok/s 计算，线性上界为 357.592576 tok/s，80%～90%扩展效率对应 286.07～321.83 tok/s。若用当前 GPU 1 相邻校准值 180.649355 tok/s，则对应 289.04～325.17 tok/s。两张实际 GPU 不同，因此前者用于回答原假设，后者作为更接近当前环境的参考，不把细小差异包装成收益。
2. 完美 8/8 分流时，每副本工作状态更接近单副本 c8-mns8，因此预计 TTFT、TPOT、E2E 也更接近当前同卡 c8 校准的约 486 ms、41.95 ms、5.497 s，并有机会同时通过 Short SLO；但连接级分配偏斜可能使尾部请求重新排队，所以不预设必然通过。
3. 某个 15 秒采样点同时看到 `running=8/8`不能证明累计请求均衡。负载分布应比较按 `pod` 分组的 `request_success_total`增量、Prompt/Generation Token counter 增量，并结合每副本 running/waiting 时间线。客户端吞吐和延迟是整体效果指标，不足以单独证明请求由两个 Pod 均匀承接。
4. 10/6 分流下，第一副本预计 `running=8、waiting=2`，第二副本约 `running=6、waiting=0`；排队请求会主要抬高 TTFT/E2E P95。具体是否“显著”上升取决于这种偏斜持续多久和最慢 5%请求是否落入排队批次，必须由时间线验证。
5. 正式最低验收冻结为：300 个请求成功率至少 99%；Short SLO v1 三项同时通过；输出吞吐至少比单副本 c16-mns8 三轮基线 179.285 tok/s 提高 50%，即至少 268.93 tok/s；每个副本承接总请求的 40%～60%，否则单独标记负载不均衡。还必须确认公司 Pod Ready、restart 和 GPU 0 映射不变，本项目只占 GPU 1 加 GPU 2/3 之一，无 OOM、preemption 或第三个 vLLM Pod。
6. 吞吐还必须与单卡 mns16 的 305.434 tok/s 并列报告。若双卡只超过 268.93 tok/s但低于 305.434 tok/s，只能说明它以更多硬件换取了 SLO；不能声称吞吐效率优于单卡 mns16。若同时超过 305.434 tok/s并通过全部 SLO，才形成更强的横向扩容结论。

### 11.12 Phase 4 静态双副本结果与复盘

正式结果目录为 `results/2026-09-07/20260907-153612-phase4-static-c16-mns8-r2/`。三轮均为 100/100 成功；中位输出吞吐 332.912 tok/s，相对单副本 c16-mns8 的 179.285 tok/s 提高 85.69%，相对单卡 c16-mns16 的 305.434 tok/s仍高 9.00%，相对两倍历史 c8 的扩展效率为 93.10%。P95 TPOT 中位数 42.484 ms 通过 50 ms SLO；P95 TTFT 5469.014 ms、P95 E2E 10741.813 ms，均未通过 600 ms/6000 ms SLO。输出吞吐 CV 7.53%，TPOT CV 0.19%。

5 秒监控覆盖完整 tmux 流程的 354 个完成请求（300 正式、48 预热、6 个 benchmark 初始探测）。两个副本完成请求增量为 179/175，占比 50.56%/49.44%，累计分布通过 40%～60%标准；但 Peak waiting 分别达到 6/4。曾直接观察到一侧 `running=8、waiting=6`、另一侧仅 `running=1、waiting=0`，随后也会反向偏斜。两个副本 Peak KV Cache 都约 13.525%，两张卡负载期都达到约 97%～100% GPU-Util。

这修正了“两个副本会自然形成稳定 8/8”的假设。ClusterIP Service 做连接级分配，不感知 vLLM scheduler queue；客户端连接复用使整场累计请求可以接近 50/50，但单个并发波次仍可能超过某个副本的 mns8。少数请求因此等待约一个完整 Decode 批次，P50 TTFT 约 352 ms而 P95 约 5.47 秒；TPOT 不含完整排队时间，所以仍稳定达标。横向计算容量已验证，入口分流成为新的尾延迟瓶颈。下一步应做确定性 8/8 对照，把两卡容量与 Service 分流分开验证，而不是立即增加 mns、第三张卡或自动扩容。

实验结束后已恢复 base：Deployment `1/1/1`、策略 `Recreate`，只保留原 Pod/GPU 1且 restart=0；GPU 2释放到约 1 MiB，GPU 3始终空闲；公司 GPU 0保持约 5901 MiB、Pod Ready且历史 restart仍为1。安全回退验收通过。

### 11.13 Phase 4 确定性 8/8 对照事前假设

项目本人在查看正式命令前给出以下判断，随后再作边界校正：

1. 两条直连流各为 c8、每副本 mns8，预计负载主体阶段两个副本都接近 `running=8、waiting=0`。该判断不要求预热、批次切换和收尾阶段也恒定为 8；验收重点是不能再出现普通 Service 实验中一侧 waiting 堆积而另一侧仍有明显空槽。
2. P95 TTFT/TPOT/E2E 应更接近单副本 c8-mns8 的 `525/42.74/5554 ms`，而不是普通 Service 双副本的 `5469/42.48/10742 ms`，因为本轮强制按 8/8 分流，移除了连接级瞬时偏斜。
3. 输出吞吐最低阈值预注册为 300 tok/s，约为普通 Service 双副本中位数 332.912 tok/s 的 90.11%；不能通过大幅降低吞吐换取延迟达标。
4. 正式联合验收为 300 个请求成功率至少 99%、输出吞吐至少 300 tok/s、P95 TTFT/TPOT/E2E 分别不高于 600/50/6000 ms。若全部通过，结论不是笼统的“扩容有效”——静态实验已证明容量扩展有效——而是“确定性均衡分流能把双副本容量转化为 Short SLO 改善，普通 Service 的单波次连接分配是此前尾延迟的主要原因”。若仍失败，则不能把问题完全归因于 Service，需要继续检查两个子客户端是否同步、GPU 个体差异和服务端阶段干扰。
5. 只加入基于全局 waiting 的 KEDA 仍不能保证消除瞬时倾斜：KEDA 决定副本数量，不决定每个请求的目标 Pod，也不会迁移已经进入某个副本 waiting 队列的请求。生产方案仍需请求级、负载感知的推理路由；本项目先用直连对照验证因果，不在公司集群安装集群级组件。

### 11.14 Phase 4 确定性 8/8 对照结果与复盘

正式结果目录为 `results/2026-09-07/20260907-023250-phase4-direct-split-c16-mns8-r2/`。目录时间来自 client 容器的 `-07:00` 时区，宿主机监控窗口为北京时间 `17:32:37–17:40:32`；两者对应同一实验。三轮合计 300/300 正式请求成功，输出吞吐中位数 334.824 tok/s，P95 TTFT/TPOT/E2E 中位数分别为 524.631/42.706/5543.586 ms，全部通过预注册的吞吐和 Short SLO 门槛。输出吞吐 CV 仅 0.138%。

相对普通 Service 双副本，输出吞吐只提高 0.57%，但 P95 TTFT 降低 90.41%、P95 E2E 降低 48.39%；相对单副本 c8，三个 P95 延迟只变化约 `-0.06%/-0.08%/-0.19%`，而输出吞吐达到 1.873 倍，线性扩展效率为 93.63%。因此改善不是来自放弃吞吐，而是来自消除单波次排队。

两个 target 每轮测量时长只差 99～139 ms，六个 target 输出吞吐均为约 167.4～168.2 tok/s。5 秒监控显示两侧全流程完成请求、Prompt Token、Generation Token 增量完全相同，分别为 `180/46043/23040`；两个副本均达到 Peak running 8、Peak waiting 0、Peak KV Cache 13.525%、Peak GPU-Util 100%。其中每侧 180 包含 150 个正式请求、24 个预热和 6 个初始探测，正式 150/150另由 target JSON 直接确认。

这构成了控制变量因果证据：相同两卡计算容量和相同总并发下，普通 Service 与确定性直连的吞吐近似，但只有后者消除了 waiting 并恢复 TTFT/E2E。此前静态实验的主要尾延迟瓶颈是连接级、非队列感知的瞬时分流，而不是两卡总算力不足。直连 Pod IP 只是实验对照，不具备服务发现、故障转移或动态负载感知，不能包装成生产路由器，也不能声称已经完成 HPA/KEDA。

实验结束后重新应用 base 并删除临时 client；最终 Deployment `desired/ready/current/available=1/1/1/1`，原 Pod restart 0，GPU 2回落到 1 MiB，公司 GPU 0保持约 5901 MiB且利用率 0%。安全回退通过。

### 11.15 确定性分流实验后的理解校正

项目本人复盘认为：吞吐反映整体处理能力，TTFT/E2E 更能体现单请求体验；累计 50/50 看不到瞬时分流，而 `waiting=0/0` 更能说明本轮分流有效；实验已经证明严格 8/8 能得到预期指标，但没有证明双副本峰值性能。这个方向正确，并补充以下边界：

1. 吞吐与延迟不是“整体指标和单请求指标”的绝对二分。吞吐确实按整个测量窗口汇总；TTFT/E2E 则先按每个请求测量，再用 P95 描述最慢 5%附近的体验。普通 Service 与确定性 8/8 的吞吐只差 0.57%，说明两者在完整窗口内完成 Token 的总速率近似；但前者仍有少数请求等待一个服务波次，所以 P95 会显著恶化。若偏斜更严重或持续更久，总吞吐也可能下降。
2. 累计 50/50 会丢失时间顺序。例如第一波按 14/2 分配、第二波按 2/14 分配，最终仍是 16/16，但每一波都有一个副本超过 mns8并排队，另一个副本存在空槽。确定性对照中，两侧正式请求严格 150/150、全流程 Token counter 相同、Peak running 8/8，同时所有 5 秒采样点 waiting 都为 0，且 P95 延迟恢复到 c8；这些证据组合起来排除了已知的波次偏斜。严格表述应是“采样窗口内未观测到 waiting”，不能仅凭 5 秒 gauge 断言任意毫秒绝对为 0。
3. 本轮证明的是：在 256/128、总 c16、两张 A10、每副本 mns8 的条件下，确定性均衡分流能在保持约 335 tok/s 吞吐的同时通过 Short SLO，并支持“普通 Service 瞬时分流是此前尾延迟的主要原因”。它没有扫描更高总并发，因而没有证明双副本峰值；也没有实现生产级队列感知路由、故障转移或自动伸缩。
4. 扩容与路由解决不同问题。扩容只让第二个 Pod 变为 Ready，不会改变普通 Service 不感知 vLLM queue、客户端复用连接的事实；新容量如果没有被及时选中，仍可能出现一侧 waiting、另一侧空闲。实测第二副本冷启动约 155 秒，因此纯反应式策略在短突发开始后才扩容时，新副本可能在突发结束后才 Ready，对本次尾延迟几乎没有帮助；它更适合持续超过冷启动时间的压力、可预测流量，或以预热副本换取响应速度。

### 11.16 弹性策略事前回答与离线回放

项目本人选择 waiting 至少连续两个采样点才扩容，以过滤偶发压力；请求级路由优先使用路由器自己的实时请求数，而不是延迟的 Prometheus 数据；并判断 155 秒冷启动使反应式扩容无法保证 60 秒短突发的 SLO。这三点正确。

对缩容的原始判断是同样观察至少两个低负载采样点。校正为更保守的不对称策略：扩容连续两个 15 秒采样点即可触发，但缩容必须同时满足 `waiting=0`、`running<=4` 持续 300 秒，且第二副本 Ready 后至少驻留 300 秒。原因是扩容响应不足会直接制造排队，而过早缩容会浪费已经支付的 155 秒冷启动成本，并在流量反弹时形成 1↔2 抖动。

项目新增纯离线状态机与版本化策略，不连接集群。Phase 3 历史时间线在 `02:43:44Z` 首次出现 waiting，但下一点归零，正确地没有扩容；`02:44:14Z`、`02:44:29Z` 连续出现 waiting 后，在后一采样点请求扩容。叠加实测 155 秒冷启动，第二副本计划于 `02:47:04Z` Ready，而最后一个有负载的采样点是 `02:46:44Z`，新容量晚约 20 秒，不能改善该次短压力窗口已经产生的尾延迟。

请求级路由与容量控制据此分开：Prometheus waiting 用于 1↔2 的慢控制环；路由器本地 least-inflight 用于每个新请求的快控制环。后者必须在转发前增加计数，并在普通响应、流式关闭和异常路径上可靠减少；同值时轮询。仅按请求数仍无法表达不同 Prompt/Output 长度的成本，后续可加入 Token 估算或完成时长 EWMA，但不在第一版提前包装。

### 11.17 least-inflight 理解校正与离线实现

`in-flight`表示路由器已经接收并转发、但完整生命周期尚未结束的请求，覆盖后端 waiting、Prefill、Decode 和仍在传输的流式响应。它是路由器本地实时记账，不等于 vLLM `running` gauge，也不依赖 15 秒 Prometheus scrape。

项目本人最初判断流式请求收到响应头后即可减少计数；校正为必须等流正常结束、客户端断开或异常清理时再释放。收到响应头通常只代表流已经建立，vLLM 仍在 Decode；若提前减一，路由器会把繁忙副本误判为空闲并继续集中请求。

后端健康检查失败时，不暂停所有新请求，而是将新请求路由到其他健康副本；只有全部后端不可用时才快速失败。已经开始的请求若连接仍正常则继续；若生成中途连接失败，第一版不能透明重试，因为重新生成可能产生重复 Token 或不一致输出，应向客户端返回明确错误。摘除只影响新选择，不强行终止现有 lease。

对于长短混合请求，问题不仅是“相同类型请求可能集中”。更根本的是一个 2048/512 请求和一个 256/32 请求在 least-inflight 中都只记为 1，但前者占用 Prefill、Decode、KV 和连接的时间显著更长。第一版以固定 256/128 对照验证请求数均衡；Token 估算或 EWMA 权重保留为明确扩展点。

仓库新增线程安全的 `LeastInflightRouter`与幂等 `BackendLease`。专项 7 个测试覆盖 16 个同时持有请求形成 8/8、平局轮询、完整生命周期释放、异常清理、后端摘除、全部不可用和并发 acquire 原子性；连同弹性状态机共 11 个测试全部通过。该模块没有 HTTP 监听、流式转发、服务发现或真实健康探测，不能将“路由核心已验证”写成“生产代理已完成”。

### 11.18 最小 HTTP/SSE 适配与 mock 验证

在 `88fac32`已提交并与 `origin/main`同步、工作区干净的基础上，继续执行 Phase 4 的纯 CPU 工作。仓库没有现成 HTTP 框架依赖，因此使用 Python 标准库增加 `router/http_proxy.py`，避免为最小因果验证引入大型框架。

适配层在读取请求后 acquire lease，向唯一选中的后端转发 GET/POST/PUT/PATCH/DELETE；普通响应写完、SSE 流结束、客户端断开或上游异常后才在 `finally` 中 release。固定 `/health` 探测以 2xx 判定健康，可摘除和恢复新流量；全部后端不可用返回 503，上游连接失败返回 502。请求一旦选中就不自动改投另一后端，避免已经发送或开始生成后的重复输出风险。

本地 loopback mock backend 的 8 个专项测试全部通过：非流式完整生命周期、SSE 收到响应头后仍持有 lease、客户端强制断开清理、上游连接失败清理、健康摘除/恢复、全部不可用 503、失败请求不盲目重试，以及 16 个同时持有的 HTTP 请求严格形成 8/8。连同核心 7 个和弹性回放 4 个测试，全仓共 19 个测试通过。

边界保持不变：这是线程式、每请求新建上游连接的实验适配，只支持带 `Content-Length` 的请求体，响应使用 HTTP/1.0 connection-close 定界；没有 EndpointSlice、连接池、背压、限流、认证、指标、优雅摘流或 Token-aware 权重。客户端断开只能在下一次写下游时被发现，上游长时间不产生 chunk 时取消会延后。本轮没有访问或修改 Kubernetes，也没有占用第二张 GPU。

## 12. 当前阶段与下一步

### 12.1 阶段状态

| 阶段 | 状态 | 已完成 | 尚缺 |
| --- | --- | --- | --- |
| Phase 0 环境与安全边界 | 已完成 | 软硬件、模型、共享工作负载、Git 认证盘点 | 每次实验前刷新动态资源快照 |
| Phase 1 单副本服务 | 已完成 | Deployment/Service/探针、API、删除 Pod 自愈 | 后续将冷启动指标自动化 |
| Phase 2 基准与参数实验 | 已完成 | 工具链、聚合、Short 并发扫描、`max-num-seqs` 8/16、Prefill/Decode/组合长上下文、三张客户端性能图 | GPU/KV/waiting 时序证据归入 Phase 3 |
| Phase 3 可观测性 | 已完成（共享环境边界） | `/metrics`、ServiceMonitor、Prometheus 指标发现、共享 PromQL、Grafana 9.3/schema 37 Dashboard JSON、正式统一时间线与可复现 SVG、c16 排队和 Pod 自愈证据 | 共享 Grafana 持久化导入因安全边界明确跳过，不作为欠项 |
| Phase 4 多副本与弹性 | 进行中（最小路由适配已离线验证） | 安全审计、双副本对照、两次安全回退、1→2→1 回放、least-inflight 核心、HTTP/SSE 适配、健康探测与 19 个测试 | EndpointSlice 等生产能力不在当前最小范围；是否执行真实入口或自动弹性实验待安全评估 |

Phase 2、Phase 3 已闭环。Phase 4 已证明两卡容量、入口分流因果和短突发冷启动限制，并完成 least-inflight 核心与最小 HTTP/SSE mock 验证。下一步由项目本人检查 diff，并决定是否值得设计一次短时真实入口实验；不安装公司集群级 Adapter/KEDA，不自动占用第二张 GPU。

### 12.2 紧接着要做什么

第一步已完成：benchmark runner 会把 `max-num-seqs`、`max-model-len` 和 `gpu-memory-utilization` 写入 metadata，并在实验目录名中标识 `mns16`；工具改动和事前假设已提交为 `d9e4a0e`。

第二步已完成：项目本人回答了 11.5 的五个问题，校正后的吞吐、延迟、waiting 和 KV Cache 假设已经冻结。

第三步已完成：版本化 Deployment 已把 `--max-num-seqs` 从 `8` 改为 `16`，用户完成 dry-run、提交、apply 和新 Pod 验收；启动日志同时给出了精确 KV Cache 容量。

第四步已完成：`c16-mns16` 三轮均为 100/100 成功，输出吞吐较 mns8 提高 70.36%，但 P95 TTFT 和 P95 E2E 仍违反 SLO。

第五步已完成：mns16 结果已提交为 `5776be0`；版本化 Deployment 和集群均已恢复单副本 mns8。回退后的 Pod 健康，但被重新分配到物理 GPU 1，因此历史 GPU 3 上的 Short 数据不能直接充当严格的当前硬件对照。

第六步已完成：固定并发 8 和 mns8，在当前 Pod/GPU 的相邻时间窗口完成 `256/128` 校准、`1024/128` Prefill 对照、`256/256` Decode 对照和 `1024/256` 组合长上下文。四组共 840/840 个正式请求成功，三种长负载全部通过预注册的 P95 Long SLO；原始数据、聚合和 README 当前等待项目本人检查提交。

第七步已完成：最终 Pod 与日志审计通过，四组结果已提交为 `c3524fb`；三张确定性 SVG 已完成语法、XML、重复生成和视觉检查，并提交为 `6f8cad8`。

第八步已完成准备：Phase 3 的 13 条共享 PromQL、Grafana Dashboard JSON、统一时间线导出器和代表性 c16-mns8 场景已提交为 `188cae0`。由于此前三秒轮询没有完整保存，不能事后拼造 GPU 时序；下一步使用 Prometheus/DCGM 正式采集一次 240 请求的代表性负载，把 running、waiting、KV Cache、服务端延迟和 GPU 指标对齐到统一时间线。

第九步已完成：240/240 个正式请求成功，输出吞吐 186.87 tok/s；统一时间线捕获 `running=8、waiting=8`、KV Cache 峰值 13.525%、GPU-Util 峰值 97%，并验证负载结束后恢复空闲。导出检查同时发现 vLLM JSON 的 `date` 是轮次完成时间，修正了错误重复叠加 `duration` 的窗口边界；正式窗口为 `10:42:14–10:47:39`。运行后审计确认 live mns8 参数、Pod Ready/Running、重启 0、preemption 0；宽泛错误关键词命中的内容均来自 INFO 级随机 Prompt，没有发现真实错误日志。

第十步已完成只读 Grafana 兼容性审计：集群运行 Grafana 9.3.14，子路径为 `/ui/insight-grafana`，默认 Prometheus 数据源 UID 为 `PBFA97CFB590B2093`，现有 Dashboard 使用 schema 37。生成器已从未来版本 schema 39 修正为 37。直连身份对现有 Dashboard 为 `canSave=false`；持久化导入需要更高权限并写入公司共享 `insight-system` Grafana，违反本项目安全边界，因此明确跳过，不把“未写公司系统”误报为功能失败。

第十一步已完成只读部分并进入静态实验准备：GPU 0/1 已分别映射到公司 Pod/本项目 Pod，GPU 2/3 在宿主机与 Kubernetes 两侧均为空闲；CPU/内存 request 与宿主机瞬时余量可支持一次短时第二副本。集群没有 Metrics API、custom/external metrics API 或 KEDA，因此不修改公司基础设施。Phase 4 静态覆盖层、集群内 benchmark client、多副本 metadata 和独立场景已完成本地渲染/dry-run；下一步由项目本人检查 Git diff，并对覆盖层执行 client/server dry-run，尚不直接 apply。

第十二步已完成：静态双副本在 GPU 1/2 上安全运行并回退，冷启动 155 秒，三轮 300/300 正式请求成功。中位输出吞吐 332.912 tok/s，但 P95 TTFT/E2E 为 5469/10742 ms，仍违反 Short SLO；每副本整场累计请求约 50/50，但瞬时 waiting 峰值为 6/4，确认瓶颈转移到连接级分流。首次 client UID 报错发生在发请求前，已用非 root 环境变量修复并明确排除。

第十三步已完成：确定性 8/8 对照三轮 300/300 成功，输出吞吐中位数 334.824 tok/s，P95 TTFT/TPOT/E2E 为 524.631/42.706/5543.586 ms；两侧 Peak running 8/8、Peak waiting 0/0，所有预注册门槛通过。随后恢复单副本并释放第二张 GPU。

第十四步已完成离线方案与历史回放：waiting 连续两个采样点请求扩容，缩容使用 300 秒低负载和 300 秒 Ready 驻留；历史突发中第二副本计划 Ready 晚于最后负载采样约 20 秒。状态机的四组单元测试通过，确定性 SVG 已完成视觉检查，尚未对集群执行自动扩缩容。

第十五步已完成 CPU-only least-inflight 核心：16 个并发 lease 稳定形成 8/8，正常、异常、重复释放和后端摘除路径均通过，专项 7 个、全仓 11 个测试通过。当前只验证了选择和生命周期记账，不包含真实 HTTP/流式代理。

第十六步已完成：标准库最小 HTTP/SSE 适配通过 8 个本地 mock 专项测试，覆盖非流式与流式生命周期、503、客户端断开、连接错误、健康恢复、不盲目重试和 HTTP 层 8/8。

第十七步由项目本人检查 diff。只有本人明确决定继续，才设计真实双副本入口覆盖层并重新执行共享资源安全审计；在此之前不访问集群、不占用第二张 GPU。

## 13. 当前可用于面试的表述边界

### 13.1 已经有证据支撑

- 在 Kubernetes 1.28 双节点 GPU 集群上，以固定 vLLM 0.9.1 镜像部署 Qwen3-8B BF16 单卡服务，配置模型只读挂载、GPU 资源声明和三类健康探针，并验证 Pod 删除后的自动恢复。
- 将 vLLM `/metrics` 通过 ServiceMonitor 接入既有 Prometheus，验证 target 存活和真实请求指标持续入库。
- 构建固定 Token 长度、预热、三轮重复、种子隔离和 JSON/CSV 汇总的可复现压测流程；在单张 A10、256/128 Token 场景下，将 `max-num-seqs` 从 8 提高到 16，使 c16 输出吞吐从 179.29 提高到 305.43 tok/s、P95 E2E 从 11.10 秒降到 6.15 秒，同时识别出 TTFT/E2E 仍未满足 SLO 的边界。各档均为 300/300 请求成功。
- 在同卡相邻窗口用 256/128、1024/128、256/256、1024/256 四组控制变量实验拆分 Prefill 与 Decode：Prompt 增长使 P95 TTFT 上升约 201%，输出翻倍使 P95 E2E 增加约 5.10 秒而 P95 TPOT 基本不变；组合场景 180/180 成功并通过预注册 P95 Long SLO，但 E2E 仅剩约 211 ms 余量。
- 在共享环境安全审计后短时扩至两张 A10，以 `maxSurge=0`限制最多两个 GPU Pod；c16 输出吞吐相对单副本提高 85.69%至 332.912 tok/s，300/300 成功。每副本累计请求约 50/50，但瞬时 waiting 达 6/4并导致 TTFT/E2E SLO失败，定位普通 Service 的连接级分流为下一瓶颈；实验后恢复单副本且公司服务无变化。
- 设计确定性 8/8 双目标对照，在双副本吞吐基本不变（334.824 tok/s）的情况下，将 P95 TTFT 从 5469 ms降至 525 ms、P95 E2E 从 10742 ms降至 5544 ms；两个副本 Peak waiting 均为 0且请求/Token counter 完全对称，验证请求级分流是把横向容量转化为 SLO 收益的必要条件。

并发扫描和 mns16 参数实验的原始数据与报告均已提交，可作为已固化的远端证据；面试前仍应从原始 JSON 独立复算一次。

### 13.2 目前不能声称

- 不能声称已经完成 HPA/KEDA、自定义指标弹性或队列感知路由。
- 不能声称普通 ClusterIP 双副本已经满足 Short SLO；它只验证了容量扩展，并暴露了瞬时分流偏斜。
- 不能声称已经找到全局最优参数或单卡饱和点。
- 不能把 vLLM 自带 Continuous Batching、KV Cache 说成自己实现。
- 不能把当前 1024/256 结果推广到更长上下文、其他模型、量化模型或其他 GPU。
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
