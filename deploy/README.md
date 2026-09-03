# Deployment

本目录将存放 Kubernetes 部署清单：

- `base/`：Namespace、Deployment、Service、ConfigMap 与 probes。
- `overlays/`：不同 vLLM 参数和副本配置。
- 所有镜像必须固定 tag，不使用 `latest`。
- 不提交密码、Token、kubeconfig 或集群公网地址。

部署文件将在确认模型存储路径和可用 GPU 节点后补充。
