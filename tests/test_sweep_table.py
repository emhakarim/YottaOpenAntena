"""Tests for the sweep table (Phase 4, CST-style parameter sweeps)."""

from __future__ import annotations

import csv
import tempfile
import unittest
from pathlib import Path

from openantenna.sweep.table import MAX_RUNS, RunRecord, SweepTable, run_table


class TestSweepTable(unittest.TestCase):
    def test_factorial_enumerates_every_combination_in_order(self):
        table = SweepTable.factorial({"length_mm": [30.0, 32.0], "inset_mm": [8.0, 9.0, 10.0]})
        self.assertEqual(len(table), 6)
        self.assertEqual(table.records[0].params, {"length_mm": 30.0, "inset_mm": 8.0})
        self.assertEqual(table.records[-1].params, {"length_mm": 32.0, "inset_mm": 10.0})
        self.assertEqual([record.index for record in table], list(range(6)))

    def test_one_at_a_time_keeps_the_baseline_except_one_parameter(self):
        table = SweepTable.one_at_a_time(
            {"w_mm": 40.0, "l_mm": 32.0}, {"l_mm": [31.0, 33.0]}
        )
        self.assertEqual(len(table), 3)  # baseline + two variations
        self.assertEqual(table.records[0].note, "baseline")
        for record in table.records[1:]:
            self.assertEqual(record.params["w_mm"], 40.0)
            self.assertIn(record.params["l_mm"], (31.0, 33.0))
        self.assertEqual({record.params["l_mm"] for record in table.records[1:]}, {31.0, 33.0})

    def test_a_run_that_fails_does_not_destroy_the_sweep(self):
        table = SweepTable.factorial({"v": [1.0, 2.0, 3.0]})

        def runner(params, _record):
            if params["v"] == 2.0:
                raise RuntimeError("this point explodes")
            return {"resonance_hz": 2.4e9 + params["v"] * 1e6}

        run_table(table, runner)
        counts = table.status_counts()
        self.assertEqual(counts["done"], 2)
        self.assertEqual(counts["failed"], 1)
        failed = table.marked("failed")[0]
        self.assertIn("RuntimeError", failed.note)

    def test_the_summary_gives_one_curve_per_parameter(self):
        table = SweepTable.one_at_a_time({"l_mm": 32.0}, {"l_mm": [31.0, 32.0, 33.0]})

        def runner(params, _record):
            return {"resonance_hz": 2.45e9 * (32.0 / params["l_mm"])}

        run_table(table, runner)
        curves = table.summary("resonance_hz")
        self.assertEqual(len(curves["l_mm"]), 3)
        values = [value for _key, value in curves["l_mm"]]
        self.assertGreater(values[0][0], values[-1][0], "a longer patch resonates lower")

    def test_the_csv_round_trips_the_table(self):
        table = SweepTable.factorial({"v": [1.0, 2.0]})
        run_table(table, lambda params, _record: {"resonance_hz": 2.4e9, "s11_min_db": -18.0 - params["v"]})
        with tempfile.TemporaryDirectory() as folder:
            target = table.to_csv(Path(folder) / "sweep.csv")
            rows = list(csv.reader(target.read_text(encoding="utf-8").splitlines()))
        self.assertEqual(rows[0][:4], ["index", "v", "status", "resonance_hz"])
        self.assertEqual(len(rows), 3)
        self.assertEqual(rows[1][2], "done")

    def test_refusals(self):
        with self.assertRaises(ValueError):
            SweepTable.factorial({})
        with self.assertRaises(ValueError):
            SweepTable.factorial({"v": []})
        with self.assertRaises(ValueError):
            SweepTable.factorial({"v": [float("nan")]})
        with self.assertRaises(ValueError):
            SweepTable.one_at_a_time({"a": 1.0}, {"b": [1.0, 2.0]})

    def test_the_run_cap_is_enforced_with_a_useful_message(self):
        values = list(range(0, 40))
        with self.assertRaises(ValueError) as caught:
            SweepTable.factorial({"a": values, "b": values, "c": [1.0, 2.0, 3.0]})
        self.assertIn(str(MAX_RUNS), str(caught.exception))
        self.assertIn("one_at_a_time", str(caught.exception))

    def test_statuses_are_validated(self):
        record = RunRecord(index=0, params={"v": 1.0})
        record.mark("done", result={"x": 1.0})
        self.assertEqual(record.status, "done")
        with self.assertRaises(ValueError):
            record.mark("finished")


if __name__ == "__main__":
    unittest.main()
