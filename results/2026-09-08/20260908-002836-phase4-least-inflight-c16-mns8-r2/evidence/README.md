# Runtime evidence

This directory records the sanitized runtime summary derived from console and
five-second samples captured during the Phase 4 least-inflight experiment.
Timestamps from the benchmark client use the container's `-07:00` timezone;
host monitoring timestamps use `+08:00`.

| Evidence | Replica 1 | Replica 2 |
| --- | ---: | ---: |
| Formal-window samples | 51 | 51 |
| Max scheduler running | 8 | 8 |
| Max scheduler waiting | 0 | 0 |
| Samples with waiting > 0 | 0 | 0 |
| Router selections before | 1 | 1 |
| Router selections after | 173 | 184 |
| Selection delta share | 48.5% | 51.5% |
| Final in-flight | 0 | 0 |

The raw `router-console.log`, `benchmark-console.log`, and
`runtime-monitor.log` remain on the experiment host for local audit. They are
intentionally excluded by the repository-wide `*.log` rule because they contain
internal Pod names, Pod IPs, and absolute host paths. The public repository keeps
the sanitized findings above plus the raw per-request benchmark JSON and
aggregate files in the parent directory.

The startup-probe warning occurred only while the new replica loaded the model;
the Pod became Ready without a restart. The experiment was rolled back to the
base single-replica deployment after the formal run.
