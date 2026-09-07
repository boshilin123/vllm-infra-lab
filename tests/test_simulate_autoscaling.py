from __future__ import annotations

import unittest

from analysis.simulate_autoscaling import Policy, Sample, simulate


POLICY = Policy(
    scrape_interval_seconds=15,
    min_replicas=1,
    max_replicas=2,
    waiting_greater_than=0,
    scale_out_consecutive_samples=2,
    startup_delay_seconds=155,
    waiting_equals=0,
    running_at_most=4,
    low_load_seconds=300,
    minimum_second_replica_ready_seconds=300,
)


def sample(second: int, running: float, waiting: float) -> Sample:
    return Sample(
        timestamp=float(second),
        timestamp_utc=f"test-{second}",
        running=running,
        waiting=waiting,
    )


class AutoscalingSimulationTest(unittest.TestCase):
    def test_single_waiting_sample_does_not_scale(self) -> None:
        rows, summary = simulate(
            [sample(0, 8, 0), sample(15, 8, 2), sample(30, 8, 0)], POLICY
        )
        self.assertEqual([row["desired_replicas"] for row in rows], [1, 1, 1])
        self.assertIsNone(summary["scale_out_requested_utc"])

    def test_two_waiting_samples_schedule_delayed_capacity(self) -> None:
        rows, summary = simulate(
            [
                sample(0, 8, 4),
                sample(15, 8, 4),
                sample(165, 0, 0),
                sample(180, 0, 0),
            ],
            POLICY,
        )
        self.assertEqual(rows[1]["event"], "scale_out_requested")
        self.assertEqual(rows[1]["desired_replicas"], 2)
        self.assertEqual(rows[1]["ready_replicas"], 1)
        self.assertEqual(rows[-1]["event"], "second_replica_ready_observed")
        self.assertFalse(summary["capacity_overlapped_observed_load"])

    def test_scheduled_ready_is_retained_when_trace_ends_early(self) -> None:
        _, summary = simulate([sample(0, 8, 4), sample(15, 8, 4)], POLICY)
        self.assertEqual(
            summary["second_replica_scheduled_ready_utc"],
            "1970-01-01T00:02:50Z",
        )
        self.assertIsNone(summary["second_replica_ready_observed_utc"])

    def test_scale_in_requires_long_low_load_and_ready_residency(self) -> None:
        samples = [sample(0, 8, 4), sample(15, 8, 4)]
        samples.extend(sample(second, 0, 0) for second in range(180, 496, 15))
        rows, summary = simulate(samples, POLICY)
        scale_in_rows = [row for row in rows if row["event"] == "scale_in_requested"]
        self.assertEqual(len(scale_in_rows), 1)
        self.assertEqual(scale_in_rows[0]["timestamp"], "480.000")
        self.assertIsNotNone(summary["scale_in_requested_utc"])


if __name__ == "__main__":
    unittest.main()
