# Kubernetes manifests

Phase 1 在此实现首个可重复部署的单副本基线。提交清单前必须先核对：

- 可用 GPU 节点和节点上的并存负载；
- vLLM 容器镜像、CUDA/驱动兼容性；
- 模型权重在容器内的只读挂载方式；
- startup probe 能覆盖模型加载时间，readiness probe 能反映 API 是否接流；
- 所有镜像使用固定 tag 或 digest。

首版只维护一套清单。需要多环境差异时再引入 Kustomize overlays。
