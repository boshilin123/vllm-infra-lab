# Least-inflight 路由核心

`least_inflight.py`实现 Phase 4 的 CPU-only 请求级选择核心，不启动 HTTP 服务、不连接 Kubernetes，也不访问真实 vLLM Pod。

`in-flight`表示已经被路由器接收并转发、但生命周期尚未结束的请求，包括后端 waiting、Prefill、Decode 和仍在传输的流式响应。它不是“已经收到响应头”的请求数，也不等于 Prometheus 的瞬时 running gauge。

## 选择规则

1. 只考虑健康后端；
2. 原子选择 `in_flight` 最小者并立即加一；
3. 最小值相同时用轮询打破平局；
4. 请求完整结束或失败时通过 lease 减一；
5. 健康检查失败只阻止新请求进入，不强行中断已经开始的请求；
6. 所有后端不健康时快速失败，由未来 HTTP 层返回明确的 503。

示例：

```python
from router import BackendConfig, LeastInflightRouter

router = LeastInflightRouter(
    [
        BackendConfig("replica-a", "http://replica-a:8000"),
        BackendConfig("replica-b", "http://replica-b:8000"),
    ]
)

with router.acquire() as lease:
    target = lease.backend.base_url
    # 转发请求，并消费完整响应；退出 with 后才减少 in-flight。
```

对于流式响应，lease 必须保持到流正常结束、客户端断开或后端异常。收到 HTTP 响应头只表示生成流已经建立，后端仍在执行 Decode，此时释放会虚报空闲并继续向它集中请求。

本实现第一版只比较请求数。固定 256/128 Token 的对照中请求成本一致，适合验证 8/8；真实长短混合请求中，一个长请求和一个短请求都只计作 1，因此后续可增加 Prompt Token、`max_tokens` 或完成时长 EWMA 权重。当前不能声称已经实现生产 HTTP 代理、服务发现、自动重试或 Token-aware 路由。
