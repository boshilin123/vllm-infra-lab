# Least-inflight 路由与最小 HTTP 适配

`least_inflight.py`实现 Phase 4 的 CPU-only 请求级选择核心。`http_proxy.py`在它之上增加仅依赖 Python 标准库的最小 HTTP/SSE 适配；当前只通过本地 mock backend 验证，不连接 Kubernetes，也不访问真实 vLLM Pod。

`in-flight`表示已经被路由器接收并转发、但生命周期尚未结束的请求，包括后端 waiting、Prefill、Decode 和仍在传输的流式响应。它不是“已经收到响应头”的请求数，也不等于 Prometheus 的瞬时 running gauge。

## 选择规则

1. 只考虑健康后端；
2. 原子选择 `in_flight` 最小者并立即加一；
3. 最小值相同时用轮询打破平局；
4. 请求完整结束或失败时通过 lease 减一；
5. 健康检查失败只阻止新请求进入，不强行中断已经开始的请求；
6. 所有后端不健康时快速失败，HTTP 层返回明确的 503。

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

## 最小 HTTP/SSE 适配

本地启动示例：

```bash
python3 -m router.http_proxy \
  --backend replica-a=http://127.0.0.1:8001 \
  --backend replica-b=http://127.0.0.1:8002 \
  --listen-host 127.0.0.1 \
  --listen-port 8080
```

当前适配层会：

- 转发 GET、POST、PUT、PATCH 和 DELETE，并保留请求路径与 query；
- 在转发前 acquire，普通响应写完或 SSE 流结束后才 release；
- 客户端断开、上游连接错误和响应异常时关闭上游并在 `finally` 中释放；
- 以 `/health` 的 2xx 结果摘除或恢复后端，摘除只影响新请求；
- 所有后端不可用时返回 503，上游建立失败时返回 502；
- 每次请求只选择一个后端，不对已经发送或开始生成的请求做自动重试。

本地 mock 测试覆盖非流式完成、SSE 响应头后仍持有 lease、流式客户端断开、上游连接错误、健康摘除/恢复、全不可用 503，以及 16 个同时持有的 HTTP 请求形成 8/8：

```bash
python3 -m unittest tests/test_http_proxy.py -v
```

## 当前边界

这是实验性最小适配，不是生产代理：

- 使用线程式标准库 server，每次上游请求新建连接，没有连接池、背压或限流；
- 请求体要求 `Content-Length`，不接受 chunked request body；响应通过 HTTP/1.0 connection-close 定界；
- 客户端断开会在下一次向下游写数据时被发现并关闭上游，若上游长时间没有产生新 chunk，取消感知也会相应延后；
- 健康检查是固定 URL 轮询，没有 Kubernetes EndpointSlice 服务发现或 readiness watch；
- 没有 TLS 终止、认证、访问日志、指标、优雅摘流和跨进程共享状态；
- 仍只按请求数量计权，尚未实现 Token-aware 或 EWMA 权重。

固定 256/128 Token 的对照中请求成本一致，适合验证 8/8；真实长短混合请求中，一个长请求和一个短请求都只计作 1，因此后续可增加 Prompt Token、`max_tokens` 或完成时长 EWMA 权重。当前准确表述是“least-inflight 核心与最小 HTTP/SSE 适配已通过本地 mock 验证”，不能声称已经部署生产队列感知负载均衡器。
