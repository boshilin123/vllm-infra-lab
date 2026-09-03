# Deployment

`kubernetes/` 存放单副本基线的 Kubernetes 清单。首版先保持一套可运行配置，只有出现多节点、多模型或多环境差异时，才拆分 Kustomize `base/overlays`。

计划清单：

- `namespace.yaml`：隔离项目资源。
- `deployment.yaml`：固定镜像、模型挂载、GPU 资源、vLLM 参数和 probes。
- `service.yaml`：为 OpenAI-compatible API 和 `/metrics` 提供稳定入口。
- `pvc.yaml`：只在确认集群存储方案后启用。
- `kustomization.yaml`：固定单副本清单集合。

不提交密码、Token、kubeconfig、真实公网地址或未脱敏的内部路径。清单在 Phase 1 核对容器镜像、模型挂载和空闲 GPU 后实现。
