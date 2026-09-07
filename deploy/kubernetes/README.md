# Kubernetes manifests

Phase 1 在此实现首个可重复部署的单副本基线。提交清单前必须先核对：

- 可用 GPU 节点和节点上的并存负载；
- vLLM 容器镜像、CUDA/驱动兼容性；
- 模型权重在容器内的只读挂载方式；
- startup probe 能覆盖模型加载时间，readiness probe 能反映 API 是否接流；
- 所有镜像使用固定 tag 或 digest。

默认 `deploy/kubernetes` 始终保留单副本安全基线。

## Phase 4 静态双副本覆盖层

完成 GPU/CPU/内存快照后，Phase 4 才短时应用覆盖层：

```bash
sudo kubectl apply --dry-run=client -k deploy/phase4-static
sudo kubectl apply --dry-run=server -k deploy/phase4-static
sudo kubectl apply -k deploy/phase4-static
```

覆盖层把 vLLM 调整为两个副本，并创建一个无 GPU 的集群内 benchmark client。RollingUpdate 固定 `maxSurge=0`，保证更新时不会临时出现第三个 GPU Pod。正式压测必须从该 client 访问 `http://qwen3-8b:8000`；`kubectl port-forward service/qwen3-8b`会固定选择一个后端 Pod，不能用来验证双副本负载均衡。

实验结束后恢复安全的单副本 base，并移除临时客户端：

```bash
sudo kubectl apply -k deploy/kubernetes
sudo kubectl delete pod phase4-benchmark-client -n vllm-infra-lab --ignore-not-found
```

扩容前后都必须核对实际 GPU UUID。若新副本没有落到当时确认空闲的 GPU，立即停止实验并恢复 base。
