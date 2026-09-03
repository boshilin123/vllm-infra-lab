# Operational scripts

本目录在 Phase 1 存放可重复执行的操作脚本：

- `deploy.sh`：应用清单并等待 Deployment Ready；
- `smoke_test.py`：检查 `/v1/models` 和一次最小补全请求；
- `collect_metadata.sh`：采集 Kubernetes、GPU、驱动、镜像与 Git 版本。

脚本不得内嵌密码、Token、kubeconfig、公网地址或服务器私有路径。
