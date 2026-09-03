# Results

实验结果按日期和场景保存：

```text
results/YYYY-MM-DD/<experiment-id>/
```

每次实验至少包含：

- `metadata.yaml`：版本、节点、参数与负载。
- 经脱敏、体积可控的原始 JSON/CSV。
- 汇总数据。
- 图表和结论说明。

大型 Prometheus 快照、临时日志和模型权重不提交到 Git；生成简历结论所需的最小原始数据应随仓库保留。
